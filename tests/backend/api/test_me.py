"""me 라우터 단위테스트 — /v1/me/{sessions,assessments,dialogues}(hermetic).

엔드포인트 결선(200·직렬화·401·빈[])을 검증한다. user_id 스코핑(WHERE) 정확성은 통합
테스트(test_me_integration.py)가 실 PG로 검증한다 — FakeSession은 stmt를 무시하므로.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.activity import LearningSession
from whymath_backend.db.models.assessment import Assessment
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import AuditResourceType, Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class FakeSession:
    def __init__(
        self,
        rows: list[Any] | None = None,
        get_map: dict[uuid.UUID, Any] | None = None,
    ) -> None:
        self._rows = list(rows or [])
        # slice 50: session.get(LearningSession, session_id) 시뮬
        self._get_map = get_map or {}
        self.commits = 0
        # slice 51: session.delete(row) 캡처
        self.deleted: list[Any] = []
        # slice 57: session.add(DeletionAudit) 캡처(AsyncSession.add는 동기)
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self._rows)

    async def get(self, _model: Any, pk: Any) -> Any:
        return self._get_map.get(pk)

    async def commit(self) -> None:
        self.commits += 1

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)
        # PK로 찾아 get_map에서도 제거(후속 get은 None 반환·idempotent 검증용)
        for pk, val in list(self._get_map.items()):
            if val is obj:
                del self._get_map[pk]
                break


def _client(
    rows: list[Any],
    get_map: dict[uuid.UUID, Any] | None = None,
) -> tuple[TestClient, FakeSession]:
    """slice 50: get_map 지원 — `.get(LearningSession, id)` 호출 시뮬. 캡처 세션도 반환."""
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    fake = FakeSession(rows, get_map=get_map)

    async def _sess() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), fake


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = _sess  # 무토큰 401은 세션 전 발생(엔진 격리)
    return TestClient(app)


_ENDPOINTS = (
    "/v1/me/sessions",
    "/v1/me/assessments",
    "/v1/me/dialogues",
    "/v1/me/deletions",
)


class TestScopedLists:
    def test_sessions_returns_rows(self) -> None:
        rows = [LearningSession.from_schema(LearningSessionSchema(user_id=_UID))]
        client, _ = _client(rows)
        resp = client.get("/v1/me/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_assessments_returns_rows(self) -> None:
        rows = [Assessment.from_schema(AssessmentSchema(user_id=_UID))]
        client, _ = _client(rows)
        resp = client.get("/v1/me/assessments")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_dialogues_returns_rows(self) -> None:
        rows = [Dialogue.from_schema(DialogueSchema(user_id=_UID))]
        client, _ = _client(rows)
        resp = client.get("/v1/me/dialogues")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_deletions_returns_rows(self) -> None:
        """slice 58: 본인 삭제 감사 이력 조회 — resource_type enum 값 직렬화."""
        rows = [
            DeletionAudit.from_schema(
                DeletionAuditSchema(
                    user_id=_UID,
                    resource_type=AuditResourceType.learning_session,
                    resource_id=uuid.uuid4(),
                )
            )
        ]
        client, _ = _client(rows)
        resp = client.get("/v1/me/deletions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["resource_type"] == "learning_session"
        assert str(body[0]["user_id"]) == str(_UID)

    def test_empty_lists(self) -> None:
        client, _ = _client([])
        for path in _ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 200
            assert resp.json() == []

    def test_deletions_resource_type_filter_accepted(self) -> None:
        """slice 65: 유효한 resource_type 값은 200 — 쿼리 결선 검증.

        FakeSession은 stmt를 무시하므로 *실제 필터링*은 통합테스트가 검증한다. 여기선 enum
        값이 파라미터로 수용되고 엔드포인트가 정상 응답하는지(결선)만 본다.
        """
        rows = [
            DeletionAudit.from_schema(
                DeletionAuditSchema(
                    user_id=_UID,
                    resource_type=AuditResourceType.dialogue,
                    resource_id=uuid.uuid4(),
                )
            )
        ]
        client, _ = _client(rows)
        for value in ("learning_session", "dialogue", "assessment"):
            resp = client.get("/v1/me/deletions", params={"resource_type": value})
            assert resp.status_code == 200, resp.text

    def test_deletions_invalid_resource_type_rejected(self) -> None:
        """slice 65: enum 밖 값은 422 — 임의 문자열 주입 차단."""
        client, _ = _client([])
        resp = client.get("/v1/me/deletions", params={"resource_type": "bogus"})
        assert resp.status_code == 422

    def test_deletions_time_window_accepted(self) -> None:
        """slice 66: TZ-aware since/until은 200 — 시간창 파라미터 결선."""
        client, _ = _client([])
        resp = client.get(
            "/v1/me/deletions",
            params={
                "since": "2024-01-01T00:00:00Z",
                "until": "2024-12-31T23:59:59+00:00",
            },
        )
        assert resp.status_code == 200, resp.text

    def test_deletions_naive_datetime_rejected(self) -> None:
        """slice 66/42: timezone 없는 datetime은 422(PG TZ-aware 컬럼과 비교 모호)."""
        client, _ = _client([])
        resp = client.get("/v1/me/deletions", params={"since": "2024-01-01T00:00:00"})
        assert resp.status_code == 422

    def test_deletions_inverted_window_rejected(self) -> None:
        """slice 66/45: since > until은 빈 시간창 — 클라이언트 버그 명시 거부(422)."""
        client, _ = _client([])
        resp = client.get(
            "/v1/me/deletions",
            params={
                "since": "2024-12-31T00:00:00Z",
                "until": "2024-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_list_time_window_accepted_all_endpoints(self) -> None:
        """slice 67: sessions·assessments·dialogues도 TZ-aware since/until 수용(200·결선)."""
        client, _ = _client([])
        for path in ("/v1/me/sessions", "/v1/me/assessments", "/v1/me/dialogues"):
            resp = client.get(
                path,
                params={
                    "since": "2024-01-01T00:00:00Z",
                    "until": "2024-12-31T23:59:59+00:00",
                },
            )
            assert resp.status_code == 200, (path, resp.text)

    def test_list_time_window_naive_rejected_all_endpoints(self) -> None:
        """slice 67: 세 리스트도 naive datetime은 422(_query_filters 공용)."""
        client, _ = _client([])
        for path in ("/v1/me/sessions", "/v1/me/assessments", "/v1/me/dialogues"):
            resp = client.get(path, params={"since": "2024-01-01T00:00:00"})
            assert resp.status_code == 422, path

    def test_list_time_window_inverted_rejected_all_endpoints(self) -> None:
        """slice 67: 세 리스트도 since > until은 422(_query_filters 공용)."""
        client, _ = _client([])
        for path in ("/v1/me/sessions", "/v1/me/assessments", "/v1/me/dialogues"):
            resp = client.get(
                path,
                params={
                    "since": "2024-12-31T00:00:00Z",
                    "until": "2024-01-01T00:00:00Z",
                },
            )
            assert resp.status_code == 422, path


class TestAuthRequired:
    def test_all_require_token_401(self) -> None:
        client = _no_auth_client()
        for path in _ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 401, path
            assert "WWW-Authenticate" in resp.headers

    def test_pagination_out_of_range_422(self) -> None:
        client, _ = _client([])
        assert client.get("/v1/me/sessions?limit=0").status_code == 422
        assert client.get("/v1/me/sessions?limit=999").status_code == 422
        assert client.get("/v1/me/sessions?offset=-1").status_code == 422


class TestEndSession:
    """slice 50: `PATCH /v1/me/sessions/{id}/end` — 본인 세션 종료(idempotent·404 미존재/타인)."""

    def _session_row(self, owner: uuid.UUID, ended: bool = False) -> LearningSession:
        sid = uuid.uuid4()
        from datetime import UTC, datetime

        schema = LearningSessionSchema(
            session_id=sid,
            user_id=owner,
            ended_at=datetime.now(UTC) if ended else None,
        )
        return LearningSession.from_schema(schema)

    def test_ends_fresh_session(self) -> None:
        """미종료 세션 → ended_at 채움·commit·200."""
        row = self._session_row(_UID, ended=False)
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 200
        assert resp.json()["ended_at"] is not None
        assert fake.commits == 1
        # ORM row의 ended_at도 채워짐
        assert row.ended_at is not None

    def test_idempotent_already_ended(self) -> None:
        """이미 종료된 세션 → 기존 ended_at 보존·commit 없음·200."""
        row = self._session_row(_UID, ended=True)
        original_ended = row.ended_at
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 200
        # 시각 변경 없음
        assert row.ended_at == original_ended
        assert fake.commits == 0  # 변경 없으면 commit 0

    def test_nonexistent_returns_404(self) -> None:
        """미존재 세션 → 404."""
        fake_id = uuid.uuid4()
        client, _ = _client([], get_map={})
        resp = client.patch(f"/v1/me/sessions/{fake_id}/end")
        assert resp.status_code == 404

    def test_other_users_session_returns_404(self) -> None:
        """타인 소유 세션 → 404(존재 여부 비누설·slice 24 패턴)."""
        other_uid = uuid.uuid4()
        row = self._session_row(other_uid, ended=False)
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 404
        # 실제 ended_at는 *수정 안 됨*
        assert row.ended_at is None
        assert fake.commits == 0


class TestDeleteSession:
    """slice 51: `DELETE /v1/me/sessions/{id}` — GDPR 영구 삭제·404 미존재/타인."""

    def _session_row(self, owner: uuid.UUID) -> LearningSession:
        sid = uuid.uuid4()
        schema = LearningSessionSchema(session_id=sid, user_id=owner)
        return LearningSession.from_schema(schema)

    def test_delete_own_session_returns_204(self) -> None:
        """본인 세션 삭제 → 204 No Content·session.delete + commit 호출."""
        row = self._session_row(_UID)
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.delete(f"/v1/me/sessions/{row.session_id}")
        assert resp.status_code == 204
        assert resp.content == b""  # 204 응답 body 비어있음
        assert fake.deleted == [row]
        assert fake.commits == 1
        # slice 57: 삭제와 동일 트랜잭션으로 DeletionAudit 1행 적재
        assert len(fake.added) == 1
        audit = fake.added[0]
        assert audit.resource_type == "learning_session"
        assert audit.resource_id == row.session_id
        assert audit.user_id == _UID

    def test_delete_nonexistent_returns_404(self) -> None:
        fake_id = uuid.uuid4()
        client, fake = _client([], get_map={})
        resp = client.delete(f"/v1/me/sessions/{fake_id}")
        assert resp.status_code == 404
        assert fake.deleted == []
        assert fake.commits == 0
        assert fake.added == []  # slice 57: 404는 감사 미적재

    def test_delete_other_users_session_returns_404(self) -> None:
        """타인 소유 → 404 + 행 삭제 안 됨(상태 불변·정보 비누설)."""
        other_uid = uuid.uuid4()
        row = self._session_row(other_uid)
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.delete(f"/v1/me/sessions/{row.session_id}")
        assert resp.status_code == 404
        assert fake.deleted == []
        assert fake.commits == 0
        assert fake.added == []  # slice 57: 타인 소유 404도 감사 미적재
        # 행 그대로 존재
        assert row.session_id in fake._get_map

    def test_delete_then_get_returns_404(self) -> None:
        """slice 51: 삭제 후 같은 ID 재호출은 404(idempotent 의미·DELETE *aFTER*는 두 번째 호출이 미존재)."""
        row = self._session_row(_UID)
        client, _ = _client([], get_map={row.session_id: row})
        first = client.delete(f"/v1/me/sessions/{row.session_id}")
        assert first.status_code == 204
        # 두 번째 호출은 미존재 → 404
        second = client.delete(f"/v1/me/sessions/{row.session_id}")
        assert second.status_code == 404


class TestDialogueLifecycle:
    """slice 52: Dialogue end + delete — slice 50/51 패턴 답습 invariant 3회차."""

    def _dialogue_row(self, owner: uuid.UUID, ended: bool = False) -> Dialogue:
        did = uuid.uuid4()
        schema = DialogueSchema(
            dialogue_id=did,
            user_id=owner,
            ended_at=datetime.now(UTC) if ended else None,
        )
        return Dialogue.from_schema(schema)

    # ── PATCH end ──
    def test_end_fresh_dialogue(self) -> None:
        row = self._dialogue_row(_UID, ended=False)
        client, fake = _client([], get_map={row.dialogue_id: row})
        resp = client.patch(f"/v1/me/dialogues/{row.dialogue_id}/end")
        assert resp.status_code == 200
        assert resp.json()["ended_at"] is not None
        assert fake.commits == 1

    def test_end_idempotent_already_ended(self) -> None:
        row = self._dialogue_row(_UID, ended=True)
        original = row.ended_at
        client, fake = _client([], get_map={row.dialogue_id: row})
        resp = client.patch(f"/v1/me/dialogues/{row.dialogue_id}/end")
        assert resp.status_code == 200
        assert row.ended_at == original
        assert fake.commits == 0

    def test_end_nonexistent_returns_404(self) -> None:
        fake_id = uuid.uuid4()
        client, _ = _client([], get_map={})
        resp = client.patch(f"/v1/me/dialogues/{fake_id}/end")
        assert resp.status_code == 404

    def test_end_other_users_dialogue_returns_404(self) -> None:
        other_uid = uuid.uuid4()
        row = self._dialogue_row(other_uid, ended=False)
        client, fake = _client([], get_map={row.dialogue_id: row})
        resp = client.patch(f"/v1/me/dialogues/{row.dialogue_id}/end")
        assert resp.status_code == 404
        assert row.ended_at is None
        assert fake.commits == 0

    # ── DELETE ──
    def test_delete_own_dialogue_returns_204(self) -> None:
        row = self._dialogue_row(_UID)
        client, fake = _client([], get_map={row.dialogue_id: row})
        resp = client.delete(f"/v1/me/dialogues/{row.dialogue_id}")
        assert resp.status_code == 204
        assert fake.deleted == [row]
        assert fake.commits == 1
        # slice 57: dialogue 삭제 감사 적재
        assert len(fake.added) == 1
        assert fake.added[0].resource_type == "dialogue"
        assert fake.added[0].resource_id == row.dialogue_id

    def test_delete_nonexistent_returns_404(self) -> None:
        fake_id = uuid.uuid4()
        client, fake = _client([], get_map={})
        resp = client.delete(f"/v1/me/dialogues/{fake_id}")
        assert resp.status_code == 404
        assert fake.deleted == []

    def test_delete_other_users_dialogue_returns_404(self) -> None:
        other_uid = uuid.uuid4()
        row = self._dialogue_row(other_uid)
        client, fake = _client([], get_map={row.dialogue_id: row})
        resp = client.delete(f"/v1/me/dialogues/{row.dialogue_id}")
        assert resp.status_code == 404
        assert fake.deleted == []
        assert row.dialogue_id in fake._get_map


class TestAssessmentLifecycle:
    """slice 53: Assessment complete + delete — slice 50/51 패턴 답습 invariant 4회차.

    *Assessment는 completed_at*(`ended_at` 아님). 경로도 `/complete`로 명칭만 컬럼 의미 추종.
    """

    def _assessment_row(self, owner: uuid.UUID, completed: bool = False) -> Assessment:
        aid = uuid.uuid4()
        schema = AssessmentSchema(
            assessment_id=aid,
            user_id=owner,
            completed_at=datetime.now(UTC) if completed else None,
        )
        return Assessment.from_schema(schema)

    # ── PATCH complete ──
    def test_complete_fresh_assessment(self) -> None:
        row = self._assessment_row(_UID, completed=False)
        client, fake = _client([], get_map={row.assessment_id: row})
        resp = client.patch(f"/v1/me/assessments/{row.assessment_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None
        assert fake.commits == 1

    def test_complete_idempotent_already_completed(self) -> None:
        row = self._assessment_row(_UID, completed=True)
        original = row.completed_at
        client, fake = _client([], get_map={row.assessment_id: row})
        resp = client.patch(f"/v1/me/assessments/{row.assessment_id}/complete")
        assert resp.status_code == 200
        assert row.completed_at == original
        assert fake.commits == 0

    def test_complete_nonexistent_returns_404(self) -> None:
        fake_id = uuid.uuid4()
        client, _ = _client([], get_map={})
        resp = client.patch(f"/v1/me/assessments/{fake_id}/complete")
        assert resp.status_code == 404

    def test_complete_other_users_assessment_returns_404(self) -> None:
        other_uid = uuid.uuid4()
        row = self._assessment_row(other_uid, completed=False)
        client, fake = _client([], get_map={row.assessment_id: row})
        resp = client.patch(f"/v1/me/assessments/{row.assessment_id}/complete")
        assert resp.status_code == 404
        assert row.completed_at is None
        assert fake.commits == 0

    # ── DELETE ──
    def test_delete_own_assessment_returns_204(self) -> None:
        row = self._assessment_row(_UID)
        client, fake = _client([], get_map={row.assessment_id: row})
        resp = client.delete(f"/v1/me/assessments/{row.assessment_id}")
        assert resp.status_code == 204
        assert fake.deleted == [row]
        assert fake.commits == 1
        # slice 57: assessment 삭제 감사 적재
        assert len(fake.added) == 1
        assert fake.added[0].resource_type == "assessment"
        assert fake.added[0].resource_id == row.assessment_id

    def test_delete_nonexistent_returns_404(self) -> None:
        fake_id = uuid.uuid4()
        client, fake = _client([], get_map={})
        resp = client.delete(f"/v1/me/assessments/{fake_id}")
        assert resp.status_code == 404
        assert fake.deleted == []

    def test_delete_other_users_assessment_returns_404(self) -> None:
        other_uid = uuid.uuid4()
        row = self._assessment_row(other_uid)
        client, fake = _client([], get_map={row.assessment_id: row})
        resp = client.delete(f"/v1/me/assessments/{row.assessment_id}")
        assert resp.status_code == 404
        assert fake.deleted == []
        assert row.assessment_id in fake._get_map
