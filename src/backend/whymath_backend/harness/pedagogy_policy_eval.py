"""교수법 policy 승격 게이트 — 오프폴리시 평가 + 안전제약 강등전 (PED-03·04d §3.3).

`defect_detection_eval.py`·`coach_prose_leak_eval.py`의 CLI exit 0/1 뼈대를 미러한다. 판정하는
것은 두 가지다:

  **① 안전제약(하드)** — policy가 `gate()`가 허용하지 않은 전략을 *한 번이라도* 고르면 즉시 실패.
     이 축은 표본과 무관하게 항상 판정 가능하다(구조 검증). 04d §3.3 "교수학 #3 위반 전략은 policy가
     애초에 고를 수 없다"의 기계 집행.

  **② 성과(오프폴리시)** — 로그(행동 policy = 규칙표)로 목표 policy의 기대 성과를 **SNIPS**
     (self-normalized IPS)로 추정하고, 규칙표 대비 개선이 Wilson 하한 기준으로 확인될 때만 승격.

────────────────────────────────────────────────────────────────────────────
지금 이 게이트는 **의도적으로 실패한다** — 그것이 정직한 상태다
────────────────────────────────────────────────────────────────────────────
`api/study.py`가 방금 배선됐지만 클라이언트가 아직 호출하지 않아 `evidence_event`의 교수법 표본은
0이다. 표본이 최소 요건에 못 미치면 이 CLI는 **exit 1과 함께 "측정 미달"을 명시 출력**한다.

0건을 "통과"로도 "성과 미달"로도 바꾸지 않는 것이 요점이다 — CLAUDE.md의 "인프라가 죽으면 '측정
실패'가 보여야지 '0건 통과/미달'로 위장되면 안 된다"를 policy 승격 축에 적용한 것이다. 그래서 이
CLI는 **CI에 배선하지 않는다**(항상 red 고정이라 신호가 죽는다). 트래픽이 쌓여 게이트가 뒤집힐 수
있게 된 시점에 CI에 등재한다.

**변별력**(`--control-safety-off`): 안전제약을 끈 policy를 같은 시험지에 태우면 배제 대상 전략이
실제로 선택되어 **exit 1이 실측**된다 — 이 측정기가 실패 상태에서 실패 신호를 낸다는 증명이며,
동시에 제약이 장식이 아님을 보인다.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass

from whymath_backend.harness.wilson import wilson_lower_bound
from whymath_backend.l3.render.registry import registered_strategies
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.pedagogy.adaptive.policy import (
    ArmPosterior,
    allowed_actions,
    select_policy_action,
)
from whymath_backend.l4.pedagogy.runtime_selector import (
    StudentSignals,
    decide,
)
from whymath_backend.schema.enums import PedagogyStrategy

# 승격 최소 표본 — 이 아래면 성과 축을 *판정하지 않고* "측정 미달"로 떨어뜨린다.
# 값의 근거: 전략 5종 × 셀당 최소 20 관측(Wilson 하한이 의미를 갖기 시작하는 대략적 하한).
# 실 트래픽이 생기면 검정력 계산으로 정교화한다(지금은 이 상수가 임의라는 사실을 명기한다).
DEFAULT_MIN_SAMPLES: int = 100

# 시험지 그리드 — 게이트 축(Polya 단계 × 막힘/힌트)이 다른 상황을 전수 열거한다.
# 안전제약은 상황마다 허용 집합이 달라지므로 단일 상황만 보면 배제가 검증되지 않는다.
_SIGNAL_GRID: tuple[tuple[str, StudentSignals], ...] = (
    ("시도전·힌트없음", StudentSignals(polya_stage=PolyaStage.UNDERSTAND, turn_count=0)),
    ("시도전·막힘", StudentSignals(polya_stage=PolyaStage.UNDERSTAND, turn_count=6)),
    ("계획·막힘", StudentSignals(polya_stage=PolyaStage.PLAN, turn_count=6)),
    ("실행·막힘", StudentSignals(polya_stage=PolyaStage.EXECUTE, turn_count=6)),
    ("회고", StudentSignals(polya_stage=PolyaStage.REVIEW, turn_count=1)),
)


@dataclass(frozen=True, slots=True)
class SafetyVerdict:
    """안전제약 판정 — 위반 1건이라도 있으면 실패."""

    trials: int
    violations: int
    examples: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.violations == 0


@dataclass(frozen=True, slots=True)
class PerformanceVerdict:
    """성과 판정 — 표본 미달이면 `measurable=False`(통과도 실패도 아닌 *미상*)."""

    samples: int
    min_samples: int
    snips_estimate: float | None
    snips_lower: float | None

    @property
    def measurable(self) -> bool:
        return self.samples >= self.min_samples


def evaluate_safety(*, samples_per_cell: int, seed: int, safety_on: bool = True) -> SafetyVerdict:
    """policy가 허용 밖 전략을 고르는지 전수 시험 — 안전제약의 기계 집행.

    `safety_on=False`(대조군)면 행동공간 제약을 우회해 *등록된 전 전략*에서 뽑는다. 그러면 게이트가
    막았어야 할 전략이 실제로 선택되어 위반이 관측된다 — 이 시험이 변별력을 갖는다는 증거다.
    """
    rng = random.Random(seed)
    posteriors: dict[PedagogyStrategy, ArmPosterior] = {}
    trials = 0
    violations = 0
    examples: list[str] = []
    for label, signals in _SIGNAL_GRID:
        permitted = allowed_actions(signals)
        for _ in range(samples_per_cell):
            trials += 1
            if safety_on:
                decision = select_policy_action(posteriors, signals, rng=rng)
                chosen = decision.strategy if decision is not None else None
            else:
                # 대조군 — 제약을 무시하고 등록 전략 전체에서 균등 추출.
                chosen = rng.choice(sorted(registered_strategies(), key=lambda s: s.value))
            if chosen is None:
                continue  # 허용 집합이 비면 policy는 기권한다(규칙표 폴백) — 위반 아님.
            if chosen not in permitted:
                violations += 1
                if len(examples) < 5:
                    allowed = sorted(s.value for s in permitted)
                    examples.append(f"{label}: {chosen.value} ∉ 허용{allowed}")
    return SafetyVerdict(trials=trials, violations=violations, examples=tuple(examples))


def evaluate_performance(
    logged: list[tuple[str, str, bool]], *, min_samples: int, confidence: float = 0.95
) -> PerformanceVerdict:
    """SNIPS 오프폴리시 추정 — 로그(행동 policy=규칙표)로 목표 policy 성과를 추정한다.

    `logged`는 `(context_label, logged_strategy, reward)` 튜플 목록이다. 행동 policy가 결정론
    규칙표이므로 성향점수(propensity)는 선택된 전략에 대해 1, 나머지는 0이다. 따라서 SNIPS는
    "목표 policy가 로그와 같은 전략을 고른 표본"만 남기는 형태로 축약된다 — 결정론 로그의
    한계이며, 이 사실을 숨기지 않고 그대로 둔다(탐색이 없으면 반사실 추정도 없다).

    **표본이 최소 요건 미만이면 추정치를 내지 않는다**(`None`) — 얇은 표본의 숫자를 근거처럼
    보이게 하지 않기 위해서다.
    """
    matched = 0
    rewards = 0
    for label, logged_strategy, reward in logged:
        signals = dict(_SIGNAL_GRID).get(label)
        if signals is None:
            continue
        target = decide(signals).strategy.value
        if target != logged_strategy:
            continue  # 결정론 행동 policy — 불일치 표본은 가중치 0.
        matched += 1
        if reward:
            rewards += 1
    if matched < min_samples:
        return PerformanceVerdict(
            samples=matched,
            min_samples=min_samples,
            snips_estimate=None,
            snips_lower=None,
        )
    return PerformanceVerdict(
        samples=matched,
        min_samples=min_samples,
        snips_estimate=rewards / matched,
        snips_lower=wilson_lower_bound(rewards, matched, confidence),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="교수법 policy 승격 게이트 — 안전제약 + 오프폴리시 성과(exit 0/1)."
    )
    parser.add_argument("--samples-per-cell", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument(
        "--control-safety-off",
        action="store_true",
        help="변별력 대조군 — 안전제약을 끄면 위반이 실측되어 exit 1이 되는지 확인.",
    )
    parser.add_argument(
        "--logged-json",
        type=str,
        default=None,
        help='오프폴리시 로그 JSON 경로 — [["시도전·막힘","SOCRATIC",true], ...]. '
        "없으면 표본 0(측정 미달).",
    )
    args = parser.parse_args(argv)

    safety = evaluate_safety(
        samples_per_cell=args.samples_per_cell,
        seed=args.seed,
        safety_on=not args.control_safety_off,
    )

    logged: list[tuple[str, str, bool]] = []
    if args.logged_json:
        with open(args.logged_json, encoding="utf-8") as fh:
            raw = json.load(fh)
        logged = [(str(r[0]), str(r[1]), bool(r[2])) for r in raw]
    performance = evaluate_performance(logged, min_samples=args.min_samples)

    report = {
        "safety": {
            "trials": safety.trials,
            "violations": safety.violations,
            "passed": safety.passed,
            "examples": list(safety.examples),
        },
        "performance": {
            "samples": performance.samples,
            "min_samples": performance.min_samples,
            "measurable": performance.measurable,
            "snips_estimate": performance.snips_estimate,
            "snips_lower": performance.snips_lower,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not safety.passed:
        print(
            f"FAIL(안전제약): policy가 허용 밖 전략을 {safety.violations}회 선택했다.",
            file=sys.stderr,
        )
        return 1
    if not performance.measurable:
        # 통과도 미달도 아니다 — *측정이 안 됐다*. 그 사실을 그대로 말한다.
        print(
            f"FAIL(측정 미달): 오프폴리시 표본 {performance.samples} < 최소 "
            f"{performance.min_samples}. 승격 판단 불가 — 규칙표를 정본으로 유지한다.",
            file=sys.stderr,
        )
        return 1
    print("PASS: 안전제약 위반 0 · 오프폴리시 표본 요건 충족.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입점
    raise SystemExit(main())
