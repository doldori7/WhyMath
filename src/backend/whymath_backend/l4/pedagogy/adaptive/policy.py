"""L4 적응 교수법 policy — Thompson sampling 스캐폴드 + **하드 안전제약** (PED-03).

04d §3.3의 구현. 교수법을 고정 규칙이 아니라 학습 가능한 policy로 만들되, **교수학 우선순위(#3)를
위반하는 전략은 policy가 애초에 고를 수 없다**.

────────────────────────────────────────────────────────────────────────────
안전제약이 "보상 페널티"가 아니라 **행동공간 배제**인 이유
────────────────────────────────────────────────────────────────────────────
위반 전략에 낮은 보상을 주는 방식(soft penalty)은 데이터가 충분히 쌓이면 policy가 "그래도 이게
이득"이라고 판단해 뒤집을 수 있다. CLAUDE.md 의사결정 우선순위는 **비용(#6)이 교수학 정확성(#3)을
역전할 수 없다**고 못박았으므로, 학습으로 뒤집힐 수 있는 제약은 제약이 아니다.

따라서 `_allowed_actions()`가 `gate()`를 통과하지 못한 전략을 **표본 추출 목록에서 제거**한다 —
사후분포를 아무리 갱신해도 배제된 전략은 뽑힐 수 없다(구조적 차단).

────────────────────────────────────────────────────────────────────────────
⚠️ 이 policy는 **규칙표를 대체하지 않는다** (미승격)
────────────────────────────────────────────────────────────────────────────
런타임 선택의 정본은 여전히 `runtime_selector.decide()`(규칙기반 v1)다. 이 모듈은 그 옆에 존재할
뿐이며 어떤 학생 경로도 이것을 호출하지 않는다. 승격 조건(04d §3.3)은
`harness/pedagogy_policy_eval.py`의 **오프폴리시 평가 + 결함 주입 강등전 통과**이며, 현재는 실
트래픽이 없어 표본 미달로 **통과하지 못한다**. 그 상태가 정직하게 보이는 것이 지금의 산출물이다.

7계층: L4 내부(교수학 결정). L2 데이터를 집계한 결과(`effectiveness`)를 입력으로 받되 DB에 직접
접근하지 않는다(순수 함수·주입).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from whymath_backend.l3.render.registry import registered_strategies
from whymath_backend.l4.pedagogy.runtime_selector import StudentSignals, gate
from whymath_backend.schema.enums import PedagogyStrategy
from whymath_backend.schema.pedagogy_pack import PedagogyPack

# Beta 사후의 무정보 사전(Jeffreys 아님 — 균등 Beta(1,1)). 관측이 없으면 모든 허용 전략이
# 동일 사전에서 출발한다("모르면 모른다" — 특정 전략을 근거 없이 선호하지 않는다).
_PRIOR_ALPHA: float = 1.0
_PRIOR_BETA: float = 1.0


@dataclass(frozen=True, slots=True)
class ArmPosterior:
    """한 전략(arm)의 Beta 사후 — 성공/실패 관측만으로 갱신된다."""

    successes: int = 0
    failures: int = 0

    @property
    def alpha(self) -> float:
        return _PRIOR_ALPHA + self.successes

    @property
    def beta(self) -> float:
        return _PRIOR_BETA + self.failures

    @property
    def trials(self) -> int:
        return self.successes + self.failures


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """policy 산출 — 뽑힌 전략 + 그 시점의 행동공간(감사용).

    `action_space`를 함께 돌려주는 이유: "왜 이게 뽑혔나"를 사후에 검증하려면 무엇이 후보였는지
    알아야 한다. 배제된 전략이 실제로 배제됐는지도 이 필드로 확인된다.
    """

    strategy: PedagogyStrategy
    action_space: frozenset[PedagogyStrategy]


def allowed_actions(
    signals: StudentSignals, *, pack: PedagogyPack | None = None
) -> frozenset[PedagogyStrategy]:
    """이 상황에서 policy가 **고를 수 있는** 전략 집합 — 하드 안전제약.

    후보는 렌더 어댑터가 등록된 전략(`registered_strategies()`)에서 출발한다(어댑터 없는 전략을
    골라 봐야 렌더 불가). 거기서 `gate()`가 **그대로 통과시킨 것만** 남긴다 — 게이트가 다른
    전략으로 강등했다면 그 전략은 이 상황에서 허용되지 않는다는 뜻이므로 후보에서 뺀다.

    강등 결과를 후보에 도로 넣지 않는 것이 중요하다: 그렇게 하면 배제 대상이 강등을 경유해
    행동공간에 되돌아온다(우회로).
    """
    survivors: set[PedagogyStrategy] = set()
    for strategy in registered_strategies():
        verdict = gate(strategy, signals, pack=pack)
        if verdict.allowed and verdict.strategy == strategy:
            survivors.add(strategy)
    return frozenset(survivors)


def select_policy_action(
    posteriors: dict[PedagogyStrategy, ArmPosterior],
    signals: StudentSignals,
    *,
    pack: PedagogyPack | None = None,
    rng: random.Random | None = None,
) -> PolicyDecision | None:
    """Thompson sampling — 허용 행동공간에서만 표본을 뽑는다.

    각 허용 전략의 Beta(α, β)에서 한 번씩 표본을 뽑아 가장 큰 값을 고른다(탐색과 활용의 균형이
    사후분포의 불확실성에서 자연 도출된다 — ε 같은 별도 손잡이 불요).

    **행동공간이 비면 `None`** 을 돌려준다. 임의 전략으로 폴백하지 않는다 — 허용된 것이 없다는
    판정을 "아무거나 골라도 된다"로 바꾸면 안전제약이 무의미해진다. 호출자는 None을 받으면
    규칙표(`decide()`)로 되돌아가야 한다.

    `rng` 주입으로 결정론 테스트가 가능하다(전역 random 상태 비의존).
    """
    space = allowed_actions(signals, pack=pack)
    if not space:
        return None
    chooser = rng if rng is not None else random.Random()
    best: PedagogyStrategy | None = None
    best_sample = -1.0
    # 정렬 순회 — 동률 표본에서 결정론을 보장한다(dict/set 순서 비의존).
    for strategy in sorted(space, key=lambda s: s.value):
        arm = posteriors.get(strategy, ArmPosterior())
        sample = chooser.betavariate(arm.alpha, arm.beta)
        if sample > best_sample:
            best_sample = sample
            best = strategy
    assert best is not None  # space가 비어 있지 않으므로 항상 채워진다.
    return PolicyDecision(strategy=best, action_space=space)


def posteriors_from_report(
    counts: dict[str, tuple[int, int]],
) -> dict[PedagogyStrategy, ArmPosterior]:
    """집계 결과(전략명 → (성공, 시도)) → arm 사후. 알 수 없는 전략명은 버린다.

    `effectiveness.EffectivenessReport`를 policy 입력으로 옮기는 얇은 어댑터다. enum에 없는
    문자열은 조용히 버리지 않고 *건너뛴다* — 표기 오류가 사후에 섞이면 배제 대상이 되살아날 수
    있기 때문이다(허용 판정은 enum 축에서만 이뤄져야 한다).
    """
    out: dict[PedagogyStrategy, ArmPosterior] = {}
    for name, (successes, trials) in counts.items():
        try:
            strategy = PedagogyStrategy(name)
        except ValueError:
            continue
        out[strategy] = ArmPosterior(successes=successes, failures=max(0, trials - successes))
    return out


__all__ = [
    "ArmPosterior",
    "PolicyDecision",
    "allowed_actions",
    "posteriors_from_report",
    "select_policy_action",
]
