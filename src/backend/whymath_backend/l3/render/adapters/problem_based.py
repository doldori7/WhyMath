"""PROBLEM_BASED 어댑터 — 문제부터 제시(03c §2.1).

assessment 문제로 시작해 학생이 *먼저 스스로 풀게* 한다 — **정답을 노출하지 않는다**(CLAUDE.md
"바로 정답 제공 금지"). 다만 제시 전에 gold answer를 SymPy 검증해 *풀 수 있는 문제*만 내보낸다
(malformed 문제 노출 차단·검증 실패 시 ValidationSignal). 개념 무관·LLM=0 결정론.

오개념은 초기 context에 preload하지 않는다(반응형 retrieval만·CLAUDE.md) — 문제 제시 단계에서
misconception 힌트를 미리 얹지 않는다.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import i_ga
from whymath_backend.l3.render.adapters._common import problem_statement, resolve_and_verify
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


class ProblemBasedAdapter:
    """문제부터 렌더 — 문제 제시 + 자력 풀이 유도(정답 미노출·풀림 검증·개념 무관)."""

    strategy: PedagogyStrategy = PedagogyStrategy.PROBLEM_BASED

    def can_render(self, dsl: ConceptDSL) -> bool:
        """문제부터 제시하려면 assessment 시드(문제)가 필수."""
        return bool(dsl.assessment)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """첫 시드로 문제 제시 — 내부적으로 gold answer 검증(풀 수 있는 문제만 노출)."""
        seed = dsl.assessment[0]
        _gold, signal = resolve_and_verify(seed)
        problem_block = RenderBlock(kind="problem", text=problem_statement(seed))
        if signal is not None:
            # 풀림 검증 실패 — malformed 문제를 제시하지 않는다(문제문만·신호 실림).
            return RenderedUnit(
                strategy=self.strategy,
                blocks=(problem_block,),
                validation_signal=signal,
            )
        # 자력 풀이 유도(josa: 이/가). 변수명은 정답 키에서(개념 무관). 정답 값은 노출하지 않는다.
        var = next(iter(seed.answer), "값")
        invite = f"{var}{i_ga(var)} 무엇일지 먼저 스스로 구해 보세요."
        blocks = (problem_block, RenderBlock(kind="invitation", text=invite))
        return RenderedUnit(strategy=self.strategy, blocks=blocks, validation_signal=None)


__all__ = ["ProblemBasedAdapter"]
