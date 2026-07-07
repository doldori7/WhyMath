"""GET·POST /v1/visualizations/spec 단위테스트 — Graph2dSpec 명세 라운드트립. 슬라이스 96-B.

라이브 DB·LLM 없음: dependency_overrides(get_consented_user·get_session·get_settings)로
검증/인코딩 글루(200·라운드트립·웹 호환 base64·422·401)를 hermetic 검증.
"""

from __future__ import annotations

import base64
import json
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

_PATH = "/v1/visualizations/spec"
_SPEC = {
    "function": "a*x**2+b*x+c",
    "domain": [-5.0, 5.0],
    "parameters": [{"name": "a", "min": -3.0, "max": 3.0, "step": 0.1, "default": 1.0}],
}


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출(spec 엔드포인트는 LLM 무관)."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")


class _FakeSession:
    """get_session 오버라이드용 — 쿼리 미발생(spec 엔드포인트는 DB 무관)."""


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


def _b64(spec: dict[str, object]) -> str:
    """표준 base64(compact JSON) — 웹 atob·Flutter encodeGraph2dSpecParam과 동일 인코딩."""
    return base64.b64encode(
        json.dumps(spec, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode()


def test_post_spec_returns_share_link() -> None:
    """POST 유효 명세 → 200 + spec_param/​share_query."""
    resp = _client().post(_PATH, json={"type": "interactive_graph_2d", "spec": _SPEC})
    assert resp.status_code == 200
    body = resp.json()
    # spec_param는 spec dict의 base64(JSON) — 디코드하면 원 spec과 동치.
    assert json.loads(base64.b64decode(body["spec_param"])) == _SPEC
    assert body["share_query"] == f"?spec={body['spec_param']}"
    assert body["visualization"]["type"] == "interactive_graph_2d"


def test_post_spec_param_is_web_compatible_base64() -> None:
    """spec_param이 웹/Flutter와 동일한 표준 base64(compact JSON)인지 단언."""
    resp = _client().post(_PATH, json={"type": "interactive_graph_2d", "spec": _SPEC})
    assert resp.json()["spec_param"] == _b64(_SPEC)


def test_roundtrip_post_then_get() -> None:
    """POST가 만든 spec_param → GET ?spec= → 동일 spec 복원."""
    client = _client()
    param = client.post(_PATH, json={"type": "interactive_graph_2d", "spec": _SPEC}).json()[
        "spec_param"
    ]
    resp = client.get(_PATH, params={"spec": param})
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "interactive_graph_2d"
    assert body["spec"] == _SPEC


def test_get_spec_decodes_minimal() -> None:
    """GET ?spec=<base64({function})> → 200 interactive_graph_2d."""
    resp = _client().get(_PATH, params={"spec": _b64({"function": "x**2"})})
    assert resp.status_code == 200
    assert resp.json()["spec"] == {"function": "x**2"}


def test_post_invalid_spec_422() -> None:
    """type 위반(function=123) → Visualization 검증 실패로 422."""
    resp = _client().post(_PATH, json={"type": "interactive_graph_2d", "spec": {"function": 123}})
    assert resp.status_code == 422


def test_get_broken_base64_422() -> None:
    """깨진 base64 → 422."""
    assert _client().get(_PATH, params={"spec": "@@not-base64@@"}).status_code == 422


def test_get_non_json_422() -> None:
    """유효 base64이나 JSON이 아님 → 422."""
    assert (
        _client().get(_PATH, params={"spec": base64.b64encode(b"xx").decode()}).status_code == 422
    )


def test_post_requires_auth_401() -> None:
    """미인증 → 401."""
    resp = _client(authed=False).post(_PATH, json={"type": "interactive_graph_2d", "spec": _SPEC})
    assert resp.status_code == 401
