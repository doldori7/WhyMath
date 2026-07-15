"""코퍼스 감사 CLI — 초인간 검증 §2 "S5 보증된 오류 상한"(순수·결정론·LLM 0).

정본: `docs/standards/superhuman_verification_standard.md` §2 S5·§5 롤백. 전수 인간
검수를 **합격 로트 샘플링(acceptance sampling)**으로 대체하는 통계 게이트다. 감사자가
무작위 표본을 결함/정상으로 라벨링한 JSONL을 받아 **결함율을 점추정이 아니라 Wilson
95% 단측 상한으로** 보고하고, 상한이 임계(기본 2%)를 넘으면 exit 1(전수 검수 복귀 신호).

"낮을수록 좋은" 결함율이라 *상한*을 본다 — 관측 0건이어도 상한>0이므로 "표본에서
결함 0 = 코퍼스 결함 0"으로 과신하지 않는다(모르면 모른다·`wilson_upper_bound`).

입력 JSONL(한 줄당):
    {"problem_id": "...", "verdict": "ok"|"defect", "defect_class": "..."(선택)}
    {"as_found_n": N, "as_found_defects": D}   ← as-found 병기 선언(선택·1개)

as-found 병기(§4.5): 결함 교정 후 재채점으로 FAIL→PASS를 감추지 않도록, 교정 전
(as-found) 결함율·Wilson 상한을 감사 기록에 병기한다. `--require-as-found`는 이 병기
선언 라인 부재 시 exit 1로 의무를 기계 강제한다(산문→CLI 게이트 승격·검증 권위 서열 ②).

사용:
    python -m whymath_backend.harness.corpus_audit_eval audit.jsonl \
        --max-defect-upper 0.02 --min-n 200 --require-as-found
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from whymath_backend.harness.wilson import wilson_upper_bound

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

AuditVerdictLabel = Literal["ok", "defect"]


class AuditLabel(BaseModel):
    """감사 표본 1건 — 감사자가 라벨링한 결함 여부(JSONL 한 줄)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    problem_id: str = Field(..., description="감사한 문항 식별자.")
    verdict: AuditVerdictLabel = Field(
        ..., description="감사 판정: ok(정상)/defect(결함)."
    )
    defect_class: str = Field(default="", description="결함 유형(선택·집계용).")


class AsFoundRecord(BaseModel):
    """as-found 병기 선언 1건 — 교정 전(as-found) 결함 수·표본 수(JSONL 특수 라인).

    정본: 초인간 검증 §4.5 "as-found 병기 의무" — 결함 교정 후 재채점으로 FAIL→PASS를
    감추지 않도록, 교정 전 결함율·Wilson 상한을 감사 기록에 *항상 병기*(역사 위조 금지).
    `as_found_n` 키 존재로 `AuditLabel`과 판별한다(AuditLabel은 `extra="forbid"`라 상호 배타).
    """

    model_config = ConfigDict(extra="forbid")

    as_found_n: int = Field(..., ge=1, description="교정 전 감사 표본 수(≥1).")
    as_found_defects: int = Field(
        ..., ge=0, description="교정 전 결함 수(≥0·≤ as_found_n)."
    )

    @field_validator("as_found_defects")
    @classmethod
    def _defects_not_exceed_n(cls, v: int, info: ValidationInfo) -> int:
        n = info.data.get("as_found_n")
        if n is not None and v > n:
            raise ValueError(f"as_found_defects({v}) > as_found_n({n})")
        return v

    def defect_rate_upper_bound(self, confidence: float = 0.95) -> float:
        """as-found 결함율 Wilson 단측 상한 — n≥1 보장이라 항상 값."""
        return wilson_upper_bound(self.as_found_defects, self.as_found_n, confidence)

    @property
    def point_estimate(self) -> float:
        return self.as_found_defects / self.as_found_n


@dataclass(slots=True, frozen=True)
class AuditInput:
    """감사 JSONL 파싱 결과 — 문항 라벨 + (선택) as-found 병기 선언. 불변."""

    labels: list[AuditLabel]
    as_found: AsFoundRecord | None


def load_audit(text: str) -> AuditInput:
    """JSONL 텍스트 → AuditInput(라벨 + as-found 선언). 빈 줄·`#` 주석 무시.

    각 라인을 `as_found_n` 키 유무로 판별해 `AsFoundRecord`/`AuditLabel`로 분류한다.
    as-found 선언이 2개 이상이면 ValueError(단일 진실 원천). 파싱 오류는 줄 번호와 함께.
    """
    labels: list[AuditLabel] = []
    as_found: AsFoundRecord | None = None
    as_found_line: int | None = None
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            obj = json.loads(stripped)
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
        if isinstance(obj, dict) and "as_found_n" in obj:
            if as_found is not None:
                raise ValueError(
                    f"as-found 선언 중복 — line {as_found_line}·{line_num}(하나만 허용)"
                )
            try:
                # pydantic ValidationError는 ValueError 하위형 — 줄 번호로 감싸 재던짐.
                as_found = AsFoundRecord.model_validate(obj)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"line {line_num}: {exc}") from exc
            as_found_line = line_num
        else:
            try:
                labels.append(AuditLabel.model_validate(obj))
            except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
                raise ValueError(f"line {line_num}: {exc}") from exc
    return AuditInput(labels=labels, as_found=as_found)


def load_labels(text: str) -> list[AuditLabel]:
    """JSONL 텍스트 → AuditLabel 리스트(하위호환 래퍼·as-found 선언은 제외)."""
    return load_audit(text).labels


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
        lab.defect_class
        for lab in labels
        if lab.verdict == "defect" and lab.defect_class
    )
    return AuditReport(n=len(labels), defects=defects, defect_classes=dict(classes))


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def format_report(
    report: AuditReport,
    *,
    confidence: float,
    as_found: AsFoundRecord | None = None,
) -> str:
    """사람 가독 요약 — 표본·결함율 점추정·Wilson 상한·결함류 분포·(선택) as-found 병기."""
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
    # as-found 병기(초인간 검증 §4.5) — 교정 전 결함율·Wilson 상한을 정직하게 병기.
    if as_found is not None:
        lines.append("-" * 60)
        lines.append(
            f"as-found 병기(§4.5): n={as_found.as_found_n}  결함={as_found.as_found_defects}  "
            f"점추정={_fmt(as_found.point_estimate)}  "
            f"{pct}% 상한={_fmt(as_found.defect_rate_upper_bound(confidence))}"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def _run(
    path: Path,
    *,
    max_defect_upper: float,
    min_n: int,
    confidence: float,
    require_as_found: bool = False,
) -> int:
    audit = load_audit(path.read_text(encoding="utf-8"))
    report = summarize(audit.labels)
    print(format_report(report, confidence=confidence, as_found=audit.as_found))
    # as-found 병기 게이트(opt-in·§4.5) — 병기 선언 라인 부재 시 exit 1.
    # 값(as-found 상한)은 게이트하지 않는다 — 의무의 본질은 정직한 공개이지 통과가 아니다
    # (§4.5: as-found FAIL이어도 더 큰 코퍼스로 실체 결론 유지 가능).
    if require_as_found and audit.as_found is None:
        print(
            "게이트 미달 — as-found 병기 선언 부재(§4.5 as-found 병기 의무 위반·역사 위조 금지)."
        )
        return _EXIT_GATE_FAIL
    # 게이트 — 표본 부족(min_n 미달)이거나 결함율 상한이 임계 초과면 exit 1.
    if report.n < min_n:
        print(f"게이트 미달 — 표본 {report.n} < min_n {min_n}(증거 부족·해금 불가).")
        return _EXIT_GATE_FAIL
    upper = report.defect_rate_upper_bound(confidence)
    if max_defect_upper < 1.0 and (upper is None or upper > max_defect_upper):
        print(
            f"게이트 미달 — 결함율 상한 {_fmt(upper)} > 임계 {max_defect_upper}(전수 검수 복귀)."
        )
        return _EXIT_GATE_FAIL
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI — 감사 라벨 JSONL → 결함율 Wilson 상한 리포트. exit 0(통과)/1(게이트 미달)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.corpus_audit_eval",
        description="코퍼스 감사 표본 → 결함율 Wilson 상한 게이트(전수→표본 감사 해금·S5).",
    )
    parser.add_argument(
        "labels_path", type=str, help="감사 라벨 JSONL(한 줄당 AuditLabel)."
    )
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
    parser.add_argument(
        "--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측)."
    )
    parser.add_argument(
        "--require-as-found",
        action="store_true",
        help='as-found 병기 선언(`{"as_found_n":N,"as_found_defects":D}`) 부재 시 exit 1'
        " — §4.5 as-found 병기 의무 기계 강제(기본 off·opt-in).",
    )
    args = parser.parse_args(argv)
    return _run(
        Path(args.labels_path),
        max_defect_upper=args.max_defect_upper,
        min_n=args.min_n,
        confidence=args.confidence,
        require_as_found=args.require_as_found,
    )


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
