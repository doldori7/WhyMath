"""S3-27(원 S3-10) 완료를 풀이 제출에 통합 — 완료 상태머신·정답 도달 감지·돌아보기 결선(hermetic).

**철학(Kiki 교수학 지적)**: 완료를 *오직 풀이 제출을 통해서*만 일어나게 한다. 풀이 마지막 단계가
기대정답이면 서버가 감지하고, *바로 넘기지 않고* Polya 돌아보기(메타인지) 1턴을 거친 뒤 완료→다음
문항으로 간다. 별도 "정답 제출" 버튼(POST /me/attempts 직접 호출)을 대체한다.

검증 범위:
  - 순수 상태머신(`decide_completion`) 4전이 전수.
  - create_session: 정답 첫 도달 → 돌아보기 대기(review_pending)·완료 아님·attempt 미적재.
  - append_turns: 돌아보기 응답 턴 → 완료 확정(problem_complete·ProblemAttempt is_correct=True
    적재).
  - 오답/미검증 last step → 완료 없음·기존 코칭 지속(회귀 불변).
  - 이미 완료(attempt_id 존재) → 재완료 금지(중복 attempt 0).
  - 게이트 off → 완료 기능 완전 inert(기존 동작 비트동일).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import ProblemAttempt as ProblemAttemptORM
from whymath_backend.db.models.dialogue import Dialogue as DialogueORM
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.db.session import get_session
from whymath_backend.l4.completion import CompletionAction, decide_completion
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_SECRET = "test-secret-0123456789abcdef"
_REFLECTION_MARK = "설명해줄래"  # 돌아보기 프롬프트 표식(문구 취지 검증)
_ACK_MARK = "다음 문제로 가보자"  # 완료 인정 발화 표식


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    import asyncio

    asyncio.run(reset_store())


# ──────────────────────────────────────────────────────────────────────────
# 순수 상태머신 — decide_completion 4전이 전수(DB 0·LLM 0)
# ──────────────────────────────────────────────────────────────────────────
class TestDecideCompletionPure:
    def test_enter_review_on_first_correct(self) -> None:
        """돌아보기 전(prior=0)·미완료·정답 도달 → ENTER_REVIEW(대기·완료 아님)."""
        cd = decide_completion(
            prior_review_remaining=0, already_completed=False, final_answer_correct=True
        )
        assert cd.action is CompletionAction.ENTER_REVIEW
        assert cd.problem_complete is False
        assert cd.awaiting_reflection is True
        assert cd.review_turns_remaining_after == 1  # 기본 1턴
        assert cd.prompt is not None and _REFLECTION_MARK in cd.prompt
        assert cd.socratic_category == "meta"

    def test_complete_on_reflection_response(self) -> None:
        """돌아보기 중(prior=1)·미완료 → COMPLETE(완료·인정 발화). 이 턴 풀이 내용 무관."""
        cd = decide_completion(
            prior_review_remaining=1, already_completed=False, final_answer_correct=False
        )
        assert cd.action is CompletionAction.COMPLETE
        assert cd.problem_complete is True
        assert cd.awaiting_reflection is False
        assert cd.review_turns_remaining_after == 0
        assert cd.prompt is not None and _ACK_MARK in cd.prompt

    def test_continue_review_when_two_turns(self) -> None:
        """2턴 확장 — prior=2면 아직 남음(CONTINUE_REVIEW·완료 아님)."""
        cd = decide_completion(
            prior_review_remaining=2, already_completed=False, final_answer_correct=False
        )
        assert cd.action is CompletionAction.CONTINUE_REVIEW
        assert cd.problem_complete is False
        assert cd.awaiting_reflection is True
        assert cd.review_turns_remaining_after == 1

    def test_two_turn_reflection_configurable(self) -> None:
        """reflection_turns=2로 첫 도달 시 2턴이 심어진다(확장성)."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=False,
            final_answer_correct=True,
            reflection_turns=2,
        )
        assert cd.review_turns_remaining_after == 2
        assert cd.action is CompletionAction.ENTER_REVIEW

    def test_none_on_incorrect(self) -> None:
        """오답(정답 미도달)·돌아보기 전 → NONE(완료 무관·발화 override 없음)."""
        cd = decide_completion(
            prior_review_remaining=0, already_completed=False, final_answer_correct=False
        )
        assert cd.action is CompletionAction.NONE
        assert cd.problem_complete is False
        assert cd.awaiting_reflection is False
        assert cd.prompt is None

    def test_none_when_already_completed(self) -> None:
        """이미 완료된 세션 → 정답 재도달이어도 NONE(재완료·중복 attempt 금지)."""
        cd = decide_completion(
            prior_review_remaining=0, already_completed=True, final_answer_correct=True
        )
        assert cd.action is CompletionAction.NONE
        assert cd.problem_complete is False


# ──────────────────────────────────────────────────────────────────────────
# hermetic 엔드포인트 하네스 — test_coach.py `_CapturingSession` 패턴과 동형(로컬 자체 정의).
# ──────────────────────────────────────────────────────────────────────────
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
        return 0.0  # curate_hypothesis net_support 집계(증거 없음)


class _CapturingSession:
    """add/add_all/commit/refresh/get/execute 캡처 — test_coach.py 패턴 답습."""

    def __init__(self, preload: dict[Any, Any] | None = None) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self._preload = preload or {}

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
        return _Result([])


def _settings() -> Settings:
    # 레이트리밋 비활성(주입 소비처 전용). 완료 게이트(`l4_solution_completion_enabled`)는 코치
    # 헬퍼가 *모듈* get_settings()를 직접 읽으므로 주입으로 못 끈다 — 게이트 off 테스트는 env+
    # cache_clear로 끈다(step_shadow 테스트와 동형). 기본 env는 완료 게이트 ON(기본값 True).
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
    )


def _client(
    preload: dict[Any, Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = lambda: UserProfileSchema(
        user_id=_UID, persona_primary=Persona.A_일반고고3
    )
    app.dependency_overrides[get_settings] = lambda: _settings()
    captured = _CapturingSession(preload=preload)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


def _preloaded_dialogue(
    dialogue_id: uuid.UUID,
    problem_id: uuid.UUID | None,
    *,
    total_turns: int = 2,
    review_turns_remaining: int | None = None,
    attempt_id: uuid.UUID | None = None,
) -> DialogueORM:
    return DialogueORM.from_schema(
        DialogueSchema(
            dialogue_id=dialogue_id,
            user_id=_UID,
            problem_id=problem_id,
            attempt_id=attempt_id,
            total_turns=total_turns,
            student_turns=1,
            assistant_turns=1,
            review_turns_remaining=review_turns_remaining,
        )
    )


# 정답 도달 감지용 문항(answer="3") — 마지막 단계 "x = 3"이면 correct.
def _problem(answer: str | None = "3") -> SimpleNamespace:
    return SimpleNamespace(answer=answer, choices=None, question_format=None, multiple_answers=None)


# ──────────────────────────────────────────────────────────────────────────
# ① create_session: 정답 첫 도달 → 돌아보기 대기(완료 아님·attempt 미적재)
# ──────────────────────────────────────────────────────────────────────────
class TestCreateSessionEntersReview:
    def test_correct_final_step_enters_review_not_complete(self) -> None:
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "다 풀었어요",
                "problem_id": str(pid),
                "solution_steps": ["2*x = 6", "x = 3"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 완료 아님 — 돌아보기 대기(review_pending).
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is True
        assert body["completed_attempt_id"] is None
        # 발화는 결정론 메타인지 프롬프트(왜/어떻게 설명 요청).
        assert _REFLECTION_MARK in body["decision"]["prompt"]
        assert body["decision"]["socratic_category"] == "meta"
        # ProblemAttempt는 아직 적재되지 않음(완료 전).
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        # dialogue에 돌아보기 대기 상태(1턴)가 심어짐.
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 1
        assert dialogue.attempt_id is None

    def test_incorrect_final_step_no_review(self) -> None:
        """오답 마지막 단계 → 돌아보기 없음·완료 없음·기존 코칭 그대로(회귀 불변)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "이렇게 풀었어요",
                "problem_id": str(pid),
                "solution_steps": ["2*x = 6", "x = 4"],  # 마지막 x=4 ≠ 3
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert _REFLECTION_MARK not in body["decision"]["prompt"]
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0

    def test_no_solution_steps_no_review(self) -> None:
        """solution_steps 미제공(대화만) → 감지 없음·기존 동작(회귀 불변)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "모르겠어요", "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["awaiting_reflection"] is False
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0

    def test_gate_off_inert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """게이트 off → 정답 도달이어도 완료 기능 완전 inert(감지·돌아보기 0·완전 되돌리기).

        게이트는 코치 헬퍼가 모듈 `get_settings()`를 직접 읽으므로 env+cache_clear로 끈다
        (step_shadow 테스트 동형). off면 정답이어도 no-op — 기존 동작 비트동일.
        """
        monkeypatch.setenv("WHYMATH_L4_SOLUTION_COMPLETION_ENABLED", "false")
        get_settings.cache_clear()
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        try:
            resp = client.post(
                "/v1/coach/sessions",
                json={
                    "student_input": "다 풀었어요",
                    "problem_id": str(pid),
                    "solution_steps": ["2*x = 6", "x = 3"],
                },
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["problem_complete"] is False
            assert body["awaiting_reflection"] is False
            assert _REFLECTION_MARK not in body["decision"]["prompt"]
            dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
            assert dialogue.review_turns_remaining == 0
        finally:
            get_settings.cache_clear()


# ──────────────────────────────────────────────────────────────────────────
# ② append_turns: 돌아보기 응답 턴 → 완료 확정(ProblemAttempt 적재)
# ──────────────────────────────────────────────────────────────────────────
class TestAppendTurnsCompletes:
    def test_reflection_response_completes_and_records_attempt(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=4, review_turns_remaining=1)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "양변을 2로 나눠서 x=3이 나왔어요"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 완료 확정.
        assert body["problem_complete"] is True
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is not None
        assert _ACK_MARK in body["decision"]["prompt"]
        # ProblemAttempt(is_correct=True) 적재 — submit_attempt 헬퍼 재사용 경로.
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1
        assert attempts[0].is_correct is True
        assert attempts[0].problem_id == pid
        assert attempts[0].user_id == _UID
        assert str(attempts[0].attempt_id) == body["completed_attempt_id"]
        # dialogue에 완료 링크·돌아보기 상태 해제.
        assert dialogue.attempt_id == attempts[0].attempt_id
        assert dialogue.review_turns_remaining == 0

    def test_already_completed_no_double_attempt(self) -> None:
        """이미 완료(attempt_id 존재)된 세션에 정답 재제출 → 재완료·중복 attempt 금지."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        existing_attempt = uuid.uuid4()
        dialogue = _preloaded_dialogue(
            did, pid, total_turns=6, review_turns_remaining=0, attempt_id=existing_attempt
        )
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "또 풀었어요", "solution_steps": ["2*x = 6", "x = 3"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.attempt_id == existing_attempt  # 기존 링크 유지

    def test_first_correct_on_append_enters_review(self) -> None:
        """append에서 정답 첫 도달(prior=0) → 돌아보기 대기·완료 아님·attempt 미적재."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=2, review_turns_remaining=0)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "풀이 제출", "solution_steps": ["2*x = 6", "x = 3"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is True
        assert _REFLECTION_MARK in body["decision"]["prompt"]
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.review_turns_remaining == 1


# ──────────────────────────────────────────────────────────────────────────
# ③ 미검증(unverifiable) — 기대정답 미보유 → 완료 없음(정직·correct 위장 금지)
# ──────────────────────────────────────────────────────────────────────────
class TestAppendTurnsUnverifiable:
    def test_no_expected_answer_no_completion(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=2, review_turns_remaining=0)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem(None)}
        )
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "풀이", "solution_steps": ["2*x = 6", "x = 3"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.review_turns_remaining == 0

    def test_problem_missing_no_completion(self) -> None:
        """문항 미존재(코퍼스 미적재) → graceful·완료 없음."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=2, review_turns_remaining=0)
        client, captured = _client(preload={(DialogueORM, did): dialogue})  # Problem 미preload
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "풀이", "solution_steps": ["2*x = 6", "x = 3"]},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["problem_complete"] is False
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)


# ──────────────────────────────────────────────────────────────────────────
# ④ 기대정답 비노출 — 완료 경로 어디에도 Problem.answer가 응답에 새지 않음
# ──────────────────────────────────────────────────────────────────────────
class TestAnswerNotLeaked:
    def test_detection_never_leaks_expected_answer(self) -> None:
        """감지 턴(create_session)에서 기대정답 표현(학생이 타이핑하지 않은 형태)이 응답에 안 샌다.

        문항 기대정답="6/2"(학생은 "x = 3"으로 제출·서로 다른 표현이나 값 동치→correct). 서버가
        정답 도달을 감지해 돌아보기로 진입하되, **기대정답 원문("6/2")은 응답 어디에도 노출되지
        않는다**(verify_final_answer 비노출 계약·CLAUDE.md 정답 누출 차단).
        """
        import json

        pid = uuid.uuid4()
        client, _ = _client(preload={(ProblemORM, pid): _problem("6/2")})
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "다 풀었어요",
                "problem_id": str(pid),
                "solution_steps": ["2*x = 6", "x = 3"],  # 값 동치("6/2"=3)나 표현은 다름
            },
        )
        assert resp.status_code == 201, resp.text
        # 정답 도달은 감지됨(돌아보기 진입) — 그러나 기대정답 표현은 응답에 부재.
        assert resp.json()["awaiting_reflection"] is True
        assert "6/2" not in resp.text
        assert "6/2" not in json.dumps(resp.json())
