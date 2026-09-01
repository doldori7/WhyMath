"""12월 검증 결론 판정기 — Hard Gate F-Ⅰ~F-Ⅴ + KPI 12종 스코어카드 (EOS-61).

`docs/standards/eos_verification_design_v1.md`(G0 동결본)의 §5 실패정의와 §6 KPI는
**이미 동결돼 있다**. 없는 것은 그 기준을 읽어 판정을 뱉는 **실행기**였다. 이 모듈이 그것이다.

BI 대시보드가 아니라 CLI다. 주간 7지표의 주기 집계는 `OPS-56`이 별도 좌석이고, 이쪽은
**12/31 최종 판정**(G5)이다.

────────────────────────────────────────────────────────────────────────────
설계 규칙 4 — 어기면 판정이 판정이 아니게 된다
────────────────────────────────────────────────────────────────────────────
1. **Hard Gate가 점수보다 먼저다.** F-Ⅰ~F-Ⅴ 중 하나라도 해당하면 종합 점수를 *산출하기
   전에* NO_GO다. 단일 EOS Score를 만들지 않는 이유가 이것이다 — 치명 오류 하나가
   나머지 11개 지표의 평균에 묻히면, 그 평균은 실패를 감추는 장치가 된다.
2. **미측정은 PASS가 아니다.** 입력이 비어 있으면 "기준 미달 아님 → 통과"가 아니라
   **측정 실패**다. 이 저장소가 반복해서 다친 부류이므로 `KpiVerdict`에 `unmeasured`를
   독립 상태로 두고, 하나라도 있으면 CLI가 exit 1을 낸다.
3. **평균으로 앵커를 덮지 않는다.** F-Ⅳ는 "앵커 6개 중 3개 이상 미달"이라 **앵커 단위
   분해가 판정의 전제**다. 전체 평균만 보면 한 앵커의 붕괴가 다른 다섯에 희석된다.
4. **점추정으로 게이트를 넘지 않는다.** 비율 지표는 Wilson 단측 경계로 판정한다
   (`superhuman_verification_standard`). "85.1%니까 통과"는 표본이 20이면 아무 말도 아니다.

────────────────────────────────────────────────────────────────────────────
결선표 (acceptance ⑤) — 어느 지표가 어느 소스에서 오는가
────────────────────────────────────────────────────────────────────────────
`KPI_SOURCES`가 그 정본이다. 내용 KPI 6종은 **`qa_confusion_matrix.CONTENT_KPI_CONSUMERS`를
재사용**한다 — 거기 이미 KPI↔골든 라벨축↔채점기 모듈↔좌석 태스크가 모델링돼 있고,
`consumer_module=None`이 "아직 만들어지지 않았다"는 정직한 공백 표기다. 같은 것을 여기
다시 적으면 진실 원천이 둘이 된다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.ops.qa_confusion_matrix import CONTENT_KPI_CONSUMERS

__all__ = [
    "Verdict",
    "KpiVerdict",
    "KpiResult",
    "HardGateResult",
    "Scorecard",
    "KPI_SOURCES",
    "evaluate",
    "render",
    "main",
]

CONFIDENCE = 0.95


class Verdict(str, Enum):
    """최종 3단계 판정 — 검증설계서 §5 '판정 체계'."""

    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"


class KpiVerdict(str, Enum):
    """KPI 1종의 판정 — `unmeasured`가 독립 상태인 것이 핵심이다.

    `pass`/`fail` 2상태만 두면 "입력이 없다"가 둘 중 하나로 접히고, 어느 쪽으로 접든
    거짓말이 된다: `pass`면 미측정을 통과로 위장하고, `fail`이면 측정하지도 않은 것을
    미달로 낙인찍는다.
    """

    passed = "pass"
    failed = "fail"
    unmeasured = "unmeasured"


# ──────────────────────────────────────────────────────────────────────────
# 결선표 — 기술 KPI 6종 (내용 6종은 CONTENT_KPI_CONSUMERS 재사용)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class KpiSource:
    """KPI 1종의 입력 출처 — '어디서 오는가'를 코드가 말한다."""

    kpi: str
    """검증설계서 §6 지표명(동결 문언 요약)."""

    target: str
    """목표값 문언. G2에서 재조정 가능하되 *지표 정의*는 불변(§7-1)."""

    source_module: str
    """이 지표를 산출하는 모듈(import 경로). 미착지면 `payload`에 키가 없어 unmeasured."""

    payload_key: str
    """`--input` JSON에서 이 지표가 실리는 키."""

    seat_task: str
    """산출 좌석의 태스크 id — 미착지분의 추적 축(만료 없는 유예 금지)."""


KPI_SOURCES: tuple[KpiSource, ...] = (
    KpiSource(
        kpi="HIT (CU당 인간 개입 시간)",
        target="중앙값 ≤4분 · P90 ≤8분",
        source_module="whymath_backend.ops.hit_cu_metrics",
        payload_key="hit",
        seat_task="EOS-54-hit-cu-metrics",
    ),
    KpiSource(
        kpi="자동검증 1차 통과율",
        target="≥85%",
        source_module="whymath_backend.ops.hit_cu_metrics",
        payload_key="auto_gate_pass",
        seat_task="EOS-55-generation-run-log",
    ),
    KpiSource(
        kpi="재작업률",
        target="≤15% (2회+ 재생성 ≤3%)",
        source_module="whymath_backend.ops.hit_cu_metrics",
        payload_key="rework",
        seat_task="EOS-55-generation-run-log",
    ),
    KpiSource(
        kpi="처리량",
        target="≥30 CU/h (인간 기준)",
        source_module="whymath_backend.ops.hit_cu_metrics",
        payload_key="throughput",
        seat_task="EOS-54-hit-cu-metrics",
    ),
    KpiSource(
        kpi="단위 비용",
        target="≤250원/CU (상한 400원)",
        source_module="whymath_backend.ops.cost_probe",
        payload_key="unit_cost",
        seat_task="EOS-55-generation-run-log",
    ),
    KpiSource(
        kpi="실패 유형 분포 (기계형 F1+F2)",
        target="≥60% — F-Ⅲ의 역·가장 중요한 예측 지표",
        source_module="whymath_backend.ops.hit_cu_metrics",
        payload_key="machine_share",
        seat_task="EOS-54-hit-cu-metrics",
    ),
)


#: 결선표(`CONTENT_KPI_CONSUMERS`)에 **없는** 내용 KPI 2종 — 그것이 결함이 아니라 사실이다.
#:
#: §6은 내용 KPI를 6종으로 동결했는데 EOS-60의 결선표에는 4종만 있다(2026-09-01 실측).
#: 빠진 둘은 **골든 벤치마크의 라벨 축으로 잴 수 없는 것들**이라 거기 없는 것이 맞다:
#:
#:   · 난이도 타당도 — 사람 순위와의 상관(Spearman ρ)이라 혼동행렬 축이 아니다. §7-4가
#:     "12월 내 미검증"으로 이미 자인했다(깊이앵커 A4만 학생 반응 수집).
#:   · 힌트 누설률 — F-Ⅴ Hard Gate가 같은 사실을 *차단* 축에서 본다. KPI 축에도 표기하는
#:     이유는 §6이 6종을 요구하기 때문이고, 게이트에 걸리지 않아도 0%가 아닐 수 있다.
#:
#: 이 둘을 스코어카드에서 빼면 "12종 중 10종만 있는데 12종을 봤다"는 착시가 생긴다.
#: `CONTENT_KPI_CONSUMERS`를 늘리지 않는 이유: 그것은 EOS-60(골든 벤치마크) 소유의
#: 정본이고, 골든 라벨 축이 없는 지표를 거기 끼우면 그 계약이 거짓이 된다.
NON_GOLDEN_CONTENT_KPIS: tuple[tuple[str, str, str], ...] = (
    (
        "난이도 타당도 (깊이 Spearman ρ≥0.5 · 폭 전문가 순위 ρ≥0.6)",
        "ρ≥0.5 / ρ≥0.6",
        "§7-4 — 12월 내 구조적 미검증(폭 앵커 학생 반응 미수집). 골든 라벨 축 아님",
    ),
    (
        "힌트 누설률 L1·L2 (무관용 0%)",
        "0%",
        "F-Ⅴ Hard Gate가 차단 축에서 본다. 골든 라벨 축 아님 — 전수 자동+LLM 심판+인간 30건",
    ),
)


# ──────────────────────────────────────────────────────────────────────────
# 판정 결과 타입
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class KpiResult:
    """KPI 1종의 판정 — 목표·실측·판정 + **표본수**를 항상 함께 낸다.

    표본수를 빼면 "통과"가 표본 3건짜리인지 300건짜리인지 구별되지 않는다(§7-3의
    검출력 한계가 정직하려면 분모가 보여야 한다).
    """

    kpi: str
    target: str
    verdict: KpiVerdict
    observed: str
    """사람이 읽는 실측 문언. 미측정이면 '—'."""

    sample_size: int | None = None
    wilson_bound: float | None = None
    note: str = ""
    """미측정 사유·한계·좌석 태스크 등."""


@dataclass(frozen=True, slots=True)
class HardGateResult:
    """Hard Gate 1건 — 해당하면 즉시 NO_GO."""

    code: str
    """F-Ⅰ~F-Ⅴ."""

    definition: str
    triggered: bool
    """True = 실패 정의에 해당(= NO_GO 사유)."""

    measurable: bool
    """False = 판정에 필요한 입력이 없다. `triggered`와 구분한다 —
    '실패가 아니다'와 '실패인지 모른다'는 다르다."""

    observed: str


@dataclass(frozen=True, slots=True)
class Scorecard:
    verdict: Verdict
    hard_gates: tuple[HardGateResult, ...]
    kpis: tuple[KpiResult, ...]
    limits: tuple[str, ...]
    unmeasured_count: int = 0
    unmeasurable_gate_count: int = 0

    @property
    def measurement_failed(self) -> bool:
        """측정 자체가 불완전한가 — 판정치와 **별개 축**이다.

        NO_GO는 '검증했더니 실패'이고, 측정 실패는 '검증하지 못함'이다. 둘을 같은
        exit code로 내면 후자가 전자로 읽혀 전략 변경을 오발동시킨다.
        """
        return self.unmeasured_count > 0 or self.unmeasurable_gate_count > 0


# ──────────────────────────────────────────────────────────────────────────
# Hard Gate 판정 — 점수보다 먼저 (설계 규칙 1)
# ──────────────────────────────────────────────────────────────────────────
def _num(payload: Any, *path: str) -> float | None:
    """중첩 dict에서 수치를 꺼낸다 — 없으면 None(0으로 위장하지 않는다)."""
    node: Any = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return float(node)


def evaluate_hard_gates(payload: dict[str, Any]) -> tuple[HardGateResult, ...]:
    """F-Ⅰ~F-Ⅴ 전수 판정 — 동결 문언 그대로(12월 수정 금지)."""
    results: list[HardGateResult] = []

    # F-Ⅰ: 중등 기준선 앵커(A3·A4)에서조차 HIT 중앙값 > 12분/CU
    baseline = payload.get("hit", {}).get("baseline_anchor_median_minutes")
    if isinstance(baseline, dict) and baseline:
        worst = max(float(v) for v in baseline.values() if isinstance(v, (int, float)))
        results.append(
            HardGateResult(
                "F-Ⅰ",
                "중등 기준선 앵커(A3·A4) HIT 중앙값 > 12분/CU",
                triggered=worst > 12.0,
                measurable=True,
                observed=f"최대 {worst:.1f}분 ({', '.join(sorted(baseline))})",
            )
        )
    else:
        results.append(
            HardGateResult("F-Ⅰ", "중등 기준선 앵커 HIT 중앙값 > 12분/CU", False, False, "—")
        )

    # F-Ⅱ: 인간 검수를 통과한 CU의 수학적 오류율 > 2%
    errs = _num(payload, "content", "reviewed_math_errors")
    total = _num(payload, "content", "reviewed_cu_total")
    if errs is not None and total is not None and total > 0:
        # 상한을 쓴다 — "2% 넘지 않았다"를 주장하려면 낙관적 점추정으로는 부족하다.
        upper = wilson_upper_bound(int(errs), int(total), CONFIDENCE)
        results.append(
            HardGateResult(
                "F-Ⅱ",
                "인간 검수 통과 CU의 수학적 오류율 > 2%",
                triggered=upper > 0.02,
                measurable=True,
                observed=f"{errs:.0f}/{total:.0f} · Wilson 상한 {upper:.2%}",
            )
        )
    else:
        results.append(HardGateResult("F-Ⅱ", "검수 통과 CU 오류율 > 2%", False, False, "—"))

    # F-Ⅲ: 판단형(F3+F6+F7) 합 > 60%
    judgment = _num(payload, "failure_distribution", "judgment_share")
    if judgment is not None:
        results.append(
            HardGateResult(
                "F-Ⅲ",
                "판단형(F3+F6+F7) 합 > 60% (자동화로 흡수 불가한 실패가 지배)",
                triggered=judgment > 0.60,
                measurable=True,
                observed=f"{judgment:.1%}",
            )
        )
    else:
        results.append(HardGateResult("F-Ⅲ", "판단형(F3+F6+F7) 합 > 60%", False, False, "—"))

    # F-Ⅳ: 앵커 6개 중 3개 이상 기준 미달 (2개면 Conditional Go)
    anchors = payload.get("anchors")
    if isinstance(anchors, dict) and anchors:
        failing = sorted(name for name, ok in anchors.items() if ok is False)
        results.append(
            HardGateResult(
                "F-Ⅳ",
                "앵커 6개 중 3개 이상 기준 미달 (2개면 Conditional Go)",
                triggered=len(failing) >= 3,
                measurable=True,
                observed=f"{len(failing)}/{len(anchors)} 미달"
                + (f" — {', '.join(failing)}" if failing else ""),
            )
        )
    else:
        results.append(HardGateResult("F-Ⅳ", "앵커 6개 중 3개 이상 미달", False, False, "—"))

    # F-Ⅴ: 힌트의 의미적 정답 누설이 표본 검수에서 ≥ 10%
    leaks = _num(payload, "content", "hint_leak_hits")
    leak_n = _num(payload, "content", "hint_leak_sample")
    if leaks is not None and leak_n is not None and leak_n > 0:
        upper = wilson_upper_bound(int(leaks), int(leak_n), CONFIDENCE)
        results.append(
            HardGateResult(
                "F-Ⅴ",
                "힌트의 의미적 정답 누설(자동 검사 밖)이 표본 검수에서 ≥ 10%",
                triggered=upper >= 0.10,
                measurable=True,
                observed=f"{leaks:.0f}/{leak_n:.0f} · Wilson 상한 {upper:.2%}",
            )
        )
    else:
        results.append(HardGateResult("F-Ⅴ", "힌트 의미적 정답 누설 ≥ 10%", False, False, "—"))

    return tuple(results)


# ──────────────────────────────────────────────────────────────────────────
# KPI 스코어카드
# ──────────────────────────────────────────────────────────────────────────
def _ratio_kpi(
    src: KpiSource, payload: dict[str, Any], *, floor: float | None, ceiling: float | None
) -> KpiResult:
    """비율 지표 — Wilson 단측 경계로 판정한다(점추정 금지·설계 규칙 4)."""
    node = payload.get(src.payload_key)
    if not isinstance(node, dict):
        return KpiResult(
            src.kpi, src.target, KpiVerdict.unmeasured, "—", note=f"좌석 {src.seat_task}"
        )
    hits = _num(node, "hits")
    trials = _num(node, "trials")
    if hits is None or trials is None or trials <= 0:
        return KpiResult(
            src.kpi, src.target, KpiVerdict.unmeasured, "—", note=f"좌석 {src.seat_task}"
        )

    if floor is not None:
        bound = wilson_lower_bound(int(hits), int(trials), CONFIDENCE)
        ok = bound >= floor
        shown = f"{hits / trials:.1%} · Wilson 하한 {bound:.1%}"
    else:
        assert ceiling is not None
        bound = wilson_upper_bound(int(hits), int(trials), CONFIDENCE)
        ok = bound <= ceiling
        shown = f"{hits / trials:.1%} · Wilson 상한 {bound:.1%}"
    return KpiResult(
        src.kpi,
        src.target,
        KpiVerdict.passed if ok else KpiVerdict.failed,
        shown,
        sample_size=int(trials),
        wilson_bound=bound,
    )


def _scalar_kpi(src: KpiSource, payload: dict[str, Any], *, spec: dict[str, Any]) -> KpiResult:
    """분포 지표(HIT·처리량·단가) — 중앙값·P90 등 요약값을 목표와 대조."""
    node = payload.get(src.payload_key)
    if not isinstance(node, dict):
        return KpiResult(
            src.kpi, src.target, KpiVerdict.unmeasured, "—", note=f"좌석 {src.seat_task}"
        )

    parts: list[str] = []
    verdicts: list[bool] = []
    for key, (limit, direction, unit) in spec.items():
        value = _num(node, key)
        if value is None:
            return KpiResult(
                src.kpi, src.target, KpiVerdict.unmeasured, "—", note=f"'{key}' 미산출"
            )
        ok = value <= limit if direction == "max" else value >= limit
        verdicts.append(ok)
        parts.append(f"{key}={value:g}{unit}{'' if ok else ' ✗'}")

    n = _num(node, "sample_size")
    return KpiResult(
        src.kpi,
        src.target,
        KpiVerdict.passed if all(verdicts) else KpiVerdict.failed,
        " · ".join(parts),
        sample_size=int(n) if n is not None else None,
    )


#: 기술 KPI별 판정 규격 — 목표값은 G2 재조정 가능하되 지표 정의는 불변(§7-1).
_TECHNICAL_SPECS: dict[str, dict[str, Any]] = {
    "hit": {"median_minutes": (4.0, "max", "분"), "p90_minutes": (8.0, "max", "분")},
    "throughput": {"cu_per_hour": (30.0, "min", " CU/h")},
    "unit_cost": {"krw_per_cu": (250.0, "max", "원")},
}


def evaluate_kpis(payload: dict[str, Any]) -> tuple[KpiResult, ...]:
    """KPI 12종 — 기술 6(실측) + 내용 6(결선표 기반 착지 여부)."""
    out: list[KpiResult] = []
    for src in KPI_SOURCES:
        if src.payload_key in _TECHNICAL_SPECS:
            out.append(_scalar_kpi(src, payload, spec=_TECHNICAL_SPECS[src.payload_key]))
        elif src.payload_key == "auto_gate_pass":
            out.append(_ratio_kpi(src, payload, floor=0.85, ceiling=None))
        elif src.payload_key == "rework":
            out.append(_ratio_kpi(src, payload, floor=None, ceiling=0.15))
        elif src.payload_key == "machine_share":
            out.append(_ratio_kpi(src, payload, floor=0.60, ceiling=None))
        else:  # pragma: no cover — KPI_SOURCES에 규격 없는 항목이 늘면 여기로 온다
            out.append(
                KpiResult(src.kpi, src.target, KpiVerdict.unmeasured, "—", note="판정 규격 미정의")
            )

    # 내용 KPI 6종 — 채점기가 착지했는지를 결선표(CONTENT_KPI_CONSUMERS)가 말한다.
    content = payload.get("content", {})
    for consumer in CONTENT_KPI_CONSUMERS:
        if consumer.consumer_module is None:
            out.append(
                KpiResult(
                    consumer.kpi,
                    "§6 내용 KPI",
                    KpiVerdict.unmeasured,
                    "—",
                    note=f"채점기 미착지 — 좌석 {consumer.seat_task}",
                )
            )
            continue
        node = content.get(consumer.seat_task)
        if not isinstance(node, dict):
            out.append(
                KpiResult(
                    consumer.kpi,
                    "§6 내용 KPI",
                    KpiVerdict.unmeasured,
                    "—",
                    note=f"채점기는 있으나 입력 없음 — {consumer.consumer_module}",
                )
            )
            continue
        hits, trials = _num(node, "hits"), _num(node, "trials")
        floor = node.get("floor")
        if hits is None or trials is None or trials <= 0 or not isinstance(floor, (int, float)):
            out.append(
                KpiResult(
                    consumer.kpi,
                    "§6 내용 KPI",
                    KpiVerdict.unmeasured,
                    "—",
                    note="입력 불완전",
                )
            )
            continue
        bound = wilson_lower_bound(int(hits), int(trials), CONFIDENCE)
        out.append(
            KpiResult(
                consumer.kpi,
                f"≥{float(floor):.0%}",
                KpiVerdict.passed if bound >= float(floor) else KpiVerdict.failed,
                f"{hits / trials:.1%} · Wilson 하한 {bound:.1%}",
                sample_size=int(trials),
                wilson_bound=bound,
            )
        )

    # 골든 라벨 축으로 잴 수 없는 내용 KPI 2종 — 빼면 12종이 10종이 된다(상수 주석 참조).
    for kpi, target, reason in NON_GOLDEN_CONTENT_KPIS:
        node = content.get(kpi)
        if isinstance(node, dict) and isinstance(node.get("observed"), str):
            out.append(
                KpiResult(
                    kpi,
                    target,
                    KpiVerdict.passed if bool(node.get("passed")) else KpiVerdict.failed,
                    str(node["observed"]),
                    sample_size=(
                        int(node["sample_size"])
                        if isinstance(node.get("sample_size"), int)
                        else None
                    ),
                )
            )
        else:
            out.append(KpiResult(kpi, target, KpiVerdict.unmeasured, "—", note=reason))
    return tuple(out)


# ──────────────────────────────────────────────────────────────────────────
# 종합 판정 — Hard Gate가 먼저다 (설계 규칙 1)
# ──────────────────────────────────────────────────────────────────────────
#: §7 한계 — 리포트에 **항상** 동반 출력한다(acceptance ④).
#: 이 한계를 빼면 "오류율 0.5% 통과"가 정밀 추정으로 읽히는데, 185 CU 표본은 그 해상도를
#: 갖지 않는다. 한계를 적어야 판정이 정직하다.
DESIGN_LIMITS: tuple[str, ...] = (
    "§7-1 목표값은 실측 벤치마크가 아니라 산술 손익분기 도출값 — "
    "G2 기준선 실측에서 재조정이 정상 경로다(지표 정의는 불변).",
    "§7-2 손익분기 산식의 물량 가정(545노드×4문항)은 실측(원자 리프 1,823)과 다르다 — "
    "G5 판정 시 통과 학교급 기준으로 재산출해야 한다.",
    "§7-3 검수 185 CU 표본은 '치명적으로 나쁨'(오류율 8%+)은 잡지만 "
    "0.5% 수준의 정밀 추정은 못 한다.",
    "§7-4 폭 앵커 난이도 타당도는 12월 내 미검증 — 학생 반응은 깊이앵커(A4)만 수집.",
)


def evaluate(payload: dict[str, Any]) -> Scorecard:
    """입력 → 3단계 판정. **Hard Gate를 먼저 보고, 걸리면 점수를 만들지 않는다.**"""
    gates = evaluate_hard_gates(payload)
    kpis = evaluate_kpis(payload)

    unmeasured = sum(1 for k in kpis if k.verdict is KpiVerdict.unmeasured)
    unmeasurable_gates = sum(1 for g in gates if not g.measurable)

    if any(g.triggered for g in gates):
        # F-Ⅰ~Ⅴ 중 1+ 해당 → No-Go. 종합 점수를 산출하지 않는다.
        return Scorecard(Verdict.NO_GO, gates, kpis, DESIGN_LIMITS, unmeasured, unmeasurable_gates)

    # Conditional Go — F-Ⅳ의 "2개면 Conditional Go" 조항. 앵커 미달이 1~2개면 학교급 일부만
    # 성립한 것이고, 그때의 결론은 통과가 아니라 **출시 범위 축소 확정**이다.
    anchors = payload.get("anchors")
    failing = sum(1 for ok in anchors.values() if ok is False) if isinstance(anchors, dict) else 0
    if failing > 0 or any(k.verdict is KpiVerdict.failed for k in kpis):
        return Scorecard(
            Verdict.CONDITIONAL_GO, gates, kpis, DESIGN_LIMITS, unmeasured, unmeasurable_gates
        )

    # **GO는 측정이 완결됐을 때만 도달 가능하다.**
    #
    # 이 가드가 없으면 *빈 입력*이 GO를 낸다 — Hard Gate가 전부 '판정 불가'라 아무것도
    # triggered되지 않고, KPI가 전부 '미측정'이라 failed도 없기 때문이다. 실측으로 확인했다:
    # `evaluate({})` → GO(미측정 KPI 10 · 판정 불가 게이트 5). 그 GO를 읽는 소비자에게는
    # "검증했고 통과했다"로 보이는데 실제로는 아무것도 검증하지 않았다.
    #
    # 4번째 상태(UNDETERMINED)를 만들지 않은 이유: 판정 형식 3단계는 §5에서 동결됐고
    # 12월 수정 금지다(acceptance ③). 대신 **GO를 도달 불가로 만든다** — 확인되지 않은
    # 것은 "주 기준 충족"이 아니므로 GO의 정의를 애초에 만족하지 않는다. 측정 불완전의
    # *사실*은 `measurement_failed`·리포트 경고·CLI exit 1이 별도 축으로 말한다.
    if unmeasured or unmeasurable_gates:
        return Scorecard(
            Verdict.CONDITIONAL_GO, gates, kpis, DESIGN_LIMITS, unmeasured, unmeasurable_gates
        )
    return Scorecard(Verdict.GO, gates, kpis, DESIGN_LIMITS, unmeasured, unmeasurable_gates)


def render(card: Scorecard) -> str:
    lines = ["# EOS 12월 검증 결론 스코어카드 (EOS-61)", ""]
    lines.append(f"## 판정: **{card.verdict.value}**")
    if card.measurement_failed:
        lines.append("")
        lines.append(
            f"> ⚠️ **측정 불완전** — 미측정 KPI {card.unmeasured_count}종 · "
            f"판정 불가 Hard Gate {card.unmeasurable_gate_count}건. "
            "이 판정은 확정이 아니다(측정 실패 ≠ 기준 미달)."
        )
    lines += ["", "## Hard Gate — F-Ⅰ~F-Ⅴ (점수보다 먼저)", ""]
    lines.append("| 코드 | 실패 정의 | 실측 | 판정 |")
    lines.append("|---|---|---|---|")
    for g in gates_sorted(card.hard_gates):
        if g.triggered:
            mark = "🚫 해당(NO_GO)"
        else:
            mark = "✔ 미해당" if g.measurable else "— 판정 불가"
        lines.append(f"| {g.code} | {g.definition} | {g.observed} | {mark} |")

    lines += ["", "## KPI 스코어카드 (기술 6 · 내용 6)", ""]
    lines.append("| 지표 | 목표 | 실측 | 표본 | 판정 |")
    lines.append("|---|---|---|---:|---|")
    for k in card.kpis:
        mark = {"pass": "✔", "fail": "✗", "unmeasured": "— 미측정"}[k.verdict.value]
        n = str(k.sample_size) if k.sample_size is not None else "—"
        note = f" <br>_{k.note}_" if k.note else ""
        lines.append(f"| {k.kpi} | {k.target} | {k.observed}{note} | {n} | {mark} |")

    lines += ["", "## 한계 (§7 — 정직)", ""]
    lines += [f"- {limit}" for limit in card.limits]
    return "\n".join(lines)


def gates_sorted(gates: tuple[HardGateResult, ...]) -> tuple[HardGateResult, ...]:
    """해당(triggered) → 판정 불가 → 미해당 순 — 읽는 사람이 먼저 봐야 할 것이 위로."""
    return tuple(sorted(gates, key=lambda g: (not g.triggered, g.measurable)))


def main(argv: list[str] | None = None) -> int:
    """CLI — exit 0 = GO, 1 = 그 외(CONDITIONAL_GO·NO_GO·측정 실패).

    exit 1을 세 경우가 공유하는 이유: **셋 다 '지금 그대로 진행하면 안 된다'**이기 때문이다.
    셋의 *구분*은 stdout의 판정 문구와 측정 불완전 경고가 한다 — exit code를 셋으로 쪼개면
    호출 스크립트가 조건 분기를 잘못 짜서 CONDITIONAL_GO를 GO로 흡수할 여지가 생긴다.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="집계 입력 JSON")
    parser.add_argument("--json", type=Path, default=None, help="판정 결과 JSON 출력 경로")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # 입력을 못 읽은 것은 '기준 미달'이 아니라 측정 실패다 — 사유를 남긴다.
        print(f"측정 실패({type(exc).__name__}): {args.input} — {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(f"측정 실패: {args.input} 최상위가 객체가 아니다", file=sys.stderr)
        return 1

    card = evaluate(payload)
    print(render(card))
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "verdict": card.verdict.value,
                    "measurement_failed": card.measurement_failed,
                    "unmeasured_kpis": card.unmeasured_count,
                    "unmeasurable_gates": card.unmeasurable_gate_count,
                    "hard_gates": [
                        {
                            "code": g.code,
                            "triggered": g.triggered,
                            "measurable": g.measurable,
                            "observed": g.observed,
                        }
                        for g in card.hard_gates
                    ],
                    "kpis": [
                        {
                            "kpi": k.kpi,
                            "verdict": k.verdict.value,
                            "observed": k.observed,
                            "sample_size": k.sample_size,
                        }
                        for k in card.kpis
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    if card.measurement_failed:
        print(
            f"\n측정 실패: 미측정 KPI {card.unmeasured_count}종 · "
            f"판정 불가 게이트 {card.unmeasurable_gate_count}건 — 이 상태로 GO를 선언할 수 없다.",
            file=sys.stderr,
        )
        return 1
    return 0 if card.verdict is Verdict.GO else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
