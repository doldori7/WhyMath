"""교수법 어댑터 구현 모음 — 개념 무관·LLM=0 결정론 렌더(03c §2).

각 어댑터는 하나의 `PedagogyStrategy`를 담당하며 *모든* 개념에 작동한다(개념별 복제 금지).
레지스트리(`l3/render/registry.py`)가 strategy→adapter로 묶는다(Renderer=Plugin 경계).
"""

from __future__ import annotations

from whymath_backend.l3.render.adapters.analogy import AnalogyAdapter
from whymath_backend.l3.render.adapters.direct import DirectAdapter
from whymath_backend.l3.render.adapters.problem_based import ProblemBasedAdapter
from whymath_backend.l3.render.adapters.socratic import SocraticAdapter
from whymath_backend.l3.render.adapters.worked_example import WorkedExampleAdapter

__all__ = [
    "AnalogyAdapter",
    "DirectAdapter",
    "ProblemBasedAdapter",
    "SocraticAdapter",
    "WorkedExampleAdapter",
]
