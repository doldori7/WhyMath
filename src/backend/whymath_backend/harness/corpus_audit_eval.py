"""코퍼스 감사 CLI — 초인간 검증 §2 "S5 보증된 오류 상한"(순수·결정론·LLM 0).

정본: `docs/standards/superhuman_verification_standard.md` §2 S5·§5 롤백. 전수 인간
검수를 **합격 로트 샘플링(acceptance sampling)**으로 대체하는 통계 게이트다. 감사자가
무작위 표본을 결함/정상으로 라벨링한 JSONL을 받아 **결함율을 점추정이 아니라 Wilson
95% 단측 상한으로** 보고하고, 상한이 임계(기본 2%)를 넘으면 exit 1(전수 검수 복귀 신호).

"낮을수록 좋은" 결함율이라 *상한*을 본다 — 관측 0건이어도 상한>0이므로 "표본에서
결함 0 = 코퍼스 결함 0"으로 과신하지 않는다(모르면 모른다·`wilson_upper_bound`).

입력 JSONL(한 줄당):
    {"problem_id": "...", "verdict": "ok"|"defect", "defect_class": "..."(선택)}

사용:
    python -m whymath_backend.harness.corpus_audit_eval audit.jsonl \
        --max-defect-upper 0.02 --min-n 200
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.wilson import wilson_upper_bound

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

AuditVerdictLabel = Literal["ok", "defect"]


class AuditLabel(BaseModel):
    """감사 표본 1건 — 감사자가 라벨링한 결함 여부(JSONL 한 줄)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    problem_id: str = Field(..., description="감사한 문항 식별자.")
    verdict: AuditVerdictLabel = Field(..., description="감사 판정: ok(정상)/defect(결함).")
    defect_class: str = Field(default="", description="결함 유형(선택·집계용).")


def load_labels(text: str) -> list[AuditLabel]:
    """JSONL 텍스트 → AuditLabel 리스트. 빈 줄·`#` 주석 무시. 파싱 오류는 줄 번호와 함께."""
    labels: list[AuditLabel] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            labels.append(AuditLabel.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return labels


@dataclass(slots=True, frozen=True)
class AuditReport:
    """감사 배치 결과 — 표본 수·결함 수·결함율 상한·결함류 분포. 불변."""

    n: int
    defects: int
    defect_classes: dict[str, int]

    @property
    def point_estimate(self) -> float | None:
        return self.defects / self.n if self.n else None

    def defect_rate_upper_bound(self, confidence: float = 0.95) -> float | None:
        """결함율 Wilson 단측 상한 — 표본 0이면 None(판정 불가)."""
        if self.n == 0:
            return None
        return wilson_upper_bound(self.defects, self.n, confidence)


def summarize(labels: list[AuditLabel]) -> AuditReport:
    """감사 라벨 → 결함율 집계(순수)."""
    defects = sum(1 for lab in labels if lab.verdict == "defect")
    classes = Counter(
        lab.defect_class for lab in labels if lab.verdict == "defect" and lab.defect_class
    )
    return AuditReport(n=len(labels), defects=defects, defect_classes=dict(classes))


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def format_report(report: AuditReport, *, confidence: float) -> str:
    """사람 가독 요약 — 표본·결함율 점추정·Wilson 상한·결함류 분포."""
    pct = round(confidence * 100)
    lines = [
        "=" * 60,
        "코퍼스 감사 — 합격 로트 샘플링(초인간 검증 S5)",
        "=" * 60,
        f"표본 n={report.n}  결함={report.defects}",
        f"결함율 점추정={_fmt(report.point_estimate)}  "
        f"{pct}% 상한={_fmt(report.defect_rate_upper_bound(confidence))}",
    ]
    if report.defect_classes:
        lines.append("결함류 분포:")
        for name, count in sorted(report.defect_classes.items()):
            lines.append(f"  {name}: {count}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _run(path: Path, *, max_defect_upper: float, min_n: int, confidence: float) -> int:
    report = summarize(load_labels(path.read_text(encoding="utf-8")))
    print(format_report(report, confidence=confidence))
    # 게이트 — 표본 부족(min_n 미달)이거나 결함율 상한이 임계 초과면 exit 1.
    if report.n < min_n:
        print(f"게이트 미달 — 표본 {report.n} < min_n {min_n}(증거 부족·해금 불가).")
        return _EXIT_GATE_FAIL
    upper = report.defect_rate_upper_bound(confidence)
    if max_defect_upper < 1.0 and (upper is None or upper > max_defect_upper):
        print(f"게이트 미달 — 결함율 상한 {_fmt(upper)} > 임계 {max_defect_upper}(전수 검수 복귀).")
        return _EXIT_GATE_FAIL
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI — 감사 라벨 JSONL → 결함율 Wilson 상한 리포트. exit 0(통과)/1(게이트 미달)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.corpus_audit_eval",
        description="코퍼스 감사 표본 → 결함율 Wilson 상한 게이트(전수→표본 감사 해금·S5).",
    )
    parser.add_argument("labels_path", type=str, help="감사 라벨 JSONL(한 줄당 AuditLabel).")
    parser.add_argument(
        "--max-defect-upper",
        type=float,
        default=1.0,
        help="결함율 Wilson 상한 임계 — 초과면 exit 1(기본 1.0=off, S5 권장 0.02).",
    )
    parser.add_argument(
        "--min-n",
        type=int,
        default=0,
        help="최소 표본 수 — 미달이면 exit 1(증거 부족·기본 0=off, S5 권장 200).",
    )
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측).")
    args = parser.parse_args(argv)
    return _run(
        Path(args.labels_path),
        max_defect_upper=args.max_defect_upper,
        min_n=args.min_n,
        confidence=args.confidence,
    )


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
