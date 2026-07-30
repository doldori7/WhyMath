"""S3-27(원 S3-10) 완료를 풀이 제출에 통합 + S3-31(원 S3-15) 오답 재고 유도 — 완료 상태머신·정답/오답
도달 감지·돌아보기 결선(hermetic).

**철학(Kiki 교수학 지적)**: 완료를 *오직 풀이 제출을 통해서*만 일어나게 한다. 풀이 마지막 단계가
기대정답이면 서버가 감지하고, *바로 넘기지 않고* Polya 돌아보기(메타인지) 1턴을 거친 뒤 완료→다음
문항으로 간다. 별도 "정답 제출" 버튼(POST /me/attempts 직접 호출)을 대체한다. 명확한 *오답*이면
(S3-31) 일반 소크라테스 반복 대신 재고 유도 발화로 방향을 준다(Kiki '오답에 같은 답만 하는 건 잘못').

검증 범위:
  - 순수 상태머신(`decide_completion`) 5전이 전수(REDIRECT 포함).
  - create_session: 정답 첫 도달 → 돌아보기 대기(review_pending)·완료 아님·attempt 미적재.
  - append_turns: 돌아보기 응답 턴 → 완료 확정(problem_complete·ProblemAttempt is_correct=True
    적재).
  - 명확한 오답 last step/대화 입력 → REDIRECT(재고 유도 발화·정답 비노출·톤필터 금지패턴 0)·
    완료/attempt/돌아보기 없음.
  - 미검증·사변(unverifiable) → 완료 없음·재고 유도도 없음·기존 코칭 지속(회귀 불변).
  - 이미 완료(attempt_id 존재) → 재완료 금지(중복 attempt 0)·재고 발화도 없음.
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
from whymath_backend.l4.completion import (
    _REDIRECT_PROMPT,
    _REDIRECT_PROMPT_SPECIFIC,
    CompletionAction,
    decide_completion,
)
from whymath_backend.l4.tone_filter import filter_tone
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_SECRET = "test-secret-0123456789abcdef"
_REFLECTION_MARK = "설명해줄래"  # 돌아보기 프롬프트 표식(문구 취지 검증)
_ACK_MARK = "다음 문제로 가보자"  # 완료 인정 발화 표식
# S3-31 재고 유도 발화 상수 2종(일반·구체) — 단일 진실원천으로 import해 exact 비교한다.
_REDIRECT_PROMPTS = (_REDIRECT_PROMPT, _REDIRECT_PROMPT_SPECIFIC)


def _assert_tone_safe(text: str) -> None:
    """톤필터 금지 6패턴(틀렸·못 하·잘못된·실수·바보·포기) 0건 — 재고 발화 정서안전 봉인."""
    _, report = filter_tone(text)
    assert report.violations == [], f"금지 패턴 검출: {report.violations}"


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

    def test_none_on_unverifiable(self) -> None:
        """미검증·사변(correct도 incorrect도 아님)·돌아보기 전 → NONE(완료 무관·발화 override 없음)."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=False,
            final_answer_correct=False,
            final_answer_incorrect=False,
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

    # ── S3-31: REDIRECT 전이(명확한 오답 → 재고 유도) ─────────────────────────────
    def test_redirect_on_incorrect_first_turn(self) -> None:
        """돌아보기 전·미완료·명확한 오답(turn 1) → REDIRECT(일반 재고 발화·완료/attempt 없음)."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=False,
            final_answer_correct=False,
            final_answer_incorrect=True,
        )
        assert cd.action is CompletionAction.REDIRECT
        assert cd.problem_complete is False
        assert cd.awaiting_reflection is False
        assert cd.review_turns_remaining_after == 0
        assert cd.prompt == _REDIRECT_PROMPT  # turn_index 기본 1 → 일반 재고
        assert cd.socratic_category == "meta"
        _assert_tone_safe(cd.prompt)

    def test_redirect_variant_on_later_turn(self) -> None:
        """2회차 이후(turn_index≥2) → 같은 발화 반복 대신 구체 재고 발화로 변주."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=False,
            final_answer_correct=False,
            final_answer_incorrect=True,
            redirect_turn_index=2,
        )
        assert cd.action is CompletionAction.REDIRECT
        assert cd.prompt == _REDIRECT_PROMPT_SPECIFIC
        assert cd.prompt != _REDIRECT_PROMPT  # 변주됨(verbatim 반복 아님)
        _assert_tone_safe(cd.prompt)

    def test_correct_wins_over_incorrect(self) -> None:
        """방어 — correct·incorrect가 동시에 True로 들어와도 correct 우선(ENTER_REVIEW)."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=False,
            final_answer_correct=True,
            final_answer_incorrect=True,
        )
        assert cd.action is CompletionAction.ENTER_REVIEW

    def test_no_redirect_during_review(self) -> None:
        """돌아보기 중(prior>0)엔 오답 신호여도 재검증하지 않고 review 진행(여기선 COMPLETE)."""
        cd = decide_completion(
            prior_review_remaining=1,
            already_completed=False,
            final_answer_correct=False,
            final_answer_incorrect=True,
        )
        assert cd.action is CompletionAction.COMPLETE

    def test_no_redirect_when_already_completed_incorrect(self) -> None:
        """이미 완료된 세션 → 오답 재제출이어도 NONE(재고 발화도 없음·불변)."""
        cd = decide_completion(
            prior_review_remaining=0,
            already_completed=True,
            final_answer_correct=False,
            final_answer_incorrect=True,
        )
        assert cd.action is CompletionAction.NONE
        assert cd.prompt is None


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


# 객관식 문항 — 실기기 실측 (f∘g)(1) 유형(정답 4·합성순서 오개념이면 6 제출). choices 보유 →
# verify_final_answer가 객관식 값 매칭 경로로 판정(다른 선택지 값이면 incorrect).
def _problem_mc(answer: str = "4", choices: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        answer=answer,
        choices=choices if choices is not None else ["2", "4", "6", "8"],
        question_format=None,
        multiple_answers=None,
    )


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

    def test_incorrect_final_step_redirects(self) -> None:
        """S3-31 — 오답 마지막 단계(x=4≠3) → 재고 유도 발화(REDIRECT)·완료/돌아보기/attempt 없음."""
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
        assert body["completed_attempt_id"] is None
        # 돌아보기 프롬프트 아님·재고 유도 발화(일반·turn 1).
        assert _REFLECTION_MARK not in body["decision"]["prompt"]
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT
        assert body["decision"]["socratic_category"] == "meta"
        _assert_tone_safe(body["decision"]["prompt"])
        assert "3" not in body["decision"]["prompt"]  # 기대정답 비노출
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0
        assert dialogue.attempt_id is None

    def test_no_solution_steps_no_review(self) -> None:
        """solution_steps 미제공(대화만·"모르겠어요"=사변) → 감지 없음·기존 동작(회귀 불변·재고 아님)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "모르겠어요", "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["awaiting_reflection"] is False
        assert body["decision"]["prompt"] not in _REDIRECT_PROMPTS  # 사변 → 재고 유도 아님
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
# ⑤ S3-28(원 S3-11): 대화 입력(student_input) 최종답 감지 — 대화 모드에서도 돌아보기→완료
# ──────────────────────────────────────────────────────────────────────────
class TestChatInputAnswerDetection:
    """S3-28(원 S3-11) — 학생이 답을 대화창(student_input)에 타이핑해도 완료 경로가 작동한다
    (서버만·클라 무변경).

    실기기 3차 실증: 학생은 답을 풀이 제출이 아니라 대화창에 자연스럽게 타이핑한다. 감지는
    solution_steps(S3-27) 우선·없거나 감지 실패면 student_input 폴백. 보수성(거짓 완료 0)은
    verify_final_answer의 3상태가 자연 필터 — 짧은 답 형태만 correct·긴 문장/사변은 unverifiable.
    """

    @pytest.mark.parametrize("chat_answer", ["x=3", "3"])
    def test_chat_answer_enters_review_on_create(self, chat_answer: str) -> None:
        """① 대화 입력 "x=3"/"3"(기대정답 3) → 돌아보기 대기(완료 아님·attempt 미적재)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": chat_answer, "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # solution_steps 경로(S3-27)와 동일 — 돌아보기 진입·완료 아님.
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is True
        assert body["completed_attempt_id"] is None
        assert _REFLECTION_MARK in body["decision"]["prompt"]
        assert body["decision"]["socratic_category"] == "meta"
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 1
        assert dialogue.attempt_id is None

    def test_chat_answer_enters_review_on_append(self) -> None:
        """① append_turns에서도 대화 입력 정답 감지 → 돌아보기 대기(생성/추가 양쪽 계약)."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=2, review_turns_remaining=0)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": "x=3"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is True
        assert _REFLECTION_MARK in body["decision"]["prompt"]
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.review_turns_remaining == 1

    def test_reflection_after_chat_detection_completes(self) -> None:
        """② 대화 감지(생성 턴) → 이어 자연어 근거 턴 → 완료 확정·attempt 적재(전체 흐름 E2E)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        # 턴 1 — 대화 입력 "x=3" → 돌아보기 진입.
        resp1 = client.post(
            "/v1/coach/sessions",
            json={"student_input": "x=3", "problem_id": str(pid)},
        )
        assert resp1.status_code == 201, resp1.text
        assert resp1.json()["awaiting_reflection"] is True
        did = uuid.UUID(resp1.json()["dialogue_id"])
        # 생성된 dialogue를 preload에 등록해 append가 조회할 수 있게 한다(hermetic 세션 규약).
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        captured._preload[(DialogueORM, did)] = dialogue
        # 턴 2 — 자연어 근거 응답(돌아보기) → 완료 확정·ProblemAttempt(is_correct=True) 적재.
        resp2 = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "일차방정식이라 양변을 2로 나눠서 x=3이 나왔어요"},
        )
        assert resp2.status_code == 201, resp2.text
        body = resp2.json()
        assert body["problem_complete"] is True
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is not None
        assert _ACK_MARK in body["decision"]["prompt"]
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1
        assert attempts[0].is_correct is True
        assert dialogue.attempt_id == attempts[0].attempt_id
        assert dialogue.review_turns_remaining == 0

    @pytest.mark.parametrize(
        "long_text",
        [
            "인수분해 근 중에 큰거",  # 파싱 불가 사변(실기기 실측 유형)
            "그러니까 x=3이 맞는 것 같아요",  # 정답 값이 문장 속에 있어도 파싱 불가 → 감지 안 됨
            "이차방정식이니까 근의 공식을 쓰면 될 것 같아요",  # 중간 사변
        ],
    )
    def test_long_sentence_not_detected(self, long_text: str) -> None:
        """③ 긴 문장·사변 → unverifiable → 감지 안 됨(거짓 완료 0 — 보수성 봉인)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": long_text, "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert _REFLECTION_MARK not in body["decision"]["prompt"]
        assert body["decision"]["prompt"] not in _REDIRECT_PROMPTS  # 사변 → 재고 유도 아님
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0

    def test_incorrect_chat_answer_redirects(self) -> None:
        """④ S3-31 — 명확한 오답 대화 입력 "x=5" → 재고 유도(REDIRECT)·완료/attempt 없음·정답 비노출."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "x=5", "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is None
        assert _REFLECTION_MARK not in body["decision"]["prompt"]
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT  # 대화만·create → turn 1 일반 재고
        assert body["decision"]["socratic_category"] == "meta"
        _assert_tone_safe(body["decision"]["prompt"])
        assert "3" not in body["decision"]["prompt"]  # 기대정답 비노출
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0

    def test_already_completed_chat_answer_no_recompletion(self) -> None:
        """⑤ 이미 완료된 세션(attempt_id 존재)에 대화 정답 재입력 → 재완료·중복 attempt 금지."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        existing_attempt = uuid.uuid4()
        dialogue = _preloaded_dialogue(
            did, pid, total_turns=6, review_turns_remaining=0, attempt_id=existing_attempt
        )
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": "x=3"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.attempt_id == existing_attempt  # 기존 링크 유지

    def test_steps_detection_failure_falls_back_to_chat(self) -> None:
        """풀이 단계 감지 실패(단계 미검증)여도 대화 입력이 correct면 감지한다(폴백 순서 봉인)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "x=3",
                "problem_id": str(pid),
                "solution_steps": ["2*x = 6", "그래서 답이 나왔어요"],  # 마지막 단계 unverifiable
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["awaiting_reflection"] is True
        assert body["problem_complete"] is False
        assert _REFLECTION_MARK in body["decision"]["prompt"]


# ──────────────────────────────────────────────────────────────────────────
# ⑥ S3-31: 명확한 오답 → 재고 유도(REDIRECT) — 일반 소크라테스 반복 대신 방향 제시
# ──────────────────────────────────────────────────────────────────────────
class TestRedirectOnIncorrect:
    """오답을 인식(verify incorrect)하면 재고 유도 발화로 학생이 오답에 갇히지 않게 방향을 준다.

    실기기 실증(Kiki 지적): (f∘g)(1) 정답 4인데 학생이 6(합성순서 오개념)을 반복 제출해도 코치가
    일반 반복만 했다. 이제 명확한 오답이면 REDIRECT(완료/attempt/돌아보기 없음·정답 비노출·톤필터
    금지 6패턴 0). unverifiable(사변)은 재고 대상 아님(기존 코칭 유지·다른 테스트에서 봉인).
    """

    def test_mc_wrong_choice_redirects(self) -> None:
        """객관식(정답 4·choices) 대화 입력 "6" → REDIRECT(일반 재고·완료/attempt 없음·정답 비노출)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem_mc("4")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "6", "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is None
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT
        assert body["decision"]["socratic_category"] == "meta"
        _assert_tone_safe(body["decision"]["prompt"])
        assert "4" not in body["decision"]["prompt"]  # 기대정답 비노출
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        dialogue = next(o for o in captured.added if isinstance(o, DialogueORM))
        assert dialogue.review_turns_remaining == 0
        assert dialogue.attempt_id is None

    def test_wrong_equation_solution_redirects(self) -> None:
        """주관식 오답 방정식(정답 3·마지막 단계 x=5) → REDIRECT(풀이 제출 경로)."""
        pid = uuid.uuid4()
        client, captured = _client(preload={(ProblemORM, pid): _problem("3")})
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "이렇게 풀었어요",
                "problem_id": str(pid),
                "solution_steps": ["2*x = 10", "x = 5"],  # 마지막 x=5 ≠ 3
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT
        _assert_tone_safe(body["decision"]["prompt"])
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)

    def test_repeated_wrong_answer_varies_utterance(self) -> None:
        """같은 세션 후속 턴(turn_index≥2) 오답 → 같은 재고 발화 반복 대신 구체 발화로 변주."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        # total_turns=2(직전 1교환) → 이 append는 turn_index=2 → 구체 재고.
        dialogue = _preloaded_dialogue(did, pid, total_turns=2, review_turns_remaining=0)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": "x=5"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT_SPECIFIC  # 변주(2회차 구체)
        _assert_tone_safe(body["decision"]["prompt"])
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)

    def test_review_turn_wrong_input_still_completes_not_redirect(self) -> None:
        """돌아보기 중(prior=1) 오답스러운 입력 "x=5" → 재검증 없이 review 완료(REDIRECT 아님)."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = _preloaded_dialogue(did, pid, total_turns=4, review_turns_remaining=1)
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": "x=5"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 돌아보기 응답 턴이라 재검증 없이 완료 확정(오답 신호는 무시) — 재고 유도 아님.
        assert body["problem_complete"] is True
        assert body["decision"]["prompt"] not in _REDIRECT_PROMPTS
        assert _ACK_MARK in body["decision"]["prompt"]
        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1

    def test_already_completed_wrong_answer_no_redirect(self) -> None:
        """이미 완료(attempt_id 존재)된 세션에 오답 재제출 → 불변(재고 발화도 없음·중복 attempt 0)."""
        did = uuid.uuid4()
        pid = uuid.uuid4()
        existing_attempt = uuid.uuid4()
        dialogue = _preloaded_dialogue(
            did, pid, total_turns=6, review_turns_remaining=0, attempt_id=existing_attempt
        )
        client, captured = _client(
            preload={(DialogueORM, did): dialogue, (ProblemORM, pid): _problem("3")}
        )
        resp = client.post(f"/v1/coach/sessions/{did}/turns", json={"student_input": "x=5"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["decision"]["prompt"] not in _REDIRECT_PROMPTS
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        assert dialogue.attempt_id == existing_attempt

    def test_redirect_never_leaks_expected_answer(self) -> None:
        """오답 재고 경로에서도 기대정답(distinctive "17/5")이 응답 어디에도 노출되지 않는다."""
        import json

        pid = uuid.uuid4()
        client, _ = _client(preload={(ProblemORM, pid): _problem("17/5")})
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "x=4", "problem_id": str(pid)},  # 4 ≠ 17/5 → incorrect
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT  # 재고 유도로 진입했음을 확인
        assert "17/5" not in resp.text
        assert "17/5" not in json.dumps(body)

    def test_redirect_prompts_pass_tone_filter(self) -> None:
        """재고 발화 상수 2종 모두 톤필터 금지 6패턴 0(정서안전 봉인·멱등)."""
        for prompt in _REDIRECT_PROMPTS:
            rewritten, report = filter_tone(prompt)
            assert report.violations == []
            assert report.rewritten is False
            assert rewritten == prompt  # 치환 없음(원문 그대로)


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
