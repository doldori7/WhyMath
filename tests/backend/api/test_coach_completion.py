"""S3-32 learning-loop-closure — coach.py 완료 판정 결선 테스트.

순수 조합 로직(`l3.verify_final_answer`·`l4.completion`)은 각각의 유닛테스트
(`tests/backend/l3/test_verify_final_answer.py`·`tests/backend/l4/test_completion.py`)가 이미
전수 검증했다. 여기서는 *결선*만 본다:
  - `_apply_completion`의 멱등 가드(이미 완료된 대화는 재판정·중복 적재 없음)
  - `completed=True` 시 `ProblemAttempt` 신규 적재 + `dialogue.attempt_id`/
    `server_verified_completed_at` 갱신
  - `CoachResponse.dialogue_completed`가 True/False/None 세 값 모두 실제 HTTP 응답에 실리는지
  - incorrect일 때 `decision.prompt`가 재고 유도 문구로 교체되고 `decision.system`은 불변인지

`_CapturingSession`/`_session_client` 등은 `tests/backend/api/test_coach.py`의 관례를 그대로
따른 로컬 사본이다(이 코드베이스의 기존 패턴 — 파일마다 독립 사본을 둔다,
`test_coach_pack_wiring.py`·`test_coach_grade_standard_code.py` 등 선례).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import ProblemAttempt as ProblemAttemptORM
from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l4.completion import RECONSIDER_PROMPT
from whymath_backend.l4.models import PedagogyDecision, PolyaStage, PolyaState
from whymath_backend.l4.polya.prompts import STAGE_PROMPTS
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    asyncio.run(reset_store())


def _settings_override() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
        coach_device_hmac_secret=SecretStr(""),
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


# ── 결선(API) 테스트용 캡처 세션 — test_coach.py `_CapturingSession`과 동형(로컬 사본) ──────
class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)

    def scalar_one(self) -> Any:
        return 0.0

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


class _CapturingSession:
    def __init__(
        self, preload: dict[Any, Any] | None = None, execute_rows: list[Any] | None = None
    ) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = 0
        self._preload = preload or {}
        self._execute_rows = list(execute_rows or [])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, obj: Any) -> None:
        self.refreshes += 1

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self._execute_rows)


def _session_client(
    preload: dict[Any, Any] | None = None,
    execute_rows: list[Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_override
    captured = _CapturingSession(preload=preload, execute_rows=execute_rows)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


# ── 헬퍼 유닛(_apply_completion 등) 직접 호출용 최소 가짜 세션 ─────────────────────────────
class _HelperFakeSession:
    """`_apply_completion`이 쓰는 두 연산만 시뮬 — `get`(Problem 조회)·`add`(attempt 적재)."""

    def __init__(self, preload: dict[Any, Any] | None = None) -> None:
        self.added: list[Any] = []
        self._preload = preload or {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def get(self, model: Any, pk: Any) -> Any | None:
        return self._preload.get((model, pk))


def _decision(stage: PolyaStage = PolyaStage.REVIEW) -> PedagogyDecision:
    sp = STAGE_PROMPTS[stage]
    return PedagogyDecision(polya_stage_to_advance="stay", prompt=sp.prompt, system=sp.system)


class _ExplodingSession:
    """`.get`/`.add` 호출 시 즉시 실패 — 멱등 가드가 DB에 *전혀* 손대지 않음을 증명."""

    async def get(self, model: Any, pk: Any) -> Any:
        raise AssertionError("이미 완료된 대화는 정답을 재조회하면 안 된다.")

    def add(self, obj: Any) -> None:
        raise AssertionError("이미 완료된 대화는 ProblemAttempt를 재적재하면 안 된다.")


class TestApplyCompletionHelper:
    """`coach._apply_completion` 직접 호출 — 결선 유닛(HTTP 계층 없이)."""

    def test_correct_at_review_persists_attempt_and_links_dialogue(self) -> None:
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        dialogue = DialogueORM.from_schema(DialogueSchema(user_id=uid, problem_id=pid))
        sess = _HelperFakeSession(preload={(ProblemORM, pid): SimpleNamespace(answer="x=2")})

        decision, completed = asyncio.run(
            coach._apply_completion(
                sess,  # type: ignore[arg-type]
                dialogue=dialogue,
                decision=_decision(PolyaStage.REVIEW),
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="x=2",
                user_id=uid,
                now=now,
            )
        )

        assert completed is True
        assert dialogue.attempt_id is not None
        assert dialogue.server_verified_completed_at == now
        assert len(sess.added) == 1
        attempt = sess.added[0]
        assert isinstance(attempt, ProblemAttemptORM)
        assert attempt.attempt_id == dialogue.attempt_id
        assert attempt.is_correct is True
        assert attempt.user_id == uid
        assert attempt.problem_id == pid
        assert attempt.student_answer == "x=2"
        assert attempt.used_socratic is True
        # decision.prompt는 correct 경로에서 건드리지 않는다(재고 유도는 incorrect 전용).
        assert decision.prompt == _decision(PolyaStage.REVIEW).prompt

    def test_correct_before_review_does_not_complete_or_persist(self) -> None:
        # REVIEW 미도달(EXECUTE) — correct여도 완료 아님·ProblemAttempt 미적재("정답을 빠르게" 금지).
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        dialogue = DialogueORM.from_schema(DialogueSchema(user_id=uid, problem_id=pid))
        sess = _HelperFakeSession(preload={(ProblemORM, pid): SimpleNamespace(answer="x=2")})

        _, completed = asyncio.run(
            coach._apply_completion(
                sess,  # type: ignore[arg-type]
                dialogue=dialogue,
                decision=_decision(PolyaStage.EXECUTE),
                state=PolyaState(current_stage=PolyaStage.EXECUTE),
                solution_text="x=2",
                user_id=uid,
                now=datetime.now(timezone.utc),
            )
        )

        assert completed is False
        assert dialogue.attempt_id is None
        assert dialogue.server_verified_completed_at is None
        assert sess.added == []

    def test_incorrect_replaces_prompt_only_not_system(self) -> None:
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        dialogue = DialogueORM.from_schema(DialogueSchema(user_id=uid, problem_id=pid))
        sess = _HelperFakeSession(preload={(ProblemORM, pid): SimpleNamespace(answer="x=2")})
        original = _decision(PolyaStage.REVIEW)

        decision, completed = asyncio.run(
            coach._apply_completion(
                sess,  # type: ignore[arg-type]
                dialogue=dialogue,
                decision=original,
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="x=3",  # 기대정답 x=2와 불일치
                user_id=uid,
                now=datetime.now(timezone.utc),
            )
        )

        assert completed is False
        assert decision.prompt == RECONSIDER_PROMPT
        assert decision.system == original.system  # 톤·원칙 프롬프트는 불변
        assert sess.added == []
        assert dialogue.server_verified_completed_at is None

    def test_no_solution_text_no_context_dormant(self) -> None:
        # 학생 풀이 텍스트가 없으면 DB 왕복 없이 dormant(정직 중립 — completed=False).
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        dialogue = DialogueORM.from_schema(DialogueSchema(user_id=uid, problem_id=pid))
        sess = _ExplodingSession()  # 정답 조회를 시도하면 즉시 실패

        decision, completed = asyncio.run(
            coach._apply_completion(
                sess,  # type: ignore[arg-type]
                dialogue=dialogue,
                decision=_decision(PolyaStage.REVIEW),
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="   ",
                user_id=uid,
                now=datetime.now(timezone.utc),
            )
        )
        # 컨텍스트 없음(빈 풀이) → None(정직 중립) — False(평가는 했으나 미완료)와 구분된다.
        assert completed is None
        assert decision.prompt == _decision(PolyaStage.REVIEW).prompt

    def test_idempotent_guard_skips_reverification_and_reinsertion(self) -> None:
        """이미 완료된 대화(`server_verified_completed_at` 채워짐) — 재판정·재적재 없이 True."""
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        already = datetime.now(timezone.utc)
        dialogue = DialogueORM.from_schema(
            DialogueSchema(user_id=uid, problem_id=pid, server_verified_completed_at=already)
        )
        sess = _ExplodingSession()  # DB에 손대면 즉시 실패 — 재판정이 없음을 증명
        original = _decision(PolyaStage.REVIEW)

        decision, completed = asyncio.run(
            coach._apply_completion(
                sess,  # type: ignore[arg-type]
                dialogue=dialogue,
                decision=original,
                # 오답 텍스트를 줘도(state도 EXECUTE로 후퇴해도) 가드가 먼저 반환해야 한다.
                state=PolyaState(current_stage=PolyaStage.EXECUTE),
                solution_text="완전히 틀린 답",
                user_id=uid,
                now=datetime.now(timezone.utc),
            )
        )

        assert completed is True
        assert decision.prompt == original.prompt  # 재고 유도로 바뀌지 않음(가드가 먼저 반환)
        assert dialogue.server_verified_completed_at == already  # 갱신되지 않음(그대로)


class TestDecideCompletionForHelper:
    """`coach._decide_completion_for` — DB 왕복 게이팅(빈 풀이·문항 미보유는 조회 스킵)."""

    def test_empty_solution_text_skips_db(self) -> None:
        sess = _ExplodingSession()
        decision = asyncio.run(
            coach._decide_completion_for(
                sess,  # type: ignore[arg-type]
                problem_id=uuid.uuid4(),
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="",
            )
        )
        assert decision.completed is False
        assert decision.verify_state is None

    def test_no_problem_id_skips_db(self) -> None:
        sess = _ExplodingSession()
        decision = asyncio.run(
            coach._decide_completion_for(
                sess,  # type: ignore[arg-type]
                problem_id=None,
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="x=2",
            )
        )
        assert decision.completed is False
        assert decision.verify_state is None

    def test_problem_not_found_yields_none_context(self) -> None:
        sess = _HelperFakeSession(preload={})
        decision = asyncio.run(
            coach._decide_completion_for(
                sess,  # type: ignore[arg-type]
                problem_id=uuid.uuid4(),
                state=PolyaState(current_stage=PolyaStage.REVIEW),
                solution_text="x=2",
            )
        )
        assert decision.completed is False
        assert decision.verify_state is None


class TestFinalAnswerForVerificationHelper:
    def test_none_problem_id_returns_none(self) -> None:
        sess = _HelperFakeSession()
        result = asyncio.run(coach._final_answer_for_verification(sess, None))  # type: ignore[arg-type]
        assert result is None

    def test_found_problem_returns_answer(self) -> None:
        pid = uuid.uuid4()
        sess = _HelperFakeSession(preload={(ProblemORM, pid): SimpleNamespace(answer="x=2")})
        result = asyncio.run(
            coach._final_answer_for_verification(sess, pid)  # type: ignore[arg-type]
        )
        assert result == "x=2"


class TestSessionCreateDialogueCompleted:
    """`POST /v1/coach/sessions` — `dialogue_completed` 3값 노출(API 레벨)."""

    def test_completed_true_when_review_stage_and_correct(self) -> None:
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): SimpleNamespace(answer="x=2")}
        client, captured = _session_client(preload=preload)

        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "검산해봤는데 x=2가 맞는 것 같아요",
                "student_solution": "x=2",
                "problem_id": str(pid),
                "polya_state": {"current_stage": "review", "turn_count": 0},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is True

        # 서버검증 ProblemAttempt가 실제로 세션에 add됐는지(중복 적재 축 확인).
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1
        assert attempts[0].is_correct is True
        assert attempts[0].problem_id == pid

        dialogues = [o for o in captured.added if isinstance(o, DialogueORM)]
        assert len(dialogues) == 1
        assert dialogues[0].attempt_id == attempts[0].attempt_id
        assert dialogues[0].server_verified_completed_at is not None

    def test_completed_false_when_incorrect(self) -> None:
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): SimpleNamespace(answer="x=2")}
        client, captured = _session_client(preload=preload)

        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "다시 봤는데",
                "student_solution": "x=3",
                "problem_id": str(pid),
                "polya_state": {"current_stage": "review", "turn_count": 0},
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["dialogue_completed"] is False
        # incorrect 재고 유도 — 정답을 노출하지 않고 decision.prompt가 교체된다.
        assert body["decision"]["prompt"] == RECONSIDER_PROMPT
        assert body["decision"]["system"] == STAGE_PROMPTS[PolyaStage.REVIEW].system
        assert "2" not in body["decision"]["prompt"]  # 정답 값(2) 비노출
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []

    def test_completed_none_without_problem_context(self) -> None:
        # problem_id 미제공 — 완료 판정 컨텍스트 없음(정직 중립).
        client, captured = _session_client()
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "음",
                "student_solution": "x=2",
                "polya_state": {"current_stage": "review", "turn_count": 0},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is None
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []

    def test_completed_none_when_correct_but_before_execute(self) -> None:
        # "정답을 빠르게" 금지 — 기본 진입 단계(UNDERSTAND)는 검증 시도 자체를 하지 않는다
        # (`_FINAL_ANSWER_ELIGIBLE_STAGES` — 잡담을 최종답으로 오인해 검증하지 않음). 컨텍스트
        # 미시도이므로 None(정직 중립) — "평가는 했으나 미완료"(False)와 구분된다.
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): SimpleNamespace(answer="x=2")}
        client, captured = _session_client(preload=preload)

        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "x=2",
                "student_solution": "x=2",
                "problem_id": str(pid),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is None
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []

    def test_completed_false_when_correct_at_execute_but_not_review(self) -> None:
        # EXECUTE는 검증 대상 단계지만(재고 유도를 태울 수 있어야 하므로), REVIEW 게이트를
        # 아직 통과하지 못했으므로 completed는 여전히 False다("정답을 빠르게" 금지 핵심 규약).
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): SimpleNamespace(answer="x=2")}
        client, captured = _session_client(preload=preload)

        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "따라서 x=2",
                "student_solution": "x=2",
                "problem_id": str(pid),
                "polya_state": {"current_stage": "execute", "turn_count": 0},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is False
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []


class TestTurnAppendDialogueCompleted:
    """`POST /v1/coach/sessions/{id}/turns` — 멀티턴 경로의 완료 판정·멱등 가드(API 레벨).

    `append_turns`는 클라 제출 `polya_state`가 아니라 *서버 파생* 상태(`derive_polya_state`,
    PED-04 D2)를 완료 판정에 쓴다 — 그래서 여기서는 `derive_polya_state`를 monkeypatch해
    "이미 REVIEW 단계 프롬프트를 받은 뒤"를 시뮬한다(기존 `test_coach.py`의
    `monkeypatch.setattr(coach, ...)` 좌석 관례와 동형 — 새 모킹 인프라 발명 아님). 이 monkeypatch
    자체가 "서버가 상태를 소유한다"는 계약을 건드리지 않는다 — 이 클래스는 완료 판정 결선만 본다.
    """

    def _preloaded_dialogue(
        self,
        did: uuid.UUID,
        pid: uuid.UUID,
        *,
        server_verified_completed_at: datetime | None = None,
    ) -> DialogueORM:
        return DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                problem_id=pid,
                total_turns=2,
                student_turns=1,
                assistant_turns=1,
                server_verified_completed_at=server_verified_completed_at,
            )
        )

    def test_completed_true_on_review_stage_turn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            coach,
            "derive_polya_state",
            lambda *_a, **_k: PolyaState(current_stage=PolyaStage.REVIEW, turn_count=1),
        )
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._preloaded_dialogue(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): SimpleNamespace(answer="x=2"),
        }
        client, captured = _session_client(preload=preload)

        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={
                "student_input": "검산 다 했어요, x=2 맞아요",
                "student_solution": "x=2",
                "polya_state": {"current_stage": "review", "turn_count": 1},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is True
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1
        assert dialogue.server_verified_completed_at is not None
        assert dialogue.attempt_id == attempts[0].attempt_id

    def test_completed_false_when_server_state_not_yet_review(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """서버 파생 상태가 아직 EXECUTE면 — 클라가 REVIEW를 자칭해도(D2 참고값) 완료 아님."""
        monkeypatch.setattr(
            coach,
            "derive_polya_state",
            lambda *_a, **_k: PolyaState(current_stage=PolyaStage.EXECUTE, turn_count=1),
        )
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._preloaded_dialogue(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): SimpleNamespace(answer="x=2"),
        }
        client, captured = _session_client(preload=preload)

        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={
                "student_input": "x=2",
                "student_solution": "x=2",
                # 클라는 review를 자칭하지만 서버 파생값(EXECUTE)이 우선한다(PED-04 D2).
                "polya_state": {"current_stage": "review", "turn_count": 1},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is False
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []

    def test_idempotent_guard_no_duplicate_attempt_on_repeat_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """이미 완료된 dialogue(REVIEW self-loop 재방문) — ProblemAttempt 중복 적재 없음."""
        monkeypatch.setattr(
            coach,
            "derive_polya_state",
            lambda *_a, **_k: PolyaState(current_stage=PolyaStage.REVIEW, turn_count=2),
        )
        did = uuid.uuid4()
        pid = uuid.uuid4()
        already = datetime.now(timezone.utc)
        dialogue = self._preloaded_dialogue(did, pid, server_verified_completed_at=already)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): SimpleNamespace(answer="x=2"),
        }
        client, captured = _session_client(preload=preload)

        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={
                "student_input": "고마워요! 다른 방법도 있을까요?",
                "student_solution": "x=2",
                "polya_state": {"current_stage": "review", "turn_count": 2},
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dialogue_completed"] is True
        # 멱등 가드 — 이번 턴에 ProblemAttempt가 *새로* 적재되지 않는다.
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert attempts == []
        # 완료 시각도 갱신되지 않는다(최초 완료 시각 그대로).
        assert dialogue.server_verified_completed_at == already
