"""me 라우터 단위테스트 — /v1/me/{sessions,assessments,dialogues}(hermetic).

엔드포인트 결선(200·직렬화·401·빈[])을 검증한다. user_id 스코핑(WHERE) 정확성은 통합
테스트(test_me_integration.py)가 실 PG로 검증한다 — FakeSession은 stmt를 무시하므로.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api.me import (
    ConceptAbilityItem,
    _add_ability_snapshot_if_attempts,
    _weak_concept_weights,
)
from whymath_backend.app import create_app
from whymath_backend.db.models.activity import LearningSession
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import AbilitySnapshot as AbilitySnapshotSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
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

    def scalar(self) -> int:
        # slice 71: count(*) 쿼리 시뮬 — FakeSession은 stmt를 무시하므로 행 수를 총 건수로
        # 흉내(정확한 필터 적용 count는 통합테스트가 실 PG로 검증). 헤더 결선·숫자성만 본다.
        return len(self._rows)

    def all(self) -> list[Any]:
        # slice L2-5d: join 쿼리(select(CMH, code, name))는 result.all()로 Row 튜플 순회.
        # /mastery/current 테스트는 (cmh, code, name) 튜플 리스트를 그대로 전달(_snapshot_row).
        return list(self._rows)


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

    def test_deletions_multiple_resource_types_accepted(self) -> None:
        """slice 68: resource_type 반복 지정(OR/IN) 200 — 다중 도메인 결선."""
        client, _ = _client([])
        resp = client.get(
            "/v1/me/deletions",
            params=[("resource_type", "dialogue"), ("resource_type", "assessment")],
        )
        assert resp.status_code == 200, resp.text

    def test_deletions_multiple_resource_types_one_invalid_rejected(self) -> None:
        """slice 68: 다중 값 중 하나라도 enum 밖이면 422(부분 주입 차단)."""
        client, _ = _client([])
        resp = client.get(
            "/v1/me/deletions",
            params=[("resource_type", "dialogue"), ("resource_type", "bogus")],
        )
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

    # slice 69: lifecycle 종료 시각 시간창 — 엔드포인트별 파라미터명(ended_/completed_).
    _CLOSE_WINDOW_ENDPOINTS = (
        ("/v1/me/sessions", "ended_since", "ended_until"),
        ("/v1/me/dialogues", "ended_since", "ended_until"),
        ("/v1/me/assessments", "completed_since", "completed_until"),
    )

    def test_close_time_window_accepted_all_endpoints(self) -> None:
        """slice 69: ended_/completed_ 시간창 TZ-aware 수용(200·결선)."""
        client, _ = _client([])
        for path, lo, hi in self._CLOSE_WINDOW_ENDPOINTS:
            resp = client.get(
                path,
                params={lo: "2024-01-01T00:00:00Z", hi: "2024-12-31T23:59:59+00:00"},
            )
            assert resp.status_code == 200, (path, resp.text)

    def test_close_time_window_naive_rejected_all_endpoints(self) -> None:
        """slice 69: 종료 시각 시간창도 naive datetime은 422(공용 검증)."""
        client, _ = _client([])
        for path, lo, _hi in self._CLOSE_WINDOW_ENDPOINTS:
            resp = client.get(path, params={lo: "2024-01-01T00:00:00"})
            assert resp.status_code == 422, path

    def test_close_time_window_inverted_rejected_all_endpoints(self) -> None:
        """slice 69: 종료 시각 시간창도 since > until은 422(공용 검증)."""
        client, _ = _client([])
        for path, lo, hi in self._CLOSE_WINDOW_ENDPOINTS:
            resp = client.get(
                path,
                params={lo: "2024-12-31T00:00:00Z", hi: "2024-01-01T00:00:00Z"},
            )
            assert resp.status_code == 422, path

    def test_order_param_accepted_all_endpoints(self) -> None:
        """slice 70: order=asc/desc 모두 200(결선)·생략도 200(기본 desc)."""
        client, _ = _client([])
        for path in _ENDPOINTS:
            for order in ("asc", "desc"):
                resp = client.get(path, params={"order": order})
                assert resp.status_code == 200, (path, order, resp.text)
            assert client.get(path).status_code == 200, path  # 생략=기본 desc

    def test_order_param_invalid_rejected_all_endpoints(self) -> None:
        """slice 70: order Literal 밖 값은 422(asc/desc만 허용)."""
        client, _ = _client([])
        for path in _ENDPOINTS:
            resp = client.get(path, params={"order": "sideways"})
            assert resp.status_code == 422, path

    def test_include_total_sets_header_all_endpoints(self) -> None:
        """slice 71: include_total=true면 X-Total-Count 헤더 노출(숫자).

        FakeSession은 stmt 무시·scalar()=행 수라 *필터 적용 count*는 통합테스트가 검증.
        여기선 헤더 결선(존재·숫자성)만. 빈 시드라 len([])=0 → "0".
        """
        client, _ = _client([])
        for path in _ENDPOINTS:
            resp = client.get(path, params={"include_total": "true"})
            assert resp.status_code == 200, path
            assert resp.headers.get("X-Total-Count") == "0", path

    def test_no_total_header_by_default_all_endpoints(self) -> None:
        """slice 71: include_total 생략(기본 false)이면 X-Total-Count 헤더 없음(COUNT 비용 회피)."""
        client, _ = _client([])
        for path in _ENDPOINTS:
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert "X-Total-Count" not in resp.headers, path


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

    def test_end_captures_ability_snapshot_when_attempts_exist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 34/75: 처음 종료 + 채점 이력 있으면 θ 스냅샷 자동 적재(종료 1 + 스냅샷 1 commit).

        개념별 θ 적재(slice 75)는 `TestSessionEndConceptSnapshots`·통합테스트가 검증 — 여기선
        전과목 캡처·단일 트랜잭션만 보려 `compute_concept_abilities`를 빈 리스트로 고정한다
        (FakeSession은 단일 행셋만 반환해 전과목 3-튜플과 개념 6-튜플을 동시에 못 줌).
        """

        async def _no_concepts(session: Any, user_id: Any) -> list[ConceptAbilityItem]:
            return []

        monkeypatch.setattr("whymath_backend.api.me.compute_concept_abilities", _no_concepts)
        row = self._session_row(_UID, ended=False)
        # FakeSession.execute(θ 쿼리) → (is_correct, difficulty, irt_difficulty_b) 행
        client, fake = _client(
            [(True, 3.0, None), (False, 3.0, None)], get_map={row.session_id: row}
        )
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 200
        snaps = [a for a in fake.added if isinstance(a, AbilitySnapshot)]
        assert len(snaps) == 1
        assert snaps[0].response_count == 2
        assert snaps[0].concept_id is None  # 전과목 단일 θ
        assert fake.commits == 1  # slice 35: 종료 + 스냅샷 단일 트랜잭션

    def test_end_no_attempts_skips_snapshot(self) -> None:
        """채점 이력 0 → θ=0 노이즈 스냅샷 미적재(종료만)."""
        row = self._session_row(_UID, ended=False)
        client, fake = _client([], get_map={row.session_id: row})
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 200
        assert not any(isinstance(a, AbilitySnapshot) for a in fake.added)
        assert fake.commits == 1  # 종료만

    def test_idempotent_end_skips_snapshot(self) -> None:
        """이미 종료된 세션 재호출 → 채점 이력 있어도 스냅샷 미적재(멱등 트리거)."""
        row = self._session_row(_UID, ended=True)
        client, fake = _client([(True, 3.0, None)], get_map={row.session_id: row})
        resp = client.patch(f"/v1/me/sessions/{row.session_id}/end")
        assert resp.status_code == 200
        assert not any(isinstance(a, AbilitySnapshot) for a in fake.added)
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
        """slice 51: 삭제 후 같은 ID 재호출은 404
        (idempotent 의미·DELETE *aFTER*는 두 번째 호출이 미존재)."""
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


# ── slice L2-4: POST /v1/me/attempts (풀이 채점 제출 + 숙달 자동 갱신) ──────────
class _AQResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_AQResult":
        return self

    def all(self) -> list[Any]:
        return self._rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _QueueSession:
    """execute 호출마다 큐잉 결과를 순서대로 반환 — 채점 엔드포인트의 다중 쿼리(개념 조회 →
    개념별 prior) 시뮬. add/commit 캡처."""

    def __init__(self, results: list[_AQResult]) -> None:
        self._results = results
        self._i = 0
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _stmt: Any) -> _AQResult:
        result = self._results[self._i]
        self._i += 1
        return result

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _attempts_client(session: _QueueSession) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user

    async def _sess() -> AsyncIterator[_QueueSession]:
        yield session

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class TestSubmitAttempt:
    def test_submit_with_assessed_concept(self) -> None:
        """채점 제출 → ProblemAttempt 적재 + 평가 개념 숙달 갱신 응답."""
        cid = uuid.uuid4()
        # 개념 숙달: execute#1=개념 [cid]·#2=개념 prior 없음.
        # 스킬 숙달(Phase 2b-2): #3=개념 [cid]·#4=스킬 해소 [](미매핑 → 스킬행 0).
        session = _QueueSession([_AQResult([cid]), _AQResult([]), _AQResult([cid]), _AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={"problem_id": str(uuid.uuid4()), "is_correct": True},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        uuid.UUID(body["attempt_id"])  # 발급됨
        assert body["is_correct"] is True
        assert len(body["mastery_updates"]) == 1
        upd = body["mastery_updates"][0]
        assert upd["concept_id"] == str(cid)
        assert upd["mastery"] == 0.69  # 첫 관측·정답
        assert upd["sample_size"] == 1
        assert body["skill_mastery_updates"] == []  # 스킬 해소 0(미매핑)
        # ProblemAttempt + 개념 숙달행 add·attempt commit 발생(스킬행 0)
        assert len(session.added) == 2

    def test_submit_no_mapped_concepts(self) -> None:
        """문제↔개념 매핑 없으면 attempt만 적재·mastery/skill 갱신 빈 리스트."""
        # 오답(모델 B): 개념 PRIMARY→[]·TESTED 폴백→[]. 스킬(Phase 2b-2): PRIMARY→[]·TESTED→[].
        session = _QueueSession([_AQResult([]), _AQResult([]), _AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={"problem_id": str(uuid.uuid4()), "is_correct": False},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["mastery_updates"] == []
        assert resp.json()["skill_mastery_updates"] == []
        assert len(session.added) == 1  # attempt만

    def test_submit_overconfident_returns_coaching(self) -> None:
        """과신 제출(틀림 + 확신≥0.7) → calibration_coaching.focus==overconfident(§11.4)."""
        # 오답(모델 B): 개념 PRIMARY→[]·TESTED→[]·스킬 PRIMARY→[]·TESTED→[](매핑 없음).
        session = _QueueSession([_AQResult([]), _AQResult([]), _AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={
                "problem_id": str(uuid.uuid4()),
                "is_correct": False,
                "confidence_self_reported": 0.9,
            },
        )
        assert resp.status_code == 201, resp.text
        coaching = resp.json()["calibration_coaching"]
        assert coaching is not None
        assert coaching["focus"] == "calibration_overconfident"
        assert coaching["socratic_category"] == "assumption"
        # 적재 로직 불변 — attempt 1건만 add(개념 매핑 없음).
        assert len(session.added) == 1

    def test_submit_well_calibrated_no_coaching(self) -> None:
        """잘 보정됨(맞음 + 확신 높음) → calibration_coaching==null."""
        # 정답: 개념 assessed→[]·스킬 assessed→[](매핑 없음·둘 다 갱신 0).
        session = _QueueSession([_AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={
                "problem_id": str(uuid.uuid4()),
                "is_correct": True,
                "confidence_self_reported": 0.9,
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["calibration_coaching"] is None

    def test_submit_no_confidence_no_coaching(self) -> None:
        """확신 미제출(confidence 없음) → calibration_coaching==null(보정 평가 불가)."""
        # 오답(모델 B): 개념 PRIMARY→[]·TESTED→[]·스킬 PRIMARY→[]·TESTED→[](매핑 없음).
        session = _QueueSession([_AQResult([]), _AQResult([]), _AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={"problem_id": str(uuid.uuid4()), "is_correct": False},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["calibration_coaching"] is None

    def test_submit_requires_auth(self) -> None:
        """무토큰은 401(인증 게이트)."""
        app = create_app()

        async def _sess() -> AsyncIterator[_QueueSession]:
            yield _QueueSession([_AQResult([])])

        app.dependency_overrides[get_session] = _sess
        client = TestClient(app)
        resp = client.post(
            "/v1/me/attempts",
            json={"problem_id": str(uuid.uuid4()), "is_correct": True},
        )
        assert resp.status_code == 401

    def test_submit_missing_fields_422(self) -> None:
        session = _QueueSession([_AQResult([])])
        client = _attempts_client(session)
        # is_correct 누락
        assert (
            client.post("/v1/me/attempts", json={"problem_id": str(uuid.uuid4())}).status_code
            == 422
        )
        # problem_id 누락
        assert client.post("/v1/me/attempts", json={"is_correct": True}).status_code == 422

    def test_submit_extra_field_422(self) -> None:
        """extra='forbid' — 모르는 필드 거부(예: user_id 사칭 시도)."""
        session = _QueueSession([_AQResult([])])
        client = _attempts_client(session)
        resp = client.post(
            "/v1/me/attempts",
            json={
                "problem_id": str(uuid.uuid4()),
                "is_correct": True,
                "user_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 422


# ── slice L2-5: GET /v1/me/mastery (학습곡선 조회 — ConceptMasteryHistory 시계열) ──
def _mastery_row(mastery: float = 0.69, sample_size: int = 1) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        ConceptMasteryHistorySchema(
            user_id=_UID,
            concept_id=uuid.uuid4(),
            measured_at=datetime(2026, 1, 1, tzinfo=UTC),
            mastery=mastery,
            sample_size=sample_size,
        )
    )


def _snapshot_row(
    mastery: float | None = 0.69, code: str | None = "C-1", name: str | None = "개념"
) -> tuple[ConceptMasteryHistory, str | None, str | None]:
    """slice L2-5d: /mastery/current join 쿼리의 Row 튜플 시뮬 — (CMH, code, name_ko)."""
    cmh = ConceptMasteryHistory.from_schema(
        ConceptMasteryHistorySchema(
            user_id=_UID,
            concept_id=uuid.uuid4(),
            measured_at=datetime(2026, 1, 1, tzinfo=UTC),
            mastery=mastery,
            sample_size=1,
        )
    )
    return (cmh, code, name)


class TestMasteryCurve:
    def test_returns_rows(self) -> None:
        client, _ = _client([_mastery_row()])
        resp = client.get("/v1/me/mastery")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        assert float(body[0]["mastery"]) == 0.69
        assert str(body[0]["user_id"]) == str(_UID)

    def test_empty(self) -> None:
        client, _ = _client([])
        resp = client.get("/v1/me/mastery")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/mastery").status_code == 401

    def test_concept_id_filter_accepted(self) -> None:
        """?concept_id=<uuid> 결선(200)·잘못된 uuid는 422."""
        client, _ = _client([_mastery_row()])
        assert (
            client.get("/v1/me/mastery", params={"concept_id": str(uuid.uuid4())}).status_code
            == 200
        )
        assert client.get("/v1/me/mastery", params={"concept_id": "not-a-uuid"}).status_code == 422

    def test_include_total_header(self) -> None:
        client, _ = _client([_mastery_row()])
        resp = client.get("/v1/me/mastery", params={"include_total": "true"})
        assert resp.headers.get("X-Total-Count") == "1"

    def test_order_accepted(self) -> None:
        client, _ = _client([_mastery_row()])
        for order in ("asc", "desc"):
            assert client.get("/v1/me/mastery", params={"order": order}).status_code == 200
        assert client.get("/v1/me/mastery", params={"order": "sideways"}).status_code == 422

    def test_time_window_validation(self) -> None:
        """measured_at 시간창도 naive 422·since>until 422(공용 검증)."""
        client, _ = _client([])
        assert (
            client.get("/v1/me/mastery", params={"since": "2024-01-01T00:00:00"}).status_code == 422
        )
        assert (
            client.get(
                "/v1/me/mastery",
                params={
                    "since": "2024-12-31T00:00:00Z",
                    "until": "2024-01-01T00:00:00Z",
                },
            ).status_code
            == 422
        )

    def test_current_returns_rows_with_concept_meta(self) -> None:
        """slice L2-5b/5d: 스냅샷 — 200·개념 메타(name/code) 조인 노출."""
        client, _ = _client([_snapshot_row(0.69, code="CAL-1", name="정적분")])
        resp = client.get("/v1/me/mastery/current")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        assert body[0]["concept_code"] == "CAL-1"
        assert body[0]["concept_name"] == "정적분"
        assert float(body[0]["mastery"]) == 0.69

    def test_current_orphan_concept_null_meta(self) -> None:
        """개념 삭제(orphan·LEFT JOIN) 시 name/code는 null이나 행은 보존."""
        client, _ = _client([_snapshot_row(0.5, code=None, name=None)])
        resp = client.get("/v1/me/mastery/current")
        body = resp.json()
        assert len(body) == 1
        assert body[0]["concept_name"] is None
        assert body[0]["concept_code"] is None

    def test_current_empty(self) -> None:
        client, _ = _client([])
        assert client.get("/v1/me/mastery/current").json() == []

    def test_current_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/mastery/current").status_code == 401

    def test_current_order_by_mastery_weakest_first(self) -> None:
        """slice L2-5c: order_by=mastery&order=asc → 약점(낮은 숙달) 우선."""
        rows = [_snapshot_row(0.9), _snapshot_row(0.3), _snapshot_row(0.6)]
        client, _ = _client(rows)
        resp = client.get("/v1/me/mastery/current", params={"order_by": "mastery", "order": "asc"})
        assert resp.status_code == 200, resp.text
        assert [float(r["mastery"]) for r in resp.json()] == [0.3, 0.6, 0.9]

    def test_current_order_by_mastery_strongest_first(self) -> None:
        rows = [_snapshot_row(0.3), _snapshot_row(0.9)]
        client, _ = _client(rows)
        resp = client.get("/v1/me/mastery/current", params={"order_by": "mastery", "order": "desc"})
        assert [float(r["mastery"]) for r in resp.json()] == [0.9, 0.3]

    def test_current_mastery_null_always_last(self) -> None:
        """mastery NULL은 정렬 방향 무관 항상 끝."""
        client, _ = _client([_snapshot_row(None), _snapshot_row(0.5)])
        resp = client.get("/v1/me/mastery/current", params={"order_by": "mastery", "order": "asc"})
        body = resp.json()
        assert body[-1]["mastery"] is None

    def test_current_invalid_order_by_422(self) -> None:
        client, _ = _client([])
        assert client.get("/v1/me/mastery/current", params={"order_by": "bogus"}).status_code == 422


class TestAbility:
    """slice L2-11: GET /v1/me/ability — 채점 풀이 이력에서 IRT θ 추정.

    FakeSession._Result.all()이 (is_correct, difficulty_overall, irt_difficulty_b) 튜플 리스트를
    반환(조인 쿼리 시뮬). 실제 JOIN/WHERE 정확성은 통합테스트가 검증. slice 79: 보정 b 컬럼 추가
    (여기선 None=휴리스틱 폴백 — 보정 b 소비는 L2 단위테스트가 검증).
    """

    def test_empty_zero_theta(self) -> None:
        """응답 0건 → θ=0·측정 불가(SE·CI null)."""
        client, _ = _client([])
        resp = client.get("/v1/me/ability")
        assert resp.status_code == 200
        assert resp.json() == {
            "theta": 0.0,
            "response_count": 0,
            "standard_error": None,
            "confidence_interval": None,
        }

    def test_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/ability").status_code == 401

    def test_all_correct_upper_bound(self) -> None:
        """전부 정답 → θ 상한(4.0)·응답 수 반영."""
        client, _ = _client([(True, 3.0, None), (True, 4.0, None)])
        body = client.get("/v1/me/ability").json()
        assert body["theta"] == 4.0
        assert body["response_count"] == 2

    def test_all_incorrect_lower_bound(self) -> None:
        client, _ = _client([(False, 3.0, None), (False, 2.0, None)])
        assert client.get("/v1/me/ability").json()["theta"] == -4.0

    def test_correct_on_hard_higher_theta(self) -> None:
        """어려운 문항을 맞히면(쉬운 문항 맞힘보다) 능력 추정 높음."""
        # 어려움(5.0) 정답·중간(3.0) 오답 vs 쉬움(1.0) 정답·중간 오답
        hard, _ = _client([(True, 5.0, None), (False, 3.0, None)])
        easy, _ = _client([(True, 1.0, None), (False, 3.0, None)])
        theta_hard = hard.get("/v1/me/ability").json()["theta"]
        theta_easy = easy.get("/v1/me/ability").json()["theta"]
        assert theta_hard > theta_easy

    def test_skips_null_difficulty(self) -> None:
        """difficulty_overall NULL·보정 b 없는 문항은 제외(추정에서 빠짐)."""
        client, _ = _client([(True, 3.0, None), (True, None, None)])
        body = client.get("/v1/me/ability").json()
        assert body["response_count"] == 1  # NULL 난이도 1건 제외

    def test_standard_error_and_confidence_interval(self) -> None:
        """혼합 응답(난이도3 1정답·1오답) → θ=0·SE=1/√0.5·대칭 95% CI(θ±1.96·SE)."""
        client, _ = _client([(True, 3.0, None), (False, 3.0, None)])
        body = client.get("/v1/me/ability").json()
        assert body["theta"] == 0.0
        # 두 문항 b=0·θ=0 → 정보 2·0.25=0.5 → SE=1/√0.5≈1.41421
        assert round(body["standard_error"], 5) == 1.41421
        lo, hi = body["confidence_interval"]
        assert round(lo, 5) == -2.77186  # -1.96·SE
        assert round(hi, 5) == 2.77186

    def test_more_responses_smaller_standard_error(self) -> None:
        """응답이 많을수록 SE↓(측정 정밀도↑)."""
        few, _ = _client([(True, 3.0, None), (False, 3.0, None)])
        many, _ = _client([(True, 3.0, None), (False, 3.0, None)] * 4)
        se_few = few.get("/v1/me/ability").json()["standard_error"]
        se_many = many.get("/v1/me/ability").json()["standard_error"]
        assert se_many < se_few


class TestAbilityHistory:
    """slice L2-28: GET /v1/me/ability/history — θ 성장 곡선(시간 재생).

    FakeSession._Result.all()이 (created_at, is_correct, difficulty, irt_difficulty_b) 튜플(시간
    오름차순)을 반환. 누적 재생·시점 방출만 본다(실 ORDER BY는 통합테스트). slice 81: 보정 b 컬럼
    추가(None=휴리스틱 폴백).
    """

    @staticmethod
    def _ts(day: int) -> datetime:
        return datetime(2026, 1, day, tzinfo=UTC)

    def test_empty_returns_empty(self) -> None:
        client, _ = _client([])
        resp = client.get("/v1/me/ability/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/ability/history").status_code == 401

    def test_cumulative_growth_curve(self) -> None:
        """1오답→θ-4, +1정답→θ0, +1정답→θ>0. response_count 1·2·3·as_of 보존."""
        client, _ = _client(
            [
                (self._ts(1), False, 3.0, None),
                (self._ts(2), True, 3.0, None),
                (self._ts(3), True, 3.0, None),
            ]
        )
        body = client.get("/v1/me/ability/history").json()
        assert [p["response_count"] for p in body] == [1, 2, 3]
        assert body[0]["theta"] == -4.0  # 전부 오답
        assert body[1]["theta"] == 0.0  # 1F1T 대칭
        assert body[2]["theta"] > 0.0  # 2T1F → 양수
        assert body[0]["as_of"].startswith("2026-01-01")

    def test_limit_returns_last_n(self) -> None:
        """?limit=1 → 끝(최근) 1개 지점만."""
        client, _ = _client(
            [
                (self._ts(1), False, 3.0, None),
                (self._ts(2), True, 3.0, None),
                (self._ts(3), True, 3.0, None),
            ]
        )
        body = client.get("/v1/me/ability/history?limit=1").json()
        assert len(body) == 1
        assert body[0]["response_count"] == 3  # 마지막 지점

    def test_standard_error_present(self) -> None:
        client, _ = _client([(self._ts(1), True, 3.0, None), (self._ts(2), False, 3.0, None)])
        body = client.get("/v1/me/ability/history").json()
        # 응답 있으니 SE 유한(측정 가능)
        assert all(p["standard_error"] is not None for p in body)

    def test_skips_attempt_without_b_source(self) -> None:
        """slice 81: 난이도·보정 b 둘 다 없는 풀이는 θ 시점 생성에서 제외."""
        client, _ = _client([(self._ts(1), True, 3.0, None), (self._ts(2), True, None, None)])
        body = client.get("/v1/me/ability/history").json()
        assert len(body) == 1  # None-b 풀이 제외 → 시점 1개


class TestAbilitySnapshots:
    """slice L2-32: POST/GET /v1/me/ability/snapshots — θ 시계열 적재·조회."""

    @staticmethod
    def _snap(theta: float, day: int) -> AbilitySnapshot:
        return AbilitySnapshot.from_schema(
            AbilitySnapshotSchema(
                user_id=_UID,
                theta=theta,
                response_count=1,
                measured_at=datetime(2026, 1, day, tzinfo=UTC),
            )
        )

    def test_capture_inserts_snapshot(self) -> None:
        """POST → 현재 θ 계산(난이도3 1정답1오답→θ0)·1행 적재·201 + 스키마 반환."""
        client, fake = _client([(True, 3.0, None), (False, 3.0, None)])
        resp = client.post("/v1/me/ability/snapshots")
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["theta"] == 0.0
        assert body["response_count"] == 2
        assert body["standard_error"] is not None
        assert body["concept_id"] is None  # 전 과목 단일 θ
        uuid.UUID(body["snapshot_id"])  # 발급됨
        assert len(fake.added) == 1  # AbilitySnapshot 1행 적재
        assert fake.commits == 1

    def test_capture_empty_history_se_null(self) -> None:
        """채점 이력 0 → θ0·response_count0·SE null도 적재."""
        client, fake = _client([])
        body = client.post("/v1/me/ability/snapshots").json()
        assert body["theta"] == 0.0
        assert body["response_count"] == 0
        assert body["standard_error"] is None
        assert len(fake.added) == 1

    def test_capture_requires_auth(self) -> None:
        assert _no_auth_client().post("/v1/me/ability/snapshots").status_code == 401

    def test_list_returns_chronological(self) -> None:
        client, _ = _client([self._snap(0.2, 1), self._snap(1.1, 2)])
        body = client.get("/v1/me/ability/snapshots").json()
        assert [s["theta"] for s in body] == [0.2, 1.1]
        assert body[0]["measured_at"].startswith("2026-01-01")

    def test_list_limit_tail(self) -> None:
        client, _ = _client([self._snap(0.2, 1), self._snap(1.1, 2)])
        body = client.get("/v1/me/ability/snapshots?limit=1").json()
        assert len(body) == 1
        assert body[0]["theta"] == 1.1  # 끝(최근) 1개

    def test_list_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/ability/snapshots").status_code == 401

    def test_capture_include_concepts_writes_per_concept(self) -> None:
        """slice 33: ?include_concepts=true → 전과목 1행 + 개념별 N행 적재(같은 시각)."""
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        # execute#1=전과목 attempt 행·#2=개념별 행(둘 다 끝에 irt_b 컬럼 추가)
        session = _QueueSession(
            [
                _AQResult([(True, 3.0, None), (False, 3.0, None)]),
                _AQResult(
                    [
                        (c1, "C1", "개념1", True, 3.0, None),
                        (c2, "C2", "개념2", False, 3.0, None),
                    ]
                ),
            ]
        )
        client = _attempts_client(session)
        resp = client.post("/v1/me/ability/snapshots?include_concepts=true")
        assert resp.status_code == 201, resp.text
        assert resp.json()["concept_id"] is None  # 응답은 전과목 스냅샷
        assert len(session.added) == 3  # 전과목 1 + 개념 2
        assert session.commits == 1
        # 적재된 행 중 개념별 2행은 concept_id 보유
        concept_ids = {s.concept_id for s in session.added if s.concept_id is not None}
        assert concept_ids == {c1, c2}

    def test_list_concept_id_filter_serializes(self) -> None:
        """slice 33: ?concept_id 지정 → 그 개념 스냅샷(concept_id 직렬화)."""
        cid = uuid.uuid4()
        snap = AbilitySnapshot.from_schema(
            AbilitySnapshotSchema(
                user_id=_UID,
                concept_id=cid,
                theta=0.5,
                response_count=1,
                measured_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        client, _ = _client([snap])
        body = client.get(f"/v1/me/ability/snapshots?concept_id={cid}").json()
        assert len(body) == 1
        assert body[0]["concept_id"] == str(cid)


class TestAbilityByConcept:
    """slice L2-18: GET /v1/me/ability/by-concept — 개념별 θ 분리 추정.

    FakeSession._Result.all()이 (concept_id, code, name, is_correct, difficulty, irt_difficulty_b)
    6튜플을 반환(조인 시뮬). 그룹화·정렬·θ/SE 산출만 본다(실 JOIN/WHERE는 통합테스트). slice 79:
    보정 b 컬럼 추가(None=휴리스틱 폴백).
    """

    def test_empty_returns_empty_list(self) -> None:
        client, _ = _client([])
        resp = client.get("/v1/me/ability/by-concept")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self) -> None:
        assert _no_auth_client().get("/v1/me/ability/by-concept").status_code == 401

    def test_single_concept_theta_and_meta(self) -> None:
        """한 개념 1정답·1오답(난이도3) → θ=0·count 2·SE=1/√0.5·개념 메타 노출."""
        cid = uuid.uuid4()
        client, _ = _client(
            [
                (cid, "TRIG-1", "삼각함수", True, 3.0, None),
                (cid, "TRIG-1", "삼각함수", False, 3.0, None),
            ]
        )
        body = client.get("/v1/me/ability/by-concept").json()
        assert len(body) == 1
        item = body[0]
        assert item["concept_id"] == str(cid)
        assert item["concept_code"] == "TRIG-1"
        assert item["concept_name"] == "삼각함수"
        assert item["theta"] == 0.0
        assert item["response_count"] == 2
        assert round(item["standard_error"], 5) == 1.41421

    def test_multiple_concepts_sorted_weakest_first(self) -> None:
        """능력 낮은(약점) 개념 먼저 — 전부오답(θ=-4) < 전부정답(θ=4)."""
        c_weak, c_strong = uuid.uuid4(), uuid.uuid4()
        client, _ = _client(
            [
                (c_strong, "S", "강점개념", True, 3.0, None),
                (c_weak, "W", "약점개념", False, 3.0, None),
            ]
        )
        body = client.get("/v1/me/ability/by-concept").json()
        assert [i["concept_id"] for i in body] == [str(c_weak), str(c_strong)]
        assert body[0]["theta"] == -4.0
        assert body[1]["theta"] == 4.0

    def test_orphan_concept_null_meta(self) -> None:
        """concept 행 없는(orphan) 개념은 code·name null(LEFT JOIN)."""
        cid = uuid.uuid4()
        client, _ = _client([(cid, None, None, True, 3.0, None)])
        item = client.get("/v1/me/ability/by-concept").json()[0]
        assert item["concept_code"] is None
        assert item["concept_name"] is None
        assert item["theta"] == 4.0  # 단일 정답 → 상한


class TestNextProblem:
    """slice L2-12: GET /v1/me/next-problem — IRT 정보량 최대 미응답 문항 추천.

    _QueueSession이 execute 2회(①채점 이력 ②후보 풀)를 큐로 반환. 실 JOIN/NOT IN/거리정렬은
    통합테스트가 검증(FakeSession은 stmt 무시).
    """

    def test_no_candidates_null(self) -> None:
        """이력 없음(θ=0)·후보 없음 → 추천 null."""
        session = _QueueSession([_AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body == {
            "problem_id": None,
            "theta": 0.0,
            "difficulty": None,
            "standard_error": None,
            "measurement_sufficient": False,
        }

    def test_requires_auth(self) -> None:
        app = create_app()

        async def _sess() -> AsyncIterator[_QueueSession]:
            yield _QueueSession([_AQResult([]), _AQResult([])])

        app.dependency_overrides[get_session] = _sess
        assert TestClient(app).get("/v1/me/next-problem").status_code == 401

    def test_recommends_nearest_difficulty(self) -> None:
        """이력 없음(θ=0) → 난이도 2·3·5 후보 중 b=0(난이도 3)이 정보량 최대로 추천."""
        pid_easy, pid_mid, pid_hard = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        session = _QueueSession(
            [
                _AQResult([]),
                _AQResult([(pid_easy, 2.0, None), (pid_mid, 3.0, None), (pid_hard, 5.0, None)]),
            ]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["problem_id"] == str(pid_mid)
        assert body["difficulty"] == 3.0
        assert body["theta"] == 0.0

    def test_uses_calibrated_b_over_heuristic(self) -> None:
        """slice 81: 후보 선택이 보정 b(irt_difficulty_b) 우선 — θ=0에서 보정 b=0 문항 선택.

        A: 난이도 5(휴리스틱 b=2)이나 보정 b=0 · B: 난이도 3(휴리스틱 b=0)이나 보정 b=2.
        휴리스틱이면 B(난이도3→b0)가 θ=0 정보량 최대지만, 보정 b를 쓰면 A(b=0)가 선택된다.
        """
        pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
        session = _QueueSession(
            [
                _AQResult([]),  # 이력 없음 → θ=0
                _AQResult([(pid_a, 5.0, 0.0), (pid_b, 3.0, 2.0)]),
            ]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["theta"] == 0.0
        assert body["problem_id"] == str(pid_a)  # 보정 b=0 → θ 근접(휴리스틱이면 pid_b)

    def test_skips_attempt_without_b_source(self) -> None:
        """slice 81: 난이도·보정 b 둘 다 없는 풀이는 θ 추정에서 제외(θ=0)."""
        cand = uuid.uuid4()
        session = _QueueSession(
            [
                _AQResult([(uuid.uuid4(), True, None, None)]),  # b 소스 없음 → 제외
                _AQResult([(cand, 3.0, None)]),
            ]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["theta"] == 0.0  # 유효 응답 0 → θ=0
        assert body["problem_id"] == str(cand)

    def test_high_theta_picks_harder(self) -> None:
        """전부 정답 → θ 상한(4.0). 난이도 3·5 후보 중 b=2(난이도 5)가 정보량 최대."""
        pid_mid, pid_hard = uuid.uuid4(), uuid.uuid4()
        attempts = [(uuid.uuid4(), True, 5.0, None), (uuid.uuid4(), True, 4.0, None)]
        session = _QueueSession(
            [
                _AQResult(attempts),
                _AQResult([(pid_mid, 3.0, None), (pid_hard, 5.0, None)]),
            ]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["theta"] == 4.0
        assert body["problem_id"] == str(pid_hard)
        assert body["difficulty"] == 5.0
        # 응답 2건뿐 → SE 큼(>0.3)·측정 불충분
        assert body["standard_error"] is not None
        assert body["measurement_sufficient"] is False

    def test_measurement_sufficient_when_many_responses(self) -> None:
        """난이도3(b=0) 46건 절반 정답 → θ=0·SE=2/√46≈0.295 ≤ 0.3 → 중단 권고."""
        attempts = [(uuid.uuid4(), i % 2 == 0, 3.0, None) for i in range(46)]
        cand = uuid.uuid4()
        session = _QueueSession([_AQResult(attempts), _AQResult([(cand, 3.0, None)])])
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["theta"] == 0.0
        assert round(body["standard_error"], 3) == 0.295
        assert body["measurement_sufficient"] is True
        # 중단 권고와 무관히 후보가 있으면 추천은 제공
        assert body["problem_id"] == str(cand)

    def test_no_responses_se_null_not_sufficient(self) -> None:
        """응답 없음 → SE null·measurement_sufficient=False(측정 불가)."""
        cand = uuid.uuid4()
        session = _QueueSession([_AQResult([]), _AQResult([(cand, 3.0, None)])])
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["standard_error"] is None
        assert body["measurement_sufficient"] is False
        assert body["problem_id"] == str(cand)

    def test_weak_concept_priority_reorders(self) -> None:
        """slice 17: 동일 정보량 두 후보 중 약점 개념(저숙달) 문항이 가중으로 선택.

        쿼리 4회: ①채점 이력 ②후보 ③숙달 스냅샷 ④후보 개념 매핑.
        """
        c_strong, c_weak = uuid.uuid4(), uuid.uuid4()
        pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
        session = _QueueSession(
            [
                _AQResult([]),  # 채점 이력 없음 → θ=0
                _AQResult([(pid_a, 3.0, None), (pid_b, 3.0, None)]),  # 동일 난이도(b=0)
                _AQResult([(c_strong, 1.0), (c_weak, 0.0)]),  # 숙달: 강·약
                _AQResult([(pid_a, c_strong), (pid_b, c_weak)]),  # 개념 매핑
            ]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem?prioritize_weak_concepts=true").json()
        # 균등이면 동률→pid_a(낮은 인덱스)이나, 약점 가중으로 pid_b(저숙달) 선택
        assert body["problem_id"] == str(pid_b)
        assert body["theta"] == 0.0

    def test_default_ignores_weak_concepts(self) -> None:
        """기본(flag 미지정) → 가중 쿼리 없이 동률은 낮은 인덱스(slice 12 동작 보존)."""
        pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
        session = _QueueSession(
            [_AQResult([]), _AQResult([(pid_a, 3.0, None), (pid_b, 3.0, None)])]
        )
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem").json()
        assert body["problem_id"] == str(pid_a)

    def test_weak_priority_no_candidates_skips_weight_queries(self) -> None:
        """후보 없으면 flag=true라도 가중 쿼리 생략(2쿼리만)·problem_id null."""
        # _QueueSession에 2건만 제공 — 가중 쿼리를 돌리면 IndexError(가드 검증)
        session = _QueueSession([_AQResult([]), _AQResult([])])
        client = _attempts_client(session)
        body = client.get("/v1/me/next-problem?prioritize_weak_concepts=true").json()
        assert body["problem_id"] is None


class TestWeakConceptWeights:
    """slice 17: `_weak_concept_weights` 순수 헬퍼 — 문항별 약점 가중치 산출."""

    def test_no_concept_mapping_neutral(self) -> None:
        pid = uuid.uuid4()
        assert _weak_concept_weights([pid], {}, {}) == [1.0]

    def test_mapped_but_no_mastery_neutral(self) -> None:
        pid, c = uuid.uuid4(), uuid.uuid4()
        assert _weak_concept_weights([pid], {pid: {c}}, {}) == [1.0]

    def test_weakness_scales_weight(self) -> None:
        pid, c = uuid.uuid4(), uuid.uuid4()
        assert _weak_concept_weights([pid], {pid: {c}}, {c: 0.0}) == [2.0]  # 완전 약점
        assert _weak_concept_weights([pid], {pid: {c}}, {c: 1.0}) == [1.0]  # 완전 숙달
        assert _weak_concept_weights([pid], {pid: {c}}, {c: 0.25}) == [1.75]

    def test_min_mastery_among_concepts(self) -> None:
        """문항의 여러 평가 개념 중 *최저* 숙달로 weakness 산출."""
        pid = uuid.uuid4()
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        weights = _weak_concept_weights([pid], {pid: {c1, c2}}, {c1: 0.8, c2: 0.2})
        assert weights == [1.8]  # min(0.8, 0.2)=0.2 → 1+0.8

    def test_order_and_independence(self) -> None:
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        c = uuid.uuid4()
        # p1 약점·p2 매핑 없음 → [2.0, 1.0] 순서 보존
        assert _weak_concept_weights([p1, p2], {p1: {c}}, {c: 0.0}) == [2.0, 1.0]


def _diagnosis_client(mastery_rows: list[Any], irt_rows: list[Any]) -> TestClient:
    """slice 19: 진단 엔드포인트(쿼리 2회 — ①BKT 스냅샷 ②개념별 IRT) 큐 세션."""
    return _attempts_client(_QueueSession([_AQResult(mastery_rows), _AQResult(irt_rows)]))


class TestConceptDiagnosis:
    """slice L2-19: GET /v1/me/diagnosis/concepts — BKT↔IRT 교차검증.

    쿼리 2회: ①BKT 숙달 스냅샷(concept_id,code,name,mastery) ②개념별 IRT
    (concept_id,code,name,is_correct,difficulty,irt_difficulty_b). 그룹화·합집합·신호 분류만 본다.
    slice 81: IRT 행에 보정 b 컬럼 추가(None=휴리스틱 폴백).
    """

    def test_empty_returns_empty(self) -> None:
        body = _diagnosis_client([], []).get("/v1/me/diagnosis/concepts").json()
        assert body == []

    def test_requires_auth(self) -> None:
        app = create_app()

        async def _sess() -> AsyncIterator[_QueueSession]:
            yield _QueueSession([_AQResult([]), _AQResult([])])

        app.dependency_overrides[get_session] = _sess
        assert TestClient(app).get("/v1/me/diagnosis/concepts").status_code == 401

    def test_both_signals_agree(self) -> None:
        """BKT 0.5 · IRT 1정답1오답(θ=0→프록시 0.5) → agree."""
        cid = uuid.uuid4()
        client = _diagnosis_client(
            [(cid, "C", "개념", 0.5)],
            [(cid, "C", "개념", True, 3.0, None), (cid, "C", "개념", False, 3.0, None)],
        )
        body = client.get("/v1/me/diagnosis/concepts").json()
        assert len(body) == 1
        item = body[0]
        assert item["bkt_mastery"] == 0.5
        assert item["irt_theta"] == 0.0
        assert item["irt_mastery_proxy"] == 0.5
        assert item["response_count"] == 2
        assert item["agreement"] == "agree"
        assert item["concept_name"] == "개념"
        # slice 21: L4 코칭 처방 결선 — 합의·수준 0.5<0.6 → foundation
        assert item["coaching"]["focus"] == "foundation"
        assert item["coaching"]["prompt"]
        assert item["coaching"]["rationale"]

    def test_irt_higher_signal(self) -> None:
        """BKT 0.1인데 전부 정답(θ=4·프록시≈0.98) → irt_higher·코칭 consolidate."""
        cid = uuid.uuid4()
        client = _diagnosis_client([(cid, "C", "개념", 0.1)], [(cid, "C", "개념", True, 3.0, None)])
        item = client.get("/v1/me/diagnosis/concepts").json()[0]
        assert item["agreement"] == "irt_higher"
        assert item["irt_theta"] == 4.0
        assert item["coaching"]["focus"] == "consolidate"
        # slice 22: 코칭에 대화 진입 소크라테스 카테고리 노출
        assert item["coaching"]["socratic_category"] == "evidence"

    def test_bkt_higher_signal(self) -> None:
        """BKT 0.9인데 전부 오답(θ=-4·프록시≈0.02) → bkt_higher·코칭 retrieval."""
        cid = uuid.uuid4()
        client = _diagnosis_client(
            [(cid, "C", "개념", 0.9)], [(cid, "C", "개념", False, 3.0, None)]
        )
        item = client.get("/v1/me/diagnosis/concepts").json()[0]
        assert item["agreement"] == "bkt_higher"
        assert item["coaching"]["focus"] == "retrieval"

    def test_bkt_only_concept_insufficient(self) -> None:
        """IRT 채점 없는 개념 → theta·proxy null·insufficient·코칭 diagnose."""
        cid = uuid.uuid4()
        client = _diagnosis_client([(cid, "C", "개념", 0.6)], [])
        item = client.get("/v1/me/diagnosis/concepts").json()[0]
        assert item["bkt_mastery"] == 0.6
        assert item["irt_theta"] is None
        assert item["irt_mastery_proxy"] is None
        assert item["response_count"] == 0
        assert item["agreement"] == "insufficient"
        assert item["coaching"]["focus"] == "diagnose"

    def test_irt_only_concept_insufficient(self) -> None:
        """BKT 숙달 없는 개념(IRT만) → bkt null·insufficient."""
        cid = uuid.uuid4()
        client = _diagnosis_client([], [(cid, "C", "개념", True, 3.0, None)])
        item = client.get("/v1/me/diagnosis/concepts").json()[0]
        assert item["bkt_mastery"] is None
        assert item["irt_theta"] == 4.0
        assert item["agreement"] == "insufficient"

    def test_irt_row_without_b_source_skipped(self) -> None:
        """slice 81: IRT 행의 난이도·보정 b 둘 다 없으면 제외 — 그 개념 IRT 신호 없음."""
        cid = uuid.uuid4()
        client = _diagnosis_client(
            [(cid, "C", "개념", 0.6)], [(cid, "C", "개념", True, None, None)]
        )
        item = client.get("/v1/me/diagnosis/concepts").json()[0]
        assert item["irt_theta"] is None  # 유일 IRT 행 제외 → θ 없음
        assert item["response_count"] == 0
        assert item["agreement"] == "insufficient"

    def test_sorted_weakest_first(self) -> None:
        """약점(저신호) 개념 먼저 — BKT 0.1 < 0.9."""
        c_low, c_high = uuid.uuid4(), uuid.uuid4()
        client = _diagnosis_client([(c_high, "H", "상", 0.9), (c_low, "L", "하", 0.1)], [])
        body = client.get("/v1/me/diagnosis/concepts").json()
        assert [i["concept_id"] for i in body] == [str(c_low), str(c_high)]

    def test_limit_returns_n_weakest(self) -> None:
        """slice 26: ?limit=1 → 약점 먼저 정렬 후 상위 1개(가장 약한 개념)."""
        c_low, c_mid, c_high = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        client = _diagnosis_client(
            [
                (c_high, "H", "상", 0.9),
                (c_low, "L", "하", 0.1),
                (c_mid, "M", "중", 0.5),
            ],
            [],
        )
        body = client.get("/v1/me/diagnosis/concepts?limit=1").json()
        assert len(body) == 1
        assert body[0]["concept_id"] == str(c_low)

    def test_agreement_filter_only_matching(self) -> None:
        """slice 26: ?agreement=insufficient → 해당 신호 개념만."""
        # BKT만(insufficient) c1 · 합의(agree) c2
        c_insuff, c_agree = uuid.uuid4(), uuid.uuid4()
        client = _diagnosis_client(
            [(c_insuff, "I", "불충분", 0.3), (c_agree, "A", "합의", 0.5)],
            [
                (c_agree, "A", "합의", True, 3.0, None),
                (c_agree, "A", "합의", False, 3.0, None),
            ],
        )
        body = client.get("/v1/me/diagnosis/concepts?agreement=insufficient").json()
        assert [i["concept_id"] for i in body] == [str(c_insuff)]
        assert all(i["agreement"] == "insufficient" for i in body)

    def test_agreement_filter_multi_or(self) -> None:
        """반복 지정 시 OR — 두 신호 모두 포함."""
        c_insuff, c_agree = uuid.uuid4(), uuid.uuid4()
        client = _diagnosis_client(
            [(c_insuff, "I", "불충분", 0.3), (c_agree, "A", "합의", 0.5)],
            [
                (c_agree, "A", "합의", True, 3.0, None),
                (c_agree, "A", "합의", False, 3.0, None),
            ],
        )
        body = client.get("/v1/me/diagnosis/concepts?agreement=insufficient&agreement=agree").json()
        assert len(body) == 2

    def test_invalid_agreement_rejected_422(self) -> None:
        client = _diagnosis_client([], [])
        resp = client.get("/v1/me/diagnosis/concepts?agreement=bogus")
        assert resp.status_code == 422


class TestDiagnosisSummary:
    """slice L2-27: GET /v1/me/diagnosis/summary — 진단 집계(대시보드 헤더)."""

    def test_empty_zeros(self) -> None:
        body = _diagnosis_client([], []).get("/v1/me/diagnosis/summary").json()
        assert body == {
            "total_concepts": 0,
            "agree": 0,
            "irt_higher": 0,
            "bkt_higher": 0,
            "insufficient": 0,
            "attention_count": 0,
            "weakest_concept_id": None,
            "weakest_concept_name": None,
        }

    def test_requires_auth(self) -> None:
        app = create_app()

        async def _sess() -> AsyncIterator[_QueueSession]:
            yield _QueueSession([_AQResult([]), _AQResult([])])

        app.dependency_overrides[get_session] = _sess
        assert TestClient(app).get("/v1/me/diagnosis/summary").status_code == 401

    def test_aggregates_and_weakest(self) -> None:
        """c1 insufficient(BKT 0.3)·c2 agree(0.5+θ0)·c3 irt_higher(0.1+전부정답·θ4)."""
        c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        client = _diagnosis_client(
            [(c1, "I", "불충분", 0.3), (c2, "A", "합의", 0.5), (c3, "H", "높θ", 0.1)],
            [
                (c2, "A", "합의", True, 3.0, None),
                (c2, "A", "합의", False, 3.0, None),
                (c3, "H", "높θ", True, 3.0, None),
            ],
        )
        body = client.get("/v1/me/diagnosis/summary").json()
        assert body["total_concepts"] == 3
        assert body["agree"] == 1
        assert body["irt_higher"] == 1
        assert body["bkt_higher"] == 0
        assert body["insufficient"] == 1
        assert body["attention_count"] == 1  # irt_higher + bkt_higher
        # 최약점 = 최저 신호 c3(0.1)
        assert body["weakest_concept_id"] == str(c3)
        assert body["weakest_concept_name"] == "높θ"


class TestSessionEndConceptSnapshots:
    """slice 75: 세션 종료 자동 적재가 전과목 θ + 개념별 θ를 *같은 시각*으로 함께 추가."""

    async def test_adds_global_and_concept_snapshots(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cid_x, cid_y = uuid.uuid4(), uuid.uuid4()

        async def _fake_global(session: Any, user_id: Any) -> tuple[float, float | None, int]:
            return (1.2, 0.3, 5)

        async def _fake_concepts(session: Any, user_id: Any) -> list[ConceptAbilityItem]:
            return [
                ConceptAbilityItem(
                    concept_id=cid_x,
                    concept_code="A",
                    concept_name="가",
                    theta=0.8,
                    response_count=3,
                    standard_error=0.4,
                ),
                ConceptAbilityItem(
                    concept_id=cid_y,
                    concept_code="B",
                    concept_name="나",
                    theta=-0.5,
                    response_count=2,
                    standard_error=None,
                ),
            ]

        monkeypatch.setattr("whymath_backend.api.me.estimate_global_ability", _fake_global)
        monkeypatch.setattr("whymath_backend.api.me.compute_concept_abilities", _fake_concepts)
        fake = FakeSession()
        await _add_ability_snapshot_if_attempts(cast(AsyncSession, fake), _UID)

        # 전과목 1(concept_id None) + 개념 2(concept_id 값)
        assert len(fake.added) == 3
        globals_ = [a for a in fake.added if a.concept_id is None]
        concepts_ = [a for a in fake.added if a.concept_id is not None]
        assert len(globals_) == 1
        assert {a.concept_id for a in concepts_} == {cid_x, cid_y}
        # 전과목·개념 전원 동일 measured_at(같은 시각 원자 적재)
        assert len({a.measured_at for a in fake.added}) == 1
        # commit은 호출자(end_my_session) 책임 — 헬퍼는 add만
        assert fake.commits == 0

    async def test_skips_all_when_no_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_global(session: Any, user_id: Any) -> tuple[float, float | None, int]:
            return (0.0, None, 0)

        async def _boom(session: Any, user_id: Any) -> list[ConceptAbilityItem]:
            raise AssertionError("count==0이면 개념 θ 계산조차 하지 않아야 함")

        monkeypatch.setattr("whymath_backend.api.me.estimate_global_ability", _fake_global)
        monkeypatch.setattr("whymath_backend.api.me.compute_concept_abilities", _boom)
        fake = FakeSession()
        await _add_ability_snapshot_if_attempts(cast(AsyncSession, fake), _UID)
        # 채점 0 → 전과목·개념 θ 모두 미적재(개념 계산도 skip)
        assert fake.added == []
