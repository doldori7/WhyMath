"""계정 삭제권 엔드포인트(`DELETE /v1/me`) — hermetic(FakeSession·인증 오버라이드).

`erase_my_account`의 *엔드포인트 결선*만 검증한다: 확인 문구 게이트(400)·인증(401)·필드 검증(422)·
정상 경로(200 영수증 + erase_user 호출 + commit + DeletionAudit 적재). ★실제 삭제(전 테이블·
CASCADE·고아 제거·DeletionAudit 잔존)는 `privacy/test_erasure.py` 통합테스트가 검증한다(중복 0).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_current_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_CONFIRM = "DELETE_MY_ACCOUNT"


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeSession:
    """erase_user가 부르는 execute(delete)·add(audit)·flush + 엔드포인트의 commit 캡처."""

    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.added: list[Any] = []
        self.commits = 0
        self.flushes = 0

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(self.rowcount)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


def _client(rowcount: int = 1) -> tuple[TestClient, _FakeSession]:
    app = create_app()
    fake = _FakeSession(rowcount)
    app.dependency_overrides[get_current_user] = _user

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), fake


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess  # 무토큰 401은 세션 사용 전 발생
    return TestClient(app)


class TestEraseMyAccount:
    def test_valid_confirmation_erases_200(self) -> None:
        """확인 문구 일치 → 200 영수증(user_id·총 삭제 행수)·commit·DeletionAudit 적재."""
        client, fake = _client(rowcount=2)
        resp = client.request("DELETE", "/v1/me", json={"confirmation": _CONFIRM})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"] == str(_UID)
        # 18개 테이블(+skill_mastery_history·Phase 2b-2) + user_profile, 각 2행 = 38.
        assert body["total_rows_deleted"] == 38
        assert fake.commits == 1  # 엔드포인트가 commit(원자적)
        # DeletionAudit 1행 적재(GDPR 증빙·삭제 전).
        from whymath_backend.db.models.audit import DeletionAudit

        audits = [o for o in fake.added if isinstance(o, DeletionAudit)]
        assert len(audits) == 1
        assert audits[0].user_id == _UID
        assert audits[0].resource_type == "user_profile"

    def test_wrong_confirmation_400_no_delete(self) -> None:
        """확인 문구 불일치 → 400·삭제/commit 없음(오삭제 방지)."""
        client, fake = _client()
        resp = client.request("DELETE", "/v1/me", json={"confirmation": "oops"})
        assert resp.status_code == 400
        assert fake.commits == 0
        assert fake.added == []

    def test_missing_confirmation_422(self) -> None:
        """확인 필드 누락 → 422(Pydantic 검증)."""
        client, _ = _client()
        resp = client.request("DELETE", "/v1/me", json={})
        assert resp.status_code == 422

    def test_extra_field_forbidden_422(self) -> None:
        """추가 필드 → 422(extra='forbid')."""
        client, _ = _client()
        resp = client.request("DELETE", "/v1/me", json={"confirmation": _CONFIRM, "evil": 1})
        assert resp.status_code == 422

    def test_no_token_401(self) -> None:
        """무토큰 → 401(인증 필수·삭제권도 본인 인증 전제)."""
        client = _no_auth_client()
        resp = client.request("DELETE", "/v1/me", json={"confirmation": _CONFIRM})
        assert resp.status_code == 401

    def test_pending_external_logged_not_in_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """외부 store 별도 삭제 필요를 *ops 로그*로만 가시화 — 응답엔 미노출(정보 누출 0)."""
        client, _ = _client(rowcount=2)
        with caplog.at_level(logging.INFO, logger="whymath.api.me"):
            resp = client.request("DELETE", "/v1/me", json={"confirmation": _CONFIRM})
        assert resp.status_code == 200
        # ops 로그에 store명·user_id가 남아 누락이 가시화된다(조용한 누락 0).
        logged = "\n".join(r.getMessage() for r in caplog.records if r.name == "whymath.api.me")
        assert "clickhouse" in logged and "s3" in logged and "redis" in logged
        assert str(_UID) in logged
        # student-facing 응답엔 인프라/매니페스트 미노출(요약 영수증 2필드만).
        assert set(resp.json()) == {"user_id", "total_rows_deleted"}
