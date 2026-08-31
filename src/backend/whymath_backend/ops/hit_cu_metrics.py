"""HIT·CU 단위 생산 계측 집계 CLI — 주 기준 KPI(HIT 중앙값≤4분)의 판독기 (EOS-54 acceptance ②).

무엇을 재나 (정본: `docs/standards/eos_verification_design_v1.md` §6)
--------------------------------------------------------------------
검수 타이머 이벤트(`schema/review_timer.py` — started/finished/aborted)를 CU 단위로 묶어:

1. **HIT 분포** — CU당 인간 개입 시간(초): 그 CU 전 세션(sitting)의 계측 경과 합.
   중앙값·P90(목표 중앙값 ≤4분·P90 ≤8분 — 목표값은 G2 재조정 가능, 지표 정의는 동결).
2. **적재율("작동한 비율" 원칙 — acceptance ①)** — 검수 *판정*(코퍼스 review_status·#841
   라벨 JSONL) 중 타이머 이벤트가 동반된 비율. 정상 응답 200은 계측이 아니다 — 판정은
   있는데 타이머가 없으면 이 비율이 떨어져 그대로 드러난다. 판정은 **Wilson 단측 하한**
   병기(점추정·인상 판정 금지 — 초인간 검증 표준).
3. **CU당 토큰·금액** — GenerationLog 행(JSONL export)을 CU에 조인해 CU당 비용 분포·합계.
4. **실패코드 분포** — 반려(rejected) 판정의 F1~F8 분포(`GenerationFailureCode` 동결 enum
   소비 — 8코드 전건 표기·0 포함) + 기계형(F1+F2)/판단형(F3+F6+F7) 비중(F-Ⅲ 판정 축).

미측정 ≠ 0 (acceptance ④ — 2026-08-22 규칙)
--------------------------------------------
측정 실패가 "0분"으로 위장되지 않게 다음을 강제한다:
  - **CU 3분류**: measured(종결+전 세션 계측) / unmeasured(종결했으나 경과 미계측 세션 존재 —
    HIT 표본 제외·분리 카운트·0초 산입 금지) / unfinished(종결 이벤트 없음 — 검수 미완).
  - **입력 0건 = 측정 실패**: 이벤트 0건·시간 창 내 0건·measured CU 0건은 전부 "성공 0"이
    아니라 **exit 1**로 승격한다.
  - **적재율 미산출 명시**: 판정 소스(--verdicts)가 없으면 적재율을 0%로 찍지 않고
    "미산출(소스 미제공)"로 보고한다. --min-coverage 게이트가 지정됐는데 소스가 없으면
    통과가 아니라 측정 실패(exit 1)다.
  - **비용 미계측 분리**: 비용 행이 조인되지 않은 CU는 0원 산입이 아니라 분리 카운트.

인프로세스 이중 회계 (`ops/cost_probe` 원칙 — SaaS 단독 의존 금지)
------------------------------------------------------------------
비용·토큰의 판정 원천은 **인프로세스 영속**(`GenerationLog` — `db/models/provenance.py`,
JSONL export)이다. Langfuse 등 외부 관측 인프라에 일절 의존하지 않는다 — 관측 SaaS가 죽어도
이 CLI는 로컬 기록만으로 판정치를 내고, 기록 자체가 없으면 "측정 실패"가 보인다(0건
통과/미달로 위장되지 않음 — langfuse v2 8일 무증상 전멸의 교훈).

측정 도구 실패 경로 설계 (2026-08-22 규칙)
------------------------------------------
  - **단계별 즉시 출력** — 로드 단계마다 결과(건수·실패 사유)를 그 자리에서 flush 출력한다.
    중간에 죽어도 어디까지 갔는지 보인다.
  - **실패 원인 보존** — 파싱 실패는 예외 타입명+줄 번호로 전건 보고(값·원문 미출력).
  - **시간 필터** — `--since`/`--until`로 "지금 보는 것이 이번 실행 것인가"를 강제할 수 있다
    (이전 실행 증거 오독 방지). 귀속 시각은 발생(occurred_at) 우선·수신(recorded_at) 폴백
    (EOS-48 `effective_event_moment` 계약 동형). 시각 미상 이벤트는 필터 시 제외+분리 카운트.
  - **외부 프로세스 0** — 파일 I/O만 한다(서브프로세스·네트워크 없음 — 타임아웃 대상 없음).

입력 형식
---------
  --events   검수 타이머 이벤트 JSONL(`harness/review_timer.append_event_jsonl` 산출) [필수]
  --verdicts 검수 판정 JSONL — 코퍼스 레코드(slug+review_status) 또는 #841 라벨(code+
             review_status) 형식. approved/rejected 행만 판정으로 센다(pending=미판정).
  --generation-log  GenerationLog 행 JSONL — slug 또는 problem_id + input_tokens/
             output_tokens/cost_usd. DB 직접 조회 모드는 미구현(정직한 공백 — 현행 검수
             흐름이 파일 기반이라 export 파일 입력으로 시작·후속 확장).

exit code (게이트 CLI 관례 — cost_probe·corpus_audit_eval 동형)
---------------------------------------------------------------
  0 — 측정 성공(HIT 표본 ≥1) + 지정된 게이트 전부 통과.
  1 — 측정 실패(입력/창/표본 0건·입력 파일 부재·파싱 전멸) 또는 게이트 위반.

집행 별항(정본화≠집행 — acceptance ③)
--------------------------------------
검수 UI(**ADMIN-07**)가 타이머·반려코드 없이 판정 제출 자체를 불가하게 하는 UI 결선은
**후속 태스크**다(ADMIN-07 acceptance 확장 — amend CLI 부재(HARN-24 todo)로 등재 세션 판정
사안). 이 리포트는 그 미결선을 footer로 상시 명기한다 — 적재율이 100%가 되기 전까지 이
계측기는 "부분 배선" 상태다.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whymath_backend.harness.review_timer import load_events_jsonl
from whymath_backend.harness.wilson import wilson_lower_bound
from whymath_backend.schema.enums import GenerationFailureCode
from whymath_backend.schema.review_timer import ReviewTimerEvent, ReviewTimerEventType

__all__ = [
    "CuSummary",
    "HitCuReport",
    "SessionSummary",
    "aggregate",
    "classify_cus",
    "classify_sessions",
    "effective_moment",
    "main",
    "render_report",
]

_EXIT_OK = 0
_EXIT_MEASUREMENT_FAIL = 1

# F-Ⅲ 판정 축(설계서 §4·§5) — 기계형/판단형 부분집합. 정본은 GenerationFailureCode docstring·
# `test_generation_failure_code.py::test_judgment_type_subset_frozen`이 동결(여기는 소비).
_MACHINE_CODES = frozenset({GenerationFailureCode.F1, GenerationFailureCode.F2})
_JUDGMENT_CODES = frozenset(
    {GenerationFailureCode.F3, GenerationFailureCode.F6, GenerationFailureCode.F7}
)


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 코어 — I/O 없음(픽스처 전수 검증 가능·cost_report/cost_probe 동형).
# ──────────────────────────────────────────────────────────────────────────


def _percentile(sorted_vals: list[float], q: float) -> float | None:
    """선형 보간 백분위 — `ops/cost_report._percentile` 동일 규약(소비만·정본 그쪽)."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _ensure_aware(moment: datetime) -> datetime:
    """naive datetime은 UTC로 간주해 aware화(혼합 비교 TypeError 방지 — writer는 항상 aware)."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def effective_moment(event: ReviewTimerEvent) -> datetime | None:
    """이벤트 귀속 시각 — 발생(occurred_at) 우선·수신(recorded_at) 폴백(EOS-48 계약 동형)."""
    if event.occurred_at is not None:
        return _ensure_aware(event.occurred_at)
    if event.recorded_at is not None:
        return _ensure_aware(event.recorded_at)
    return None


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """검수 세션(sitting) 1건 요약 — 같은 review_session_id 이벤트의 축약."""

    review_session_id: uuid.UUID
    cu_slug: str
    has_finish: bool
    """finished 이벤트 존재 여부(판정 동반 종결)."""
    has_terminal: bool
    """종결 신호(finished 또는 aborted) 존재 여부. False = dangling start(신호 유실)."""
    measured: bool
    """계측 성립 — 종결 신호가 있고 그 전건에 elapsed_ms가 있다. dangling은 False."""
    elapsed_ms_total: int
    """계측된 경과 합(ms) — 미계측(None)은 합산하지 않는다(0 날조 금지)."""
    verdicts: tuple[str, ...]
    """finished 이벤트의 판정들(정상 1개 — 복수는 anomaly로 별도 카운트)."""
    failure_codes: tuple[str, ...]
    """반려 실패코드들(F1~F8 값)."""


def dedupe_events(
    events: Sequence[ReviewTimerEvent],
) -> tuple[list[ReviewTimerEvent], int]:
    """event_id 중복 제거(첫 관측 유지·입력 순서 보존) + 제거 수.

    같은 event_id 재출현은 새 관측이 아니라 같은 관측의 재기록이다(append 재시도 경로) —
    그대로 두면 종결 이벤트가 두 번 합산돼 1분 검수가 2분이 된다(중앙값·P90 게이트 오염).
    제거 수는 리포트로 올린다(조용히 버리면 침묵 실패).
    """
    seen: set[uuid.UUID] = set()
    unique: list[ReviewTimerEvent] = []
    duplicates = 0
    for event in events:
        if event.event_id in seen:
            duplicates += 1
            continue
        seen.add(event.event_id)
        unique.append(event)
    return unique, duplicates


def classify_sessions(events: Sequence[ReviewTimerEvent]) -> tuple[list[SessionSummary], int]:
    """이벤트 → 세션 요약 + anomaly 수(한 세션 복수 slug/복수 종결).

    anomaly 세션은 **계측 성립(measured)으로 치지 않는다** — 복수 종결의 경과 합산·복수
    slug의 임의 slug 귀속은 구조적으로 신뢰할 수 없는 측정이라, 표본에 넣으면 중앙값·P90
    게이트가 오염된다. 대신 버리지도 않는다: unmeasured로 강등해 CU 미계측 카운트와
    anomaly 수 양쪽으로 가시화한다(관측을 버리면 침묵 실패).
    """
    by_session: dict[uuid.UUID, list[ReviewTimerEvent]] = {}
    for event in events:
        by_session.setdefault(event.review_session_id, []).append(event)

    summaries: list[SessionSummary] = []
    anomaly_count = 0
    for session_id, group in by_session.items():
        slugs = {e.cu_slug for e in group}
        terminal = [
            e
            for e in group
            if e.event_type
            in (ReviewTimerEventType.FINISHED.value, ReviewTimerEventType.ABORTED.value)
        ]
        finishes = [e for e in terminal if e.event_type == ReviewTimerEventType.FINISHED.value]
        anomalous = len(slugs) > 1 or len(terminal) > 1
        if anomalous:
            anomaly_count += 1
        # 결정론: slug는 started 이벤트 우선, 없으면 정렬 최솟값(안정).
        started = [e for e in group if e.event_type == ReviewTimerEventType.STARTED.value]
        slug = started[0].cu_slug if started else min(slugs)
        # anomaly는 measured 불성립 — 오염 표본을 KPI에 넣지 않는다(수는 위에서 셌다).
        measured = (
            bool(terminal) and not anomalous and all(e.elapsed_ms is not None for e in terminal)
        )
        elapsed_total = sum(e.elapsed_ms for e in terminal if e.elapsed_ms is not None)
        summaries.append(
            SessionSummary(
                review_session_id=session_id,
                cu_slug=slug,
                has_finish=bool(finishes),
                has_terminal=bool(terminal),
                measured=measured,
                elapsed_ms_total=elapsed_total,
                verdicts=tuple(str(e.verdict) for e in finishes if e.verdict is not None),
                failure_codes=tuple(
                    str(e.failure_code) for e in finishes if e.failure_code is not None
                ),
            )
        )
    return summaries, anomaly_count


@dataclass(frozen=True, slots=True)
class CuSummary:
    """CU 1건 요약 — kind는 3분류(measured/unmeasured/unfinished — 미측정≠0의 구조화)."""

    cu_slug: str
    kind: str
    """'measured' = HIT 표본 / 'unmeasured' = 종결했으나 미계측 세션 존재(분리·0초 산입
    금지) / 'unfinished' = 종결 이벤트 없음(검수 미완 — HIT 대상 아님)."""
    hit_seconds: float | None
    """measured일 때만 값(전 세션 경과 합·초). 그 외 None — 0으로 위장하지 않는다."""
    session_count: int


def classify_cus(sessions: Sequence[SessionSummary]) -> list[CuSummary]:
    """세션 → CU 3분류. measured CU만 hit_seconds를 갖는다(그 외 None — 날조 금지)."""
    by_cu: dict[str, list[SessionSummary]] = {}
    for session in sessions:
        by_cu.setdefault(session.cu_slug, []).append(session)

    cus: list[CuSummary] = []
    for slug in sorted(by_cu):
        group = by_cu[slug]
        has_finish = any(s.has_finish for s in group)
        all_measured = all(s.measured for s in group)
        if not has_finish:
            kind, hit = "unfinished", None
        elif not all_measured:
            kind, hit = "unmeasured", None
        else:
            kind = "measured"
            hit = sum(s.elapsed_ms_total for s in group) / 1000.0
        cus.append(CuSummary(cu_slug=slug, kind=kind, hit_seconds=hit, session_count=len(group)))
    return cus


def _parse_verdict_rows(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[tuple[str, str]], int, list[str]]:
    """판정 JSONL 행 → (식별자, 판정) 목록 + 비판정 행 수 + 실패 사유.

    식별자 키는 slug/cu_slug/code(코퍼스·#841 라벨 양식 수용), 판정 키는 review_status/
    verdict. approved/rejected만 판정 — pending 등은 비판정으로 분리(분모 오염 방지).
    """
    verdicts: list[tuple[str, str]] = []
    non_verdict = 0
    errors: list[str] = []
    for idx, row in enumerate(rows, start=1):
        identity = row.get("slug") or row.get("cu_slug") or row.get("code")
        status = row.get("review_status") or row.get("verdict")
        if not isinstance(identity, str) or not identity:
            errors.append(f"row {idx}: MissingIdentityKey(slug/cu_slug/code)")
            continue
        if status in ("approved", "rejected"):
            verdicts.append((identity, str(status)))
        else:
            non_verdict += 1  # pending·미기재 — 판정 아님(분모 제외·정직)
    return verdicts, non_verdict, errors


@dataclass(frozen=True, slots=True)
class HitCuReport:
    """집계 리포트 — 사람용 렌더·JSON 직렬화의 단일 진실."""

    # ── 입력 위생(실패 경로 가시화) ──
    event_count: int
    parse_error_count: int
    window_excluded_count: int
    time_unknown_excluded_count: int
    session_anomaly_count: int
    duplicate_event_count: int
    """같은 event_id 재출현으로 제거된 행 수(append 재시도 등) — 중복 합산 오염 방지."""

    # ── 세션·CU 3분류(미측정≠0) ──
    session_count: int
    dangling_session_count: int
    cu_total: int
    cu_measured: int
    cu_unmeasured: int
    cu_unfinished: int

    # ── HIT 분포(초) — measured CU 표본만 ──
    hit_median_seconds: float | None
    hit_p90_seconds: float | None
    hit_mean_seconds: float | None
    hit_total_seconds: float

    # ── 적재율("작동한 비율") — 판정 소스 있을 때만 산출(없으면 None=미산출·0% 아님) ──
    verdict_total: int | None
    verdict_with_timer: int | None
    coverage_rate: float | None
    coverage_wilson_lower: float | None
    verdict_non_verdict_rows: int
    verdict_parse_errors: tuple[str, ...] = field(default=())

    # ── 실패코드 분포(F1~F8 전건 표기 — GenerationFailureCode 소비) ──
    rejected_count: int = 0
    failure_code_counts: dict[str, int] = field(default_factory=dict)
    machine_share: float | None = None
    judgment_share: float | None = None
    unknown_failure_code_count: int = 0

    # ── CU당 비용(GenerationLog 인프로세스 기록 — SaaS 비의존) ──
    cost_rows_matched: int = 0
    cost_rows_unmatched: int = 0
    cost_rows_unmetered: int = 0
    """조인은 됐으나 cost_usd(또는 토큰 전건)가 null인 행 — 0으로 날조하지 않고 분리."""
    cost_parse_errors: tuple[str, ...] = field(default=())
    cu_with_cost: int = 0
    cu_cost_incomplete: int = 0
    """비용 미기록 행이 섞인 CU — 부분합은 과소집계라 백분위 표본에서 제외."""
    cu_without_cost: int = 0
    cost_usd_per_cu_p50: float | None = None
    cost_usd_per_cu_p90: float | None = None
    cost_usd_total: float | None = None
    tokens_total: int | None = None


def aggregate(
    events: Sequence[ReviewTimerEvent],
    *,
    parse_error_count: int = 0,
    window_excluded_count: int = 0,
    time_unknown_excluded_count: int = 0,
    verdict_rows: Sequence[dict[str, Any]] | None = None,
    genlog_rows: Sequence[dict[str, Any]] | None = None,
) -> HitCuReport:
    """순수 집계 — 이벤트(+판정·비용 행) → HitCuReport. I/O 0."""
    raw_count = len(events)
    deduped, duplicate_count = dedupe_events(events)
    events = deduped
    sessions, anomaly_count = classify_sessions(events)
    cus = classify_cus(sessions)

    measured = [c for c in cus if c.kind == "measured"]
    hit_samples = sorted(float(c.hit_seconds) for c in measured if c.hit_seconds is not None)

    # ── 적재율 — 판정 소스가 있을 때만(없으면 None=미산출 — 0%로 위장 금지) ──
    finished_slugs = {s.cu_slug for s in sessions if s.has_finish}
    verdict_total: int | None = None
    verdict_with_timer: int | None = None
    coverage_rate: float | None = None
    coverage_wilson: float | None = None
    non_verdict_rows = 0
    verdict_errors: tuple[str, ...] = ()
    if verdict_rows is not None:
        verdicts, non_verdict_rows, errors = _parse_verdict_rows(verdict_rows)
        verdict_errors = tuple(errors)
        verdict_total = len(verdicts)
        verdict_with_timer = sum(1 for identity, _ in verdicts if identity in finished_slugs)
        if verdict_total > 0:
            coverage_rate = verdict_with_timer / verdict_total
            coverage_wilson = wilson_lower_bound(verdict_with_timer, verdict_total)

    # ── 실패코드 분포 — enum 전 멤버 0 포함(동결 8코드 소비·자유 코드는 unknown 분리) ──
    code_counts: dict[str, int] = {code.value: 0 for code in GenerationFailureCode}
    known_values = set(code_counts)
    rejected_count = 0
    unknown_code_count = 0
    for session in sessions:
        for verdict in session.verdicts:
            if verdict == "rejected":
                rejected_count += 1
        for code in session.failure_codes:
            if code in known_values:
                code_counts[code] += 1
            else:
                unknown_code_count += 1  # schema 밖 경로 유입 방어(버리지 않고 센다)
    machine_share: float | None = None
    judgment_share: float | None = None
    if rejected_count > 0:
        machine_share = sum(code_counts[c.value] for c in _MACHINE_CODES) / rejected_count
        judgment_share = sum(code_counts[c.value] for c in _JUDGMENT_CODES) / rejected_count

    # ── CU당 비용 조인(slug 우선·problem_id 폴백) — 미조인 CU는 분리(0원 산입 금지) ──
    slug_by_problem: dict[str, str] = {}
    for event in events:
        if event.problem_id is not None:
            slug_by_problem[str(event.problem_id)] = event.cu_slug
    cu_slugs = {c.cu_slug for c in cus}
    cost_by_cu: dict[str, float] = {}
    tokens_by_cu: dict[str, int] = {}
    cost_incomplete_cus: set[str] = set()
    matched = 0
    unmatched = 0
    unmetered = 0
    cost_errors: list[str] = []
    for idx, row in enumerate(genlog_rows or (), start=1):
        slug_value = row.get("slug") or row.get("cu_slug")
        slug: str | None = slug_value if isinstance(slug_value, str) else None
        if slug is None and row.get("problem_id") is not None:
            slug = slug_by_problem.get(str(row["problem_id"]))
        if slug is None or slug not in cu_slugs:
            unmatched += 1
            continue
        # null=미기록 — 0으로 변환하면 미계측 생성이 "$0 계측됨"으로 위장된다(스키마상
        # cost_usd·토큰은 nullable). 미기록은 미기록으로 남기고 수를 센다.
        cost_raw = row.get("cost_usd")
        in_raw = row.get("input_tokens")
        out_raw = row.get("output_tokens")
        try:
            cost = float(cost_raw) if cost_raw is not None else None
            tokens_in = int(in_raw) if in_raw is not None else None
            tokens_out = int(out_raw) if out_raw is not None else None
        except (TypeError, ValueError) as exc:
            cost_errors.append(f"row {idx}: {type(exc).__name__}")
            continue
        matched += 1
        if cost is None or (tokens_in is None and tokens_out is None):
            unmetered += 1
        if cost is None:
            # 비용 미기록 행이 섞인 CU는 부분합(과소집계) — 백분위 표본에서 제외한다.
            cost_incomplete_cus.add(slug)
        else:
            cost_by_cu[slug] = cost_by_cu.get(slug, 0.0) + cost
        recorded_tokens = (tokens_in or 0) + (tokens_out or 0)
        if tokens_in is not None or tokens_out is not None:
            tokens_by_cu[slug] = tokens_by_cu.get(slug, 0) + recorded_tokens
    # 완전 계측 CU만 백분위 표본 — 부분 기록 CU의 합은 진짜 비용의 하한일 뿐이다.
    complete_cost_by_cu = {
        slug: value for slug, value in cost_by_cu.items() if slug not in cost_incomplete_cus
    }
    per_cu_costs = sorted(complete_cost_by_cu.values())
    has_cost_input = genlog_rows is not None

    return HitCuReport(
        event_count=raw_count,
        parse_error_count=parse_error_count,
        window_excluded_count=window_excluded_count,
        time_unknown_excluded_count=time_unknown_excluded_count,
        session_anomaly_count=anomaly_count,
        duplicate_event_count=duplicate_count,
        session_count=len(sessions),
        dangling_session_count=sum(1 for s in sessions if not s.has_terminal),
        cu_total=len(cus),
        cu_measured=len(measured),
        cu_unmeasured=sum(1 for c in cus if c.kind == "unmeasured"),
        cu_unfinished=sum(1 for c in cus if c.kind == "unfinished"),
        hit_median_seconds=_percentile(hit_samples, 0.50),
        hit_p90_seconds=_percentile(hit_samples, 0.90),
        hit_mean_seconds=(sum(hit_samples) / len(hit_samples)) if hit_samples else None,
        hit_total_seconds=sum(hit_samples),
        verdict_total=verdict_total,
        verdict_with_timer=verdict_with_timer,
        coverage_rate=coverage_rate,
        coverage_wilson_lower=coverage_wilson,
        verdict_non_verdict_rows=non_verdict_rows,
        verdict_parse_errors=verdict_errors,
        rejected_count=rejected_count,
        failure_code_counts=code_counts,
        machine_share=machine_share,
        judgment_share=judgment_share,
        unknown_failure_code_count=unknown_code_count,
        cost_rows_matched=matched,
        cost_rows_unmatched=unmatched,
        cost_rows_unmetered=unmetered,
        cost_parse_errors=tuple(cost_errors),
        cu_with_cost=len(complete_cost_by_cu),
        cu_cost_incomplete=len(cost_incomplete_cus),
        cu_without_cost=(
            len(cu_slugs) - len(complete_cost_by_cu) - len(cost_incomplete_cus)
            if has_cost_input
            else len(cu_slugs)
        ),
        cost_usd_per_cu_p50=_percentile(per_cu_costs, 0.50),
        cost_usd_per_cu_p90=_percentile(per_cu_costs, 0.90),
        # 총액은 "기록된 비용의 합"(부분 기록 CU 포함) — 백분위와 달리 하한임을 렌더가 명기.
        cost_usd_total=sum(cost_by_cu.values()) if has_cost_input else None,
        tokens_total=sum(tokens_by_cu.values()) if has_cost_input else None,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 미계측·미산출을 숫자 0과 절대 섞지 않는다.
# ──────────────────────────────────────────────────────────────────────────


def _fmt_minutes(seconds: float | None) -> str:
    if seconds is None:
        return "미산출(표본 0)"
    return f"{seconds / 60.0:.2f}분 ({seconds:.0f}초)"


def render_report(report: HitCuReport) -> str:
    """사람용 리포트 — 적재율·미계측 분리·실패코드 분포·집행 별항을 상시 명기."""
    lines: list[str] = [
        "# HIT·CU 생산 계측 리포트 (EOS-54)",
        "",
        f"- 이벤트: 유효 {report.event_count} · 파싱 실패 {report.parse_error_count} · "
        f"중복 제거 {report.duplicate_event_count} · 창 밖 제외 "
        f"{report.window_excluded_count} · 시각 미상 제외 {report.time_unknown_excluded_count}",
        f"- 세션: {report.session_count} (dangling {report.dangling_session_count} · "
        f"anomaly {report.session_anomaly_count} — anomaly는 계측 불성립으로 강등, "
        "HIT 표본 제외)",
        f"- CU 3분류: 계측 {report.cu_measured} / 미계측 {report.cu_unmeasured} / "
        f"미종결 {report.cu_unfinished} (합 {report.cu_total}) — 미계측·미종결은 HIT 표본에서 "
        "제외·분리 카운트(0초 산입 금지)",
        "",
        "## HIT (CU당 인간 개입 시간 — 목표 중앙값 ≤4분·P90 ≤8분)",
        f"- 중앙값: {_fmt_minutes(report.hit_median_seconds)}",
        f"- P90: {_fmt_minutes(report.hit_p90_seconds)}",
        f"- 평균: {_fmt_minutes(report.hit_mean_seconds)} · 계측 총합 "
        f"{report.hit_total_seconds:.0f}초",
        "",
        "## 타이머 적재율 (작동한 비율 — 검수 판정 중 타이머 동반)",
    ]
    if report.verdict_total is None:
        lines.append(
            "- **미산출(판정 소스 미제공)** — 0%가 아니라 잰 적이 없음. --verdicts로 코퍼스 "
            "review_status 또는 검수 라벨 JSONL을 제공하라."
        )
    else:
        rate = f"{report.coverage_rate:.1%}" if report.coverage_rate is not None else "미산출"
        wilson = (
            f"{report.coverage_wilson_lower:.1%}"
            if report.coverage_wilson_lower is not None
            else "미산출"
        )
        lines.append(
            f"- 판정 {report.verdict_total}건 중 타이머 동반 {report.verdict_with_timer}건 = "
            f"{rate} (Wilson 단측 하한 {wilson})"
        )
        lines.append(
            f"- 비판정 행(pending 등) {report.verdict_non_verdict_rows}건 분모 제외 · "
            f"판정 행 파싱 실패 {len(report.verdict_parse_errors)}건"
        )
    lines += [
        "",
        f"## 실패코드 분포 (반려 {report.rejected_count}건 — F1~F8 동결 계약)",
    ]
    for code in GenerationFailureCode:
        lines.append(f"- {code.value}: {report.failure_code_counts.get(code.value, 0)}")
    if report.unknown_failure_code_count:
        lines.append(f"- (계약 밖 코드: {report.unknown_failure_code_count}건 — 조사 필요)")
    machine = f"{report.machine_share:.1%}" if report.machine_share is not None else "미산출"
    judgment = f"{report.judgment_share:.1%}" if report.judgment_share is not None else "미산출"
    lines += [
        f"- 기계형(F1+F2) 비중: {machine} · 판단형(F3+F6+F7) 비중: {judgment} — F-Ⅲ 축",
        "",
        "## CU당 토큰·비용 (GenerationLog 인프로세스 기록 — SaaS 비의존 이중 회계)",
    ]
    if report.cost_usd_total is None:
        lines.append(
            "- **미산출(GenerationLog 소스 미제공)** — --generation-log로 export JSONL을 "
            "제공하라(비용 0원이 아니라 잰 적이 없음)."
        )
    else:
        p50 = (
            f"${report.cost_usd_per_cu_p50:.4f}"
            if report.cost_usd_per_cu_p50 is not None
            else "미산출(조인 0)"
        )
        p90 = (
            f"${report.cost_usd_per_cu_p90:.4f}"
            if report.cost_usd_per_cu_p90 is not None
            else "미산출(조인 0)"
        )
        lines += [
            f"- CU당 비용 p50 {p50} · p90 {p90} (완전 계측 CU 표본만) · 기록 비용 합 "
            f"${report.cost_usd_total:.4f}(부분 기록 CU 포함 — 하한) · 기록 토큰 합 "
            f"{report.tokens_total}",
            f"- 비용 조인: CU {report.cu_with_cost}개 완전 계측 / "
            f"{report.cu_cost_incomplete}개 부분 기록(백분위 제외) / "
            f"{report.cu_without_cost}개 미계측(0원 산입 금지) · 행 매칭 "
            f"{report.cost_rows_matched} · 미매칭 {report.cost_rows_unmatched} · "
            f"메트릭 미기록 {report.cost_rows_unmetered} · 파싱 실패 "
            f"{len(report.cost_parse_errors)}",
        ]
    lines += [
        "",
        "---",
        "집행 별항(정본화≠집행): 검수 UI(ADMIN-07)가 타이머·반려코드 없이 판정 제출 불가하게 "
        "하는 결선은 후속 태스크(ADMIN-07 acceptance 확장 — HARN-24 amend CLI 부재로 등재 "
        "세션 판정). 그 전까지 적재율 100% 미만은 정상 관측이다 — 낮은 적재율을 숨기지 말 것.",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# CLI shell — 단계별 즉시 출력·전 판정 exit code.
# ──────────────────────────────────────────────────────────────────────────


def _say(message: str) -> None:
    """단계별 진행·판정 출력 — stderr·즉시 flush(중간에 죽어도 어디까지 갔는지 남는다).

    stdout은 데이터 전용이다 — --json 소비자(`jq`·`json.load`)가 진행 메시지에 깨지지
    않도록 진행·판정 문구는 전부 stderr로 보낸다.
    """
    print(message, file=sys.stderr, flush=True)


def _load_jsonl_dicts(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """보조 JSONL(판정·GenerationLog) 로더 — dict 행 + 실패 사유(타입명·줄 번호)."""
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except ValueError as exc:
                errors.append(f"line {line_no}: {type(exc).__name__}")
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                errors.append(f"line {line_no}: NotAnObject")
    return rows, errors


def _parse_moment(raw: str) -> datetime:
    """--since/--until ISO 파싱 — naive는 UTC 간주(aware 강제·혼합 비교 방지)."""
    return _ensure_aware(datetime.fromisoformat(raw))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hit_cu_metrics",
        description="HIT(CU당 인간 개입 시간)·CU당 토큰/비용·적재율·실패코드 분포 집계 "
        "(EOS-54 — exit 0/1)",
    )
    parser.add_argument("--events", required=True, help="검수 타이머 이벤트 JSONL 경로(필수)")
    parser.add_argument(
        "--verdicts", default=None, help="검수 판정 JSONL(코퍼스 review_status·#841 라벨)"
    )
    parser.add_argument(
        "--generation-log", default=None, help="GenerationLog export JSONL(CU당 비용 조인)"
    )
    parser.add_argument(
        "--since",
        default=None,
        help="이 ISO 시각 이후 이벤트만(발생 우선 귀속 — 이전 실행 오독 방지)",
    )
    parser.add_argument("--until", default=None, help="이 ISO 시각 이전 이벤트만")
    parser.add_argument(
        "--max-median-minutes",
        type=float,
        default=None,
        help="HIT 중앙값 게이트(분) — 초과 시 exit 1(미지정=계측 전용·게이트 없음)",
    )
    parser.add_argument(
        "--max-p90-minutes", type=float, default=None, help="HIT P90 게이트(분) — 초과 시 exit 1"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="적재율 게이트(0~1) — Wilson 단측 하한이 이 값 미만이면 exit 1(--verdicts 필수)",
    )
    parser.add_argument("--json", action="store_true", help="리포트를 JSON으로 출력")
    args = parser.parse_args(argv)

    # ── ① 타이머 이벤트 로드(측정 실패는 즉시·타입명과 함께) ──
    events_path = Path(args.events)
    try:
        events, load_errors = load_events_jsonl(events_path)
    except FileNotFoundError:
        _say(f"[측정 실패] FileNotFoundError: 이벤트 파일 없음 — {events_path}")
        return _EXIT_MEASUREMENT_FAIL
    _say(f"[① 이벤트] 유효 {len(events)}건 · 파싱 실패 {len(load_errors)}건 — {events_path}")
    for reason in load_errors:
        _say(f"  · 파싱 실패: {reason}")
    if not events:
        _say("[측정 실패] 유효 이벤트 0건 — '성공 0'이 아니라 계측 부재다(acceptance ④)")
        return _EXIT_MEASUREMENT_FAIL

    # ── ② 시간 창 필터(이번 실행 것인가 — 발생 우선 귀속·시각 미상은 분리 제외) ──
    window_excluded = 0
    time_unknown_excluded = 0
    if args.since or args.until:
        try:
            since = _parse_moment(args.since) if args.since else None
            until = _parse_moment(args.until) if args.until else None
        except ValueError as exc:
            _say(f"[측정 실패] {type(exc).__name__}: --since/--until ISO 파싱 불가")
            return _EXIT_MEASUREMENT_FAIL
        kept: list[ReviewTimerEvent] = []
        for event in events:
            moment = effective_moment(event)
            if moment is None:
                time_unknown_excluded += 1
                continue
            if (since is not None and moment < since) or (until is not None and moment > until):
                window_excluded += 1
                continue
            kept.append(event)
        events = kept
        _say(
            f"[② 시간 창] 창 내 {len(events)}건 · 창 밖 제외 {window_excluded}건 · "
            f"시각 미상 제외 {time_unknown_excluded}건"
        )
        if not events:
            _say("[측정 실패] 창 내 이벤트 0건 — 이번 창에 잰 것이 없다(0분 위장 금지)")
            return _EXIT_MEASUREMENT_FAIL

    # ── ③ 판정 소스(선택 — 명시 입력의 부재는 오독이 아니라 실패) ──
    verdict_rows: list[dict[str, Any]] | None = None
    verdict_load_errors: list[str] = []
    if args.verdicts:
        verdicts_path = Path(args.verdicts)
        try:
            verdict_rows, verdict_load_errors = _load_jsonl_dicts(verdicts_path)
        except FileNotFoundError:
            _say(f"[측정 실패] FileNotFoundError: 판정 파일 없음 — {verdicts_path}")
            return _EXIT_MEASUREMENT_FAIL
        _say(
            f"[③ 판정] 행 {len(verdict_rows)}건 · 파싱 실패 {len(verdict_load_errors)}건 — "
            f"{verdicts_path}"
        )
        for reason in verdict_load_errors:
            _say(f"  · 파싱 실패: {reason}")
    elif args.min_coverage is not None:
        _say(
            "[측정 실패] --min-coverage 게이트가 지정됐는데 --verdicts 소스가 없다 — 적재율을 "
            "잴 수 없으면 통과가 아니라 측정 실패다"
        )
        return _EXIT_MEASUREMENT_FAIL

    # ── ④ GenerationLog 소스(선택) — 인프로세스 이중 회계(SaaS 비의존) ──
    genlog_rows: list[dict[str, Any]] | None = None
    genlog_load_errors: list[str] = []
    if args.generation_log:
        genlog_path = Path(args.generation_log)
        try:
            genlog_rows, genlog_load_errors = _load_jsonl_dicts(genlog_path)
        except FileNotFoundError:
            _say(f"[측정 실패] FileNotFoundError: GenerationLog 파일 없음 — {genlog_path}")
            return _EXIT_MEASUREMENT_FAIL
        _say(
            f"[④ 비용] 행 {len(genlog_rows)}건 · 파싱 실패 {len(genlog_load_errors)}건 — "
            f"{genlog_path}"
        )
        for reason in genlog_load_errors:
            _say(f"  · 파싱 실패: {reason}")

    # ── ⑤ 집계·렌더 ──
    report = aggregate(
        events,
        parse_error_count=len(load_errors),
        window_excluded_count=window_excluded,
        time_unknown_excluded_count=time_unknown_excluded,
        verdict_rows=verdict_rows,
        genlog_rows=genlog_rows,
    )
    # 데이터는 stdout(단일 JSON 문서 또는 리포트 본문), 진행·판정은 stderr(_say) — 분리.
    if args.json:
        print(json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2), flush=True)
    else:
        print(render_report(report), flush=True)

    # ── ⑥ 판정 — 표본 0은 성공 0이 아니라 측정 실패(acceptance ④) ──
    # 파싱 실패 행이 하나라도 있으면 통과 금지 — 깨진 행이 하필 '느린 finished'였다면
    # HIT 표본에서 사라진 채 게이트가 성공한다(부분 입력으로 판정 금지). 리포트는 이미
    # 출력했으므로 증거는 남는다.
    parse_failure_total = (
        len(load_errors)
        + len(verdict_load_errors)
        + len(genlog_load_errors)
        + len(report.verdict_parse_errors)
        + len(report.cost_parse_errors)
    )
    if parse_failure_total > 0:
        _say(
            f"[측정 실패] 파싱 실패 {parse_failure_total}건 — 유실된 행이 표본을 바꿨을 수 "
            "있어 부분 입력으로는 판정하지 않는다(입력을 고치고 재실행)"
        )
        return _EXIT_MEASUREMENT_FAIL
    if report.cu_measured == 0:
        _say(
            "[측정 실패] 계측 CU 0건 — 판정은 있어도 경과가 전건 미계측이면 HIT는 '0분'이 "
            "아니라 '잰 적 없음'이다"
        )
        return _EXIT_MEASUREMENT_FAIL
    failures: list[str] = []
    if args.max_median_minutes is not None and report.hit_median_seconds is not None:
        if report.hit_median_seconds > args.max_median_minutes * 60.0:
            failures.append(
                f"HIT 중앙값 {report.hit_median_seconds / 60.0:.2f}분 > 게이트 "
                f"{args.max_median_minutes}분"
            )
    if args.max_p90_minutes is not None and report.hit_p90_seconds is not None:
        if report.hit_p90_seconds > args.max_p90_minutes * 60.0:
            failures.append(
                f"HIT P90 {report.hit_p90_seconds / 60.0:.2f}분 > 게이트 {args.max_p90_minutes}분"
            )
    if args.min_coverage is not None:
        wilson = report.coverage_wilson_lower
        if wilson is None:
            failures.append("적재율 표본 0 — 게이트 판정 불가(측정 실패)")
        elif wilson < args.min_coverage:
            failures.append(
                f"적재율 Wilson 하한 {wilson:.1%} < 게이트 {args.min_coverage:.1%} "
                "(점추정 아님 — 초인간 검증 표준)"
            )
    if failures:
        for failure in failures:
            _say(f"[게이트 FAIL] {failure}")
        return _EXIT_MEASUREMENT_FAIL
    _say(
        "[OK] 측정 성공"
        + (" · 게이트 전부 통과" if _any_gate(args) else " (게이트 미지정 — 계측 전용)")
    )
    return _EXIT_OK


def _any_gate(args: argparse.Namespace) -> bool:
    """게이트 플래그가 하나라도 지정됐는가(출력 문구용)."""
    return (
        args.max_median_minutes is not None
        or args.max_p90_minutes is not None
        or args.min_coverage is not None
    )


if __name__ == "__main__":
    sys.exit(main())
