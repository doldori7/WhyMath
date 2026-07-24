"""교수법 팩 금지모드 가드 결함주입 측정(PED-01 슬라이스 ③ acceptance) — 위반 미검출률 게이트.

`coach_prose_leak_eval.py`(코치 프로즈 유출 측정)의 미러다: **정답지를 우리가 100% 아는** 결함
주입 시험지를 만들어 `mode_guard.check_forbidden_modes`(순수 규칙 가드)에 태우고, 검출을 기계
판정해 Wilson 단측 **상한**으로 게이트한다(exit 0/1·점추정 금지). 라이브 LLM 0 — 스크립트 응답
주입(hermetic·결정론·고정 그리드)이라 컨테이너·CI에서 완결된다. primary 러너·톤필터·플래그와 무관
(가드는 순수 함수라 직접 태운다).

시험지 그리드(전수 열거·셀당 n 변형):
  - 대상: 실 코퍼스 팩(`get_pedagogy_packs`) 중 **규칙 검출 가능한 금지모드**
    (RULE_DETECTABLE_MODES)를 금지하는 팩만. v1은 개념형 팩의 WORKED_EXAMPLE_FIRST 1축
    (검출기 등록분). 후속 검출기·팩이
    늘면 `_MODE_REPLY_BANK`에 응답 은행을 추가하는 것으로 자동 확장(정직: 은행 없는 모드는 미측정).
  - 카테고리 2종:
    · **violating**(정답지=위반) — 정의·정답을 단정하고 유도 질문이 없는 응답(완전예제 선행).
      가드가 그 모드 토큰을 반환해야 한다 — None이면 **미검출**(false negative·핵심 게이트 축).
    · **clean**(정답지=무위반) — 정의어를 언급해도 명백히 유도하는 소크라테스 응답. 가드가 None을
      반환해야 한다 — 토큰 반환이면 **오검출**(false alarm·과차단 회계).

판정(기계·순수): violating 셀에서 가드가 기대 모드 토큰을 못 내면 miss, clean 셀에서 토큰을 내면
false_alarm. 게이트: 미검출률 Wilson 상한 ≤ `--max-miss-upper`(기본 0.05) AND 오검출률 Wilson
상한 ≤ `--max-false-alarm-upper`(기본 0.2) → exit 0, 아니면 1.

**변별력 대조군**(`--control`·"변별력 없는 검증 스텝 금지" 준수): 가드를 *무력화한 널 가드*(항상
None)로 같은 시험지를 돌리면 violating 셀이 전부 미검출 → 미검출률≈1 → exit 1이 *실측*된다. 이는
(a) 시험지에 실제 위반이 들어 있고 (b) 정상 경로의 0 미검출이 시험지가 순해서가 아니라 *검출기가
잡아서*임을 동시에 증명한다(coach_prose_leak_eval의 --control-flag-off와 동형 철학 — 보호 계층을
꺼서 실패가 드러남을 보인다).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from whymath_backend.harness.wilson import wilson_upper_bound
from whymath_backend.l4.pedagogy.mode_guard import (
    RULE_DETECTABLE_MODES,
    check_forbidden_modes,
)
from whymath_backend.l4.pedagogy.pack_registry import get_pedagogy_packs
from whymath_backend.schema.pedagogy_pack import PedagogyPack

# 종료 코드 — 게이트 CLI 관례(coach_prose_leak_eval·defect_detection_eval 동형).
_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

# 가드 함수 시그니처 — 정상=check_forbidden_modes, 대조군=널 가드(무력화). 변별력 대조의 스왑 지점.
GuardFn = Callable[[PedagogyPack, str], "str | None"]

# 변형 접미 토큰 — 무숫자·무신호(가드 신호 어휘에 없는 한글)라 셀 반복이 동일 입력이 되지 않게 하되
# 검출 결과는 바꾸지 않는다(괄호 부기는 단정·유도 신호를 더하지 않음).
_VARIANT_TOKENS = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"


# ──────────────────────────────────────────────────────────────────────────
# 모드별 응답 은행 (정답지) — violating(위반) vs clean(무위반) 스크립트
# ──────────────────────────────────────────────────────────────────────────
# WORKED_EXAMPLE_FIRST(개념형): 위반=정의·정답 단정 + 유도 부재, clean=정의어 있어도 명백히 유도.
# clean은 일부러 정의어(정의는/정의하면/답은)를 넣어 *오검출 축을 실제로 시험*한다(정의어가 있어도
# 유도가 살아 있으면 가드가 잡으면 안 된다 — false alarm 방어의 진짜 시험).
_WORKED_EXAMPLE_FIRST_VIOLATING: tuple[str, ...] = (
    "이 개념의 정의는 주변보다 큰 값이라는 것이다. 그대로 외우면 된다.",
    "정답은 바로 이거야. 이렇게 정의된다고 알려줄게, 그냥 받아들이면 돼.",
    "먼저 식을 세우면 f=2x-4, 2x-4=0, 따라서 x=2가 최종 결론이다.",
    "답은 x=2이다. 계산하면 2x=4 이고 따라서 x=2로 끝난다.",
    "이 용어란 특정 조건을 만족하는 값을 뜻한다. 정의를 이렇게 정리해 준다.",
    "정의하면 이렇게 되고, 그러므로 이 값이 정답이라고 정리해 준다.",
)
_WORKED_EXAMPLE_FIRST_CLEAN: tuple[str, ...] = (
    "이걸 뭐라고 정의하면 좋을까? 네 생각을 말해 줄래?",
    "정의는 우리가 함께 만들어 보자. 예를 들어볼까, 아니면 반대인 경우는?",
    "답은 네가 찾아야 해. 어떻게 접근하면 좋을지 말해 줄래?",
    "이건 예일까 아닐까? 왜 그렇게 생각했는지 들려줄래?",
    "예와 예가 아닌 걸 나란히 봤을 때 어떤 점이 다를까?",
    "경계가 어디쯤일지 네 말로 다시 세워볼까?",
)

# 모드 토큰 → (위반 스크립트, 무위반 스크립트). 규칙 검출기가 있는 모드만 은행을 둔다(정직: 은행
# 없는 모드는 시험 대상 아님·후속). 후속 검출기 추가 시 여기에 은행을 더한다.
_MODE_REPLY_BANK: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "WORKED_EXAMPLE_FIRST": (_WORKED_EXAMPLE_FIRST_VIOLATING, _WORKED_EXAMPLE_FIRST_CLEAN),
}


@dataclass(frozen=True, slots=True)
class CaseSpec:
    """시험지 1건 — (팩×모드×카테고리×템플릿×변형) 셀. 정답지 = 기대 검출(mode 또는 None)."""

    k_type: str
    mode: str
    category: str  # "violating" | "clean"
    reply: str
    expected: str | None  # 기대 검출 결과(violating→mode 토큰, clean→None)


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    """기계 측정 1건 — 가드 검출 결과와 미검출·오검출 판정."""

    spec: CaseSpec
    detected: str | None
    missed: bool  # violating인데 기대 모드 미검출(false negative)
    false_alarm: bool  # clean인데 무언가 검출(false positive)


def _null_guard(pack: PedagogyPack, reply: str) -> str | None:
    """대조군 널 가드 — 검출기를 무력화(항상 None). 보호 계층 OFF의 변별력 실측용."""
    del pack, reply  # 항상 무검출 — 시험지의 실제 위반이 그대로 새어 exit 1이 나야 정상.
    return None


def build_exam(n_per_cell: int) -> list[CaseSpec]:
    """전수 그리드 × 셀당 n 변형 — 결정론(난수 0·순서 고정·무숫자·무신호 접미 변형).

    실 코퍼스 팩을 순회해 규칙 검출 가능(RULE_DETECTABLE_MODES)하고 응답 은행이 있는 금지모드만
    시험지에 올린다(정직: 은행 없는 축은 미측정). 팩 순서는 k_type 정렬로 고정한다.
    """
    if n_per_cell < 1:
        raise ValueError("n_per_cell은 1 이상이어야 합니다.")
    if n_per_cell > len(_VARIANT_TOKENS):
        raise ValueError(f"n_per_cell은 최대 {len(_VARIANT_TOKENS)}입니다(무숫자 변형 토큰 한계).")
    cases: list[CaseSpec] = []
    packs = get_pedagogy_packs()
    for k_type in sorted(packs):
        pack = packs[k_type]
        for mode in pack.forbidden_modes:
            if mode not in RULE_DETECTABLE_MODES or mode not in _MODE_REPLY_BANK:
                continue  # 검출기·은행 없는 축은 시험 대상 아님(정직한 공백·후속).
            violating, clean = _MODE_REPLY_BANK[mode]
            for category, templates, expected in (
                ("violating", violating, mode),
                ("clean", clean, None),
            ):
                for template in templates:
                    for variant in range(n_per_cell):
                        cases.append(
                            CaseSpec(
                                k_type=k_type,
                                mode=mode,
                                category=category,
                                reply=f"{template} ({_VARIANT_TOKENS[variant]}변형)",
                                expected=expected,
                            )
                        )
    return cases


def _judge(spec: CaseSpec, detected: str | None) -> CaseOutcome:
    """기계 판정(순수) — violating: 기대 모드 미검출=miss / clean: 무언가 검출=false_alarm."""
    if spec.category == "violating":
        missed = detected != spec.expected
        return CaseOutcome(spec=spec, detected=detected, missed=missed, false_alarm=False)
    false_alarm = detected is not None
    return CaseOutcome(spec=spec, detected=detected, missed=False, false_alarm=false_alarm)


def run_machine(cases: list[CaseSpec], guard_fn: GuardFn) -> list[CaseOutcome]:
    """전 케이스를 가드에 태워 판정 — 순수·결정론(IO 0·LLM 0). guard_fn 스왑이 변별력 대조 지점."""
    packs = get_pedagogy_packs()
    outcomes: list[CaseOutcome] = []
    for spec in cases:
        detected = guard_fn(packs[spec.k_type], spec.reply)
        outcomes.append(_judge(spec, detected))
    return outcomes


@dataclass(frozen=True, slots=True)
class FidelityReport:
    """측정 요약 — 미검출·오검출 계수 + 셀별 분해(정직 회계·관측 0 ≠ 확정 0)."""

    violating_total: int
    missed: int
    clean_total: int
    false_alarm: int
    by_cell: dict[str, tuple[int, int]]  # "k_type/mode/category" → (문제건수, 총건수)

    def miss_upper_bound(self, confidence: float = 0.95) -> float:
        """미검출률 Wilson 단측 상한 — '낮을수록 좋은' 핵심 지표는 상한(보수·과신 금지)."""
        return wilson_upper_bound(self.missed, self.violating_total, confidence)

    def false_alarm_upper_bound(self, confidence: float = 0.95) -> float:
        """오검출률 Wilson 단측 상한 — 과차단(품질 손실) 회계."""
        return wilson_upper_bound(self.false_alarm, self.clean_total, confidence)


def summarize(outcomes: list[CaseOutcome]) -> FidelityReport:
    """순수 집계 — LLM·IO 0 (coach_prose_leak_eval.summarize 동형)."""
    violating_total = missed = clean_total = false_alarm = 0
    by_cell: dict[str, tuple[int, int]] = {}
    for outcome in outcomes:
        spec = outcome.spec
        key = f"{spec.k_type}/{spec.mode}/{spec.category}"
        bad, total = by_cell.get(key, (0, 0))
        if spec.category == "violating":
            violating_total += 1
            missed += int(outcome.missed)
            by_cell[key] = (bad + int(outcome.missed), total + 1)
        else:
            clean_total += 1
            false_alarm += int(outcome.false_alarm)
            by_cell[key] = (bad + int(outcome.false_alarm), total + 1)
    return FidelityReport(
        violating_total=violating_total,
        missed=missed,
        clean_total=clean_total,
        false_alarm=false_alarm,
        by_cell=by_cell,
    )


def render_report(report: FidelityReport, *, confidence: float, control: bool) -> str:
    """사람용 요약 — 응답 원문 미출력(카운트·상한·셀 라벨만)."""
    miss_upper = report.miss_upper_bound(confidence)
    alarm_upper = report.false_alarm_upper_bound(confidence)
    banner = "교수법 팩 금지모드 가드 결함주입 측정 (PED-01 ③)"
    if control:
        banner += " — [대조군: 널 가드]"
    lines = ["=" * 64, banner + " — Wilson 상한 게이트", "=" * 64]
    lines.append(f"violating 셀: {report.violating_total}건 중 미검출 {report.missed}건")
    lines.append(f"  미검출률 Wilson 상한({confidence:.0%}): {miss_upper:.4f}")
    lines.append(f"clean 셀: {report.clean_total}건 중 오검출 {report.false_alarm}건")
    lines.append(f"  오검출률 Wilson 상한({confidence:.0%}): {alarm_upper:.4f}")
    problem_cells = {k: v for k, v in report.by_cell.items() if v[0] > 0}
    if problem_cells:
        lines.append("[문제 셀 — (문제건수/총건수)]")
        for key in sorted(problem_cells):
            bad, total = problem_cells[key]
            lines.append(f"  {key}: {bad}/{total}")
    else:
        lines.append("[문제 셀 없음 — 전 셀 무결]")
    lines.append("=" * 64)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.pedagogy_pack_fidelity_eval",
        description=(
            "교수법 팩 금지모드 가드 결함주입 측정 — 규칙 검출 가능한 금지모드의 위반 미검출을 "
            "실 코퍼스 팩·순수 가드에서 Wilson 상한으로 게이트한다(hermetic·라이브 LLM 0·exit 0/1)."
        ),
    )
    parser.add_argument("--n-per-cell", type=int, default=12, help="셀당 변형 수(표본 크기).")
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 단측 신뢰수준.")
    parser.add_argument(
        "--max-miss-upper",
        type=float,
        default=0.05,
        help="미검출률 Wilson 상한 임계 — 초과면 exit 1(핵심 게이트).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=0.2,
        help="오검출률 Wilson 상한 임계 — 초과면 exit 1(과차단 방지).",
    )
    parser.add_argument(
        "--control",
        action="store_true",
        help="변별력 대조군 — 가드 무력화(널 가드) 측정(미검출≈전량 실측돼 exit 1이어야 정상).",
    )
    parser.add_argument("--json", type=Path, default=None, help="JSON 리포트 출력 경로(선택).")
    args = parser.parse_args(argv)

    guard_fn: GuardFn = _null_guard if args.control else check_forbidden_modes
    outcomes = run_machine(build_exam(args.n_per_cell), guard_fn)
    report = summarize(outcomes)
    print(render_report(report, confidence=args.confidence, control=args.control))
    if args.json is not None:
        payload = dataclasses.asdict(report)
        payload["miss_upper_bound"] = report.miss_upper_bound(args.confidence)
        payload["false_alarm_upper_bound"] = report.false_alarm_upper_bound(args.confidence)
        payload["control"] = args.control
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 리포트 저장: {args.json}")

    gate_ok = (
        report.miss_upper_bound(args.confidence) <= args.max_miss_upper
        and report.false_alarm_upper_bound(args.confidence) <= args.max_false_alarm_upper
    )
    verdict = "PASS" if gate_ok else "FAIL"
    print(
        f"게이트 판정(미검출 상한 ≤{args.max_miss_upper}·"
        f"오검출 상한 ≤{args.max_false_alarm_upper}): {verdict}"
    )
    return _EXIT_OK if gate_ok else _EXIT_GATE_FAIL


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    sys.exit(main())
