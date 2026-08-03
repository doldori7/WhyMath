"""GET/DELETE /v1/auth/sessions 단위테스트 — 세션 목록·전체/단건 로그아웃(SEC-10).

hermetic: `get_current_user`를 오버라이드해 실 JWT 없이 인증된 사용자로 가장하고, `_FakeSession`이
SELECT(목록)·UPDATE(전체취소)·`get`(단건 조회)를 흉내낸다. 실 PG 왕복(정렬·소유권·platform 영속)은
`test_refresh_session_integration.py`에 통합테스트로 추가돼 있다. `_summarize_platform`(순수 함수)
단위테스트도 이 파일에 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Select, Update

from whymath_backend.api._auth import get_current_user
from whymath_backend.api.auth import _summarize_platform
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona

_UID = uuid.uuid4()
_OTHER_UID = uuid.uuid4()
_SESSIONS_PATH = "/v1/auth/sessions"


def _user() -> UserProfile:
    return UserProfile(user_id=_UID, email_hash="h", persona_primary=Persona.A_일반고고3)


def _row(
    jti: uuid.UUID,
    *,
    uid: uuid.UUID = _UID,
    revoked: bool = False,
    platform: str | None = None,
    issued_at: datetime | None = None,
) -> RefreshTokenSession:
    return RefreshTokenSession(
        token_session_id=jti,
        user_id=uid,
        issued_at=issued_at or datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        revoked=revoked,
        platform=platform,
    )


class _FakeScalars:
    def __init__(self, rows: list[RefreshTokenSession]) -> None:
        self._rows = rows

    def all(self) -> list[RefreshTokenSession]:
        return self._rows


class _FakeSelectResult:
    def __init__(self, rows: list[RefreshTokenSession]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """세션 행을 in-memory 딕셔너리로 유지 — 목록(SELECT)·전체취소(UPDATE)·단건(`get`) 지원."""

    def __init__(self, rows: list[RefreshTokenSession]) -> None:
        self.rows: dict[uuid.UUID, RefreshTokenSession] = {r.token_session_id: r for r in rows}

    async def get(self, model: object, pk: uuid.UUID) -> object | None:
        if model is RefreshTokenSession:
            return self.rows.get(pk)
        return None

    async def execute(self, statement: object) -> object:
        if isinstance(statement, Update):
            # 요청자 본인 소유 행만 취소(_revoke_all_user_sessions의 WHERE user_id==호출자와 동형).
            now = datetime.now(tz=timezone.utc)
            for row in self.rows.values():
                if row.user_id == _UID and not row.revoked:
                    row.revoked = True
                    row.revoked_at = now
            return None
        if isinstance(statement, Select):
            active = sorted(
                (r for r in self.rows.values() if r.user_id == _UID and not r.revoked),
                key=lambda r: r.issued_at,
                reverse=True,
            )
            return _FakeSelectResult(active)
        raise AssertionError(f"예상 못한 statement 타입: {type(statement)}")

    async def commit(self) -> None:
        return None


def _client(rows: list[RefreshTokenSession]) -> tuple[TestClient, _FakeSession]:
    fake = _FakeSession(rows)
    app = create_app()
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef")
    )

    async def _sess() -> object:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), fake


def _no_auth_client(rows: list[RefreshTokenSession]) -> TestClient:
    fake = _FakeSession(rows)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef")
    )

    async def _sess() -> object:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_list_sessions_returns_own_active_only_desc_order() -> None:
    """목록은 본인의 *활성* 세션만, issued_at 내림차순 — 타인·취소된 세션은 제외."""
    now = datetime.now(tz=timezone.utc)
    older = _row(uuid.uuid4(), platform="Android", issued_at=now - timedelta(days=1))
    newer = _row(uuid.uuid4(), platform="iOS", issued_at=now)
    revoked = _row(uuid.uuid4(), revoked=True)
    other_user = _row(uuid.uuid4(), uid=_OTHER_UID)
    client, _fake = _client([older, newer, revoked, other_user])

    resp = client.get(_SESSIONS_PATH, headers={"Authorization": "Bearer x"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = [s["session_id"] for s in body["sessions"]]
    assert ids == [str(newer.token_session_id), str(older.token_session_id)]
    assert body["sessions"][0]["platform"] == "iOS"
    assert body["sessions"][1]["platform"] == "Android"


def test_list_sessions_response_has_no_ip_or_user_agent_fields() -> None:
    """응답 스키마 동결 — IP·UA 원문 필드가 없다(최소 수집)."""
    client, _fake = _client([_row(uuid.uuid4())])

    resp = client.get(_SESSIONS_PATH, headers={"Authorization": "Bearer x"})

    assert resp.status_code == 200, resp.text
    session_keys = set(resp.json()["sessions"][0].keys())
    assert session_keys == {"session_id", "platform", "issued_at", "expires_at"}


def test_list_sessions_requires_auth() -> None:
    client = _no_auth_client([])
    assert client.get(_SESSIONS_PATH).status_code == 401


def test_delete_all_sessions_revokes_only_own() -> None:
    mine = _row(uuid.uuid4())
    others = _row(uuid.uuid4(), uid=_OTHER_UID)
    client, fake = _client([mine, others])

    resp = client.delete(_SESSIONS_PATH, headers={"Authorization": "Bearer x"})

    assert resp.status_code == 204, resp.text
    assert fake.rows[mine.token_session_id].revoked is True
    assert fake.rows[others.token_session_id].revoked is False


def test_delete_single_session_owned_204_idempotent() -> None:
    mine = _row(uuid.uuid4())
    client, fake = _client([mine])

    first = client.delete(
        f"{_SESSIONS_PATH}/{mine.token_session_id}", headers={"Authorization": "Bearer x"}
    )
    second = client.delete(
        f"{_SESSIONS_PATH}/{mine.token_session_id}", headers={"Authorization": "Bearer x"}
    )

    assert first.status_code == 204, first.text
    assert second.status_code == 204, second.text  # 멱등 — 이미 취소된 세션 재요청도 204
    assert fake.rows[mine.token_session_id].revoked is True


def test_delete_single_session_not_owned_404() -> None:
    others = _row(uuid.uuid4(), uid=_OTHER_UID)
    client, fake = _client([others])

    resp = client.delete(
        f"{_SESSIONS_PATH}/{others.token_session_id}", headers={"Authorization": "Bearer x"}
    )

    assert resp.status_code == 404, resp.text
    assert fake.rows[others.token_session_id].revoked is False  # 타인 세션은 건드리지 않음


def test_delete_single_session_missing_404() -> None:
    client, _fake = _client([])

    resp = client.delete(f"{_SESSIONS_PATH}/{uuid.uuid4()}", headers={"Authorization": "Bearer x"})

    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15", "iOS"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "iOS"),
        ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36", "Android"),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120", "Web"),
        ("Dart/3.0 (dart:io)", None),
        (None, None),
        ("", None),
    ],
)
def test_summarize_platform(user_agent: str | None, expected: str | None) -> None:
    assert _summarize_platform(user_agent) == expected
