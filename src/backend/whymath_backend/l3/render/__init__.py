"""L3 Rendering Engine — 교수법-중립 DSL을 전략별 학생 화면으로 렌더(03c §2).

설계 정본: `docs/architecture/03c_content_strategy_cache.md`. 저장 자산은 교수법-중립 콘텐츠
(`schema/concept_dsl.py::ConceptDSL`) 하나이고, 방식(설명/질문/문제/비유…)은 이 계층의 어댑터가
렌더 시점에 얹는다 — 저장이 *곱이 아니라 합*(atom당 DSL 1 + 개념 무관 어댑터 N)이 되는 조합폭발의
해다. 전략 *선택*은 이 계층이 아니라 L4 Runtime Pedagogy Selector(04d) 권위다(관심사 분리).

7계층: L3 지역. schema·l1·l2·l3.*·db·config만 import(l4/l5/l6/api 역방향 금지·import-linter).

공개 API:
  - models: RenderContext(중립 입력)·RenderBlock·RenderedUnit
  - adapter: PedagogyAdapter(Protocol)
  - registry: ADAPTERS·get_adapter (Renderer=Plugin 경계)
  - dsl_gate: validate_concept_dsl·assessment_dsl_violation (닫힌-DSL 게이트)
"""

from __future__ import annotations

from whymath_backend.l3.render.adapter import PedagogyAdapter
from whymath_backend.l3.render.dsl_gate import assessment_dsl_violation, validate_concept_dsl
from whymath_backend.l3.render.models import RenderBlock, RenderContext, RenderedUnit
from whymath_backend.l3.render.registry import ADAPTERS, get_adapter

__all__ = [
    "ADAPTERS",
    "PedagogyAdapter",
    "RenderBlock",
    "RenderContext",
    "RenderedUnit",
    "assessment_dsl_violation",
    "get_adapter",
    "validate_concept_dsl",
]
