"""L4 step_shadow precision eval 하니스 — A/B 후보의 사람 라벨 대비 정밀도 측정(오프라인·비노출).

2026-06-06 해금 게이트의 실측 도구: 정책은 *"shadow 데이터로 A에 대한 precision ≥ 사전 임계
입증"*을 student-facing 노출의 전제로 둔다(`MEMORY.md` 2026-06-06). slice 65가 `classify_step_break`
→ verdict → `candidate`(A/not_A/ambiguous/unknown)를 산출했고, 본 모듈은 *사람이 A/B로 라벨링한
코퍼스*에 그 휴리스틱을 돌려 **A 후보 precision/recall/혼동행렬**을 낸다.

**비노출·오프라인**: 런타임/HTTP/DB 경로와 무관한 측정 도구다. L3 `classify_step_break`(사실 판정)
+ L4 `candidate_for_verdict`(교수학 해석)을 *소비*만 한다(재구현 0·레이어 경계 준수). 입력 코퍼스는
shadow 로그(slice 65)와 같은 필드라, 실제 로그를 사람이 라벨링하면 그대로 입력이 된다.

사용법:
    python -m whymath_backend.l4.step_shadow_eval <labels.jsonl> [--min-precision 0.99]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.pregenerate.validator import (
    StepAnswerVerdict,
    StepBreak,
    classify_step_break,
)
from whymath_backend.l4.step_shadow import candidate_for_verdict

# 양성(positive) 예측 후보 라벨 — candidate_for_verdict("diverged_from_answer")와 일치.
_CANDIDATE_A = "A"

# 사람 라벨: A=순차유도 변환오류 / B=변수재사용(독립 소문제). 게이트는 A의 precision을 본다.
HumanLabel = Literal["A", "B"]


class StepBreakLabel(BaseModel):
    """사람이 A/B로 라벨링한 단계-비보존 1건 — precision eval 입력(JSONL 한 줄).

    `classify_step_break`이 보는 필드는 `solset_before`·`solset_after`·`expected_answer`뿐이다.
    나머지(`var`·`marker`·`solution_text`·`source`·`note`)는 추적·가독용(평가 미사용)이며 shadow
    로그(slice 65)가 남기는 필드와 같은 모양이라, 실제 로그를 사람이 라벨링하면 이 레코드가 된다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    solset_before: str = Field(..., description='이전 단계 해집합 문자열("{3}")')
    solset_after: str = Field(..., description='다음 단계 해집합 문자열("{4}")')
    expected_answer: str | None = Field(default=None, description="기대정답(없으면 null)")
    human_label: HumanLabel = Field(..., description="사람 라벨: A=변환오류 / B=변수재사용")
    # 추적·가독(평가에 미사용)
    var: str = Field(default="x", description="변수명(StepBreak 재구성용·평가 무관)")
    marker: str = Field(default="", description="순차유도 마커(추적용)")
    solution_text: str = Field(default="", description="원 풀이(가독·출처)")
    source: str = Field(default="", description="출처(manual·shadow-log 등)")
    note: str = Field(default="", description="라벨 근거 메모")


def load_labels(text: str) -> list[StepBreakLabel]:
    """JSONL 텍스트(한 줄당 StepBreakLabel JSON) → 리스트. 빈 줄·`#` 주석 무시.

    파싱 오류는 line 번호와 함께 ValueError로 던진다(`l3/pregenerate/__main__.py:load_items` 동형).
    """
    labels: list[StepBreakLabel] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            labels.append(StepBreakLabel.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return labels


@dataclass(slots=True, frozen=True)
class LabeledOutcome:
    """레코드 1건 평가 결과 — 사람 라벨 vs 휴리스틱 예측(verdict·candidate). 불변.

    `solset_*`·`expected_answer`는 오분류(FP/FN) 상세용 보관(평가엔 candidate/label만 사용).
    """

    human_label: HumanLabel
    verdict: StepAnswerVerdict
    candidate: str
    predicted_a: bool  # candidate == "A"(양성 예측)
    actual_a: bool  # human_label == "A"(양성 정답)
    solset_before: str
    solset_after: str
    expected_answer: str | None


def _div(numer: int, denom: int) -> float | None:
    """0 나눗셈 보수 — 분모 0이면 None(precision/recall 미정)."""
    return numer / denom if denom else None


@dataclass(slots=True, frozen=True)
class PrecisionReport:
    """A 후보 정밀도 평가 배치 결과 — outcome 리스트 + 파생 지표. 불변.

    `precision`이 해금 게이트의 핵심 수치(정책 2026-06-06: A에 대한 precision ≥ 임계). 분모 0인
    지표는 None(예: 예측 양성 0이면 precision 미정). `PrewarmReport`(pregenerate/models.py)의
    *원천=items, 카운트는 파생-프로퍼티* 패턴을 따른다.
    """

    items: tuple[LabeledOutcome, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def true_positive(self) -> int:
        return sum(1 for o in self.items if o.predicted_a and o.actual_a)

    @property
    def false_positive(self) -> int:
        return sum(1 for o in self.items if o.predicted_a and not o.actual_a)

    @property
    def false_negative(self) -> int:
        return sum(1 for o in self.items if not o.predicted_a and o.actual_a)

    @property
    def true_negative(self) -> int:
        return sum(1 for o in self.items if not o.predicted_a and not o.actual_a)

    @property
    def precision(self) -> float | None:
        """A 후보 정밀도 = TP/(TP+FP). 예측 양성 0이면 None(미정·게이트 통과 불가)."""
        return _div(self.true_positive, self.true_positive + self.false_positive)

    @property
    def recall(self) -> float | None:
        """A 재현율 = TP/(TP+FN). 정답 양성 0이면 None."""
        return _div(self.true_positive, self.true_positive + self.false_negative)

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    @property
    def confusion(self) -> dict[str, dict[str, int]]:
        """candidate → {A,B} 카운트(예측 후보별 사람 라벨 분포)."""
        matrix: dict[str, dict[str, int]] = {}
        for o in self.items:
            row = matrix.setdefault(o.candidate, {"A": 0, "B": 0})
            row[o.human_label] += 1
        return matrix


def evaluate(labels: Iterable[StepBreakLabel]) -> PrecisionReport:
    """각 라벨 레코드에 휴리스틱(classify_step_break → candidate)을 돌려 A 후보 정밀도를 집계.

    순수·결정론. `classify_step_break`이 보는 건 solset_before/after + expected_answer뿐이라,
    `StepBreak`의 나머지 필드(step_index·span)는 평가에 무관한 더미로 채운다.
    """
    outcomes: list[LabeledOutcome] = []
    for label in labels:
        break_ = StepBreak(
            step_index=0,
            span=(0, 0),
            solset_before=label.solset_before,
            solset_after=label.solset_after,
            var=label.var,
            marker=label.marker,
        )
        verdict = classify_step_break(break_, label.expected_answer)
        candidate = candidate_for_verdict(verdict)
        outcomes.append(
            LabeledOutcome(
                human_label=label.human_label,
                verdict=verdict,
                candidate=candidate,
                predicted_a=(candidate == _CANDIDATE_A),
                actual_a=(label.human_label == "A"),
                solset_before=label.solset_before,
                solset_after=label.solset_after,
                expected_answer=label.expected_answer,
            )
        )
    return PrecisionReport(items=tuple(outcomes))


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_report(report: PrecisionReport) -> str:
    """사람읽는 요약 — A 후보 precision/recall/F1 + 혼동행렬 + FP/FN 상세."""
    lines: list[str] = [
        (
            f"total={report.total} A-precision={_fmt(report.precision)} "
            f"recall={_fmt(report.recall)} f1={_fmt(report.f1)} "
            f"(TP={report.true_positive} FP={report.false_positive} "
            f"FN={report.false_negative} TN={report.true_negative})"
        ),
        "confusion (candidate → A/B):",
    ]
    confusion = report.confusion
    for candidate in sorted(confusion):
        row = confusion[candidate]
        lines.append(f"  {candidate}: A={row['A']} B={row['B']}")
    # 오분류 상세 — FP(예측 A인데 라벨 B)·FN(라벨 A인데 예측 ¬A): 한계/개선 진단용.
    for o in report.items:
        if o.predicted_a and not o.actual_a:
            tag = "FP"
        elif not o.predicted_a and o.actual_a:
            tag = "FN"
        else:
            continue
        lines.append(
            f"  [{tag}] {o.solset_before}→{o.solset_after} "
            f"expected={o.expected_answer!r} verdict={o.verdict} label={o.human_label}"
        )
    return "\n".join(lines)


def _run(specs_path: Path, *, min_precision: float) -> int:
    text = specs_path.read_text(encoding="utf-8")
    report = evaluate(load_labels(text))
    print(format_report(report))
    # 게이트: A precision이 임계 미만이면 종료코드 1. 기본 0.0=게이트 없음(리포트만).
    # precision None(예측 양성 0)은 임계>0일 때 미달로 본다(증거 없음 = 게이트 통과 불가).
    if min_precision > 0.0 and (report.precision is None or report.precision < min_precision):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — JSONL 라벨 코퍼스 → precision 리포트. 종료 0(통과)/1(임계 미달)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.step_shadow_eval",
        description=(
            "step_shadow A/B 후보 precision eval — 사람 라벨 코퍼스로 classify_step_break의 "
            "A 후보 정밀도/재현율을 측정(오프라인·비노출·해금 게이트 #2 도구)."
        ),
    )
    parser.add_argument("specs_path", type=str, help="JSONL 라벨 코퍼스(한 줄당 StepBreakLabel)")
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.0,
        help="A precision 임계 — 미만이면 종료코드 1(기본 0.0=게이트 없음·리포트만).",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    min_precision: float = args.min_precision
    return _run(Path(specs_path), min_precision=min_precision)


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "LabeledOutcome",
    "PrecisionReport",
    "StepBreakLabel",
    "evaluate",
    "format_report",
    "load_labels",
    "main",
]
