"""DIRECT 어댑터 — 설명 중심(Direct Instruction·03c §2.1).

정의 + 예시를 순서대로 조립해 *직접 설명*한다. 개념 무관: 모든 콘텐츠는 `dsl`에서 온다(개념명
하드코딩 0). LLM=0 결정론 템플릿. 정서 안전한 중립 프레이밍만 쓴다(부정 피드백 강화 금지).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import eun_neun
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


class DirectAdapter:
    """설명 중심 렌더 — 정의를 제시하고 예시로 구체화한다(개념 무관·순수 렌더)."""

    strategy: PedagogyStrategy = PedagogyStrategy.DIRECT

    def can_render(self, dsl: ConceptDSL) -> bool:
        """정의는 필수 필드라 항상 렌더 가능."""
        return bool(dsl.definition)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """정의 + 예시 블록 조립. 구조는 예시 수에만 의존(숫자/이름 무관·대칭 보장)."""
        # 개념 소개(josa: 은/는). name은 과목 불변 id — 최종 표시 다듬기는 L5 몫(표현≠의미).
        intro = f"{dsl.name}{eun_neun(dsl.name)} 다음과 같이 이해할 수 있습니다."
        blocks: list[RenderBlock] = [
            RenderBlock(kind="concept", text=intro),
            RenderBlock(kind="definition", text=dsl.definition),
        ]
        for example in dsl.examples:
            body = example.statement
            if example.note is not None:
                body = f"{body} — {example.note}"
            blocks.append(RenderBlock(kind="example", text=body))
        return RenderedUnit(strategy=self.strategy, blocks=tuple(blocks), validation_signal=None)


__all__ = ["DirectAdapter"]
