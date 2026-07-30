"""시연 전용 가짜 OAuth provider(api/demo_auth.py) 단위테스트 — S1 게이트 ① 인에이블먼트.

라이브 provider·DB 없음: `build_oauth_providers`(실 등록 경로) + create_app(oauth_providers 주입)
+ dependency_overrides(get_session·get_settings)로 hermetic 검증한다. 핵심 계약:
  1. 기본 OFF ⇒ demo 미등록 ⇒ 콜백 404(현 동작 보존·prod 안전).
  2. demo ON ⇒ 콜백 200·실 JWT 발급(sub=업서트된 데모 사용자)·발급 토큰이 get_current_user 통과.
  3. 비미성년 불변식 — 데모 사용자는 is_minor=False라 동의 게이트(get_consented_user 403)를 통과.
  4. prod 이중 방어 — 실 provider(kakao) 구성 시 flag True여도 demo 미등록(404 보존).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_current_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.api.auth import issue_oauth_state
from whymath_backend.api.demo_auth import (
    DEMO_BIRTH_YEAR,
    DEMO_EMAIL,
    FakeOAuthProvider,
    register_demo_provider,
)
from whymath_backend.api.oauth_providers import build_oauth_providers
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.consent import current_year_kst, derive_is_minor
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.security import decode_access_token

_DEMO_PATH = "/v1/auth/demo/callback"
_REDIRECT_URI = "https://demo/cb"
_SECRET = "demo-test-secret-0123456789abcdef"


def _demo_settings() -> Settings:
    """demo ON + 실 provider 미구성(로컬 시연 호스트 신호).

    SEC-08: redirect_uri allowlist에 `_REDIRECT_URI`를 등록해야 콜백이 통과한다(비면
    deny-by-default). rate limit은 이 파일의 관심사가 아니므로 0(비활성)으로 둔다.
    """
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        demo_auth_enabled=True,
        oauth_redirect_uri_allowlist=_REDIRECT_URI,
        auth_rate_limit_ip_per_minute=0,
    )


def _off_settings() -> Settings:
    """기본 — demo OFF(redirect_uri allowlist는 그대로 유지 — 404 분기를 실제로 태우기 위함)."""
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        oauth_redirect_uri_allowlist=_REDIRECT_URI,
        auth_rate_limit_ip_per_minute=0,
    )


def _body(provider: str = "demo", *, settings: Settings | None = None) -> dict[str, str]:
    """유효한 state(해당 provider로 서명)를 포함한 콜백 요청 바디.

    **모듈 상수로 미리 만들지 않는다**(과거 버그: `_BODY = _body()`를 collection 시점에 한 번
    계산해뒀더니, 대규모 랜덤 순서 전체 스위트에서 `oauth_state_ttl_seconds`(기본 300초)가
    지난 뒤에야 그 테스트가 실행되며 state가 만료돼 400으로 실패했다 — CI 970초 전체 실행에서
    실측·`test_oauth_endpoint.py` 동형). 매 호출마다 새로 발급해 사용 시점 기준 TTL이 시작되게
    한다.
    """
    signing_settings = settings if settings is not None else _demo_settings()
    return {
        "code": "demo",
        "redirect_uri": _REDIRECT_URI,
        "state": issue_oauth_state(provider, settings=signing_settings),
    }


class _FakeSession:
    """get_session 오버라이드 — resolve_user의 scalar(신규=None)+add+flush+commit + get(PK) 흡수.

    콜백이 신규 데모 사용자를 upsert하는 경로(scalar→None→add→flush)를 태우고, 추가된 사용자를
    포착(`added`)해 불변식(is_minor)·get_current_user(get by PK) 검증에 재사용한다.
    """

    def __init__(self) -> None:
        self.added: list[UserProfile] = []

    async def scalar(self, statement: object) -> object | None:
        # resolve_user의 기존 사용자 조회 — 신규 데모 사용자이므로 None(→ add 경로).
        return None

    def add(self, obj: object) -> None:
        if isinstance(obj, UserProfile):
            self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def get(self, model: object, pk: uuid.UUID) -> object | None:
        if model is UserProfile:
            for user in self.added:
                if user.user_id == pk:
                    return user
        return None


def _client(settings: Settings, session: _FakeSession) -> TestClient:
    # 실 등록 경로(build_oauth_providers)를 태워 gating을 그대로 검증한다(가짜 dict 주입 아님).
    app = create_app(oauth_providers=build_oauth_providers(settings))
    app.dependency_overrides[get_settings] = lambda: settings

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield session

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach.py 미러 — `_BACKEND`는 모듈 전역)."""
    import asyncio

    asyncio.run(reset_store())


def test_default_off_no_demo_provider() -> None:
    """기본(demo OFF) — build_oauth_providers에 demo 없음 ⇒ 콜백 404."""
    settings = _off_settings()
    assert "demo" not in build_oauth_providers(settings)
    resp = _client(settings, _FakeSession()).post(_DEMO_PATH, json=_body())
    assert resp.status_code == 404


def test_demo_on_issues_valid_token() -> None:
    """demo ON ⇒ 콜백 200·실 JWT 발급·sub가 업서트된 데모 사용자 id(UUID)."""
    settings = _demo_settings()
    assert "demo" in build_oauth_providers(settings)
    session = _FakeSession()
    resp = _client(settings, session).post(_DEMO_PATH, json=_body())
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    subject = decode_access_token(token, settings=settings)
    # 발급 토큰의 sub가 콜백이 만든 데모 사용자 PK와 일치.
    assert len(session.added) == 1
    demo_user = session.added[0]
    assert subject == str(demo_user.user_id)
    assert uuid.UUID(subject)  # 파싱 가능한 UUID


def test_demo_user_is_non_minor() -> None:
    """비미성년 불변식 — 데모 사용자 is_minor=False라 동의 게이트를 통과한다."""
    # 상수 수준: 데모 출생연도가 비미성년으로 파생됨.
    assert derive_is_minor(DEMO_BIRTH_YEAR, current_year=current_year_kst(), threshold=14) is False
    # 콜백이 만든 실제 사용자도 is_minor=False.
    session = _FakeSession()
    resp = _client(_demo_settings(), session).post(_DEMO_PATH, json=_body())
    assert resp.status_code == 200
    assert session.added[0].is_minor is False


def test_issued_token_passes_get_current_user() -> None:
    """발급 토큰이 get_current_user를 통과(보호 라우트 401 아님)."""
    import asyncio

    from fastapi.security import HTTPAuthorizationCredentials

    settings = _demo_settings()
    session = _FakeSession()
    resp = _client(settings, session).post(_DEMO_PATH, json=_body())
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    demo_user = session.added[0]

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    resolved = asyncio.run(
        get_current_user(
            credentials=creds,
            session=session,
            settings=settings,  # type: ignore[arg-type]
        )
    )
    assert resolved.user_id == demo_user.user_id


def test_prod_double_guard_refuses_when_real_provider_configured() -> None:
    """이중 방어 — demo ON이어도 실 provider(kakao) 구성 시 demo 미등록(404 보존)."""
    settings = Settings(
        jwt_secret_key=SecretStr(_SECRET),
        demo_auth_enabled=True,
        kakao_client_id="prod-kakao-id",
        oauth_redirect_uri_allowlist=_REDIRECT_URI,
        auth_rate_limit_ip_per_minute=0,
    )
    providers = build_oauth_providers(settings)
    assert "demo" not in providers
    assert "kakao" in providers
    resp = _client(settings, _FakeSession()).post(_DEMO_PATH, json=_body(settings=settings))
    assert resp.status_code == 404


def test_register_demo_provider_off_is_noop() -> None:
    """register_demo_provider — OFF면 레지스트리 무변경(직접 호출 계약)."""
    providers: dict[str, object] = {}
    register_demo_provider(providers, _off_settings())  # type: ignore[arg-type]
    assert providers == {}


def test_fake_provider_returns_fixed_identity() -> None:
    """FakeOAuthProvider — 어떤 code든 고정 데모 신원 반환(결정론)."""
    import asyncio

    ident = asyncio.run(FakeOAuthProvider().fetch_identity("anything", "any-uri"))
    assert ident.provider == "demo"
    assert ident.email == DEMO_EMAIL
    assert ident.birth_year == DEMO_BIRTH_YEAR
