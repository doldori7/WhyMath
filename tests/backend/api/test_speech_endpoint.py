"""POST /v1/speech/latex 단위테스트 — LaTeX → 한국어 낭독 명세. 음성 슬라이스 S1.

라이브 DB·LLM 없음: dependency_overrides(get_consented_user·get_session·get_settings)로 변환·
인증·검증(200·422·401)을 hermetic 검증(test_visualization_spec_endpoint 패턴 답습).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from pydantic import SecretStr
from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_PATH = "/v1/speech/latex"


class _StubProvider:
    """create_app(provider=) 주입용 — speech 엔드포인트는 LLM 무관(generate 미호출)."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


class _FakeSession:
    """get_session 오버라이드용 — speech 엔드포인트는 DB 무관(쿼리 미발생)."""


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=uuid.uuid4(), persona_primary=Persona.A_일반고고3)
    )


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


def _client(*, authed: bool = True) -> TestClient:
    app = create_app(provider=_StubProvider())
    if authed:
        app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_post_latex_returns_speech_spec() -> None:
    """POST 유효 수식 → 200 + 한국어 낭독 명세."""
    resp = _client().post(_PATH, json={"latex": "x^2", "grade_band": "고등"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plain_text"] == "엑스 제곱"
    assert body["grade_band"] == "고등"
    assert body["source_latex"] == "x^2"
    assert body["unresolved_symbols"] == []


def test_post_latex_defaults_to_high_school() -> None:
    """grade_band 생략 시 기본 고등(MVP 페르소나 A)."""
    resp = _client().post(_PATH, json={"latex": r"\int_a^b f(x)\,dx"})
    assert resp.status_code == 200
    assert resp.json()["grade_band"] == "고등"
    assert "적분" in resp.json()["plain_text"]


def test_post_empty_latex_422() -> None:
    """빈 LaTeX → 요청 검증 실패(min_length)로 422."""
    assert _client().post(_PATH, json={"latex": ""}).status_code == 422


def test_post_unreadable_latex_422() -> None:
    """발성 토큰이 없는 입력(공백 명령만) → InvalidSpeechSpecError → 422."""
    assert _client().post(_PATH, json={"latex": r"\,"}).status_code == 422


def test_post_requires_auth_401() -> None:
    """미인증 → 401."""
    resp = _client(authed=False).post(_PATH, json={"latex": "x^2"})
    assert resp.status_code == 401
