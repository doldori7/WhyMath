"""정답 해설 오진단 측정 테스트 (MISC-27).

코퍼스 전수를 도는 테스트는 1건만 둔다(9초). 나머지는 합성 입력으로 순수 로직을 밟는다 —
분류 규칙·분모 없는 0 금지·CLI 종료 코드 3종.
"""

from __future__ import annotations

import pytest

from whymath_backend.harness.misconception_false_positive_eval import (
    FalsePositive,
    FalsePositiveReport,
    classify_cause,
    evaluate,
    format_report,
    load_answer_explanations,
    main,
)


def _fp(
    *,
    kebab_id: str = "division-by-zero",
    signals: tuple[str, ...] = ("분모", "0"),
    correction: bool = False,
) -> FalsePositive:
    return FalsePositive(
        kebab_id=kebab_id,
        confidence=1.0,
        matched_signals=signals,
        mentions_correction=correction,
        text="합성",
    )


class TestClassifyCause:
    """원인을 나누는 이유: 고칠 자리가 서로 다르다. 한 숫자에 섞으면 처방이 사라진다."""

    def test_regex_only_when_no_substring_matched(self) -> None:
        assert classify_cause(_fp(signals=())) == "regex-only"

    def test_weak_signals_only(self) -> None:
        """숫자-only signal만으로 full match된 경우 — 가장 순수한 신호 정밀도 결함."""
        assert classify_cause(_fp(kebab_id="exponent-zero", signals=("0",))) == "weak-signals-only"

    def test_weak_signal_mixed(self) -> None:
        """내용성 신호에 약한 토큰이 끼어 full match를 *완성*한 경우."""
        assert classify_cause(_fp(signals=("분모", "0"))) == "weak-signal-mixed"

    def test_two_signal_cooccurrence_when_all_contentful(self) -> None:
        """내용성 신호 2개짜리 항목 — 우연 공출현이 구조적으로 쉽다."""
        assert (
            classify_cause(_fp(kebab_id="composite-function-commutes", signals=("f∘g", "g∘f")))
            == "two-signal-cooccurrence"
        )

    def test_correction_mention_is_a_separate_axis_not_a_replacement(self) -> None:
        """정정 어휘 유무는 원인을 *대체*하지 않고 접미로 붙는다.

        해설이 오개념을 가르치려고 언급한 경우("…로 하면 틀린다")와 순수 오탐은 처방이
        다르다. 그런데 신호 유형 자체도 여전히 알아야 하므로 덮어쓰지 않고 덧붙인다 —
        접미가 아니라 치환이면 "약한 신호 때문인지"가 통계에서 사라진다.
        """
        assert classify_cause(_fp(correction=True)) == "weak-signal-mixed+correction-mention"
        assert classify_cause(_fp(signals=(), correction=True)) == "regex-only+correction-mention"


class TestReportArithmetic:
    def test_empty_population_ratio_is_none_not_zero(self) -> None:
        """모집단 0이면 비율은 `None`이다 — 0.0으로 두면 '완벽'으로 위장한다."""
        assert FalsePositiveReport(total=0, false_positives=()).fp_ratio is None

    def test_zero_false_positives_with_population_is_a_real_zero(self) -> None:
        """[대조군] 모집단이 있는데 오진단 0이면 그건 진짜 0이다(None이 아니다)."""
        assert FalsePositiveReport(total=10, false_positives=()).fp_ratio == 0.0

    def test_counts_group_by_cause_and_misconception(self) -> None:
        report = FalsePositiveReport(
            total=3,
            false_positives=(_fp(), _fp(), _fp(kebab_id="exponent-zero", signals=("0",))),
        )
        assert report.by_cause["weak-signal-mixed"] == 2
        assert report.by_misconception["division-by-zero"] == 2
        assert report.fp_ratio == 1.0


class TestEvaluateOnSyntheticText:
    def test_clean_prose_yields_no_false_positive(self) -> None:
        """오개념과 무관한 산문에는 후보가 안 나온다 — 측정기가 아무거나 잡지 않는다."""
        report = evaluate(["삼각형의 넓이는 밑변 곱하기 높이 나누기 2로 구한다."])
        assert report.total == 1
        assert report.false_positives == ()
        assert report.fp_ratio == 0.0

    def test_prose_that_trips_the_gate_is_counted_with_its_cause(self) -> None:
        """[결함 재현] 몫의 미분법 해설이 `division-by-zero`로 잡힌다 — 순수 오탐.

        `분모`와 `0`이 한 문장에 있을 뿐 나눗셈 오개념과 아무 관계가 없다. 이 문장이
        분류에서 `weak-signal-mixed`로 떨어지는 것이 이 도구의 존재 이유다.
        """
        text = "몫의 미분법에 따라 분자와 분모를 각각 미분해 조합하면 f'(-1)의 값은 0이다."
        report = evaluate([text])
        assert len(report.false_positives) == 1
        found = report.false_positives[0]
        assert found.kebab_id == "division-by-zero"
        assert found.cause == "weak-signal-mixed"


class TestRealCorpus:
    """실 코퍼스 1회 — 로더와 모집단이 살아 있는지(스캔 0건은 실패)."""

    def test_loader_finds_a_substantial_population(self) -> None:
        texts = load_answer_explanations()
        assert len(texts) > 5000, len(texts)
        assert len(texts) == len(set(texts)), "중복 제거가 안 됐다 — 비율이 생성기 물량에 좌우된다"

    def test_cli_ratchet_passes_at_the_wired_threshold(self) -> None:
        """CI가 쓰는 인자 그대로 exit 0 — 배선이 상시 red가 아님을 봉인한다."""
        assert main(["--max-fp-ratio", "0.07"]) == 0

    def test_cli_fails_when_threshold_is_unreachable(self) -> None:
        """[대조군] 도달 불가 임계를 주면 실제로 exit 1이 나온다(변별력 앵커).

        이 대조군이 없으면 "임계를 아예 안 본다"도 위 테스트를 통과한다.
        """
        assert main(["--max-fp-ratio", "0.0"]) == 1

    def test_cli_observes_without_a_threshold(self) -> None:
        """임계 미지정이면 관측만 하고 exit 0 — 기본이 게이트가 아님을 고정한다."""
        assert main([]) == 0

    def test_report_states_it_is_a_proxy_metric(self) -> None:
        """리포트가 대리 지표임을 본문에 밝힌다 — 학생 지표로 오인용되지 않게."""
        rendered = format_report(FalsePositiveReport(total=1, false_positives=()))
        assert "대리 지표" in rendered
        assert "학생 입력이 아니다" in rendered


@pytest.mark.parametrize("threshold", [0.0, 0.07])
def test_cli_exit_codes_are_only_zero_or_one_for_measurable_runs(threshold: float) -> None:
    """측정 가능한 실행의 종료 코드는 0/1뿐 — 2(측정 실패)는 모집단 0에만 쓴다."""
    assert main(["--max-fp-ratio", str(threshold)]) in (0, 1)
