"""L5 OAuth 로그인 — provider code 교환 → 사용자 upsert → JWT 발급. OAuth-a.

7계층: L5(api) 인증 집행. OAuth provider(카카오·네이버)에서 받은 authorization code를 *검증된
외부 신원*(`OAuthIdentity`)으로 바꾸는 일은 provider 구현(`OAuthProvider` Protocol·주입)에
위임하고, 이 모듈은 그 신원으로 `UserProfile`을 upsert해 `create_access_token`(`security.py`)으로
집행 토큰을 발급한다 — 인증 인프라(Bearer 검증·미성년 동의·UserProfile)는 전부 재사용(신규 0).

범위: provider seam + 콜백 엔드포인트 + 사용자 upsert + JWT 발급(액세스+리프레시) + 리프레시 교환
(`POST /v1/auth/refresh`). 실제 카카오/네이버 HTTP 교환은 provider 구현(OAuth-a2)이 담당하고,
여기선 주입 가능한 Protocol로 콜백 로직을 결정론적으로 검증한다(가짜 provider 주입·정직한 경계).
upsert 키는 **이메일 해시**(`email_hash = sha256(정규화 이메일)`) — 평문 이메일 미저장(개인정보
보호·기존 필드 의미 그대로)·같은 이메일은 provider 무관 같은 계정(자연 연결)·마이그레이션 0.

리프레시(OAuth-a3·a3b·a3c): 로그인 시 액세스+리프레시를 함께 발급하고(리프레시마다 `jti`=세션 행
PK), `/refresh`는 토큰 검증·allowlist 확인 후 **회전**한다(기존 세션 취소+새 토큰 발급).
*이미 취소된* 토큰 재제출은 **재사용 탐지**로 전체 세션을 패닉 취소(탈취 대응). `/logout`은 세션
취소(denylist)로 즉시 무효화. 세션 목록/관리는 a3d·로그인 레이트리밋은 a4.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Protocol, runtime_checkable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.auth import (
    OAuthCallbackRequest,
    OAuthTokenResponse,
    RefreshRequest,
)
from whymath_backend.schema.enums import Persona
from whymath_backend.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)

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


def _refresh_unauthorized() -> HTTPException:
    """리프레시/로그아웃 401 — 불량·만료·취소·미인식 토큰(`_auth.py._unauthorized` 동형)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="리프레시 토큰이 유효하지 않습니다(다시 로그인해 주세요).",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issue_refresh_session(session: AsyncSession, user_id: uuid.UUID, settings: Settings) -> str:
    """새 jti로 리프레시 토큰 발급 + 세션 행(allowlist) add. 반환=리프레시 토큰(commit은 호출자).

    콜백(로그인)과 `/refresh`(회전)가 공유한다 — 둘 다 같은 트랜잭션에서 다른 변경과 함께 커밋한다.
    """
    jti = uuid.uuid4()
    token = create_refresh_token(user_id, settings=settings, jti=jti)
    session.add(
        RefreshTokenSession(
            token_session_id=jti,
            user_id=user_id,
            expires_at=datetime.now(tz=timezone.utc)
            + timedelta(minutes=settings.jwt_refresh_expire_minutes),
        )
    )
    return token


async def _revoke_all_user_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """사용자의 *활성* 리프레시 세션을 모두 취소(재사용 탐지 패닉·`_device_store` revoke 패턴)."""
    await session.execute(
        update(RefreshTokenSession)
        .where(
            RefreshTokenSession.user_id == user_id,
            RefreshTokenSession.revoked.is_(False),
        )
        .values(revoked=True, revoked_at=datetime.now(tz=timezone.utc))
    )


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
    (이메일 해시 키) → 액세스+리프레시 토큰 발급. 미성년 동의는 *보호된* 엔드포인트가 게이트하므로
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
    access_token = create_access_token(user.user_id, settings=settings)
    refresh_token = _issue_refresh_session(session, user.user_id, settings)
    # 세션 행(allowlist) + (신규면) 사용자까지 한 번에 영속(resolve_user는 flush만 하므로).
    await session.commit()
    return OAuthTokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=OAuthTokenResponse,
    summary="리프레시 토큰 회전 — 새 액세스+리프레시 토큰 발급",
)
async def refresh_access_token(
    body: RefreshRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> OAuthTokenResponse:
    """유효한 리프레시 토큰을 회전한다 — 기존 세션 취소+새 액세스/리프레시 발급(미인증 엔드포인트).

    리프레시 토큰을 검증(typ=refresh·만료·서명·jti)하고 그 jti의 세션 행을 allowlist 확인한다. 행이
    *없으면* 401. 행이 *이미 취소됨*이면 **재사용 탐지**(회전·로그아웃된 토큰 재제출 = 탈취 신호) →
    사용자 전체 활성 세션을 패닉 취소하고 401. 정상이면 **회전**: 기존 세션 취소 + 새 리프레시 세션
    발급 → 새 액세스+리프레시 반환. 불량/만료/타입불일치/사용자없음 → 401. 시크릿 미설정 500.
    """
    try:
        claims = decode_refresh_token(body.refresh_token, settings=settings)
        user_id = uuid.UUID(claims.subject)
        session_id = uuid.UUID(claims.jti)
    except (JWTError, ValueError) as exc:
        raise _refresh_unauthorized() from exc
    token_session = await session.get(RefreshTokenSession, session_id)
    if token_session is None:
        raise _refresh_unauthorized()
    if token_session.revoked:
        # 재사용 탐지 — 이미 회전/로그아웃된 토큰 재제출은 탈취 신호. 전체 활성 세션 패닉 취소.
        await _revoke_all_user_sessions(session, user_id)
        await session.commit()
        raise _refresh_unauthorized()
    user = await session.get(UserProfile, user_id)
    if user is None:
        raise _refresh_unauthorized()
    # 회전 — 제출 세션 취소 + 새 리프레시 세션 발급(같은 트랜잭션에서 커밋).
    token_session.revoked = True
    token_session.revoked_at = datetime.now(tz=timezone.utc)
    access_token = create_access_token(user.user_id, settings=settings)
    refresh_token = _issue_refresh_session(session, user.user_id, settings)
    await session.commit()
    return OAuthTokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃 — 리프레시 토큰 세션 취소(denylist)",
)
async def logout(
    body: RefreshRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """제출된 리프레시 토큰의 세션 행을 취소(revoked=true)해 즉시 무효화한다(미인증·denylist).

    토큰 디코드 불가/타입불일치/jti없음 → 401. 유효하면 그 jti의 세션 행을 취소한다 — 행이 없거나
    이미 취소됐어도 멱등하게 204. 취소된 리프레시 토큰은 이후 `/refresh`에서 거부된다(만료 미대기).
    """
    try:
        claims = decode_refresh_token(body.refresh_token, settings=settings)
        session_id = uuid.UUID(claims.jti)
    except (JWTError, ValueError) as exc:
        raise _refresh_unauthorized() from exc
    token_session = await session.get(RefreshTokenSession, session_id)
    if token_session is not None and not token_session.revoked:
        token_session.revoked = True
        token_session.revoked_at = datetime.now(tz=timezone.utc)
        await session.commit()
