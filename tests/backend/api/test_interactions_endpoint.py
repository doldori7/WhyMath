"""POST /v1/interactions 단위테스트 — 시각화 조작 이벤트 적재. 슬라이스 96-F.

라이브 DB 없음: get_session을 add/commit 캡처 fake 세션으로 오버라이드해, 엔드포인트가
AttemptEvent를 올바르게 구성·적재(commit)하는지 hermetic 검증(204·event_data·422·401).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import AttemptEvent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.schema.enums import EventType, Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_PATH = "/v1/interactions"
_UID = uuid.uuid4()


class _StubProvider:
    """create_app(provider=) 주입용 — generate 미호출(이벤트 적재는 LLM 무관)."""

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        return ""


class _CapturingSession:
    """get_session 오버라이드용 — add/commit를 캡처하는 최소 fake."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


# 모든 _client가 공유해 테스트에서 적재 결과를 검사한다.
_SESSION = _CapturingSession()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


def _client(*, authed: bool = True) -> TestClient:
    app = create_app(provider=_StubProvider())
    if authed:
        app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield _SESSION

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_post_interaction_persists_event() -> None:
    """유효 조작 이벤트 → 204 + AttemptEvent 1건 적재(그래프그리기·event_data 보존)·commit."""
    session = _CapturingSession()
    app = create_app(provider=_StubProvider())
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield session

    app.dependency_overrides[get_session] = _sess
    client = TestClient(app)

    resp = client.post(
        _PATH,
        json={"type": "param_change", "payload": {"name": "a", "value": 2.5}, "at": 1234},
    )
    assert resp.status_code == 204
    assert session.commits == 1
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, AttemptEvent)
    assert event.event_type == EventType.그래프그리기
    assert event.user_id == _UID
    assert event.event_data == {
        "interaction": "param_change",
        "payload": {"name": "a", "value": 2.5},
        "client_at": 1234,
    }


def test_post_interaction_empty_type_422() -> None:
    """type 빈 문자열 → 422(min_length)."""
    assert _client().post(_PATH, json={"type": ""}).status_code == 422


def test_post_interaction_extra_field_422() -> None:
    """미지 필드 → 422(extra=forbid)."""
    assert _client().post(_PATH, json={"type": "x", "nope": 1}).status_code == 422


def test_post_interaction_requires_auth_401() -> None:
    """미인증 → 401."""
    assert _client(authed=False).post(_PATH, json={"type": "param_change"}).status_code == 401
