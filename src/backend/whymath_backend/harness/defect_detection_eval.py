"""강등전 CLI — 기계 검증 스택 vs 인간 검수자의 결함 검출 대결 (초인간 검증 §3).

정본: `docs/standards/superhuman_verification_standard.md` §3.2. `defect_seeder`가 만든
결함 주입 시험지(정답지를 우리가 100% 앎)를 현 기계 스택(`evaluate_equivalent_candidate`
4종 게이트)에 태워 **결함류별 검출률·전체 검출률 Wilson 하한·무결함 오검출 상한**을
낸다. 목적은 "기계가 사람을 이겼는가"를 *측정으로* 판정하는 것 — 인상·선언이 아니라
CLI exit code로.

세 가지 실행 모드:
  1. **기계 측정(기본)**: 시험지를 기계 스택에 태워 검출표를 낸다.
     `python -m whymath_backend.harness.defect_detection_eval --n-defective 60 --n-clean 60`
  2. **블라인드 시험지 발행**(사람 라운드용): 정답(defect_class)을 뺀 문항과 분리된
     정답지를 각각 저장한다.
     `... --emit-blind blind.jsonl --answer-key key.jsonl`
  3. **강등 판정**(사람 결과 회수 후): 사람이 각 문항을 결함/정상으로 라벨링한 결과를
     받아 기계 검출률 Wilson 하한과 사람 점추정을 나란히 놓고 강등 성립 여부를 판정한다.
     `... --human-labels human.jsonl`

게이트(opt-in·exit 0/1): `--min-detection-lower`(전체 검출률 Wilson 하한 임계)·
`--max-false-alarm-upper`(무결함 오검출 Wilson 상한 임계). 미지정이면 리포트만 내고 0.

정직성: 현 스택은 결함 ⑥(statement_mismatch)을 검출 못 한다(발문-수식 교차 검사 부재).
이 CLI는 그 0%를 눈가림 없이 결함류별 표에 노출한다 — baseline은 있는 그대로 보고한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.equivalent.acceptance import evaluate_equivalent_candidate
from whymath_backend.l3.equivalent.defect_seeder import (
    DEFECT_CLASSES,
    DefectClass,
    SeededItem,
    build_defect_seeded_set,
)

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1


class MachineOutcome(BaseModel):
    """시험지 1문에 대한 기계 스택 판정 — 정답지(defect_class)와 검출 여부.

    `detected = not accepted`: 수용 게이트가 accept를 거부하면(검수필요·비동치·실패)
    "결함으로 걸러냄"으로 본다. 결함 문항은 detected가 옳고, 무결함 문항의 detected는
    오검출(false alarm)이다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str = Field(description="문항 slug(추적용).")
    defect_class: DefectClass | None = Field(description="정답지 — 주입 결함(None=무결함).")
    detected: bool = Field(description="기계가 걸러냈는가(=not accepted).")
    verdict_equivalence: str = Field(description="수용 게이트 동등성 등급(진단용).")
    verification: str = Field(description="정확성 게이트 상태(진단용).")


def _run_machine(items: list[SeededItem]) -> list[MachineOutcome]:
    """각 시험지를 기계 스택(4종 게이트)에 태워 검출 여부를 판정."""
    outcomes: list[MachineOutcome] = []
    for item in items:
        c = item.candidate
        verdict = evaluate_equivalent_candidate(
            item.spec,
            c.problem,
            provenance=c.provenance,
            conditions=c.conditions,
            answer_map=c.answer_map,
            solution_steps=c.solution_steps,
            solution_step_types=None,
            answer_selection=c.answer_selection,
        )
        outcomes.append(
            MachineOutcome(
                slug=c.problem.slug or "",
                defect_class=item.defect_class,
                detected=not verdict.accepted,
                verdict_equivalence=verdict.equivalence,
                verification=verdict.verification,
            )
        )
    return outcomes


@dataclass(slots=True, frozen=True)
class DetectionReport:
    """검출 집계 — 결함류별 검출·전체 검출률 Wilson 하한·무결함 오검출 Wilson 상한."""

    per_class: dict[str, tuple[int, int]]  # defect_class → (detected, total)
    defective_detected: int
    defective_total: int
    false_alarm: int
    clean_total: int

    def detection_lower_bound(self, confidence: float = 0.95) -> float | None:
        """전체 결함 검출률의 Wilson 단측 하한 — 결함 표본 0이면 None."""
        if self.defective_total == 0:
            return None
        return wilson_lower_bound(self.defective_detected, self.defective_total, confidence)

    def false_alarm_upper_bound(self, confidence: float = 0.95) -> float | None:
        """무결함 오검출률의 Wilson 단측 상한 — 무결함 표본 0이면 None."""
        if self.clean_total == 0:
            return None
        return wilson_upper_bound(self.false_alarm, self.clean_total, confidence)


def summarize(outcomes: list[MachineOutcome]) -> DetectionReport:
    """기계 판정 리스트 → 검출 집계(결함류별 + 전체 + 오검출). 순수."""
    per_class: dict[str, list[int]] = {k: [0, 0] for k in DEFECT_CLASSES}
    defective_detected = defective_total = false_alarm = clean_total = 0
    for o in outcomes:
        if o.defect_class is not None:
            per_class[o.defect_class][1] += 1
            defective_total += 1
            if o.detected:
                per_class[o.defect_class][0] += 1
                defective_detected += 1
        else:
            clean_total += 1
            if o.detected:
                false_alarm += 1
    return DetectionReport(
        per_class={k: (v[0], v[1]) for k, v in per_class.items()},
        defective_detected=defective_detected,
        defective_total=defective_total,
        false_alarm=false_alarm,
        clean_total=clean_total,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_report(
    report: DetectionReport, *, confidence: float, human_detection_rate: float | None
) -> str:
    """사람 가독 리포트 — 결함류별 표 + 전체 검출률 하한 + 오검출 상한 + (있으면) 강등 판정."""
    pct = round(confidence * 100)
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("강등전 — 기계 검증 스택의 결함 검출 (초인간 검증 §3)")
    lines.append("=" * 64)
    lines.append("[결함류별 검출]")
    for name in DEFECT_CLASSES:
        detected, total = report.per_class[name]
        rate = _fmt(detected / total) if total else "n/a"
        flag = "  ← 미검출(공백)" if total and detected == 0 else ""
        lines.append(f"  {name:26s} {detected:>3d}/{total:<3d}  ({rate}){flag}")
    dlb = report.detection_lower_bound(confidence)
    fau = report.false_alarm_upper_bound(confidence)
    point = report.defective_detected / report.defective_total if report.defective_total else None
    lines.append("[전체]")
    lines.append(
        f"  결함 검출률   : {report.defective_detected}/{report.defective_total} "
        f"(점추정 {_fmt(point)}·{pct}% 하한 {_fmt(dlb)})"
    )
    lines.append(
        f"  무결함 오검출 : {report.false_alarm}/{report.clean_total} " f"({pct}% 상한 {_fmt(fau)})"
    )
    if human_detection_rate is not None:
        lines.append("[강등 판정 — 기계 하한 vs 사람 점추정]")
        lines.append(f"  사람 검출률(점추정): {_fmt(human_detection_rate)}")
        if dlb is not None and dlb > human_detection_rate:
            lines.append(
                f"  ✅ 강등 성립 — 기계 {pct}% 하한 {_fmt(dlb)} > 사람 {_fmt(human_detection_rate)}"
            )
        else:
            lines.append(
                f"  ❌ 강등 미성립 — 기계 하한 {_fmt(dlb)} ≤ 사람 {_fmt(human_detection_rate)} "
                "(미검출 결함류를 감사기로 보강 후 재대결)"
            )
    lines.append("=" * 64)
    return "\n".join(lines)


def _emit_blind(items: list[SeededItem], blind_path: Path, key_path: Path) -> None:
    """블라인드 시험지(정답 제거) + 분리된 정답지를 각각 JSONL로 저장(사람 라운드용)."""
    with blind_path.open("w", encoding="utf-8") as blind, key_path.open(
        "w", encoding="utf-8"
    ) as key:
        for item in items:
            problem = item.candidate.problem
            blind.write(
                json.dumps(
                    {
                        "slug": problem.slug,
                        "question_text": problem.question_text,
                        "choices": problem.choices,
                        "answer": problem.answer,
                        "answer_explanation": problem.answer_explanation,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            key.write(
                json.dumps(
                    {
                        "slug": problem.slug,
                        "defect_class": item.defect_class,
                        "mutation_note": item.mutation_note,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _human_detection_rate(labels_path: Path) -> float:
    """사람 라벨 JSONL({slug, human_label: defect|ok}) → 결함 문항에 대한 검출률(점추정).

    정답지는 slug로 재생성하지 않고 라벨 파일이 실은 `is_defect`(주최자가 병기)를 쓴다:
    각 줄 {slug, is_defect: bool, human_label: "defect"|"ok"}. 결함 문항(is_defect=True)
    중 human_label=="defect" 비율이 사람 검출률이다.
    """
    detected = total = 0
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        row = json.loads(stripped)
        if not row.get("is_defect"):
            continue
        total += 1
        if row.get("human_label") == "defect":
            detected += 1
    if total == 0:
        raise ValueError("human-labels에 결함 문항(is_defect=true)이 없습니다.")
    return detected / total


def main(argv: list[str] | None = None) -> int:
    """강등전 CLI — 시험지 생성 → 기계 측정/블라인드 발행/강등 판정. exit 0(통과)/1(게이트 미달)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.defect_detection_eval",
        description="결함 주입 강등전 — 기계 스택 검출률 측정·블라인드 발행·사람 대비 강등 판정.",
    )
    parser.add_argument("--n-defective", type=int, default=100, help="결함 문항 수(기본 100).")
    parser.add_argument("--n-clean", type=int, default=100, help="무결함 문항 수(기본 100).")
    parser.add_argument("--seed", type=int, default=20260708, help="셋 생성 시드(결정론).")
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측).")
    parser.add_argument("--emit-blind", default=None, help="블라인드 시험지 저장 경로(사람용).")
    parser.add_argument("--answer-key", default=None, help="정답지 저장 경로(--emit-blind와 짝).")
    parser.add_argument("--human-labels", default=None, help="사람 결과 JSONL → 강등 판정.")
    parser.add_argument(
        "--min-detection-lower",
        type=float,
        default=0.0,
        help="전체 검출률 Wilson 하한 임계 — 미만이면 exit 1(기본 0=off).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=1.0,
        help="무결함 오검출 Wilson 상한 임계 — 초과면 exit 1(기본 1.0=off).",
    )
    args = parser.parse_args(argv)

    items = build_defect_seeded_set(
        n_defective=args.n_defective, n_clean=args.n_clean, seed=args.seed
    )

    if args.emit_blind is not None:
        if args.answer_key is None:
            parser.error("--emit-blind는 --answer-key와 함께 지정해야 합니다.")
        _emit_blind(items, Path(args.emit_blind), Path(args.answer_key))
        print(f"블라인드 시험지 {len(items)}문 저장: {args.emit_blind} / 정답지: {args.answer_key}")
        return _EXIT_OK

    outcomes = _run_machine(items)
    report = summarize(outcomes)
    human_rate = (
        _human_detection_rate(Path(args.human_labels)) if args.human_labels is not None else None
    )
    print(format_report(report, confidence=args.confidence, human_detection_rate=human_rate))

    # 게이트(opt-in) — 검출률 하한 미달 또는 오검출 상한 초과면 exit 1.
    exit_code = _EXIT_OK
    dlb = report.detection_lower_bound(args.confidence)
    if args.min_detection_lower > 0.0 and (dlb is None or dlb < args.min_detection_lower):
        exit_code = _EXIT_GATE_FAIL
    fau = report.false_alarm_upper_bound(args.confidence)
    if args.max_false_alarm_upper < 1.0 and (fau is None or fau > args.max_false_alarm_upper):
        exit_code = _EXIT_GATE_FAIL
    return exit_code


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
