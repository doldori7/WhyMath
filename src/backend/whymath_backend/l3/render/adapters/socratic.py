"""SOCRATIC 어댑터 — 질문 중심(문답식·03c §2.1).

정의·예시를 *발문*으로 재구성해 학생이 스스로 도달하게 한다 — **정답을 주지 않는다**(CLAUDE.md
"막혔을 때 바로 정답 제공 금지"의 렌더 실천). 개념 무관: 모든 콘텐츠는 `dsl`에서. LLM=0 결정론.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import i_ga
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


class SocraticAdapter:
    """질문 중심 렌더 — 정의/예시를 발문으로 바꾼다(정답 미노출·개념 무관)."""

    strategy: PedagogyStrategy = PedagogyStrategy.SOCRATIC

    def can_render(self, dsl: ConceptDSL) -> bool:
        """정의는 필수 필드라 항상 발문 가능."""
        return bool(dsl.definition)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """열린 발문 + 예시별 관찰 발문 + 근거 발문. 구조는 예시 수에만 의존(대칭 보장)."""
        # 열린 발문(josa: 이/가). 정의 본문을 답으로 노출하지 않고 스스로 설명하게 유도.
        opening = f"{dsl.name}{i_ga(dsl.name)} 무엇을 뜻하는지 스스로 설명해 볼까요?"
        blocks: list[RenderBlock] = [RenderBlock(kind="question_open", text=opening)]
        for example in dsl.examples:
            probe = f"이 예시에서 무엇이 성립하는지 살펴볼까요? {example.statement}"
            blocks.append(RenderBlock(kind="question_example", text=probe))
        blocks.append(RenderBlock(kind="question_why", text="왜 그렇게 되는지 근거를 말해 볼까요?"))
        return RenderedUnit(strategy=self.strategy, blocks=tuple(blocks), validation_signal=None)


__all__ = ["SocraticAdapter"]
