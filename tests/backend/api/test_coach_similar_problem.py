"""L4 coach 유사문제 실시간 서빙(MISC-03) — REC-02 L1 좌석 재사용 결선 단위테스트.

`_similar_problem_for`(순수 게이트 + 좌석 위임)와 `create_session`/`append_turns` HTTP 결선을
검증한다. L1 좌석(`fetch_probe_candidates_by_mids`) 자체의 mids 매칭·난이도 필터·미응답 필터·
정렬 로직은 `tests/backend/l1/problem_bank/test_probe_candidates.py`가 이미 봉인 — 여기서는
그 로직을 재검증하지 않는다(중복 0). REC-02 소비처 테스트(`tests/backend/harness/
test_wh1_probe_supply.py`)와 동형으로, HTTP/게이트 결선은 monkeypatch로 좌석을 대체해 *호출
여부·인자·응답 결선*만 보고, 좌석 자체가 실제로 mids 매칭·미응답 필터를 정확히 수행하는지는
별도 "실 좌석 경유" 테스트(`TestSimilarProblemForRealSeat`)에서 얇은 세션 스텁으로 한 번 더
end-to-end 확인한다(REC-02 재구현 없이 그대로 통과시킴을 증명).

핵심 봉인:
- 게이트(reactive retrieval): `intervention=None`이면 DB 무접근(0회 호출)·None 반환 —
  오개념을 초기 context에 preload하지 않는다(CLAUDE.md).
- 게이트 통과: intervention 확정 시 좌석을 `mids=[misconception_id]`(단일 원소)·`user_id`·
  `limit=1`로 호출하고, `rows[0].problem_id`를 UUID로 변환해 반환.
- rows 없음(오개념 미태깅/난이도 부재/전부 응답함 어느 사유든) → None(그레이스풀 — 오류 아님).
- HTTP: `create_session`·`append_turns`(세션 기반)에서만 `similar_problem_id`가 채워지고,
  stateless `/v1/coach`는 항상 None·좌석 자체가 호출되지 않는다(DB 무접근 계약과 정합).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l1.problem_bank.probe_candidates import (
    ProbeCandidateQuery,
    ProbeCandidateRow,
)
from whymath_backend.l4.misconception import InterventionDecision, InterventionPattern
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()

# 완전 substring 매칭(confidence 1.0) — distribution-over-power. select_intervention이
# COUNTEREXAMPLE로 확정(test_coach.py TestMisconceptionIntegration과 동형 신호).
_SUBSTR_FULL = "내 풀이는 (a+b)² = a² + b²로 전개했어"
# substring·의미 매칭 둘 다 안 잡는 중립 발화 — intervention이 None(진단 보류).
_NEUTRAL = "이 문제 어떻게 접근하면 좋을까"
_CONFIRMED_MID = "distribution-over-power"


def _intervention(mid: str = _CONFIRMED_MID) -> InterventionDecision:
    return InterventionDecision(
        pattern=InterventionPattern.COUNTEREXAMPLE, prompt="P", misconception_id=mid
    )


class _ExplodingSession:
    """intervention=None 게이트 검증용 — 어떤 DB 메서드가 호출돼도 즉시 실패(preload 금지 위반)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("intervention=None인데 L1 조회가 발생함(reactive retrieval 위반).")

    async def get(self, model: object, pk: object) -> None:
        raise AssertionError("intervention=None인데 DB 접근이 발생함.")


# ──────────────────────────────────────────────────────────────────────────
# 단위 — `_similar_problem_for` 게이트·좌석 위임(seat monkeypatch — REC-02 소비처 테스트 동형)
# ──────────────────────────────────────────────────────────────────────────
class TestSimilarProblemForGate:
    async def test_none_intervention_no_db_call(self) -> None:
        result = await coach._similar_problem_for(_ExplodingSession(), _UID, None)  # type: ignore[arg-type]
        assert result is None

    async def test_confirmed_intervention_queries_seat_with_single_mid_and_limit_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        pid = uuid.uuid4()

        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            captured["mids"] = mids
            captured["kwargs"] = kwargs
            return ProbeCandidateQuery(
                rows=(ProbeCandidateRow(problem_id=str(pid), difficulty_overall=3.0),),
                tagged_count=1,
                tagged_with_difficulty_count=1,
            )

        monkeypatch.setattr(coach, "fetch_probe_candidates_by_mids", _fake)
        result = await coach._similar_problem_for(object(), _UID, _intervention("mis.x"))
        assert result == pid
        # 단일 원소 mids — REC-02 좌석 자체 매칭 로직을 여기서 재구현하지 않는다.
        assert captured["mids"] == ["mis.x"]
        assert captured["kwargs"]["user_id"] == _UID  # 미응답 필터 threading
        assert captured["kwargs"]["limit"] == 1  # "1건" 자체를 좌석에 위임(별도 슬라이싱 0)

    async def test_empty_rows_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

        monkeypatch.setattr(coach, "fetch_probe_candidates_by_mids", _fake)
        result = await coach._similar_problem_for(object(), _UID, _intervention())
        assert result is None


# ──────────────────────────────────────────────────────────────────────────
# 실 좌석 경유(session.execute 스텁만 대체 — `fetch_probe_candidates_by_mids` 자체는 실물)
# ──────────────────────────────────────────────────────────────────────────
class _SequencedResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalars(self) -> "_SequencedScalars":
        return _SequencedScalars(self._rows)


class _SequencedScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _SequencedSession:
    """`execute` 호출 순서대로 미리 준비된 결과를 반환 — 실 PostgreSQL 없이 L1 좌석의
    두 단계 쿼리(문항 fetch → 미응답 attempted id fetch)를 그대로 통과시킨다."""

    def __init__(self, results: list[list[Any]]) -> None:
        self._results = list(results)
        self.calls = 0

    async def execute(self, stmt: object) -> _SequencedResult:
        rows = self._results[self.calls]
        self.calls += 1
        return _SequencedResult(rows)


def _distractor_map(mid: str) -> list[dict[str, object]]:
    return [{"choice_index": 0, "misconception_id": mid}]


class TestSimilarProblemForRealSeat:
    """`fetch_probe_candidates_by_mids`(REC-02 실물)를 그대로 경유 — 신규 로직 없음을 증명."""

    async def test_returns_tagged_unattempted_problem_with_difficulty(self) -> None:
        pid = uuid.uuid4()
        rows = [(pid, _distractor_map(_CONFIRMED_MID), 3.0, None, None)]
        session = _SequencedSession([rows, []])  # 문항 1건 · 미응답 이력 없음
        result = await coach._similar_problem_for(session, _UID, _intervention())
        assert result == pid

    async def test_excludes_already_attempted_problem(self) -> None:
        pid_attempted = uuid.uuid4()
        pid_unattempted = uuid.uuid4()
        rows = [
            (pid_attempted, _distractor_map(_CONFIRMED_MID), 3.0, None, None),
            (pid_unattempted, _distractor_map(_CONFIRMED_MID), 3.0, None, None),
        ]
        session = _SequencedSession([rows, [pid_attempted]])  # pid_attempted=이미 채점 완료
        result = await coach._similar_problem_for(session, _UID, _intervention())
        assert result == pid_unattempted

    async def test_no_matching_tag_returns_none(self) -> None:
        rows = [(uuid.uuid4(), _distractor_map("mis.other"), 3.0, None, None)]
        session = _SequencedSession([rows, []])
        result = await coach._similar_problem_for(session, _UID, _intervention())
        assert result is None

    async def test_no_difficulty_returns_none(self) -> None:
        rows = [(uuid.uuid4(), _distractor_map(_CONFIRMED_MID), None, None, None)]
        session = _SequencedSession([rows, []])
        result = await coach._similar_problem_for(session, _UID, _intervention())
        assert result is None


# ──────────────────────────────────────────────────────────────────────────
# HTTP 결선 — create_session/append_turns만 채우고 stateless /v1/coach는 항상 None
# ──────────────────────────────────────────────────────────────────────────
def _settings_no_limits() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """stateless `/v1/coach`용 — execute 호출 시 AssertionError(DB 무접근 계약)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_Scalars":
        return _Scalars(self._rows)

    def scalar_one(self) -> Any:
        return 0.0

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _CapturingSession:
    """`/v1/coach/sessions`(+turns)용 — add/add_all/commit/refresh/get/execute 캡처
    (`tests/backend/api/test_coach.py::_CapturingSession`과 동형 — 독립 파일 격리 목적으로 복제,
    `test_coach_visualization.py`가 자체 `_FakeSession`을 복제하는 것과 같은 관례)."""

    def __init__(
        self,
        preload: dict[Any, Any] | None = None,
        execute_rows: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self._preload = preload or {}
        self._execute_rows = list(execute_rows or [])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self._execute_rows)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    asyncio.run(reset_store())


def _stateless_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _session_client(
    preload: dict[Any, Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits
    captured = _CapturingSession(preload=preload)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


def _seat_stub(monkeypatch: pytest.MonkeyPatch, pid: uuid.UUID) -> list[list[str]]:
    """`coach.fetch_probe_candidates_by_mids`를 대체 — mids 인자를 매 호출 기록하고,
    `_CONFIRMED_MID`가 포함되면 pid 1건, 아니면 빈 결과(L1 자체 로직 재검증은 상단 클래스가
    이미 수행 — 여기선 HTTP 결선만 본다)."""
    calls: list[list[str]] = []

    async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
        calls.append(list(mids))
        if _CONFIRMED_MID in mids:
            return ProbeCandidateQuery(
                rows=(ProbeCandidateRow(problem_id=str(pid), difficulty_overall=3.0),),
                tagged_count=1,
                tagged_with_difficulty_count=1,
            )
        return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

    monkeypatch.setattr(coach, "fetch_probe_candidates_by_mids", _fake)
    return calls


class TestSessionCreateHttpWiring:
    def test_confirmed_intervention_surfaces_similar_problem_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid = uuid.uuid4()
        calls = _seat_stub(monkeypatch, pid)
        client, _ = _session_client()
        resp = client.post("/v1/coach/sessions", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["intervention"] is not None
        assert body["similar_problem_id"] == str(pid)
        assert len(calls) == 1  # 게이트 통과 시 정확히 1회 호출(preload 아님·이번 턴 반응적)

    def test_pending_diagnosis_omits_similar_problem_id_and_skips_seat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _seat_stub(monkeypatch, uuid.uuid4())
        client, _ = _session_client()
        resp = client.post("/v1/coach/sessions", json={"student_input": _NEUTRAL})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["intervention"] is None
        assert body["similar_problem_id"] is None
        assert calls == []  # reactive retrieval — 진단 보류면 좌석 호출 0


class TestTurnAppendHttpWiring:
    def _preloaded_dialogue(self, dialogue_id: uuid.UUID, owner: uuid.UUID) -> Any:
        from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
        from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

        return (DialogueORM, dialogue_id), DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=dialogue_id,
                user_id=owner,
                total_turns=2,
                student_turns=1,
                assistant_turns=1,
            )
        )

    def test_confirmed_intervention_surfaces_similar_problem_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid = uuid.uuid4()
        calls = _seat_stub(monkeypatch, pid)
        did = uuid.uuid4()
        key, dialogue = self._preloaded_dialogue(did, _UID)
        client, _ = _session_client(preload={key: dialogue})
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": _SUBSTR_FULL},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["intervention"] is not None
        assert body["similar_problem_id"] == str(pid)
        assert len(calls) == 1

    def test_pending_diagnosis_omits_similar_problem_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _seat_stub(monkeypatch, uuid.uuid4())
        did = uuid.uuid4()
        key, dialogue = self._preloaded_dialogue(did, _UID)
        client, _ = _session_client(preload={key: dialogue})
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": _NEUTRAL},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["intervention"] is None
        assert body["similar_problem_id"] is None
        assert calls == []


class TestStatelessCoachNeverPopulates:
    """stateless `/v1/coach` — DB 무접근 계약이라 좌석 자체가 호출되지 않는다."""

    def test_confirmed_diagnosis_field_stays_none_and_seat_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            raise AssertionError("stateless /v1/coach가 L1 좌석을 호출함(DB 무접근 계약 위반).")

        monkeypatch.setattr(coach, "fetch_probe_candidates_by_mids", _boom)
        resp = _stateless_client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["intervention"] is not None  # 진단 자체는 stateless에서도 확정된다
        assert body["similar_problem_id"] is None  # 그러나 서빙은 세션 엔드포인트 전용

    def test_neutral_input_field_stays_none(self) -> None:
        resp = _stateless_client().post("/v1/coach", json={"student_input": _NEUTRAL})
        assert resp.status_code == 200, resp.text
        assert resp.json()["similar_problem_id"] is None
