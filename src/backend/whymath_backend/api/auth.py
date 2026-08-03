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
취소(denylist)로 즉시 무효화.

SEC-10(세션 가시성·전체/단건 로그아웃 — a3d 자백 해소): `_revoke_all_user_sessions`가 이미
있었는데 재사용 탐지 경로에서만 호출돼 학생이 *스스로* 세션을 끊을 방법이 없었다. `GET
/sessions`(목록)·`DELETE /sessions`(전체 — 기존 함수 재사용)·`DELETE /sessions/{session_id}`
(단건·본인 스코핑)를 추가한다. **한계를 정직 표기**: ⑴ `device_credential`(rate limit 신뢰용
기기 자격증명) 폐기는 이 세션 취소와 *무관*하다 — 기기를 폐기해도 그 기기가 들고 있는 JWT는
살아있다(`api/devices.py`의 `/revoke`와 혼동 금지). ⑵ "전체 로그아웃"은 *리프레시 토큰만*
취소한다 — 이미 발급된 액세스 토큰은 `jwt_expire_minutes`까지 자체 만료 전엔 유효하다(즉시
무효화 아님). 세션 목록의 `platform`은 로그인·리프레시 시점 User-Agent에서 도출한 좁은 요약뿐
(IP·UA 원문 미저장 — 최소 수집, `docs/architecture/account_security_gap_review.md` D4).

SEC-08(하드닝 — 인증 표면 남용 방어 + OAuth CSRF/open-redirect 방지):
  - **rate limit**: `/{provider}/callback`·`/refresh`에 IP 단위 한도 부착(`_rate_limit.
    RateLimitedAuthCallback`/`RateLimitedAuthRefresh`, category="auth"). 미인증 표면이라
    IP 키만 가능(사용자 신원 확정 전). Redis 장애 시 OPS-06 인메모리 폴백 그대로 상속.
  - **OAuth state(CSRF)**: 이 백엔드는 `/authorize` 리다이렉트를 자체 발급하지 않는다(모바일
    클라가 provider와 직접 리다이렉트를 주고받고 code만 서버에 POST) — 그래서 서버가
    `GET /{provider}/state`로 opaque state를 *사전 발급*하고, 클라는 그 값을 provider
    authorize 요청에 실어 보낸 뒤 콜백 제출 시 그대로 동봉한다. 검증은 stateless HMAC 서명
    (`issue_oauth_state`/`verify_oauth_state`)이라 DB/Redis 저장이 없다.
  - **redirect_uri allowlist**: `Settings.oauth_redirect_uris`에 없는 redirect_uri는 400
    (open redirect 방지). 배포·데모 환경은 `WHYMATH_OAUTH_REDIRECT_URI_ALLOWLIST` 필수.
  - **클라 계약 변경(breaking)**: `OAuthCallbackRequest`에 `state`(required)가 새로 추가됐다
    — 콜백 전 반드시 `GET /{provider}/state`를 먼저 호출해 값을 받아야 한다. 실 클라(OAuth-c3
    로그인 webview)는 이 시점 아직 미구현 스텁(`src/mobile/lib/features/auth/presentation/
    login_screen.dart`·`oauth_code_requester.dart`)이라 이 변경의 실 사용자 영향은 0이다.
  - **계정 잠금(lockout) 미도입**: 의도된 결정 — 아래 `oauth_callback` 근처 주석·`db/models/
    user.py` 컬럼 부재 동결 테스트(`tests/backend/api/test_no_lockout_columns.py`) 참조.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Protocol, runtime_checkable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import CurrentUser
from whymath_backend.api._rate_limit import RateLimitedAuthCallback, RateLimitedAuthRefresh
from whymath_backend.config import Settings, get_settings
from whymath_backend.consent import current_year_kst, derive_is_minor
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.auth import (
    OAuthCallbackRequest,
    OAuthTokenResponse,
    RefreshRequest,
    SessionInfo,
    SessionListResponse,
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
    birth_year: int | None = Field(
        default=None,
        description=(
            "provider가 제공한 출생 연도(연 단위·월일 미수집). 신규 사용자 생성 시 서버측 "
            "`is_minor` 파생(consent.derive_is_minor)의 입력. provider가 동의·범위 미제공 시 "
            "None(현 동작) — 미상이면 is_minor도 None(미성년 게이트는 *알려진* 미성년만 차단). "
            "**클라가 보낸 is_minor는 신뢰하지 않고 항상 이 birth_year에서 파생한다**."
        ),
    )


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


async def resolve_user(
    session: AsyncSession, identity: OAuthIdentity, *, settings: Settings
) -> UserProfile:
    """외부 신원 → `UserProfile` upsert(이메일 해시 키). 신규면 기본 페르소나로 생성.

    같은 이메일은 provider 무관 같은 계정으로 매핑(자연 연결). 신규 사용자는 `persona_primary`가
    필수(NOT NULL)라 MVP 기본 페르소나로 생성하고 온보딩에서 정교화한다(미성년 동의는 *보호된*
    엔드포인트의 `ConsentedUser`가 게이트하고, 로그인 자체는 토큰만 발급). `user_id`는 앱에서 명시
    생성(서버 default 의존 없이 즉시 알 수 있게·토큰 발급에 필요).

    **미성년 게이트(서버측 is_minor 파생)**: 신규 사용자 생성 시 `is_minor`는 *반드시*
    `identity.birth_year`에서 `derive_is_minor`로 파생한다(클라/외부 입력의 is_minor를 신뢰하지
    않는 단일 진실 — `consent.py`). provider가 birth_year를 안 주면 None → is_minor도 None(미상은
    게이트 통과·*알려진* 미성년만 차단). *기존* 사용자는 birth_year/is_minor가 이미 PATCH 경로
    에서 서버 파생·관리되므로 로그인이 덮어쓰지 않는다(그대로 반환) — birth_year 갱신·재파생은
    온보딩 PATCH(`api/users.py`)가 단독 담당해 한 경로로만 파생값을 쓴다.
    """
    digest = email_hash(identity.email)
    existing = await session.scalar(select(UserProfile).where(UserProfile.email_hash == digest))
    if isinstance(existing, UserProfile):
        return existing
    user = UserProfile(
        user_id=uuid.uuid4(),
        email_hash=digest,
        persona_primary=_DEFAULT_PERSONA,
        # is_minor는 서버 파생만(외부 is_minor 미신뢰) — birth_year 없으면 None(미상).
        birth_year=identity.birth_year,
        is_minor=derive_is_minor(
            identity.birth_year,
            current_year=current_year_kst(),
            threshold=settings.minor_consent_age,
        ),
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


# ──────────────────────────────────────────────────────────────────────────
# SEC-08 — OAuth CSRF state: 서버 사전 발급 + stateless HMAC 검증(DB/Redis 저장 0)
#
# 이 백엔드는 `/authorize` 리다이렉트를 자체 발급하지 않는다(모바일 클라가 OAuth provider와
# 직접 리다이렉트를 주고받고 code만 우리 서버에 POST한다). 그래서 CSRF state는 서버가
# *사전에* opaque 토큰을 발급하고(`GET /{provider}/state`), 클라가 그 값을 provider authorize
# 요청의 state 파라미터로 실어 보낸 뒤, 콜백 제출 시 *같은 값을 그대로 동봉*해 서버가
# 검증하는 방식이다. payload(`provider:nonce:expiry`)를 `jwt_secret_key`로 HMAC-SHA256
# 서명한다 — 서버 저장 없이 서명·만료만으로 발급 사실을 검증(stateless).
# ──────────────────────────────────────────────────────────────────────────

_OAUTH_STATE_SEP = "."  # payload.signature


def issue_oauth_state(provider: str, *, settings: Settings) -> str:
    """OAuth CSRF state 발급 — provider+nonce+만료를 HMAC-SHA256(jwt_secret_key)로 서명한 opaque
    토큰.

    클라는 이 값을 provider authorize 요청의 state 파라미터로 실어 보내고, 콜백 제출 시 그대로
    동봉한다. 서버 저장 없음(stateless) — 서명·만료만으로 발급 사실을 검증한다.
    """
    nonce = uuid.uuid4().hex
    expiry = int(time.time()) + settings.oauth_state_ttl_seconds
    payload = f"{provider}:{nonce}:{expiry}"
    secret = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}{_OAUTH_STATE_SEP}{sig}"


def verify_oauth_state(provider: str, state: str, *, settings: Settings) -> bool:
    """state 검증 — 서명 일치·provider 일치·만료 전이면 True.

    불량 형식(구분자·필드 수 불일치)·서명 불일치·provider 불일치·만료는 모두 False(콜백이 400
    으로 변환) — 실패 사유를 세분해 노출하지 않는다(state 위조 시도에 힌트 제공 방지).
    """
    try:
        payload, sig = state.rsplit(_OAUTH_STATE_SEP, 1)
        state_provider, _nonce, expiry_str = payload.split(":", 2)
        expiry = int(expiry_str)
    except ValueError:
        return False
    secret = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    expected_sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return False
    if state_provider != provider:
        return False
    return time.time() <= expiry


class OAuthStateResponse(BaseModel):
    """`GET /{provider}/state` 응답 — 콜백에 그대로 동봉할 CSRF state."""

    model_config = ConfigDict(extra="forbid")

    state: str = Field(
        description="OAuth authorize 요청에 실어 보낼 CSRF state 토큰(콜백 시 동봉)."
    )


@router.get(
    "/{provider}/state",
    response_model=OAuthStateResponse,
    summary="OAuth CSRF state 발급",
)
async def issue_state(provider: str, settings: SettingsDep) -> OAuthStateResponse:
    """provider별 state 발급 — 미인증·rate limit 없음(발급 자체는 side-effect 0·소비 없이는 무해).

    실 검증(서명·provider 일치·만료)은 콜백 제출 시 `verify_oauth_state`가 수행한다.
    """
    return OAuthStateResponse(state=issue_oauth_state(provider, settings=settings))


def _refresh_unauthorized() -> HTTPException:
    """리프레시/로그아웃 401 — 불량·만료·취소·미인식 토큰(`_auth.py._unauthorized` 동형)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="리프레시 토큰이 유효하지 않습니다(다시 로그인해 주세요).",
        headers={"WWW-Authenticate": "Bearer"},
    )


# User-Agent 부분일치로 도출하는 좁은 플랫폼 범주 — 순서가 판정 순서(먼저 일치하는 것 채택).
# 새 파싱 라이브러리를 추가하지 않는다(SEC-10 — 불명확하면 None. 오분류로 거짓 정보를 만들지
# 않는 것이 세밀한 분류보다 우선).
_PLATFORM_MARKERS: tuple[tuple[str, str], ...] = (
    ("ipad", "iOS"),
    ("iphone", "iOS"),
    ("android", "Android"),
    ("mozilla", "Web"),
)


def _summarize_platform(user_agent: str | None) -> str | None:
    """User-Agent 원문 → 좁은 플랫폼 요약("iOS"/"Android"/"Web") 또는 판별 불가 시 None.

    원문 UA는 반환하지도 저장하지도 않는다(최소 수집 — SEC-10 D4). `_PLATFORM_MARKERS` 밖의
    패턴은 전부 None(과분류 방지).
    """
    if not user_agent:
        return None
    lowered = user_agent.lower()
    for marker, platform in _PLATFORM_MARKERS:
        if marker in lowered:
            return platform
    return None


def _issue_refresh_session(
    session: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
    *,
    platform: str | None = None,
) -> str:
    """새 jti로 리프레시 토큰 발급 + 세션 행(allowlist) add. 반환=리프레시 토큰(commit은 호출자).

    콜백(로그인)과 `/refresh`(회전)가 공유한다 — 둘 다 같은 트랜잭션에서 다른 변경과 함께 커밋한다.
    `platform`(SEC-10)은 `_summarize_platform`이 도출한 좁은 요약(IP·UA 원문 미저장).
    """
    jti = uuid.uuid4()
    token = create_refresh_token(user_id, settings=settings, jti=jti)
    session.add(
        RefreshTokenSession(
            token_session_id=jti,
            user_id=user_id,
            expires_at=datetime.now(tz=timezone.utc)
            + timedelta(minutes=settings.jwt_refresh_expire_minutes),
            platform=platform,
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
    dependencies=[RateLimitedAuthCallback],
)
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OAuthTokenResponse:
    """OAuth provider redirect의 authorization code로 로그인 — 토큰 발급(미인증 엔드포인트).

    흐름: redirect_uri allowlist 확인(미등록 400) → state 검증(불일치·만료 400) → provider 구현
    조회(미등록 404) → `fetch_identity`(code 교환·실패 502) → 사용자 upsert(이메일 해시 키) →
    액세스+리프레시 토큰 발급. 미성년 동의는 *보호된* 엔드포인트가 게이트하므로 로그인은 토큰만
    발급한다(JWT 시크릿 미설정 시 500·서버 구성 오류).

    **검증 순서가 provider 조회보다 앞서는 이유**: 입력 위생(redirect_uri·state)이 provider
    존재 여부보다 먼저 걸려야 의미상 맞다 — 등록되지 않은 provider라도 open redirect·위조
    state 시도는 그 자체로 걸러야 한다(provider 등록 여부와 무관한 방어선).

    **계정 잠금(lockout) 미도입 — 의도된 결정(SEC-08)**: 반복 실패로 계정을 잠그면 미성년
    학생이 정당한 재시도(오타·세션 만료·기기 변경) 중에도 학습이 *중단*된다 — CLAUDE.md
    의사결정 우선순위 #1(학생 안전·웰빙)이 #6(보안 강화)보다 위다. 위 IP 단위 rate limit이
    자동화 남용(크리덴셜 스터핑·계정 생성 폭주)은 이미 차단하므로 잠금 없이도 방어선은
    유지된다. `UserProfile`에 잠금 상태 컬럼을 추가하지 않는다(dead code 금지 — 쓰이지 않는
    좌석 금지, security_privacy.md 부기와 동형 원칙). 부재는
    `tests/backend/api/test_no_lockout_columns.py`가 동결한다.
    """
    if body.redirect_uri not in settings.oauth_redirect_uris:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="허용되지 않은 redirect_uri입니다.",
        )
    if not verify_oauth_state(provider, body.state, settings=settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="state가 유효하지 않거나 만료되었습니다(다시 로그인해 주세요).",
        )
    impl = _get_provider(request, provider)
    try:
        identity = await impl.fetch_identity(body.code, body.redirect_uri)
    except OAuthProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="로그인 제공자 인증에 실패했습니다(잠시 후 다시 시도).",
        ) from exc
    user = await resolve_user(session, identity, settings=settings)
    access_token = create_access_token(user.user_id, settings=settings)
    platform = _summarize_platform(request.headers.get("user-agent"))
    refresh_token = _issue_refresh_session(session, user.user_id, settings, platform=platform)
    # 세션 행(allowlist) + (신규면) 사용자까지 한 번에 영속(resolve_user는 flush만 하므로).
    await session.commit()
    return OAuthTokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=OAuthTokenResponse,
    summary="리프레시 토큰 회전 — 새 액세스+리프레시 토큰 발급",
    dependencies=[RateLimitedAuthRefresh],
)
async def refresh_access_token(
    body: RefreshRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OAuthTokenResponse:
    """유효한 리프레시 토큰을 회전한다 — 기존 세션 취소+새 액세스/리프레시 발급(미인증 엔드포인트).

    리프레시 토큰을 검증(typ=refresh·만료·서명·jti)하고 그 jti의 세션 행을 allowlist 확인한다. 행이
    *없으면* 401. 행이 *이미 취소됨*이면 **재사용 탐지**(회전·로그아웃된 토큰 재제출 = 탈취 신호) →
    사용자 전체 활성 세션을 패닉 취소하고 401. 정상이면 **회전**: 기존 세션 취소 + 새 리프레시 세션
    발급(SEC-10 — 이 시점 User-Agent로 `platform` 갱신 기록) → 새 액세스+리프레시 반환. 불량/만료/
    타입불일치/사용자없음 → 401. 시크릿 미설정 500.
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
    platform = _summarize_platform(request.headers.get("user-agent"))
    refresh_token = _issue_refresh_session(session, user.user_id, settings, platform=platform)
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


# ──────────────────────────────────────────────────────────────────────────
# SEC-10 — 세션 가시성·전체/단건 로그아웃(인증 필요·`CurrentUser`)
#
# `_revoke_all_user_sessions`는 재사용 탐지 경로에서만 쓰이던 기존 함수를 여기서도 재사용한다
# (중복 구현 0). 신규 테이블도 0 — `refresh_token_session`(allowlist)이 이미 있다. 응답은
# `session_id`(=jti)·`platform`(좁은 요약)·`issued_at`·`expires_at`만 노출한다 — IP·UA 원문은
# 이 엔드포인트도, 다른 어떤 경로도 저장하지 않는다(최소 수집).
#
# **한계(정직 표기)**: ⑴ `device_credential`(rate limit 신뢰용 기기 자격증명) 폐기는 이 세션
# 취소와 무관하다 — 기기를 폐기해도 그 기기가 들고 있는 JWT는 만료까지 살아있다. ⑵ "전체
# 로그아웃"은 *리프레시 토큰만* 취소한다 — 이미 발급된 액세스 토큰은 `jwt_expire_minutes`까지
# 자체 만료 전엔 유효하다(즉시 무효화 아님. 진짜 즉시 무효화는 액세스 TTL 단축 또는 denylist
# 축이 필요하고, 클라 refresh-on-401 배선 선결 — 이번 범위 밖).
# ──────────────────────────────────────────────────────────────────────────


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="내 활성 세션 목록 (SEC-10 — 낯선 기기 인지 용도)",
)
async def list_sessions(user: CurrentUser, session: SessionDep) -> SessionListResponse:
    """본인의 *활성*(미취소) 리프레시 세션 목록 — `issued_at` 내림차순.

    IP·User-Agent 원문은 응답에 없다(최소 수집) — `platform`은 좁은 요약뿐. 액세스 토큰 자체는
    이 테이블에 없어 "현재 접속 중인 기기" 여부는 구분하지 않는다(리프레시 세션 목록일 뿐).
    """
    result = await session.execute(
        select(RefreshTokenSession)
        .where(
            RefreshTokenSession.user_id == user.user_id,
            RefreshTokenSession.revoked.is_(False),
        )
        .order_by(RefreshTokenSession.issued_at.desc())
    )
    rows = result.scalars().all()
    return SessionListResponse(
        sessions=[
            SessionInfo(
                session_id=row.token_session_id,
                platform=row.platform,
                issued_at=row.issued_at,
                expires_at=row.expires_at,
            )
            for row in rows
        ]
    )


@router.delete(
    "/sessions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="전체 로그아웃 — 내 모든 활성 세션 취소 (SEC-10)",
)
async def revoke_all_sessions(user: CurrentUser, session: SessionDep) -> None:
    """본인의 모든 활성 리프레시 세션을 취소한다(재사용 탐지의 `_revoke_all_user_sessions` 재사용).

    **한계**: 리프레시 토큰만 취소된다 — 이미 발급된 액세스 토큰은 만료까지 유효하다(모듈
    docstring·§SEC-10 참조). 다른 기기의 세션까지 포함해 즉시 강제 로그아웃하려는 용도(기기
    분실·계정 탈취 의심)에 쓴다.
    """
    await _revoke_all_user_sessions(session, user.user_id)
    await session.commit()


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="단건 세션 로그아웃 — 본인 소유 세션만 (SEC-10)",
)
async def revoke_session(
    session_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    """본인 소유의 특정 세션을 취소한다 — 타인 소유·미존재 `session_id`는 404(본인 스코핑).

    이미 취소된 세션을 다시 요청해도 멱등하게 204(재확인 취소로 처리 — `/logout`과 동형).
    """
    token_session = await session.get(RefreshTokenSession, session_id)
    if token_session is None or token_session.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없습니다.",
        )
    if not token_session.revoked:
        token_session.revoked = True
        token_session.revoked_at = datetime.now(tz=timezone.utc)
        await session.commit()
