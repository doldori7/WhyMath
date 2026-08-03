"""REC-02 acceptance ⑤ — 변별력 실측: 공급 배선 전후로 select_probe의 ok가 0→>0으로 갈린다.

배경: WH-1 하네스 도구6 `select_probe`가 라이브에서 상시 실패했던 근본 원인은
`LLMTutorPolicy.probe_candidates` 기본값 `()`을 채우는 프로덕션 호출자가 0건이었기 때문이다
(`ai_recommendation_module_gap_review.md` D2). 이 파일은 **같은 가설·같은 provider**로
`probe_candidates` 유무만 다르게 준 두 실행을 나란히 돌려, `ok=False`(공급 0 — 배선 전 상태와
동치) → `ok=True`(공급 있음 — 배선 후 상태)로 실제 값이 갈리는지 `run_tutoring_turn`을 직접
호출해 확인한다(하네스 레벨 e2e — DB·네트워크 0, hermetic).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from whymath_backend.harness.wh1_llm_policy import LLMTutorPolicy
from whymath_backend.harness.wh1_loop import TurnOutcome, run_tutoring_turn
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import ProbeCandidate


class _FakeProvider:
    """스크립트된 JSON만 돌려주는 L3 provider 대역 — 소진 시 end_turn(격려)로 종료."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return GenerationResult(out)
        return GenerationResult('{"kind": "end_turn", "action_type": "격려"}')


def _select_probe_result(outcome: TurnOutcome) -> object:
    return next(r for r in outcome.trace if r.kind == "select_probe")


def _run_turn(*, probe_candidates: Sequence[ProbeCandidate]) -> TurnOutcome:
    hypotheses = [
        MisconceptionHypothesis(
            misconception_id="M-TARGET", confidence=0.8, turns_since_evidence=0, evidence_count=1
        )
    ]
    provider = _FakeProvider(
        ['{"kind": "select_probe"}', '{"kind": "end_turn", "action_type": "격려"}']
    )
    policy = LLMTutorPolicy(
        provider,
        probe_candidates=probe_candidates,
        theta=0.0,
        outside_mids=[],
    )
    return asyncio.run(
        run_tutoring_turn(
            policy=policy,
            turn_index=1,
            has_solution_steps=False,
            initial_hypotheses=hypotheses,
        )
    )


class TestProbeSupplyDiscrimination:
    def test_select_probe_ok_true_with_candidates(self) -> None:
        """공급 배선 후(candidates 있음) — 판별 문항이 실제로 선택되어 ok=True."""
        candidate = ProbeCandidate(
            problem_id="P1", difficulty=0.0, misconception_tags=frozenset({"M-TARGET"})
        )
        outcome = _run_turn(probe_candidates=[candidate])
        result = _select_probe_result(outcome)
        assert result.ok is True

    def test_select_probe_ok_false_without_candidates(self) -> None:
        """공급 배선 전(candidates 없음 — 결함 재현) — 같은 가설·같은 provider인데 ok=False."""
        outcome = _run_turn(probe_candidates=())
        result = _select_probe_result(outcome)
        assert result.ok is False
