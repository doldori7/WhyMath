"""L5 OAuth 로그인 — provider code 교환 → 사용자 upsert → JWT 발급. OAuth-a.

7계층: L5(api) 인증 집행. OAuth provider(카카오·네이버)에서 받은 authorization code를 *검증된
외부 신원*(`OAuthIdentity`)으로 바꾸는 일은 provider 구현(`OAuthProvider` Protocol·주입)에
위임하고, 이 모듈은 그 신원으로 `UserProfile`을 upsert해 `create_access_token`(`security.py`)으로
집행 토큰을 발급한다 — 인증 인프라(Bearer 검증·미성년 동의·UserProfile)는 전부 재사용(신규 0).

범위(OAuth-a): provider seam + 콜백 엔드포인트 + 사용자 upsert + JWT 발급. ★**실제 카카오/네이버
HTTP 교환 구현(httpx)·client secret 설정은 후속**(OAuth-a2) — 여기선 provider를 주입 가능한
Protocol로 두고 콜백 로직을 결정론적으로 검증한다(가짜 provider 주입·정직한 경계). upsert 키는
**이메일 해시**(`email_hash = sha256(정규화 이메일)`) — 평문 이메일 미저장(개인정보 보호·기존
필드 의미 그대로)·같은 이메일은 provider 무관 같은 계정(자연 연결)·마이그레이션 0. 로그인
레이트리밋(IP 기반 남용 방지)·리프레시 토큰은 후속.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated, Protocol, runtime_checkable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.auth import OAuthCallbackRequest, OAuthTokenResponse
from whymath_backend.schema.enums import Persona
from whymath_backend.security import create_access_token

# 신규 사용자 가입 시 기본 페르소나 — MVP 첫 노출 A(일반고 고3·MEMORY 페르소나 전략).
# persona_primary는 NOT NULL이라 가입 시 필요하고, 온보딩(PATCH /v1/users/me)에서 정교화된다.
_DEFAULT_PERSONA = Persona.A_일반고고3

# app.state에 OAuth provider 레지스트리를 두는 키(`_l3_state` 패턴·create_app이 주입).
OAUTH_PROVIDERS_KEY = "oauth_providers"


class OAuthIdentity(BaseModel):
    """OAuth provider가 검증해 돌려준 *외부 신원* — 사용자 식별의 입력.

    `email`은 사용자 식별 키(해시되어 `email_hash`로 저장·평문 미저장). `subject`는 provider의
    안정 사용자 id(텔레메트리·후속 계정 연결용). 둘 다 provider 구현이 채운다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(description="제공자 이름(예: 'kakao'·'naver').")
    subject: str = Field(description="provider의 안정 사용자 id(provider 내 고유).")
    email: str = Field(description="사용자 이메일 — 식별 키(해시 저장·평문 미저장).")


class OAuthProviderError(Exception):
    """OAuth provider code 교환 실패(불량 code·provider 오류·네트워크). 콜백이 502로 변환."""


@runtime_checkable
class OAuthProvider(Protocol):
    """OAuth provider 경계 — authorization code → 검증된 외부 신원.

    실제 구현(카카오·네이버 httpx)은 후속이고, 콜백은 이 Protocol에 주입된 구현을 호출한다.
    단위 테스트는 가짜 구현을 주입해 라이브 provider 없이 콜백 로직을 검증한다.
    """

    async def fetch_identity(self, code: str, redirect_uri: str) -> OAuthIdentity:
        """code를 provider 토큰·userinfo로 교환해 검증된 신원 반환(실패 시 `OAuthProviderError`)."""
        ...


def email_hash(email: str) -> str:
    """이메일 → sha256 hex(64자) — 평문 미저장·결정론(같은 이메일=같은 해시). 정규화(소문자)."""
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def resolve_user(session: AsyncSession, identity: OAuthIdentity) -> UserProfile:
    """외부 신원 → `UserProfile` upsert(이메일 해시 키). 신규면 기본 페르소나로 생성.

    같은 이메일은 provider 무관 같은 계정으로 매핑(자연 연결). 신규 사용자는 `persona_primary`가
    필수(NOT NULL)라 MVP 기본 페르소나로 생성하고 온보딩에서 정교화한다(미성년 동의는 *보호된*
    엔드포인트의 `ConsentedUser`가 게이트하고, 로그인 자체는 토큰만 발급). `user_id`는 앱에서 명시
    생성(서버 default 의존 없이 즉시 알 수 있게·토큰 발급에 필요).
    """
    digest = email_hash(identity.email)
    existing = await session.scalar(select(UserProfile).where(UserProfile.email_hash == digest))
    if isinstance(existing, UserProfile):
        return existing
    user = UserProfile(
        user_id=uuid.uuid4(),
        email_hash=digest,
        persona_primary=_DEFAULT_PERSONA,
    )
    session.add(user)
    await session.flush()
    return user


def _get_provider(request: Request, provider: str) -> OAuthProvider:
    """app.state 레지스트리에서 provider 구현을 찾는다 — 미등록이면 404(지원 안 함)."""
    registry: dict[str, OAuthProvider] = getattr(request.app.state, OAUTH_PROVIDERS_KEY, {})
    impl = registry.get(provider)
    if impl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 로그인 제공자입니다: {provider}",
        )
    return impl


router = APIRouter(prefix="/v1/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/{provider}/callback",
    response_model=OAuthTokenResponse,
    summary="OAuth 로그인 콜백 — code 교환 → 사용자 upsert → JWT 발급",
)
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OAuthTokenResponse:
    """OAuth provider redirect의 authorization code로 로그인 — 토큰 발급(미인증 엔드포인트).

    흐름: provider 구현 조회(미등록 404) → `fetch_identity`(code 교환·실패 502) → 사용자 upsert
    (이메일 해시 키) → `create_access_token`(JWT). 미성년 동의는 *보호된* 엔드포인트가 게이트하므로
    로그인은 토큰만 발급한다(JWT 시크릿 미설정 시 500·서버 구성 오류).
    """
    impl = _get_provider(request, provider)
    try:
        identity = await impl.fetch_identity(body.code, body.redirect_uri)
    except OAuthProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="로그인 제공자 인증에 실패했습니다(잠시 후 다시 시도).",
        ) from exc
    user = await resolve_user(session, identity)
    token = create_access_token(user.user_id, settings=settings)
    return OAuthTokenResponse(access_token=token)
