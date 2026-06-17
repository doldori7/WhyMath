"""WH-1 진단 프로브 선택(`l4/misconception/probe_selection.py`) — 단위(hermetic·순수·결정론).

§3 도구6(`select_probe`)·§3.2(정보이득 근사)·§2.2 규칙2(ε-탐색)의 순수 결정 로직을 직접
호출해 검증한다(DB·async·전역 random·임베딩 불요). `item_information`(L2 IRT)을 재사용하므로
정보량 최대=난이도가 θ에 가까운 문항·태그 판별·ε 주기·동률 tiebreak를 결정론으로 확인한다.

**정직 스코프**: 문제은행 적재·문항-오개념 태그 스키마·ε 카운터 영속·진단 신뢰도 상한 0.9
집행은 후속(하네스) — 본 테스트는 순수 선택 로직만 검증한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import (
    ProbeCandidate,
    ProbeSelection,
    ProbeTarget,
    discriminates,
    is_exploration_turn,
    plan_probe,
    resolve_probe_target,
    select_probe,
)


def _cand(
    pid: str, difficulty: float, tags: set[str], *, discrimination: float = 1.0
) -> ProbeCandidate:
    return ProbeCandidate(
        problem_id=pid,
        difficulty=difficulty,
        discrimination=discrimination,
        misconception_tags=frozenset(tags),
    )


def _hyp(mid: str, confidence: float) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=confidence, turns_since_evidence=0, evidence_count=1
    )


class TestIsExplorationTurn:
    def test_period_multiples_true(self) -> None:
        """주기(기본 5)의 양의 배수 턴 → 탐색 강제."""
        assert is_exploration_turn(5)
        assert is_exploration_turn(10)

    def test_non_multiples_false(self) -> None:
        """배수가 아니면 False."""
        assert not is_exploration_turn(1)
        assert not is_exploration_turn(4)
        assert not is_exploration_turn(6)

    def test_turn_zero_or_negative_false(self) -> None:
        """턴 인덱스 < 1(미시작)이면 False(0%period==0이라도)."""
        assert not is_exploration_turn(0)
        assert not is_exploration_turn(-5)

    def test_custom_period(self) -> None:
        """주입 주기 — 3턴마다."""
        assert is_exploration_turn(3, period=3)
        assert not is_exploration_turn(5, period=3)

    def test_nonpositive_period_raises(self) -> None:
        """주기 <= 0 → ValueError."""
        with pytest.raises(ValueError, match="period"):
            is_exploration_turn(5, period=0)


class TestDiscriminates:
    def test_target_present_competing_absent_true(self) -> None:
        """target 태그 있고 경쟁 태그 없음 → 판별 가능."""
        assert discriminates(frozenset({"A"}), "A")
        assert discriminates(frozenset({"A", "X"}), "A", competing_mids=frozenset({"B"}))

    def test_target_absent_false(self) -> None:
        """target 태그 없음 → 판별 불가."""
        assert not discriminates(frozenset({"B"}), "A")

    def test_competing_present_false(self) -> None:
        """경쟁 태그가 하나라도 있으면 → 교란으로 판별 불가."""
        assert not discriminates(frozenset({"A", "B"}), "A", competing_mids=frozenset({"B"}))

    def test_target_also_in_competing_false(self) -> None:
        """모순 입력(target이 competing에도) → 교집합 검사 우선 False(안전)."""
        assert not discriminates(frozenset({"A"}), "A", competing_mids=frozenset({"A"}))


class TestProbeCandidate:
    def test_as_irt_item_maps_params(self) -> None:
        """IrtItem 변환 — difficulty·discrimination 1:1."""
        item = _cand("p1", 0.5, {"A"}, discrimination=1.4).as_irt_item()
        assert item.difficulty == 0.5
        assert item.discrimination == 1.4


class TestSelectProbe:
    def test_picks_max_information_near_theta(self) -> None:
        """판별 후보 중 난이도가 θ에 가까운(정보량 최대) 문항 선택."""
        cands = [
            _cand("near", 0.0, {"A"}),  # θ=0 → P=0.5 → 정보 최대
            _cand("far", 2.5, {"A"}),  # θ에서 멀어 정보 적음
        ]
        target = ProbeTarget(target_misconception_id="A")
        out = select_probe(cands, target, theta=0.0)
        assert out is not None
        assert out.problem_id == "near"
        assert out.target_misconception_id == "A"
        assert out.information > 0.0

    def test_skips_non_discriminating(self) -> None:
        """target 태그 없는·경쟁 태그 든 문항은 제외."""
        cands = [
            _cand("noA", 0.0, {"B"}),  # A 없음
            _cand("hasC", 0.0, {"A", "C"}),  # 경쟁 C 있음
            _cand("clean", 0.5, {"A"}),  # 유일한 판별 후보
        ]
        target = ProbeTarget(target_misconception_id="A", competing_mids=frozenset({"C"}))
        out = select_probe(cands, target, theta=0.0)
        assert out is not None and out.problem_id == "clean"

    def test_excludes_administered(self) -> None:
        """이미 출제한 problem_id는 제외하고 차선 선택."""
        cands = [_cand("near", 0.0, {"A"}), _cand("far", 1.5, {"A"})]
        target = ProbeTarget(target_misconception_id="A")
        out = select_probe(cands, target, theta=0.0, administered=frozenset({"near"}))
        assert out is not None and out.problem_id == "far"

    def test_no_candidate_returns_none(self) -> None:
        """판별 후보가 없으면 None(억지 매칭 금지)."""
        cands = [_cand("noA", 0.0, {"B"})]
        target = ProbeTarget(target_misconception_id="A")
        assert select_probe(cands, target, theta=0.0) is None

    def test_empty_returns_none(self) -> None:
        """빈 후보 → None."""
        target = ProbeTarget(target_misconception_id="A")
        assert select_probe([], target, theta=0.0) is None

    def test_deterministic_tiebreak_by_problem_id(self) -> None:
        """동일 정보량 동률 → problem_id 사전식 더 작은 쪽(입력 순서 무관)."""
        target = ProbeTarget(target_misconception_id="A")
        # 같은 난이도·변별도 → 정보량 동일. 입력 순서를 뒤집어도 'a'가 이긴다.
        out1 = select_probe([_cand("z", 0.0, {"A"}), _cand("a", 0.0, {"A"})], target, theta=0.0)
        out2 = select_probe([_cand("a", 0.0, {"A"}), _cand("z", 0.0, {"A"})], target, theta=0.0)
        assert out1 is not None and out2 is not None
        assert out1.problem_id == "a" and out2.problem_id == "a"

    def test_propagates_is_exploration(self) -> None:
        """타깃의 is_exploration을 결과에 전파."""
        target = ProbeTarget(target_misconception_id="A", is_exploration=True)
        out = select_probe([_cand("p", 0.0, {"A"})], target, theta=0.0)
        assert out is not None and out.is_exploration is True


class TestResolveProbeTarget:
    def test_exploit_targets_top_competes_rest(self) -> None:
        """비탐색 턴 → 최상위 가설 겨냥·나머지 활성은 competing 배제."""
        active = [_hyp("top", 0.8), _hyp("mid", 0.5), _hyp("low", 0.3)]
        target = resolve_probe_target(active, [], turn_index=1)
        assert target is not None
        assert target.target_misconception_id == "top"
        assert target.competing_mids == frozenset({"mid", "low"})
        assert target.is_exploration is False

    def test_explore_turn_targets_outside(self) -> None:
        """탐색 턴(주기 배수) + 외부 후보 → 외부 겨냥·활성 전체 competing·is_exploration."""
        active = [_hyp("top", 0.8)]
        target = resolve_probe_target(active, ["outsider"], turn_index=5)
        assert target is not None
        assert target.target_misconception_id == "outsider"
        assert target.competing_mids == frozenset({"top"})
        assert target.is_exploration is True

    def test_explore_turn_no_outside_falls_back_to_exploit(self) -> None:
        """탐색 턴이지만 외부 후보 없음 → 활용(최상위)로 폴백."""
        active = [_hyp("top", 0.8)]
        target = resolve_probe_target(active, [], turn_index=5)
        assert target is not None
        assert target.target_misconception_id == "top"
        assert target.is_exploration is False

    def test_no_active_uses_outside(self) -> None:
        """활성 가설 없음 + 외부 후보 → 외부 겨냥(탐색/활용 무의미·주기만 반영)."""
        target = resolve_probe_target([], ["o1", "o2"], turn_index=1)
        assert target is not None
        assert target.target_misconception_id == "o1"
        assert target.competing_mids == frozenset()
        assert target.is_exploration is False

    def test_all_empty_returns_none(self) -> None:
        """활성·외부 모두 없음 → None(겨냥 대상 없음)."""
        assert resolve_probe_target([], [], turn_index=1) is None


class TestPlanProbe:
    def test_exploit_end_to_end(self) -> None:
        """활용 턴 — 최상위 가설을 판별하는 정보량 최대 문항."""
        active = [_hyp("A", 0.8), _hyp("B", 0.5)]
        cands = [
            _cand("pA_near", 0.0, {"A"}),  # A판별·θ근처
            _cand("pA_far", 2.0, {"A"}),
            _cand("pAB", 0.0, {"A", "B"}),  # 경쟁 B 있어 제외
            _cand("pB", 0.0, {"B"}),  # A 없어 제외
        ]
        out = plan_probe(cands, active, [], theta=0.0, turn_index=1)
        assert isinstance(out, ProbeSelection)
        assert out.problem_id == "pA_near"
        assert out.target_misconception_id == "A"
        assert out.is_exploration is False

    def test_explore_end_to_end(self) -> None:
        """탐색 턴 — 외부 오개념을 판별하는 문항."""
        active = [_hyp("A", 0.8)]
        cands = [_cand("pOut", 0.0, {"OUT"}), _cand("pA", 0.0, {"A"})]
        out = plan_probe(cands, active, ["OUT"], theta=0.0, turn_index=5)
        assert out is not None
        assert out.problem_id == "pOut"
        assert out.target_misconception_id == "OUT"
        assert out.is_exploration is True

    def test_none_when_no_target(self) -> None:
        """겨냥 대상 없음(활성·외부 0) → None."""
        assert plan_probe([_cand("p", 0.0, {"A"})], [], [], theta=0.0, turn_index=1) is None

    def test_none_when_no_discriminating_candidate(self) -> None:
        """타깃은 정해지나 판별 문항이 없으면 → None."""
        active = [_hyp("A", 0.8)]
        cands = [_cand("pB", 0.0, {"B"})]  # A 판별 문항 없음
        assert plan_probe(cands, active, [], theta=0.0, turn_index=1) is None
