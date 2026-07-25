"""교수법 어댑터 계약 `PedagogyAdapter` — 중립 DSL → 전략별 학생 화면(03c §2.2).

핵심 불변식(03c §2):
  - **어댑터는 개념 무관** — `SOCRATIC` 어댑터 하나가 일차 조건·미분·확률 *모든* 개념에 작동한다
    (개념별 복제 금지·거버넌스 테스트 동결).
  - **어댑터는 순수 렌더** — 어떤 전략을 쓸지 *고르는* 책임은 어댑터가 아니라 04d selector에.
  - **LLM=0** — 결정론 템플릿 조립. 렌더 후 검증 통과분만 학생 노출(ValidationSignal).
  - **렌더러 구현명은 DSL에 없다** — 레지스트리(strategy→adapter)가 plugin 경계(Renderer=Plugin).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from whymath_backend.l3.render.models import RenderContext, RenderedUnit
from whymath_backend.schema.concept_dsl import ConceptDSL
from whymath_backend.schema.enums import PedagogyStrategy


@runtime_checkable
class PedagogyAdapter(Protocol):
    """교수법 전략 어댑터 프로토콜 — 개념 무관·순수 렌더(03c §2.2).

    `strategy`는 이 어댑터가 담당하는 전략(레지스트리 키). `can_render`는 이 전략이 이 DSL을 렌더할
    수 있는지(예: `PROBLEM_BASED`는 assessment 시드 필요). `render`는 중립 DSL + 중립 ctx → 전략별
    구조화 산출(RenderedUnit)이며, clean이면 `validation_signal=None`이다.
    """

    strategy: PedagogyStrategy

    def can_render(self, dsl: ConceptDSL) -> bool:
        """이 전략이 이 DSL을 렌더할 수 있는가(필수 재료 충족 여부)."""
        ...

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """중립 DSL → 전략별 학생 화면 산출(LLM=0·결정론·검증 통과분만 clean)."""
        ...


__all__ = ["PedagogyAdapter"]
