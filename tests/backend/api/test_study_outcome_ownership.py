"""SEC-24(원 SEC-16) — POST /v1/me/objectives/{id}/outcome 세션 소유권 HTTP 매핑 (hermetic).

결함: `post_study_outcome`이 인증(`ConsentedUser`)은 하되 주입 user를 쓰지 않고, 클라 body의
`session_id`를 소유권 검증 없이 기록해 — 인증 학생이 임의 session_id로 미검증 outcome을 무제한
주입, L4 효과 집계(`effectiveness.py`)를 오염시킬 수 있었다
(`docs/reviews/functional_security_audit_2026-08-08.md` M2).

여기서는 검증 실패의 **HTTP 번역**을 못 박는다(검증 로직 자체는
`tests/backend/l2/test_pedagogy_evidence.py`가 결함주입으로 커버):
  - 소유권 실패(위조·타인·목표 교차) → **403 + 단일 메시지**(미존재/불일치/무바인딩을 구분해
    주면 "그 session_id가 존재하는가"의 존재 오라클이 된다 — detail 문자열 동일성으로 단언).
  - 중복 outcome → **409**.
  - 정당 소유자 → **201** + `{"recorded": true}` + outcome 행 stage.

TestClient + dependency_overrides(get_consented_user·get_session·get_settings) —
`test_speech_endpoint.py` 관례. execute 큐는 (처치 select → 중복 select) 순.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.db.models.pedagogy_dsl import LearningObjective
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_CONTENT_SOURCE,
    META_KEY_STRATEGY,
    META_KEY_USER_BINDING,
    session_user_binding,
)
from whymath_backend.schema.enums import Role

_STUDENT_ID = uuid.uuid4()
_OBJECTIVE_ID = "OBJ.sec16"
_PATH = f"/v1/me/objectives/{_OBJECTIVE_ID}/outcome"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


def _student() -> UserProfile:
    return UserProfile(user_id=_STUDENT_ID, role=Role.STUDENT)


def _objective(objective_id: str = _OBJECTIVE_ID) -> LearningObjective:
    """outcome 경로가 읽는 필드(id·k_type)만 채운 최소 학습목표."""
    return LearningObjective(id=objective_id, k_type="CONCEPT")


def _treatment_row(
    *, session_id: uuid.UUID, user_id: uuid.UUID, objective_id: str = _OBJECTIVE_ID
) -> EvidenceEvent:
    """`/study`가 남겼을 처치 행 — meta에 (session ↔ user) 키드 해시 바인딩 포함."""
    return EvidenceEvent(
        session_id=session_id,
        objective_id=objective_id,
        k_type="CONCEPT",
        event_type=EVENT_TYPE_TREATMENT,
        meta={
            META_KEY_STRATEGY: "SOCRATIC",
            META_KEY_CONTENT_SOURCE: "dsl_render",
            META_KEY_USER_BINDING: session_user_binding(session_id, user_id, settings=_settings()),
        },
    )


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _FakeSession:
    """`get(LearningObjective, id)` + execute 큐(처치 select → 중복 select 순) + add/commit.

    실행된 statement를 `statements`에 남긴다 — 목표 교차(⑤) 테스트가 "처치 select가 경로의
    objective_id로 필터한다"를 statement 파라미터로 단언하는 데 쓴다(큐 fake는 WHERE를 실행하지
    않으므로 빈 결과 주입만으로는 ①과 구분되지 않는다).
    """

    def __init__(
        self,
        objectives: dict[str, LearningObjective],
        execute_results: list[list[Any]],
    ) -> None:
        self._objectives = objectives
        self._execute_results = list(execute_results)
        self.statements: list[Any] = []
        self.added: list[Any] = []
        self.committed = False

    async def get(self, _model: Any, pk: str) -> LearningObjective | None:
        return self._objectives.get(pk)

    async def execute(self, stmt: Any) -> _Result:
        self.statements.append(stmt)
        return _Result(self._execute_results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


def _client(fake: _FakeSession) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _student
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _post(fake: _FakeSession, session_id: uuid.UUID) -> Any:
    return _client(fake).post(_PATH, json={"session_id": str(session_id), "correct": True})


class TestOutcomeOwnershipHttp:
    def test_forged_session_id_is_403(self) -> None:
        """① 위조 session_id(처치 select 빈 결과) → 403·행 stage 0."""
        fake = _FakeSession({_OBJECTIVE_ID: _objective()}, [[]])
        resp = _post(fake, uuid.uuid4())
        assert resp.status_code == 403, resp.text
        assert "소유권" in resp.json()["detail"]
        assert fake.added == []

    def test_other_students_session_is_403_with_identical_detail(self) -> None:
        """② 타 학생 바인딩 처치 → 403 + ①과 **문자열 동일** detail(존재 오라클 차단)."""
        sid = uuid.uuid4()
        other_student = uuid.uuid4()
        fake_forged = _FakeSession({_OBJECTIVE_ID: _objective()}, [[]])
        resp_forged = _post(fake_forged, uuid.uuid4())

        fake_stolen = _FakeSession(
            {_OBJECTIVE_ID: _objective()},
            [[_treatment_row(session_id=sid, user_id=other_student)]],
        )
        resp_stolen = _post(fake_stolen, sid)

        assert resp_forged.status_code == 403
        assert resp_stolen.status_code == 403, resp_stolen.text
        # 오라클 차단 — "세션 미존재"와 "타인 세션"이 같은 응답이어야 존재 여부가 새지 않는다.
        assert resp_forged.json()["detail"] == resp_stolen.json()["detail"]
        assert fake_stolen.added == []

    def test_duplicate_outcome_is_409(self) -> None:
        """③ 같은 (objective, session)에 outcome 기존재 → 409·추가 stage 0."""
        sid = uuid.uuid4()
        existing = EvidenceEvent(
            session_id=sid,
            objective_id=_OBJECTIVE_ID,
            k_type="CONCEPT",
            event_type=EVENT_TYPE_OUTCOME,
            correct=True,
        )
        fake = _FakeSession(
            {_OBJECTIVE_ID: _objective()},
            [[_treatment_row(session_id=sid, user_id=_STUDENT_ID)], [existing]],
        )
        resp = _post(fake, sid)
        assert resp.status_code == 409, resp.text
        assert fake.added == []

    def test_legitimate_owner_is_201_and_stages_outcome(self) -> None:
        """④ 정당 소유자 → 201 + {"recorded": true} + outcome 행 stage·commit."""
        sid = uuid.uuid4()
        fake = _FakeSession(
            {_OBJECTIVE_ID: _objective()},
            [[_treatment_row(session_id=sid, user_id=_STUDENT_ID)], []],
        )
        resp = _post(fake, sid)
        assert resp.status_code == 201, resp.text
        assert resp.json() == {"recorded": True}
        assert len(fake.added) == 1
        row = fake.added[0]
        assert row.event_type == EVENT_TYPE_OUTCOME
        assert row.correct is True
        assert row.session_id == sid
        assert fake.committed is True

    def test_cross_objective_treatment_is_403(self) -> None:
        """⑤ objective_id가 다른 처치(목표 교차) → 403.

        실 DB에서는 처치 select의 WHERE(objective_id = 경로값)가 교차 처치를 걸러 빈 결과가
        된다 — 큐 fake는 WHERE를 실행하지 않으므로 빈 결과를 주입하되, 실행된 statement의
        바인드 파라미터에 경로 objective_id·처치 event_type이 실제로 실려 있음을 단언해
        ①과 변별한다(WHERE가 없으면 바인딩 검증을 통과해 기입됐을 시나리오).
        """
        sid = uuid.uuid4()
        # 학생 본인 바인딩의 처치가 *다른* objective에만 있는 상황 — DB WHERE가 걸러 빈 결과.
        fake = _FakeSession({_OBJECTIVE_ID: _objective()}, [[]])
        resp = _post(fake, sid)
        assert resp.status_code == 403, resp.text
        assert fake.added == []
        # 처치 select가 경로 objective로 필터함을 statement에서 단언(목표 교차 차단의 실체).
        values = set(fake.statements[0].compile().params.values())
        assert _OBJECTIVE_ID in values
        assert sid in values
        assert EVENT_TYPE_TREATMENT in values
