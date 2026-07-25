"""WORKED_EXAMPLE 어댑터 — 완전예제 제시(03c §2.1).

assessment 시드로 *완전 풀이*를 보인다. 정답은 코드가 소유·검증한다 — `resolve_and_verify`
(derive_selected_root/verify_answer)로 gold answer를 SymPy 검산하고, **state=='pass'일 때만
clean 노출**한다(검증 실패 시 ValidationSignal — 미검증 노출 금지·03c §3). 개념 무관·LLM=0.

⚠️ 냉담 제공 불가(03c §3 게이트): "언제" 완전예제를 허용할지(Polya '시도함' 통과 뒤)는 select
상류의 게이트 책임이다. 어댑터는 *렌더*만 하며 그 시점 판단을 내리지 않는다(관심사 분리).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import eul_reul
from whymath_backend.l3.pregenerate.models import ValidationSignal
from whymath_backend.l3.render.adapters._common import (
    format_answer,
    problem_statement,
    resolve_and_verify,
)
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


class WorkedExampleAdapter:
    """완전예제 렌더 — 문제→주어진 조건→대입→결론. 정답 SymPy 검증 통과분만 clean(개념 무관)."""

    strategy: PedagogyStrategy = PedagogyStrategy.WORKED_EXAMPLE

    def can_render(self, dsl: ConceptDSL) -> bool:
        """완전예제는 assessment 시드(문제·정답)가 있어야 렌더 가능."""
        return bool(dsl.assessment)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """첫 시드로 완전예제 조립 — gold answer를 SymPy 검증(실패 시 노출 차단)."""
        seed = dsl.assessment[0]
        gold, signal = resolve_and_verify(seed)
        problem_block = RenderBlock(kind="problem", text=problem_statement(seed))
        if signal is not None or gold is None:
            # 검증 실패 — 완전예제를 학생에게 노출하지 않는다(문제문만·신호 실림).
            fail_signal = signal or ValidationSignal(kind="solution", reason="정답 미보유")
            return RenderedUnit(
                strategy=self.strategy,
                blocks=(problem_block,),
                validation_signal=fail_signal,
            )
        blocks: list[RenderBlock] = [problem_block]
        for condition in seed.conditions:
            blocks.append(RenderBlock(kind="given", text=f"주어진 조건: {condition}"))
        for var, val in gold.items():
            # josa(을/를): "2를 대입하면 …" — 검산 통과한 값을 대입해 조건 만족을 보인다.
            step = f"{var} 자리에 {val}{eul_reul(val)} 대입하면 조건을 만족합니다."
            blocks.append(RenderBlock(kind="substitution", text=step))
        blocks.append(RenderBlock(kind="conclusion", text=f"따라서 {format_answer(gold)}."))
        return RenderedUnit(strategy=self.strategy, blocks=tuple(blocks), validation_signal=None)


__all__ = ["WorkedExampleAdapter"]
