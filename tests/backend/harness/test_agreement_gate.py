"""WH-1 2단계 종료 게이트(`harness/agreement_gate.py`) — 단위(hermetic·순수·결정론).

§8.4 2단계 종료 기준(진단-실제 일치율 *유의 개선*)의 McNemar 판정을 DB·임베딩 없이 검증한다:
단측 정확 이항 p값·IMPROVED/NOT_IMPROVED/NO_DATA verdict·과소표본 거짓 PASS 0·substring
베이스라인 매처·라벨 프로브 결선. 후보 매처는 *합성*을 주입해 결정론으로 본다(임베딩 비의존).
"""

from __future__ import annotations

from whymath_backend.harness.agreement_gate import (
    AgreementVerdict,
    Phase2ExitVerdict,
    PrecisionVerdict,
    _mcnemar_one_sided_p,
    evaluate_agreement_gate,
    evaluate_phase2_exit,
    evaluate_precision_guard,
    run_agreement_gate,
    run_precision_guard,
    substring_matcher,
)

# diagnose가 confidence 1.0으로 잡는 실 신호·실 카탈로그 id.
_MATCH_TEXT = "(a+b) a² + b²"
_MID = "distribution-over-power"


class TestMcNemarExact:
    def test_known_values(self) -> None:
        """단측 정확 이항 — 알려진 값(Σ_{k=c}^{n} C(n,k)·0.5ⁿ)."""
        assert _mcnemar_one_sided_p(0, 5) == 0.5**5  # 0.03125
        assert _mcnemar_one_sided_p(0, 4) == 0.5**4  # 0.0625
        assert abs(_mcnemar_one_sided_p(2, 8) - 56 / 1024) < 1e-12  # (45+10+1)/1024
        assert _mcnemar_one_sided_p(0, 0) == 1.0  # 불일치쌍 없음 → 차이 증거 없음

    def test_symmetric_half(self) -> None:
        """b==c면 p ~ 0.5 근방(대칭·후보 우세 증거 약함)."""
        assert _mcnemar_one_sided_p(3, 3) > 0.5  # P(X>=c) with c=n/2 포함경계 → >0.5

    def test_more_candidate_lower_p(self) -> None:
        """c가 클수록(후보가 더 맞춤) p 단조 감소."""
        assert _mcnemar_one_sided_p(1, 9) < _mcnemar_one_sided_p(4, 6)


class TestEvaluateGate:
    def test_significant_improvement(self) -> None:
        """5쌍 모두 후보만 맞춤 → p=0.03125<0.05 → IMPROVED."""
        gate = evaluate_agreement_gate([(False, True)] * 5)
        assert gate.verdict is AgreementVerdict.IMPROVED
        assert gate.candidate_recall == 1.0 and gate.baseline_recall == 0.0
        assert gate.discordant_candidate_only == 5 and gate.discordant_baseline_only == 0
        assert gate.p_value is not None and gate.p_value < 0.05

    def test_equal_not_improved(self) -> None:
        """둘 다 동일하게 맞춤 → 불일치쌍 0·동등 → NOT_IMPROVED."""
        gate = evaluate_agreement_gate([(True, True)] * 6)
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED
        assert gate.baseline_recall == gate.candidate_recall == 1.0
        assert gate.p_value == 1.0

    def test_candidate_worse_not_improved(self) -> None:
        """후보가 더 못 맞춤 → NOT_IMPROVED."""
        gate = evaluate_agreement_gate([(True, False)] * 5)
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED
        assert gate.candidate_recall == 0.0 and gate.baseline_recall == 1.0

    def test_improved_but_underpowered_not_improved(self) -> None:
        """개선이나 과소표본(불일치쌍 4) → p=0.0625>0.05 → NOT_IMPROVED(거짓 PASS 0)."""
        gate = evaluate_agreement_gate([(False, True)] * 4 + [(True, True)])
        assert gate.candidate_recall is not None and gate.baseline_recall is not None
        assert gate.candidate_recall > gate.baseline_recall  # 개선은 맞음
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED  # 그러나 비유의
        assert gate.p_value is not None and gate.p_value >= 0.05

    def test_custom_alpha_flips_verdict(self) -> None:
        """같은 데이터라도 alpha=0.1이면 p=0.0625<0.1 → IMPROVED."""
        paired = [(False, True)] * 4 + [(True, True)]
        assert evaluate_agreement_gate(paired, alpha=0.1).verdict is AgreementVerdict.IMPROVED

    def test_below_min_probes_no_data(self) -> None:
        """프로브 < min_probes → NO_DATA(판정 보류·p None·일치율은 참고 채움)."""
        gate = evaluate_agreement_gate([(False, True)] * 3)
        assert gate.verdict is AgreementVerdict.NO_DATA
        assert gate.p_value is None
        assert gate.candidate_recall == 1.0  # 참고값은 채우되 verdict 보류

    def test_empty_no_data(self) -> None:
        """프로브 0 → NO_DATA·recall None."""
        gate = evaluate_agreement_gate([])
        assert gate.verdict is AgreementVerdict.NO_DATA
        assert gate.baseline_recall is None and gate.candidate_recall is None
        assert gate.n_probes == 0


class TestSubstringMatcher:
    def test_returns_top1_id_on_match(self) -> None:
        """매칭되는 진술 → diagnose top-1 오개념 id."""
        assert substring_matcher(_MATCH_TEXT) == _MID

    def test_returns_none_on_no_match(self) -> None:
        """매칭 0 → None(억지 매칭 금지)."""
        assert substring_matcher("오늘 점심은 맛있었다") is None


class TestRunAgreementGate:
    def test_synthetic_candidate_beats_baseline(self) -> None:
        """합성 프로브 — 베이스라인 전부 miss·후보 전부 hit → IMPROVED."""
        probes = [(f"s{i}", "A") for i in range(5)]
        gate = run_agreement_gate(
            candidate=lambda _s: "A",
            baseline=lambda _s: None,
            probes=probes,
        )
        assert gate.verdict is AgreementVerdict.IMPROVED
        assert gate.n_probes == 5

    def test_candidate_none_counts_as_miss(self) -> None:
        """후보가 None 반환(매치 0) → 그 프로브 miss → 동등(둘 다 miss)·NOT_IMPROVED."""
        probes = [(f"s{i}", "A") for i in range(5)]
        gate = run_agreement_gate(
            candidate=lambda _s: None,
            baseline=lambda _s: None,
            probes=probes,
        )
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED
        assert gate.candidate_recall == 0.0 and gate.baseline_recall == 0.0

    def test_default_substring_baseline_over_default_probes(self) -> None:
        """기본 경로 — 라벨 프로브셋(probes=None)·substring 동일 매처 → NOT_IMPROVED."""
        gate = run_agreement_gate(candidate=substring_matcher)
        # substring vs substring(동일 매처) → 불일치쌍 0 → 동등 → NOT_IMPROVED.
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED
        assert gate.n_probes > 0  # 실 라벨 프로브셋 로드됨
        assert gate.baseline_recall == gate.candidate_recall


class TestEvaluatePrecisionGuard:
    """FP 프로브(올바른 진술)에서 후보 거짓양성 회귀 판정 — True=오매칭(나쁨)."""

    def test_candidate_adds_false_positives_regressed(self) -> None:
        """후보만 5건 새 오매칭 → p=0.03125<0.05 → REGRESSED(정확성 #1 위반 위험)."""
        guard = evaluate_precision_guard([(False, True)] * 5)
        assert guard.verdict is PrecisionVerdict.REGRESSED
        assert guard.candidate_fp_rate == 1.0 and guard.baseline_fp_rate == 0.0
        assert guard.discordant_candidate_only == 5 and guard.discordant_baseline_only == 0
        assert guard.p_value is not None and guard.p_value < 0.05

    def test_candidate_reduces_false_positives_no_regression(self) -> None:
        """후보가 오매칭을 줄임(베이스라인만 오매칭) → 무회귀."""
        guard = evaluate_precision_guard([(True, False)] * 5)
        assert guard.verdict is PrecisionVerdict.NO_REGRESSION
        assert guard.candidate_fp_rate == 0.0 and guard.baseline_fp_rate == 1.0

    def test_equal_no_regression(self) -> None:
        """둘 다 동일 오매칭 → 불일치쌍 0 → 무회귀·p=1.0."""
        guard = evaluate_precision_guard([(True, True)] * 6)
        assert guard.verdict is PrecisionVerdict.NO_REGRESSION
        assert guard.p_value == 1.0

    def test_worse_but_underpowered_no_regression(self) -> None:
        """후보 악화나 과소표본(불일치쌍 4) → p=0.0625>0.05 → 무회귀(거짓 FAIL 0)."""
        guard = evaluate_precision_guard([(False, True)] * 4 + [(True, True)])
        assert guard.candidate_fp_rate is not None and guard.baseline_fp_rate is not None
        assert guard.candidate_fp_rate > guard.baseline_fp_rate  # 악화는 맞음
        assert guard.verdict is PrecisionVerdict.NO_REGRESSION  # 그러나 비유의
        assert guard.p_value is not None and guard.p_value >= 0.05

    def test_below_min_probes_no_data(self) -> None:
        """FP 프로브 < min_probes → NO_DATA(판정 보류·p None·FP율은 참고 채움)."""
        guard = evaluate_precision_guard([(False, True)] * 3)
        assert guard.verdict is PrecisionVerdict.NO_DATA
        assert guard.p_value is None
        assert guard.candidate_fp_rate == 1.0

    def test_custom_alpha_flips_regression(self) -> None:
        """같은 데이터라도 alpha=0.1이면 p=0.0625<0.1 → REGRESSED."""
        paired = [(False, True)] * 4 + [(True, True)]
        assert evaluate_precision_guard(paired, alpha=0.1).verdict is PrecisionVerdict.REGRESSED


class TestRunPrecisionGuard:
    def test_synthetic_candidate_adds_fps(self) -> None:
        """합성 FP 프로브 — 베이스라인 침묵·후보 전부 오매칭 → REGRESSED."""
        fp_probes = [f"올바른 진술 {i}" for i in range(5)]
        guard = run_precision_guard(
            candidate=lambda _s: "X",  # 항상 오개념 붙임(올바른 진술이므로 거짓양성)
            baseline=lambda _s: None,  # 침묵
            fp_probes=fp_probes,
        )
        assert guard.verdict is PrecisionVerdict.REGRESSED
        assert guard.n_probes == 5

    def test_default_substring_baseline_over_default_fp_probes(self) -> None:
        """기본 경로 — 실 FP 프로브셋·substring 동일 매처 → 불일치쌍 0 → 무회귀."""
        guard = run_precision_guard(candidate=substring_matcher)
        assert guard.verdict is PrecisionVerdict.NO_REGRESSION
        assert guard.n_probes > 0  # 실 FP 프로브셋 로드됨(33)
        assert guard.baseline_fp_rate == guard.candidate_fp_rate
        assert guard.baseline_fp_rate is not None and guard.baseline_fp_rate > 0  # substring FP 큼


class TestEvaluatePhase2Exit:
    """결합 — recall 유의 개선 AND 정밀도 무회귀일 때만 READY."""

    def test_improved_and_no_regression_ready(self) -> None:
        recall = evaluate_agreement_gate([(False, True)] * 5)  # IMPROVED
        precision = evaluate_precision_guard([(True, False)] * 5)  # NO_REGRESSION
        exit_ = evaluate_phase2_exit(recall, precision)
        assert exit_.verdict is Phase2ExitVerdict.READY
        assert exit_.recall_verdict is AgreementVerdict.IMPROVED
        assert exit_.precision_verdict is PrecisionVerdict.NO_REGRESSION

    def test_improved_but_precision_regressed_not_ready(self) -> None:
        """★ 핵심 안전: recall 개선이어도 정밀도 회귀면 NOT_READY(정밀도가 recall 덮어씀)."""
        recall = evaluate_agreement_gate([(False, True)] * 5)  # IMPROVED
        precision = evaluate_precision_guard([(False, True)] * 5)  # REGRESSED
        exit_ = evaluate_phase2_exit(recall, precision)
        assert exit_.verdict is Phase2ExitVerdict.NOT_READY

    def test_not_improved_recall_not_ready(self) -> None:
        recall = evaluate_agreement_gate([(True, True)] * 5)  # NOT_IMPROVED
        precision = evaluate_precision_guard([(True, False)] * 5)  # NO_REGRESSION
        assert evaluate_phase2_exit(recall, precision).verdict is Phase2ExitVerdict.NOT_READY

    def test_recall_no_data_propagates_no_data(self) -> None:
        recall = evaluate_agreement_gate([(False, True)] * 3)  # NO_DATA
        precision = evaluate_precision_guard([(True, False)] * 5)  # NO_REGRESSION
        assert evaluate_phase2_exit(recall, precision).verdict is Phase2ExitVerdict.NO_DATA

    def test_precision_no_data_propagates_no_data(self) -> None:
        recall = evaluate_agreement_gate([(False, True)] * 5)  # IMPROVED
        precision = evaluate_precision_guard([(False, True)] * 3)  # NO_DATA
        assert evaluate_phase2_exit(recall, precision).verdict is Phase2ExitVerdict.NO_DATA
