"""전략 → 어댑터 레지스트리 — 단일 조회 지점(미구현 전략은 명확히 거부).

설계 정본: `docs/architecture/03c_content_strategy_cache.md` §2.2.

`CompositeProvider`의 티어 디스패치·`acceptance._CONCEPTUAL_VERIFIERS`의 dict 디스패치와 같은
house style이다. **조용한 폴백을 두지 않는다** — 등록되지 않은 전략을 요청하면 임의의 다른
어댑터로 대체하지 않고 `LookupError`를 던진다(CLAUDE.md "모르면 모른다고"·침묵 실패 금지).

폐쇄 enum `PedagogyStrategy`는 10종이지만 이 슬라이스(REND-01)는 5종만 구현한다. 나머지 5종
(RETRIEVAL·SPACING·INTERLEAVING·SELF_EXPLANATION·VISUALIZATION)은 *의도적 미등록*이며, 요청 시
"미구현"임이 오류로 드러난다 — 있는 척하는 빈 렌더보다 낫다. 상위(supply)는 이 오류를 잡아 생성
경로로 폴백하면 된다.
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

# 전략 1개 = 어댑터 1개(개념 무관). 개념 수가 늘어도 이 표는 자라지 않는다 — 조합폭발 방지의
# 구조적 증거다(거버넌스 테스트가 이 불변식을 동결한다).
_ADAPTERS: dict[PedagogyStrategy, PedagogyAdapter] = {
    PedagogyStrategy.DIRECT: DirectAdapter(),
    PedagogyStrategy.SOCRATIC: SocraticAdapter(),
    PedagogyStrategy.WORKED_EXAMPLE: WorkedExampleAdapter(),
    PedagogyStrategy.PROBLEM_BASED: ProblemBasedAdapter(),
    PedagogyStrategy.ANALOGY: AnalogyAdapter(),
}


def get_adapter(strategy: PedagogyStrategy) -> PedagogyAdapter:
    """전략에 대응하는 어댑터 반환 — 미등록이면 `LookupError`(폴백 대체 금지).

    호출부(상위 supply)는 이 오류를 잡아 *생성 경로*로 폴백할 수 있다. 여기서 임의 어댑터로
    대체하면 학생이 요청과 다른 방식의 수업을 받게 되므로 하지 않는다.
    """
    adapter = _ADAPTERS.get(strategy)
    if adapter is None:
        available = ", ".join(sorted(s.value for s in _ADAPTERS))
        raise LookupError(
            f"전략 {strategy.value}의 렌더 어댑터가 등록되지 않았습니다(미구현). "
            f"현재 구현: {available}."
        )
    return adapter


def registered_strategies() -> frozenset[PedagogyStrategy]:
    """구현된 전략 집합 — 상위가 렌더 가능 여부를 미리 판단할 때 쓴다."""
    return frozenset(_ADAPTERS)


__all__ = ["get_adapter", "registered_strategies"]
