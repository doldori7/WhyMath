"""교수법 어댑터 레지스트리 — strategy→adapter plugin 경계(Renderer=Plugin·03c §2.2).

렌더러 구현명은 DSL에 없다(Concept Purity). 대신 이 레지스트리가 `PedagogyStrategy`를 어댑터
인스턴스에 잇는다 — select 계층(04d)이 고른 전략으로 `get_adapter(strategy)`를 조회해 렌더한다.

⚠️ 미구현 전략(RETRIEVAL·SPACING·INTERLEAVING·SELF_EXPLANATION·VISUALIZATION)은 레지스트리에
없어 `get_adapter`가 None을 돌린다 — enum(10종)은 폐쇄 축을 선언하고, 구현 어댑터(현 5종)는
점진 추가한다(plugin 경계라 새 어댑터 등록만으로 확장·기존 코드 무변경).
"""

from __future__ import annotations

from whymath_backend.l3.render.adapter import PedagogyAdapter
from whymath_backend.l3.render.adapters import (
    AnalogyAdapter,
    DirectAdapter,
    ProblemBasedAdapter,
    SocraticAdapter,
    WorkedExampleAdapter,
)
from whymath_backend.schema.enums import PedagogyStrategy

# strategy → adapter 인스턴스. 어댑터는 상태 없음(순수 렌더)이라 모듈 단위 단일 인스턴스로 충분.
ADAPTERS: dict[PedagogyStrategy, PedagogyAdapter] = {
    PedagogyStrategy.DIRECT: DirectAdapter(),
    PedagogyStrategy.SOCRATIC: SocraticAdapter(),
    PedagogyStrategy.WORKED_EXAMPLE: WorkedExampleAdapter(),
    PedagogyStrategy.PROBLEM_BASED: ProblemBasedAdapter(),
    PedagogyStrategy.ANALOGY: AnalogyAdapter(),
}


def get_adapter(strategy: PedagogyStrategy) -> PedagogyAdapter | None:
    """전략에 해당하는 어댑터를 조회 — 미구현 전략이면 None(plugin 경계).

    None은 "이 전략은 아직 어댑터가 없음"을 뜻한다 — 호출부(supply·03c §3)는 다른 전략으로
    폴백하거나 생성 경로로 내려간다(어댑터 부재를 조용히 삼키지 않는다).
    """
    return ADAPTERS.get(strategy)


__all__ = ["ADAPTERS", "get_adapter"]
