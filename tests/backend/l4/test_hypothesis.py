"""L4 활성 오개념 가설 세트 — 감쇠·강화·ε-규칙 단위테스트 (hermetic·순수·결정론).

WH-1 §8.4 2단계 *핵심 결정 로직*. `decay`/`reinforce`/`update_hypotheses`/`select_focus`를
직접 호출해 반감기·단조성·클램프·가지치기·정렬·입력 비변형·ε-규칙(주입 rng 결정론)을 검증한다
(실 SQL·async·전역 random 불요·순수 함수). canned `MisconceptionMatch`는 *실 모델*로 만든다.

**정직 스코프**: 영속(misconception_hypothesis 테이블·evidence_links 개인정보 스키마)·coach
결선·진단-실제 일치율 게이트는 후속 — 본 테스트는 순수 결정 로직만 검증.
"""

from __future__ import annotations

import random

from whymath_backend.l4.misconception.hypothesis import (
    MisconceptionHypothesis,
    decay,
    reinforce,
    select_focus,
    update_hypotheses,
)
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch


def _mc(mid: str) -> Misconception:
    """테스트용 실 `Misconception`(카탈로그 형식 — id만 의미·나머지는 형식 충족)."""
    return Misconception(
        id=mid,
        name_kr="테스트 오개념",
        domain="대수",
        canonical_statement="(a+b)² = a²+b²",
        counterexample="a=1, b=1",
        signals=("(a+b)^2",),
    )


def _match(mid: str, confidence: float) -> MisconceptionMatch:
    """테스트용 실 `MisconceptionMatch`(증거 1건)."""
    return MisconceptionMatch(misconception=_mc(mid), confidence=confidence)


def _hyp(mid: str, confidence: float, *, turns: int = 0, count: int = 1) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid,
        confidence=confidence,
        turns_since_evidence=turns,
        evidence_count=count,
    )


class TestDecay:
    def test_zero_turns_unchanged(self) -> None:
        """0턴 경과 → 불변(곱 1.0)."""
        assert decay(0.8, 0) == 0.8

    def test_half_life_halves(self) -> None:
        """반감기(기본 5턴) 경과 → 절반."""
        assert decay(0.8, 5) == 0.4

    def test_two_half_lives_quarter(self) -> None:
        """반감기 2배 → 1/4."""
        assert abs(decay(0.8, 10) - 0.2) < 1e-9

    def test_monotone_decreasing(self) -> None:
        """턴 증가 → 단조 감소."""
        seq = [decay(0.9, t) for t in range(0, 12)]
        assert all(later <= earlier for earlier, later in zip(seq, seq[1:], strict=False))

    def test_clamped_in_unit_interval(self) -> None:
        """결과는 [0,1] 범위."""
        assert 0.0 <= decay(1.0, 30) <= 1.0
        assert decay(0.0, 3) == 0.0

    def test_custom_half_life(self) -> None:
        """주입 반감기 사용 — 2턴 반감기에서 2턴 경과 시 절반."""
        assert decay(0.6, 2, half_life=2) == 0.3


class TestReinforce:
    def test_monotone_increasing(self) -> None:
        """강화는 단조 증가(절대 깎지 않음)."""
        assert reinforce(0.5, 0.4) >= 0.5

    def test_evidence_zero_unchanged(self) -> None:
        """evidence_confidence=0 → 불변."""
        assert reinforce(0.5, 0.0) == 0.5

    def test_evidence_one_saturates(self) -> None:
        """evidence_confidence=1 → 1로 포화."""
        assert reinforce(0.3, 1.0) == 1.0

    def test_formula(self) -> None:
        """0.5 + (1-0.5)*0.4 = 0.7."""
        assert abs(reinforce(0.5, 0.4) - 0.7) < 1e-9

    def test_clamped_at_one(self) -> None:
        """결과는 1 이하."""
        assert reinforce(0.99, 1.0) == 1.0


class TestUpdateHypotheses:
    def test_existing_decayed_and_turns_incremented(self) -> None:
        """매치 없는 기존 가설 → 감쇠 + turns_since_evidence 증가."""
        current = [_hyp("m1", 0.8, turns=0, count=2)]
        out = update_hypotheses(current, [], turns_elapsed=5)
        assert len(out) == 1
        assert out[0].misconception_id == "m1"
        assert out[0].confidence == 0.4  # 반감기 5턴
        assert out[0].turns_since_evidence == 5
        assert out[0].evidence_count == 2  # 증거 없으니 불변

    def test_match_reinforces_existing(self) -> None:
        """동일 id 매치 → 강화·turns_since=0·evidence_count++."""
        current = [_hyp("m1", 0.8, turns=3, count=2)]
        # 먼저 1턴 감쇠 후 강화: decay(0.8,1)=0.8*0.5**0.2, 그 위에 reinforce(.,0.5).
        out = update_hypotheses(current, [_match("m1", 0.5)], turns_elapsed=1)
        decayed = 0.8 * 0.5 ** (1 / 5)
        expected = decayed + (1 - decayed) * 0.5
        assert len(out) == 1
        assert abs(out[0].confidence - expected) < 1e-9
        assert out[0].turns_since_evidence == 0
        assert out[0].evidence_count == 3

    def test_new_match_added(self) -> None:
        """기존에 없는 id 매치 → 신규 가설 추가."""
        out = update_hypotheses([], [_match("m2", 0.6)], turns_elapsed=1)
        assert len(out) == 1
        assert out[0].misconception_id == "m2"
        assert out[0].confidence == 0.6
        assert out[0].turns_since_evidence == 0
        assert out[0].evidence_count == 1

    def test_prunes_below_threshold(self) -> None:
        """감쇠로 임계(0.1) 미만이 된 가설 가지치기."""
        current = [_hyp("low", 0.12, turns=0, count=1)]
        # decay(0.12, 5) = 0.06 < 0.1 → 제거.
        out = update_hypotheses(current, [], turns_elapsed=5)
        assert out == []

    def test_sorted_descending(self) -> None:
        """confidence 내림차순 정렬."""
        current = [_hyp("a", 0.3), _hyp("b", 0.9), _hyp("c", 0.6)]
        out = update_hypotheses(current, [], turns_elapsed=0)
        confs = [h.confidence for h in out]
        assert confs == sorted(confs, reverse=True)
        assert out[0].misconception_id == "b"

    def test_input_not_mutated(self) -> None:
        """입력 비변형 — frozen 가설·새 리스트 반환."""
        current = [_hyp("m1", 0.8, turns=0, count=1)]
        snapshot = (current[0].confidence, current[0].turns_since_evidence)
        out = update_hypotheses(current, [_match("m1", 0.4)], turns_elapsed=3)
        assert (current[0].confidence, current[0].turns_since_evidence) == snapshot
        assert out is not current

    def test_mixed_reinforce_new_and_prune(self) -> None:
        """혼합 — 강화·신규·가지치기·정렬 동시."""
        current = [_hyp("keep", 0.8), _hyp("fade", 0.11)]
        out = update_hypotheses(
            current, [_match("keep", 0.5), _match("fresh", 0.7)], turns_elapsed=5
        )
        ids = {h.misconception_id for h in out}
        assert "fade" not in ids  # decay(0.11,5)=0.055 < 0.1
        assert "keep" in ids and "fresh" in ids
        # 정렬 확인.
        confs = [h.confidence for h in out]
        assert confs == sorted(confs, reverse=True)


class TestSelectFocus:
    def test_empty_returns_none(self) -> None:
        """빈 입력 → None."""
        assert select_focus([]) is None

    def test_no_rng_always_top(self) -> None:
        """rng=None → 항상 최상위(탐색 안 함·결정론)."""
        hyps = [_hyp("top", 0.9), _hyp("mid", 0.5), _hyp("low", 0.2)]
        for _ in range(5):
            result = select_focus(hyps)
            assert result is not None and result.misconception_id == "top"

    def test_epsilon_zero_always_top(self) -> None:
        """epsilon=0 → 탐색 확률 0이라 항상 최상위(rng 있어도)."""
        hyps = [_hyp("top", 0.9), _hyp("mid", 0.5)]
        rng = random.Random(0)
        for _ in range(10):
            result = select_focus(hyps, epsilon=0.0, rng=rng)
            assert result is not None and result.misconception_id == "top"

    def test_single_hypothesis_returns_it(self) -> None:
        """원소 1개 → 탐색 불가·항상 그것(rng 있어도 폴백)."""
        hyps = [_hyp("only", 0.9)]
        rng = random.Random(0)
        result = select_focus(hyps, epsilon=1.0, rng=rng)
        assert result is not None and result.misconception_id == "only"

    def test_seeded_exploration_deterministic(self) -> None:
        """시드 rng로 탐색 결정론 — epsilon=1이면 항상 차순위에서 무작위 1개."""
        hyps = [_hyp("top", 0.9), _hyp("mid", 0.5), _hyp("low", 0.2)]
        rng = random.Random(42)
        results = []
        for _ in range(8):
            r = select_focus(hyps, epsilon=1.0, rng=rng)
            assert r is not None
            results.append(r.misconception_id)
        # epsilon=1 → 전부 차순위(top 제외)에서 선택.
        assert all(r in {"mid", "low"} for r in results)
        # 동일 시드 재현 → 동일 시퀀스(결정론).
        rng2 = random.Random(42)
        results2 = []
        for _ in range(8):
            r = select_focus(hyps, epsilon=1.0, rng=rng2)
            assert r is not None
            results2.append(r.misconception_id)
        assert results == results2

    def test_exploit_vs_explore_mix(self) -> None:
        """중간 epsilon → 활용·탐색 혼합(시드 결정론)."""
        hyps = [_hyp("top", 0.9), _hyp("mid", 0.5)]
        rng = random.Random(7)
        results = []
        for _ in range(20):
            r = select_focus(hyps, epsilon=0.5, rng=rng)
            assert r is not None
            results.append(r.misconception_id)
        assert "top" in results  # 활용 발생
        assert "mid" in results  # 탐색 발생
