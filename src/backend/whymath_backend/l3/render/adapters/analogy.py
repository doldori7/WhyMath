"""ANALOGY 어댑터 — 비유 설명(03c §2.1).

예시(구조화 콘텐츠)를 *익숙한 것에 빗대어* 제시한다. ConceptDSL은 방식-중립이라 별도 '비유 지시'
필드가 없다 — 어댑터가 예시의 맥락 슬롯/부가 설명을 비유 앵커로 재구성한다(개념 무관·LLM=0).
풍부한 비유 소싱(은유 콘텐츠 결합)은 후속이며, 여기서는 예시 재료로 결정론 비유를 조립한다.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import eun_neun, wa_gwa
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


class AnalogyAdapter:
    """비유 렌더 — 예시를 익숙한 앵커에 빗댄다(개념 무관·순수 렌더)."""

    strategy: PedagogyStrategy = PedagogyStrategy.ANALOGY

    def can_render(self, dsl: ConceptDSL) -> bool:
        """비유는 빗댈 재료(예시)가 있어야 렌더 가능."""
        return bool(dsl.examples)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """예시별 비유 블록 조립. 구조는 예시 수에만 의존(숫자/이름 무관·대칭 보장)."""
        # 도입(josa: 은/는).
        intro = f"{dsl.name}{eun_neun(dsl.name)} 익숙한 것에 빗대어 생각해 봅시다."
        blocks: list[RenderBlock] = [RenderBlock(kind="analogy_intro", text=intro)]
        for example in dsl.examples:
            # 앵커: 맥락 슬롯(익숙한 명사)을 우선, 없으면 부가 설명(note), 없으면 예시 본문.
            anchor = example.slots.get("context") or example.note or example.statement
            # josa(와/과): "…와 비교해 보면 …".
            line = f"{anchor}{wa_gwa(anchor)} 비교해 보면 이해가 쉽습니다."
            blocks.append(RenderBlock(kind="analogy", text=line))
        return RenderedUnit(strategy=self.strategy, blocks=tuple(blocks), validation_signal=None)


__all__ = ["AnalogyAdapter"]
