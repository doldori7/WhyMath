"""강등전 CLI — 잔여 축(발문↔형식모델) 교차검증기 vs 결함 정답지 (초인간 검증 §3, 확률 도메인 판).

`harness/defect_detection_eval.py`의 확률 도메인 형제. 그쪽이 "계산 축"(정답·조건식·태그
변조)을 기계 검증 스택(`evaluate_equivalent_candidate`)에 태우는 강등전이라면, 이쪽은
"서술 축"(발문↔형식모델 불일치)을 `l3/cross_verify.CrossVerifier`(독립 다관점 LLM
교차검증, K≥3)에 태운다. 정답지는 `l3/finite_probability_defect_seeder`가 결정론
변조로 만든다(우리가 어디에 무슨 결함을 심었는지 100% 안다 — 인간 라벨 0건으로 완전한
정답지가 성립).

배경: `S4-13`이 이 게이트를 위한 검증기(`CrossVerifier`)와 그 상시 게이트
(`harness/residue_cross_verify_eval.py`)를 배선했지만, CI 환경엔 LLM provider가 없어
전 테스트가 결정론 fake provider로만 돌아갔다 — 게이트 *배선*은 끝났고 게이트 *승격*
(실 LLM으로 검출력을 실측)이 미완이다. 이 CLI가 그 실측의 도구다. **이 세션에서 라이브
LLM을 호출하지 않는다** — hermetic 테스트는 전부 fake provider/verifier로 돈다.

집계는 세 갈래로 나눈다(**unclear를 not-detected로 뭉개지 않는다** — 침묵 실패 금지·
이중 회계 원칙):
  - 결함류별 `(detected, unclear, total)`.
  - 전체 결함 검출률 Wilson 하한 — 분모는 `resolved = defect_total - unclear`뿐이다.
    unclear는 "측정 실패"지 "미검출"이 아니므로 분모에서 뺀다
    (`residue_cross_verify_eval.py`의 resolved/unresolved 구분과 동형).
  - 무결함 오검출 Wilson 상한 — 같은 방식으로 unclear를 분모에서 뺀다.

게이트(opt-in·exit 0/1): `--min-detection-lower`·`--max-false-alarm-upper`. 둘 다
미지정이면 리포트만 찍고 exit 0(`corpus_audit_eval`의 opt-in 게이트 관례 미러 — 처음
실행은 임계를 모르니 리포트부터).

사용(라이브 — Phaiakes9에서 Kiki가 실행):
    python -m whymath_backend.harness.residue_gate_demotion_battle \\
        --n-per-class 10 --n-clean 10 --seed S4-16 --audit-out audit.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from whymath_backend.harness.residue_cross_verify_eval import (
    build_finite_probability_subject,
)
from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.cross_verify import CrossVerifier, ResidueSubject
from whymath_backend.l3.finite_probability_defect_seeder import (
    DEFECT_CLASSES,
    DefectClass,
    SeededResidueItem,
    build_defect_seeded_residue_set,
)

__all__ = [
    "BattleOutcome",
    "BattleReport",
    "format_report",
    "run_residue_gate_demotion_battle",
    "summarize",
]

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

AggregateLabel = Literal["ok", "defect", "unclear"]


@dataclass(frozen=True, slots=True)
class BattleOutcome:
    """시험지 1문에 대한 `CrossVerifier` 판정 — 정답지(defect_class)와 집계 라벨.

    `defect_detection_eval.MachineOutcome` 미러. `aggregate`는 `CrossVerificationResult`의
    3분류(ok/defect/unclear)를 그대로 옮긴다 — unclear를 detected/not-detected 이분법으로
    뭉개지 않는다.
    """

    slug: str
    defect_class: DefectClass | None
    aggregate: AggregateLabel
    reason: str


def _build_subject(item: SeededResidueItem) -> ResidueSubject | str:
    """시더 항목 → 교차검증 대상. 공용 조립기(`build_finite_probability_subject`) 재사용."""
    return build_finite_probability_subject(
        slug=item.slug,
        conditions=item.conditions,
        question_text=item.question_text,
        answer=item.answer,
        answer_explanation=item.answer_explanation,
        authored_by=item.authored_by,
    )


def _run_battle(items: list[SeededResidueItem], *, verifier: CrossVerifier) -> list[BattleOutcome]:
    """각 시험지를 `CrossVerifier`에 태워 집계 라벨을 판정.

    모델 조립 자체가 실패하면(발문 변조가 DSL을 건드리지 않으므로 원칙상 일어나지 않지만,
    방어적으로) unclear로 기록한다 — 조용한 스킵 금지.
    """
    outcomes: list[BattleOutcome] = []
    for item in items:
        subject = _build_subject(item)
        if isinstance(subject, str):
            outcomes.append(
                BattleOutcome(
                    slug=item.slug,
                    defect_class=item.defect_class,
                    aggregate="unclear",
                    reason=subject,
                )
            )
            continue
        result = verifier.verify(subject)
        outcomes.append(
            BattleOutcome(
                slug=item.slug,
                defect_class=item.defect_class,
                aggregate=result.aggregate,
                reason=result.reason,
            )
        )
    return outcomes


@dataclass(frozen=True, slots=True)
class BattleReport:
    """검출 집계 — 결함류별(detected·unclear·total) + 전체 검출률 하한 + 오검출 상한.

    unclear(측정 실패)와 ok(미검출·품질 실패)를 항상 분리 회계한다 — Wilson 경계의 분모는
    `resolved`(= total - unclear)뿐이다.
    """

    per_class: dict[str, tuple[int, int, int]]  # defect_class → (detected, unclear, total)
    defect_detected: int
    defect_unclear: int
    defect_total: int
    clean_false_alarm: int
    clean_unclear: int
    clean_total: int

    @property
    def defect_resolved(self) -> int:
        return self.defect_total - self.defect_unclear

    @property
    def clean_resolved(self) -> int:
        return self.clean_total - self.clean_unclear

    def detection_lower_bound(self, confidence: float = 0.95) -> float | None:
        """전체 결함 검출률의 Wilson 단측 하한 — 분모는 resolved(측정 성공)만. 0건이면 None."""
        if self.defect_resolved == 0:
            return None
        return wilson_lower_bound(self.defect_detected, self.defect_resolved, confidence)

    def false_alarm_upper_bound(self, confidence: float = 0.95) -> float | None:
        """무결함 오검출률의 Wilson 단측 상한 — 분모는 resolved(측정 성공)만. 0건이면 None."""
        if self.clean_resolved == 0:
            return None
        return wilson_upper_bound(self.clean_false_alarm, self.clean_resolved, confidence)


def summarize(outcomes: list[BattleOutcome]) -> BattleReport:
    """판정 리스트 → 검출 집계(결함류별 + 전체 + 오검출, unclear 분리 회계). 순수."""
    per_class: dict[str, list[int]] = {k: [0, 0, 0] for k in DEFECT_CLASSES}
    defect_detected = defect_unclear = defect_total = 0
    clean_false_alarm = clean_unclear = clean_total = 0
    for o in outcomes:
        if o.defect_class is not None:
            per_class[o.defect_class][2] += 1
            defect_total += 1
            if o.aggregate == "defect":
                per_class[o.defect_class][0] += 1
                defect_detected += 1
            elif o.aggregate == "unclear":
                per_class[o.defect_class][1] += 1
                defect_unclear += 1
        else:
            clean_total += 1
            if o.aggregate == "defect":
                clean_false_alarm += 1
            elif o.aggregate == "unclear":
                clean_unclear += 1
    return BattleReport(
        per_class={k: (v[0], v[1], v[2]) for k, v in per_class.items()},
        defect_detected=defect_detected,
        defect_unclear=defect_unclear,
        defect_total=defect_total,
        clean_false_alarm=clean_false_alarm,
        clean_unclear=clean_unclear,
        clean_total=clean_total,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def format_report(report: BattleReport, *, confidence: float) -> str:
    """사람 가독 리포트 — 결함류별 표(검출/판정불가/전체) + 전체 검출률 하한 + 오검출 상한."""
    pct = round(confidence * 100)
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("강등전 — 잔여 축 교차검증기의 결함 검출 (초인간 검증 §3, 확률 도메인)")
    lines.append("=" * 64)
    lines.append("[결함류별 검출]")
    for name in DEFECT_CLASSES:
        detected, unclear, total = report.per_class[name]
        resolved = total - unclear
        rate = _fmt(detected / resolved) if resolved else "n/a"
        lines.append(
            f"  {name:26s} 검출 {detected:>3d}/{resolved:<3d}(해소) "
            f"판정불가 {unclear:>3d}/{total:<3d}  ({rate})"
        )
    dlb = report.detection_lower_bound(confidence)
    fau = report.false_alarm_upper_bound(confidence)
    point = report.defect_detected / report.defect_resolved if report.defect_resolved else None
    lines.append("[전체]")
    lines.append(
        f"  결함 검출률   : {report.defect_detected}/{report.defect_resolved}(해소, "
        f"판정불가 {report.defect_unclear}/{report.defect_total}) "
        f"(점추정 {_fmt(point)}·{pct}% 하한 {_fmt(dlb)})"
    )
    lines.append(
        f"  무결함 오검출 : {report.clean_false_alarm}/{report.clean_resolved}(해소, "
        f"판정불가 {report.clean_unclear}/{report.clean_total}) "
        f"({pct}% 상한 {_fmt(fau)})"
    )
    lines.append("=" * 64)
    return "\n".join(lines)


def run_residue_gate_demotion_battle(
    *,
    verifier: CrossVerifier,
    n_per_class: int = 10,
    n_clean: int = 10,
    seed: str = "S4-16",
) -> tuple[BattleReport, list[BattleOutcome]]:
    """강등전 로직 본체(순수 조합) — 시더로 시험지 제조 → `verifier`로 대결 → 집계.

    CLI(`main`)는 이 함수를 부르는 얇은 래퍼다. `verifier`를 주입받으므로 테스트는 실
    provider 없이(`ScriptedProvider` 등) hermetic 실행이 된다(`run_residue_cross_verify`
    관례 미러).
    """
    items = build_defect_seeded_residue_set(n_per_class=n_per_class, n_clean=n_clean, seed=seed)
    outcomes = _run_battle(items, verifier=verifier)
    return summarize(outcomes), outcomes


def _write_audit_jsonl(path: Path, outcomes: list[BattleOutcome]) -> int:
    """산출 감사 JSONL — 문항별 정답지(defect_class)와 실측 판정을 나란히 기록."""
    lines = [
        json.dumps(
            {
                "slug": o.slug,
                "defect_class": o.defect_class,
                "aggregate": o.aggregate,
                "reason": o.reason,
            },
            ensure_ascii=False,
        )
        for o in outcomes
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return len(lines)


def main(argv: list[str] | None = None) -> int:
    """강등전 CLI — 시험지 생성 → 잔여 축 교차검증 대결 → 리포트 → (opt-in) 게이트 판정."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.residue_gate_demotion_battle",
        description=(
            "잔여 축(발문↔형식모델) 결함 주입 강등전 — CrossVerifier 검출률 측정·"
            "opt-in Wilson 게이트."
        ),
    )
    parser.add_argument(
        "--n-per-class",
        type=int,
        default=10,
        help="결함류당 문항 수(기본 10, 풀 20건 이내).",
    )
    parser.add_argument("--n-clean", type=int, default=10, help="무결함 문항 수(기본 10).")
    parser.add_argument("--seed", default="S4-16", help="셋 생성 시드(결정론).")
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측).")
    parser.add_argument(
        "--min-detection-lower",
        type=float,
        default=None,
        help="전체 검출률 Wilson 하한 임계 — 미지정이면 게이트 비활성(리포트만).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=None,
        help="무결함 오검출 Wilson 상한 임계 — 미지정이면 게이트 비활성(리포트만).",
    )
    parser.add_argument("--audit-out", type=Path, default=None, help="감사 JSONL 산출 경로.")
    args = parser.parse_args(argv)

    # 실 provider는 지연 연결(구성만으로 네트워크 0) — 실제 호출은 verify() 시점에 일어난다.
    # provider 선택 플래그는 만들지 않는다 — CrossVerifier() 기본값(CompositeProvider)과
    # 라우터가 이미 로컬/클라우드 선택을 결정한다(residue_cross_verify_eval.py 관례 동일).
    verifier = CrossVerifier()
    report, outcomes = run_residue_gate_demotion_battle(
        verifier=verifier,
        n_per_class=args.n_per_class,
        n_clean=args.n_clean,
        seed=args.seed,
    )
    verifier.flush_trace()
    if args.audit_out is not None:
        _write_audit_jsonl(args.audit_out, outcomes)
    print(format_report(report, confidence=args.confidence))

    # 게이트(opt-in) — 둘 다 미지정이면 리포트만 찍고 exit 0.
    exit_code = _EXIT_OK
    if args.min_detection_lower is not None:
        dlb = report.detection_lower_bound(args.confidence)
        if dlb is None or dlb < args.min_detection_lower:
            exit_code = _EXIT_GATE_FAIL
    if args.max_false_alarm_upper is not None:
        fau = report.false_alarm_upper_bound(args.confidence)
        if fau is None or fau > args.max_false_alarm_upper:
            exit_code = _EXIT_GATE_FAIL
    return exit_code


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
