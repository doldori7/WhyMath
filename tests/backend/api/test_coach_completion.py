"""완료를 풀이 제출에 통합 — 서버검증 최종답→Polya 돌아보기→attempt 적재→next-problem (S3-32).

`test_coach.py`의 `_CapturingSession`/`_session_client` hermetic 패턴과 동형(로컬 자체 정의 —
`tests/backend/api`는 `__init__.py`가 없는 비패키지 디렉터리라 파일 간 상대 import를 쓰지 않는
기존 관례를 따른다·`test_coach_grade_standard_code.py` 선례).

검증 범위:
  - create_session: 정답 최종답 첫 도달 → ENTER_REVIEW(돌아보기 대기·완료 아님·attempt 미적재).
  - append_turns: 돌아보기 응답 턴(review_turns_remaining>0) → COMPLETE(ProblemAttempt
    is_correct=True 적재·숙달 헬퍼 호출·응답 problem_complete=True).
  - append_turns: 명확한 오답 최종답 → REDIRECT(재고 유도 발화·완료/attempt 없음·정답 비노출).
  - unverifiable(파싱 불가/사변) 최종답 → 완료·재고 둘 다 없음(기존 코칭 그대로·회귀 불변).
  - 이미 완료된 세션(attempt_id 보유) → 재완료 금지(중복 attempt 0).
  - 게이트 off(`WHYMATH_L4_SOLUTION_COMPLETION_ENABLED=false`) → 완료 기능 완전 inert.
  - 기대정답(`Problem.answer`) 원문이 응답 어디에도 노출되지 않는다(sentinel 검사).

`l3/verify_final_answer.py`·`l4/completion.py`의 순수 판정 로직은 각각의 단위테스트가 이미
전수 검증한다 — 여긴 `api/coach.py` *결선*(정답/오답 감지 → attempt 적재 → 응답 필드)만 본다.
"""

from __future__ import annotations

import json
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
from whymath_backend.l4.completion import _REDIRECT_PROMPT, _REDIRECT_PROMPT_SPECIFIC
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_SECRET = "test-secret-0123456789abcdef"

# 정답 sentinel — Problem.answer에만 존재. 응답 어디에도 새면 정답 비노출 계약 위반. 시스템
# 프롬프트 보일러플레이트(번호 매김 등)와 우연히 겹치지 않도록 충분히 특이한 문자열을 쓴다.
_ANSWER_SENTINEL = "77129"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(`test_coach.py` 관례 미러)."""
    import asyncio

    asyncio.run(reset_store())


def _settings() -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
    )


def _user() -> UserProfileSchema:
    return UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)


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
        return 0.0  # curate_hypothesis net_support 집계(증거 없음).

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


class _CapturingSession:
    """`test_coach.py`의 `_CapturingSession`과 동형 — add/add_all/commit/refresh/get/execute 캡처."""

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


def _session_client(
    preload: dict[Any, Any] | None = None,
    execute_rows: list[Any] | None = None,
) -> tuple[TestClient, _CapturingSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings
    captured = _CapturingSession(preload=preload, execute_rows=execute_rows)

    async def _sess() -> AsyncIterator[_CapturingSession]:
        yield captured

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), captured


def _problem(answer: str | None = "3") -> SimpleNamespace:
    """`verify_final_answer`가 읽는 최소 필드만 담은 문항 스텁(구조적 타이핑).

    `domain`/`subunit`은 `verify_final_answer`와 무관하지만, WH-1 웜스타트 힌트 조립
    (`_warmstart_hints_or_empty`)이 같은 문항 로드를 재사용하며 이 필드들을 읽는다 — 없으면
    fail-open으로 경고 로그만 남기고 빈 힌트로 진행하니(무해) 굳이 없어도 테스트는 통과하지만,
    로그 소음을 줄이려 None으로 명시해둔다.
    """
    return SimpleNamespace(
        answer=answer,
        choices=None,
        question_format=None,
        answer_format=None,
        multiple_answers=None,
        domain=None,
        subunit=None,
    )


class TestCreateSessionEntersReview:
    """create_session — 정답 최종답 첫 도달 시 즉시 완료가 아니라 돌아보기 대기로 간다."""

    def test_correct_final_answer_enters_review_not_complete(self) -> None:
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): _problem(answer="3")}
        client, captured = _session_client(preload=preload)
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "이게 답인 것 같아요",
                "problem_id": str(pid),
                "solution_steps": ["2x=6", "x=3"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # 완료가 *아직* 아니다 — Polya 돌아보기를 먼저 거친다(정답 빠르게 KPI 금지).
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is True
        assert body["completed_attempt_id"] is None
        # 메타인지 확인 발화로 override됨(결정론 템플릿).
        assert "설명해줄래" in body["decision"]["prompt"]
        assert body["decision"]["socratic_category"] == "meta"
        # 이 턴엔 ProblemAttempt가 *아직* 적재되지 않는다(돌아보기 전).
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)

    def test_correct_final_answer_persists_review_turns_remaining(self) -> None:
        # 세션(dialogue)에 돌아보기 대기 상태가 저장돼야 다음 턴이 완료를 확정할 수 있다.
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): _problem(answer="3")}
        client, captured = _session_client(preload=preload)
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "",
                "problem_id": str(pid),
                "solution_steps": ["x=3"],
            },
        )
        assert resp.status_code == 201, resp.text
        dialogues = [o for o in captured.added if isinstance(o, DialogueORM)]
        assert len(dialogues) == 1
        assert dialogues[0].review_turns_remaining == 1

    def test_answer_not_leaked_on_correct(self) -> None:
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): _problem(answer=_ANSWER_SENTINEL)}
        client, _ = _session_client(preload=preload)
        resp = client.post(
            "/v1/coach/sessions",
            json={
                "student_input": "",
                "problem_id": str(pid),
                "solution_steps": [f"x={_ANSWER_SENTINEL}"],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # correct 판정이 실제로 났는지 먼저 확인(그렇지 않으면 아래 비노출 검사가 공허하다).
        assert body["awaiting_reflection"] is True
        # 정답 원문이 응답 전체(사유·발화 등) 어디에도 그대로 반향되지 않는다.
        assert _ANSWER_SENTINEL not in resp.text


class TestAppendTurnsCompletesAfterReflection:
    """append_turns — 돌아보기 응답 턴(review_turns_remaining>0)에서 완료가 확정된다."""

    def _dialogue_awaiting_reflection(self, did: uuid.UUID, pid: uuid.UUID) -> DialogueORM:
        return DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                problem_id=pid,
                total_turns=2,
                student_turns=1,
                assistant_turns=1,
                review_turns_remaining=1,
            )
        )

    def test_reflection_response_completes_and_records_attempt(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_awaiting_reflection(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, captured = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "2x=6이니까 양변을 2로 나눠서 x=3이 나왔어요"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is True
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is not None
        assert "다음 문제로" in body["decision"]["prompt"]

        attempts = [o for o in captured.added if isinstance(o, ProblemAttemptORM)]
        assert len(attempts) == 1
        attempt = attempts[0]
        assert attempt.is_correct is True
        assert attempt.user_id == _UID
        assert attempt.problem_id == pid
        assert attempt.used_socratic is True
        assert str(attempt.attempt_id) == body["completed_attempt_id"]

    def test_reflection_turn_does_not_reverify_solution(self) -> None:
        # 돌아보기 응답 턴은 *이 턴 풀이 내용과 무관*하게 완료된다(자연어 근거일 뿐 — 재검증 없음).
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_awaiting_reflection(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, captured = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            # solution_steps가 아예 없어도(순수 자연어 설명) 완료가 확정된다.
            json={"student_input": "왜냐하면 양변을 2로 나눴기 때문이에요"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["problem_complete"] is True
        assert any(isinstance(o, ProblemAttemptORM) for o in captured.added)


class TestAppendTurnsRedirectsOnIncorrect:
    """append_turns — 명확한 오답 최종답은 재고 유도(REDIRECT)로 방향을 준다(완료/attempt 없음)."""

    def _dialogue_fresh(
        self, did: uuid.UUID, pid: uuid.UUID, *, total_turns: int = 2
    ) -> DialogueORM:
        return DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                problem_id=pid,
                total_turns=total_turns,
                student_turns=total_turns // 2,
                assistant_turns=total_turns // 2,
                review_turns_remaining=0,
            )
        )

    def test_incorrect_final_answer_redirects_without_completing(self) -> None:
        # total_turns=0 — 이 append가 첫 교환(turn_index=1) → 일반 재고 발화(_REDIRECT_PROMPT).
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_fresh(did, pid, total_turns=0)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, captured = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "답 다시 볼게요", "solution_steps": ["x=99"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is None
        assert body["decision"]["prompt"] == _REDIRECT_PROMPT
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)

    def test_incorrect_final_answer_variant_on_later_turn(self) -> None:
        # total_turns=2 — 이미 1교환 있음 → 이 append는 turn_index=2 → 구체 재고 발화로 변주.
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_fresh(did, pid, total_turns=2)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, _ = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "", "solution_steps": ["x=99"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["decision"]["prompt"] != _REDIRECT_PROMPT
        assert "다시 확인해 보자" in body["decision"]["prompt"]

    def test_redirect_prompt_has_no_negative_affect_reinforcement(self) -> None:
        # CLAUDE.md 금기: 부정 정서강화 표현 금지(틀렸·못 하·잘못된·실수·바보·포기).
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_fresh(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, _ = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "", "solution_steps": ["x=99"]},
        )
        prompt = resp.json()["decision"]["prompt"]
        for banned in ("틀렸", "못 하", "잘못된", "실수", "바보", "포기"):
            assert banned not in prompt

    def test_incorrect_answer_not_leaked(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = self._dialogue_fresh(did, pid)
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer=_ANSWER_SENTINEL),
        }
        client, _ = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "", "solution_steps": ["x=99"]},
        )
        assert resp.status_code == 201, resp.text
        assert _ANSWER_SENTINEL not in json.dumps(resp.json())


class TestUnverifiableIsInert:
    """미검증(파싱 불가·사변) 최종답 — 완료도 재고도 없음(기존 코칭 그대로·회귀 불변)."""

    def test_unparseable_last_step_no_completion_no_redirect(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                problem_id=pid,
                total_turns=2,
                student_turns=1,
                assistant_turns=1,
                review_turns_remaining=0,
            )
        )
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, captured = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "음", "solution_steps": ["잘 모르겠어요"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False
        assert body["completed_attempt_id"] is None
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
        # EOS-69: 이 클래스 이름이 약속하는 "재고도 없음"을 실제로 단언한다. 그전까지는 완료
        # 필드만 봤기 때문에 **`unverifiable`을 `incorrect`로 접는 결함이 초록으로 통과**했다
        # (뮤테이션 M2 실측 — 서빙 계층에 변별력이 없던 자리). 재고 발화는 턴 인덱스에 따라
        # 두 변주가 있으므로 둘 다 배제한다.
        assert body["decision"]["prompt"] != _REDIRECT_PROMPT
        assert body["decision"]["prompt"] != _REDIRECT_PROMPT_SPECIFIC

    def test_no_solution_steps_no_completion(self) -> None:
        # solution_steps 미제공 — 완료 감지 트리거 자체가 없다(클라 계약: 완료를 원하면 보낸다).
        pid = uuid.uuid4()
        preload = {(ProblemORM, pid): _problem(answer="3")}
        client, _ = _session_client(preload=preload)
        resp = client.post(
            "/v1/coach/sessions",
            json={"student_input": "힌트 주세요", "problem_id": str(pid)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["awaiting_reflection"] is False


class TestAlreadyCompletedGuardsReattempt:
    """이미 완료된 세션(attempt_id 보유) — 재완료·중복 attempt 적재 금지."""

    def test_already_completed_session_does_not_reattempt(self) -> None:
        did = uuid.uuid4()
        pid = uuid.uuid4()
        existing_attempt_id = uuid.uuid4()
        dialogue = DialogueORM.from_schema(
            DialogueSchema(
                dialogue_id=did,
                user_id=_UID,
                problem_id=pid,
                attempt_id=existing_attempt_id,
                total_turns=4,
                student_turns=2,
                assistant_turns=2,
                review_turns_remaining=0,
            )
        )
        preload = {
            (DialogueORM, did): dialogue,
            (ProblemORM, pid): _problem(answer="3"),
        }
        client, captured = _session_client(preload=preload)
        resp = client.post(
            f"/v1/coach/sessions/{did}/turns",
            json={"student_input": "", "solution_steps": ["x=3"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["problem_complete"] is False
        assert body["completed_attempt_id"] is None
        assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)


class TestGateOffIsFullyInert:
    """게이트 off(`l4_solution_completion_enabled=False`) — 완료 기능 완전 비활성(기존 동작 불변)."""

    def test_gate_off_correct_answer_does_not_enter_review(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WHYMATH_L4_SOLUTION_COMPLETION_ENABLED", "false")
        get_settings.cache_clear()
        try:
            pid = uuid.uuid4()
            preload = {(ProblemORM, pid): _problem(answer="3")}
            client, captured = _session_client(preload=preload)
            resp = client.post(
                "/v1/coach/sessions",
                json={
                    "student_input": "",
                    "problem_id": str(pid),
                    "solution_steps": ["x=3"],
                },
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["problem_complete"] is False
            assert body["awaiting_reflection"] is False
            assert body["completed_attempt_id"] is None
            assert not any(isinstance(o, ProblemAttemptORM) for o in captured.added)
            dialogues = [o for o in captured.added if isinstance(o, DialogueORM)]
            assert dialogues[0].review_turns_remaining == 0
        finally:
            get_settings.cache_clear()
