"""L4 적응 교수법 policy — 안전제약·Thompson 표본 추출 단위테스트 (PED-03·hermetic).

핵심 관심사는 **교수학 #3 위반 전략이 policy 행동공간에서 배제되는가** 하나다(04d §3.3). 나머지
(사후분포·표본 추출)는 그 제약을 우회할 수 없음을 보이는 보조 검증이다.

- 행동공간은 `gate()`가 *그대로 통과*시킨 전략만 남긴다 — 강등 결과를 후보에 되돌리지 않는다.
- 행동공간이 비면 `None`(기권) — 임의 폴백 금지.
- **변별력**: 제약을 우회하면 배제 대상이 실제로 뽑힌다(제약이 장식이 아님).
"""

from __future__ import annotations

import random

from whymath_backend.l3.render.registry import registered_strategies
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.pedagogy.adaptive.policy import (
    ArmPosterior,
    allowed_actions,
    posteriors_from_report,
    select_policy_action,
)
from whymath_backend.l4.pedagogy.runtime_selector import StudentSignals, gate
from whymath_backend.schema.enums import PedagogyStrategy

# 시도 전 + 막힘 + 힌트 미상승 — PED-02 게이트 축②가 완전예제를 막는 상황.
_STUCK_PRE_ATTEMPT = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, turn_count=6)
# 힌트 미상승·막힘 아님 — 축② 미적용(완전예제 허용).
_FRESH = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, turn_count=0)


class TestActionSpace:
    def test_excludes_gated_strategy_when_stuck(self) -> None:
        """막힌 시도 전 학생에게 완전예제는 행동공간에서 빠진다(게이트 축② 집행)."""
        space = allowed_actions(_STUCK_PRE_ATTEMPT)
        assert PedagogyStrategy.WORKED_EXAMPLE not in space
        # 배제는 완전예제 축에 한정 — 다른 전략까지 싹 지우면 제약이 아니라 고장이다.
        assert PedagogyStrategy.SOCRATIC in space

    def test_allows_worked_example_when_gate_permits(self) -> None:
        """**변별력** — 게이트가 허용하는 상황에서는 같은 전략이 행동공간에 들어온다.

        위 테스트가 "항상 배제"라는 고장이 아님을 증명한다(조건이 바뀌면 판정도 바뀐다).
        """
        assert PedagogyStrategy.WORKED_EXAMPLE in allowed_actions(_FRESH)

    def test_space_is_subset_of_registered_adapters(self) -> None:
        """행동공간 ⊆ 등록 어댑터 — 렌더할 수 없는 전략을 고르면 소용이 없다."""
        assert allowed_actions(_FRESH) <= registered_strategies()

    def test_demoted_strategy_does_not_re_enter(self) -> None:
        """게이트가 *강등*한 전략은 후보에 되돌아오지 않는다(우회로 차단).

        `gate()`는 차단 시 다른 전략(SOCRATIC)으로 강등해 돌려주는데, 그 결과를 후보에 넣으면
        배제 대상이 강등을 경유해 살아 돌아온다. `allowed_actions`는 `verdict.strategy ==
        strategy`인 경우만 남겨 그 경로를 막는다.
        """
        verdict = gate(PedagogyStrategy.WORKED_EXAMPLE, _STUCK_PRE_ATTEMPT)
        assert verdict.strategy != PedagogyStrategy.WORKED_EXAMPLE  # 강등이 실제로 일어난다
        assert PedagogyStrategy.WORKED_EXAMPLE not in allowed_actions(_STUCK_PRE_ATTEMPT)


class TestThompsonSampling:
    def test_never_selects_outside_action_space(self) -> None:
        """사후분포를 배제 전략 쪽으로 극단 편향시켜도 뽑히지 않는다(구조적 차단).

        완전예제에 성공 1000/실패 0을 주면 보상 기준으로는 압도적이지만, 행동공간에 없으므로
        표본 추출 대상 자체가 아니다 — soft penalty였다면 뒤집혔을 상황이다.
        """
        posteriors = {PedagogyStrategy.WORKED_EXAMPLE: ArmPosterior(successes=1000, failures=0)}
        rng = random.Random(42)
        for _ in range(200):
            decision = select_policy_action(posteriors, _STUCK_PRE_ATTEMPT, rng=rng)
            assert decision is not None
            assert decision.strategy != PedagogyStrategy.WORKED_EXAMPLE
            assert decision.strategy in decision.action_space

    def test_favours_high_reward_arm_within_space(self) -> None:
        """허용 집합 안에서는 사후가 좋은 arm이 우세하게 뽑힌다(학습이 실제로 작동)."""
        posteriors = {
            PedagogyStrategy.ANALOGY: ArmPosterior(successes=200, failures=1),
            PedagogyStrategy.SOCRATIC: ArmPosterior(successes=1, failures=200),
        }
        rng = random.Random(7)
        picks = [select_policy_action(posteriors, _STUCK_PRE_ATTEMPT, rng=rng) for _ in range(100)]
        chosen = [p.strategy for p in picks if p is not None]
        assert chosen.count(PedagogyStrategy.ANALOGY) > chosen.count(PedagogyStrategy.SOCRATIC)

    def test_deterministic_under_seeded_rng(self) -> None:
        """같은 시드 → 같은 선택(테스트·재현성)."""
        posteriors: dict[PedagogyStrategy, ArmPosterior] = {}
        a = select_policy_action(posteriors, _FRESH, rng=random.Random(1))
        b = select_policy_action(posteriors, _FRESH, rng=random.Random(1))
        assert a is not None and b is not None
        assert a.strategy == b.strategy


class TestPosteriorAdapter:
    def test_maps_known_strategy_names(self) -> None:
        out = posteriors_from_report({"SOCRATIC": (7, 10)})
        assert out[PedagogyStrategy.SOCRATIC] == ArmPosterior(successes=7, failures=3)

    def test_drops_unknown_strategy_names(self) -> None:
        """enum 밖 문자열은 버린다 — 표기 오류가 배제 대상을 되살리지 못하게."""
        assert posteriors_from_report({"NOT_A_STRATEGY": (5, 5)}) == {}
