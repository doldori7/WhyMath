"""WH-1 프로덕션 LLM 정책(`harness/wh1_llm_policy.py`) — 단위·통합(hermetic·순수).

FakeProvider(스크립트된 JSON 반환)로 두뇌의 계약을 검증한다 — 실 네트워크·직접 LLM 호출 0.
검증 축: ①정상 매핑 ②verify 의무 이중 방어 ③unverifiable 정답 억제 ④안전 폴백(깨진 JSON·미지
kind) ⑤학생 원문·정답의 프롬프트 미노출(요구사항 ⑥) ⑥run_tutoring_turn 통합 완주.

정직 스코프: L3 provider는 FakeProvider로 대체(라우터 결정은 실제 `Router().route()`가 내리되
로컬·순수라 네트워크 없음). 하네스 불변식의 *최종* 강제는 `test_wh1_loop.py`가 검증하며, 여기서는
정책의 *선제* 방어와 매핑만 본다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from whymath_backend.harness.wh1_llm_policy import LLMTutorPolicy
from whymath_backend.harness.wh1_loop import (
    Action,
    EndTurnAction,
    MatchMisconceptionAction,
    TurnState,
    VerifyStepAction,
    run_tutoring_turn,
)
from whymath_backend.l3.models import RoutingDecision

# diagnose가 confidence 1.0으로 잡는 실 신호(wh1_loop 테스트와 동일).
_MATCH_TEXT = "(a+b) a² + b²"
# 프롬프트에 절대 새면 안 되는 민감 표지(요구사항 ⑥ 검증용).
_SECRET_STUDENT_TEXT = "비밀학생풀이-SENTINEL-x=42"
_SECRET_ANSWER_STEP = "정답원문-SENTINEL-x=3"


class FakeProvider:
    """스크립트된 JSON 응답만 돌려주는 L3 provider 대역 — LLMProvider 충족(실 네트워크 0).

    `responses`를 순서대로 방출하고 소진되면 항상 end_turn(격려)을 반환해 루프를 종료시킨다.
    호출마다 (prompt, system)을 `calls`에 기록해 원문 미노출 검증에 쓴다.
    """

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> str:
        self.calls.append((prompt, system))
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return out
        return '{"kind": "end_turn", "action_type": "격려"}'


class RaisingProvider:
    """generate가 항상 예외를 던지는 provider 대역 — provider 장애 안전 강등 검증용."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> str:
        raise RuntimeError("provider 다운(테스트)")


def _state(
    *,
    has_solution_steps: bool = False,
    verify_called: bool = False,
    last_verdict: str | None = None,
) -> TurnState:
    return TurnState(
        turn_index=1,
        has_solution_steps=has_solution_steps,
        hypotheses=[],
        verify_called=verify_called,
        last_verdict=last_verdict,  # type: ignore[arg-type]
    )


def _next(policy: LLMTutorPolicy, state: TurnState) -> Action:
    return asyncio.run(policy.next_action(state))  # type: ignore[return-value]


class TestNormalMapping:
    def test_match_misconception_maps_and_injects_private_text(self) -> None:
        """LLM이 match_misconception을 고르면 정책이 *보유한* 학생 원문으로 인자를 채운다."""
        provider = FakeProvider(['{"kind": "match_misconception"}'])
        policy = LLMTutorPolicy(provider, student_text=_MATCH_TEXT)
        action = _next(policy, _state())
        assert isinstance(action, MatchMisconceptionAction)
        # 원문은 LLM 출력이 아니라 정책 보유값에서 온다.
        assert action.student_text == _MATCH_TEXT

    def test_curate_parses_scalar_field(self) -> None:
        """비민감 스칼라(turns_elapsed)는 LLM 출력에서 파싱된다."""
        provider = FakeProvider(['{"kind": "curate_hypothesis", "turns_elapsed": 3}'])
        policy = LLMTutorPolicy(provider)
        action = _next(policy, _state())
        from whymath_backend.harness.wh1_loop import CurateHypothesisAction

        assert isinstance(action, CurateHypothesisAction)
        assert action.turns_elapsed == 3

    def test_json_inside_prose_and_codefence(self) -> None:
        """코드펜스·주변 산문에 감싸인 JSON도 관대하게 추출한다."""
        provider = FakeProvider(
            ['설명...\n```json\n{"kind": "end_turn", "action_type": "격려"}\n```']
        )
        policy = LLMTutorPolicy(provider)
        action = _next(policy, _state())
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "격려"


class TestVerifyObligationDefense:
    def test_end_turn_redirected_to_verify_when_obligation_pending(self) -> None:
        """풀이 제출·미검증인데 LLM이 end_turn을 내면 정책이 verify_step으로 재지정(이중 방어)."""
        provider = FakeProvider(['{"kind": "end_turn", "action_type": "격려"}'])
        policy = LLMTutorPolicy(provider, solution_steps=[_SECRET_ANSWER_STEP])
        action = _next(policy, _state(has_solution_steps=True, verify_called=False))
        assert isinstance(action, VerifyStepAction)
        # 단계는 정책 보유값으로 채워진다(LLM 미경유).
        assert action.steps == [_SECRET_ANSWER_STEP]

    def test_verify_step_selected_directly(self) -> None:
        """LLM이 직접 verify_step을 골라도 보유 단계로 채운다."""
        provider = FakeProvider(['{"kind": "verify_step"}'])
        policy = LLMTutorPolicy(provider, solution_steps=["x+1", "x=2"])
        action = _next(policy, _state(has_solution_steps=True, verify_called=False))
        assert isinstance(action, VerifyStepAction)
        assert action.steps == ["x+1", "x=2"]


class TestUnverifiableSuppression:
    def test_unverifiable_strips_answer_and_downgrades_to_socratic(self) -> None:
        """unverifiable 상태의 end_turn은 명시 발화 제거 + 정답 제시형(출제) → 질문 강등."""
        provider = FakeProvider(
            ['{"kind": "end_turn", "action_type": "출제", "utterance": "정답은 x=3이야."}']
        )
        policy = LLMTutorPolicy(provider)
        # 검증은 이미 호출됨(verify_called=True) → verify 의무 분기 아님, unverifiable 분기만.
        action = _next(
            policy,
            _state(has_solution_steps=True, verify_called=True, last_verdict="unverifiable"),
        )
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "질문"  # 정답 제시형(출제) → 소크라테스 질문으로 강등
        assert action.utterance is None  # LLM 정답 발화 제거 → 하네스 개입 발화가 대신 말함

    def test_unverifiable_keeps_safe_socratic_type(self) -> None:
        """unverifiable라도 이미 안전한 힌트/질문/격려는 유형 보존(발화만 제거)."""
        provider = FakeProvider(
            ['{"kind": "end_turn", "action_type": "힌트", "utterance": "여기 정답 x=3"}']
        )
        policy = LLMTutorPolicy(provider)
        action = _next(
            policy,
            _state(has_solution_steps=True, verify_called=True, last_verdict="unverifiable"),
        )
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "힌트"
        assert action.utterance is None


class TestSafeFallback:
    def test_broken_json_falls_back_to_encouragement(self) -> None:
        """깨진 JSON → 안전 폴백(격려 종료·크래시 없음)."""
        provider = FakeProvider(["이건 JSON이 아니라 그냥 문장입니다."])
        policy = LLMTutorPolicy(provider)
        action = _next(policy, _state())
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "격려"

    def test_unknown_kind_falls_back(self) -> None:
        """미지 kind → 안전 폴백."""
        provider = FakeProvider(['{"kind": "teleport_student", "foo": 1}'])
        policy = LLMTutorPolicy(provider)
        action = _next(policy, _state())
        assert isinstance(action, EndTurnAction)

    def test_invalid_action_type_falls_back(self) -> None:
        """스키마 위반(잘못된 action_type Literal) → Pydantic 검증 실패 → 폴백."""
        provider = FakeProvider(['{"kind": "end_turn", "action_type": "설명"}'])
        policy = LLMTutorPolicy(provider)
        action = _next(policy, _state())
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "격려"  # 폴백 기본

    def test_fallback_prefers_verify_when_obligation_pending(self) -> None:
        """폴백도 verify 의무를 존중 — 미검증 풀이 제출 턴이면 verify_step으로 강등."""
        provider = FakeProvider(["깨진 응답"])
        policy = LLMTutorPolicy(provider, solution_steps=["step1"])
        action = _next(policy, _state(has_solution_steps=True, verify_called=False))
        assert isinstance(action, VerifyStepAction)

    def test_provider_error_falls_back(self) -> None:
        """provider 예외(장애) → 안전 강등(학생 앞 크래시 금지)."""
        policy = LLMTutorPolicy(RaisingProvider())
        action = _next(policy, _state())
        assert isinstance(action, EndTurnAction)
        assert action.action_type == "격려"


class TestNoRawLeak:
    """요구사항 ⑥ — 학생 원문·정답이 프롬프트/시스템에 절대 실리지 않는다(요약만)."""

    def test_student_text_and_answer_absent_from_prompt(self) -> None:
        provider = FakeProvider(['{"kind": "match_misconception"}'])
        policy = LLMTutorPolicy(
            provider,
            student_text=_SECRET_STUDENT_TEXT,
            solution_steps=[_SECRET_ANSWER_STEP],
        )
        _next(policy, _state(has_solution_steps=True, verify_called=True))
        assert provider.calls, "provider가 호출되어야 한다"
        prompt, system = provider.calls[0]
        combined = prompt + system
        assert _SECRET_STUDENT_TEXT not in combined
        assert _SECRET_ANSWER_STEP not in combined


class TestIntegration:
    """LLMTutorPolicy + FakeProvider로 run_tutoring_turn 한 턴 완주(ScriptedPolicy 테스트 미러)."""

    def test_full_turn_completes_ended(self) -> None:
        """match → curate → end_turn(격려) 스크립트로 한 턴 완주(ended)."""
        provider = FakeProvider(
            [
                '{"kind": "match_misconception"}',
                '{"kind": "curate_hypothesis", "turns_elapsed": 1}',
                '{"kind": "end_turn", "action_type": "격려", "utterance": "좋아, 잘했어."}',
            ]
        )
        policy = LLMTutorPolicy(provider, student_text=_MATCH_TEXT)
        outcome = asyncio.run(run_tutoring_turn(policy=policy, has_solution_steps=False))
        assert outcome.status == "ended"
        assert outcome.action_type == "격려"
        assert outcome.utterance == "좋아, 잘했어."

    def test_full_turn_respects_verify_obligation(self) -> None:
        """풀이 제출 턴: LLM이 곧장 end_turn을 내도 정책이 verify_step으로 유도 → 검증 후 종료."""
        provider = FakeProvider(
            [
                '{"kind": "end_turn", "action_type": "격려"}',  # 정책이 verify_step으로 재지정
                '{"kind": "end_turn", "action_type": "질문"}',  # 검증 후엔 종료 허용
            ]
        )
        policy = LLMTutorPolicy(provider, solution_steps=["x = 2", "x + 1 = 3"])
        outcome = asyncio.run(run_tutoring_turn(policy=policy, has_solution_steps=True))
        assert outcome.status == "ended"
        # verify_step이 트레이스에 존재(정책 선제 방어 → 하네스 실행).
        assert any(t.kind == "verify_step" and t.ok for t in outcome.trace)

    def test_budget_exhausts_without_crash(self) -> None:
        """정책이 계속 내부 도구만 내도(예: read) 예산 소진으로 안전 종료(크래시 없음)."""
        provider = FakeProvider(['{"kind": "read_student_state"}'] * 5)
        policy = LLMTutorPolicy(provider)
        outcome = asyncio.run(run_tutoring_turn(policy=policy, max_tool_calls=3))
        assert outcome.status == "budget_exhausted"
        assert outcome.tool_calls == 3
