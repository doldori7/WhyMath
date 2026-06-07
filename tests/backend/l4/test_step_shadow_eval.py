"""L4 step_shadow_eval 단위테스트 — A/B 후보 precision eval 하니스(오프라인·비노출).

load_labels(JSONL)·evaluate(지표·0나눗셈)·format_report·CLI(main·게이트)·시드 코퍼스 스모크를 검증.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from whymath_backend.l4.step_shadow import candidate_for_verdict
from whymath_backend.l4.step_shadow_eval import (
    StepBreakLabel,
    evaluate,
    format_report,
    load_labels,
    main,
)

# 배포 시드 코퍼스(repo 루트 data/corpus/) — 테스트는 src/backend에서 돌지만 파일은 루트에 있다.
_SEED = (
    Path(__file__).resolve().parents[3] / "data" / "corpus" / "step_break_ab_seed_v1.jsonl"
)


def _label(
    before: str,
    after: str,
    expected: str | None,
    human: Literal["A", "B"],
) -> StepBreakLabel:
    return StepBreakLabel(
        solset_before=before,
        solset_after=after,
        expected_answer=expected,
        human_label=human,
    )


class TestLoadLabels:
    def test_parses_and_skips_blank_and_comments(self) -> None:
        text = (
            "# comment\n"
            "\n"
            '{"solset_before": "{3}", "solset_after": "{4}", '
            '"expected_answer": "3", "human_label": "A"}\n'
            "   \n"
            '{"solset_before": "{2}", "solset_after": "{5}", '
            '"expected_answer": "2", "human_label": "B"}\n'
        )
        labels = load_labels(text)
        assert len(labels) == 2
        assert labels[0].human_label == "A" and labels[0].solset_before == "{3}"
        assert labels[1].expected_answer == "2"

    def test_invalid_json_raises_with_line_number(self) -> None:
        text = (
            '{"solset_before": "{3}", "solset_after": "{4}", "human_label": "A"}\n'
            "{ not json }\n"
        )
        with pytest.raises(ValueError, match="line 2"):
            load_labels(text)

    def test_unknown_field_forbidden(self) -> None:
        # extra="forbid" — 오타/미정의 필드는 거부.
        with pytest.raises(ValueError, match="line 1"):
            load_labels(
                '{"solset_before": "{3}", "solset_after": "{4}", '
                '"human_label": "A", "oops": 1}\n'
            )

    def test_invalid_label_rejected(self) -> None:
        with pytest.raises(ValueError, match="line 1"):
            load_labels('{"solset_before": "{3}", "solset_after": "{4}", "human_label": "C"}\n')


class TestEvaluate:
    def test_diverged_label_a_is_true_positive(self) -> None:
        rep = evaluate([_label("{3}", "{4}", "3", "A")])
        assert rep.total == 1
        o = rep.items[0]
        assert o.verdict == "diverged_from_answer" and o.candidate == "A"
        assert o.predicted_a and o.actual_a
        assert rep.true_positive == 1 and rep.precision == 1.0 and rep.recall == 1.0

    def test_diverged_label_b_is_false_positive(self) -> None:
        rep = evaluate([_label("{3}", "{4}", "3", "B")])
        assert rep.false_positive == 1
        assert rep.precision == 0.0  # 0/(0+1)
        assert rep.recall is None  # TP+FN == 0 → 미정

    def test_reached_is_true_negative(self) -> None:
        rep = evaluate([_label("{3}", "{4}", "4", "B")])
        o = rep.items[0]
        assert o.verdict == "reached_answer" and o.candidate == "not_A"
        assert not o.predicted_a and rep.true_negative == 1

    def test_unrelated_and_indeterminate_are_false_negatives(self) -> None:
        rep = evaluate(
            [
                _label("{3}", "{4}", "5", "A"),  # unrelated → ambiguous
                _label("{3}", "{4}", None, "A"),  # indeterminate → unknown
            ]
        )
        assert rep.false_negative == 2 and rep.true_positive == 0
        assert rep.precision is None  # 예측 양성 0 → 미정
        assert rep.recall == 0.0  # 0/(0+2)

    def test_precision_recall_f1_mixed(self) -> None:
        rep = evaluate(
            [
                _label("{3}", "{4}", "3", "A"),  # TP
                _label("{2}", "{5}", "2", "A"),  # TP
                _label("{3}", "{4}", "3", "B"),  # FP
                _label("{3}", "{4}", "5", "A"),  # FN (unrelated)
            ]
        )
        assert (rep.true_positive, rep.false_positive, rep.false_negative) == (2, 1, 1)
        assert rep.precision == pytest.approx(2 / 3)
        assert rep.recall == pytest.approx(2 / 3)
        assert rep.f1 == pytest.approx(2 / 3)

    def test_f1_none_when_precision_and_recall_zero(self) -> None:
        rep = evaluate(
            [
                _label("{3}", "{4}", "3", "B"),  # FP → precision 0
                _label("{3}", "{4}", "5", "A"),  # FN → recall 0
            ]
        )
        assert rep.precision == 0.0 and rep.recall == 0.0 and rep.f1 is None

    def test_confusion_matrix(self) -> None:
        rep = evaluate(
            [
                _label("{3}", "{4}", "3", "A"),  # candidate A, label A
                _label("{3}", "{4}", "3", "B"),  # candidate A, label B
                _label("{3}", "{4}", "4", "B"),  # candidate not_A, label B
            ]
        )
        conf = rep.confusion
        assert conf["A"] == {"A": 1, "B": 1}
        assert conf["not_A"] == {"A": 0, "B": 1}

    def test_empty_corpus_metrics_none(self) -> None:
        rep = evaluate([])
        assert rep.total == 0
        assert rep.precision is None and rep.recall is None and rep.f1 is None


class TestSeedCorpus:
    def test_seed_loads_and_has_locked_distribution(self) -> None:
        # 배포 시드가 파싱·평가되고, 의도한 분포(TP5·FP2·FN3·TN6)를 유지하는지 잠금(회귀 가드).
        rep = evaluate(load_labels(_SEED.read_text(encoding="utf-8")))
        assert rep.total == 16
        counts = (
            rep.true_positive,
            rep.false_positive,
            rep.false_negative,
            rep.true_negative,
        )
        assert counts == (5, 2, 3, 6)
        assert rep.precision == pytest.approx(5 / 7)
        assert rep.recall == pytest.approx(5 / 8)


class TestFormatReport:
    def test_contains_summary_confusion_and_misclassifications(self) -> None:
        rep = evaluate(
            [
                _label("{3}", "{4}", "3", "A"),  # TP → continue 분기
                _label("{3}", "{4}", "3", "B"),  # FP
                _label("{3}", "{4}", "5", "A"),  # FN
            ]
        )
        out = format_report(rep)
        assert "A-precision=" in out
        assert "confusion" in out
        assert "[FP]" in out and "[FN]" in out

    def test_handles_none_metrics(self) -> None:
        out = format_report(evaluate([]))
        assert "A-precision=n/a" in out


class TestCli:
    def test_main_reports_and_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([str(_SEED)]) == 0
        assert "A-precision=" in capsys.readouterr().out

    def test_main_min_precision_gate_fails(self) -> None:
        # 시드 precision(≈0.714) < 1.1 → 종료코드 1.
        assert main([str(_SEED), "--min-precision", "1.1"]) == 1

    def test_main_min_precision_gate_passes(self) -> None:
        # 0.5 ≤ 0.714 → 0.
        assert main([str(_SEED), "--min-precision", "0.5"]) == 0


class TestCandidateForVerdict:
    def test_mapping(self) -> None:
        assert candidate_for_verdict("diverged_from_answer") == "A"
        assert candidate_for_verdict("reached_answer") == "not_A"
        assert candidate_for_verdict("unrelated") == "ambiguous"
        assert candidate_for_verdict("indeterminate") == "unknown"
