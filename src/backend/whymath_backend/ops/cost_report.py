"""L3 비용·토큰 판독 — 라이브 `l3_routing` 트레이스를 p50/p90 집계해 S1 게이트② 판정.

배경
----
`ops/live_preflight.py`가 라이브 키 투입 *직후 1콜*로 계측이 흐르는지 검증한다면, 이
모듈은 그 다음 단계다 — Kiki가 라이브 트래픽을 몇 분 흘린 뒤 **누적된 `l3_routing`
이벤트를 집계**해 "루프당 LLM 비용 실측"(S1 탈출 게이트 ②)을 즉석에서 판정한다.
프리플라이트가 1콜(비대표)뿐이라 낼 수 없던 *분포*(p50/p90)·로컬:클라우드 비율·튜닝
제안을 이 판독기가 채운다. `status_roadmap_2026-07.md` §4 병목 #2("AI는 측정 스크립트·
대시보드를 선제 준비해 Kiki 수동 시간을 최소화")의 저장소 측 실체다.

무엇을 집계하나 (03a §F.2 · router.langfuse_fields)
---------------------------------------------------
Langfuse 이벤트 이름 `l3_routing`의 메타데이터에서 아래를 읽는다:
- 실측 `input_tokens`/`output_tokens`/`cost_krw`/`latency_ms` → **p50·p90·평균·합**.
  (캐시 히트·비동기 enqueue·미계측 이벤트는 실측이 None이라 표본에서 제외 — 지어내지 않음)
- `cost_tier`(local/cloud_mid/cloud_high) → **로컬:클라우드 비율**(목표 80% 로컬 대비).
- `cache_hit`(bool) → **캐시 적중률**.

튜닝 산출물 (S1 게이트 ② 판정으로 연결)
--------------------------------------
`suggested_est_input_tokens`/`_output_tokens` = 실측 토큰 **p50** 반올림. 이 두 값을
`l3/router.py`의 `_EST_ASSUMED_INPUT_TOKENS`/`_EST_ASSUMED_OUTPUT_TOKENS`(현재 보수적
기본 1000)에 대입하면 `CLOUD_MIN_COST_KRW`·`est_cost_krw`·`guard_cloud` 임계값이 단일
공식으로 자동 재계산된다(router.py §H 후속 4의 튜닝 절차 그대로). est/actual 분리는
유지된다 — actual은 여전히 호출별 실측 토큰으로 계산한다(#465).

설계 경계 (live_preflight·langfuse_sink 미러)
--------------------------------------------
- **순수 집계 코어**(`aggregate_l3_events`)는 I/O 없는 순수 함수다 — dict 리스트만 받아
  리포트를 낸다. 실 Langfuse 없이 픽스처로 전수 검증 가능(hermetic 테스트).
- **fetch 어댑터**(`fetch_l3_events`)는 langfuse read 클라이언트를 *지연 import·주입
  가능*하게 감싼다(langfuse_sink._build_default_client 패턴). 미설정이면 빈 리스트(no-op),
  오류는 삼킨다 — 판독은 관측 도구이므로 절대 예외를 밖으로 던지지 않는다(never-break).

시크릿·PII 경계 (CLAUDE.md)
--------------------------
키 *값*은 출력하지 않는다(설정 여부·집계 수치만). `student_id_hash`는 *이미 해시*이며
이 모듈은 집계에 쓰지 않는다(개별 학생 식별 0 — 분포·비율만 낸다).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings
from whymath_backend.l3.models import CostTier

logger = logging.getLogger("whymath.ops.cost_report")

# 집계 대상 이벤트 이름 — langfuse_sink._EVENT_NAME과 동일(단일 진실은 그쪽, 여기선 조회 키).
_L3_EVENT_NAME = "l3_routing"

# 로컬로 분류할 cost_tier 값(그 외 cloud_* 는 클라우드). CostTier가 단일 진실(매직스트링 아님).
_LOCAL_TIER = CostTier.LOCAL.value


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 코어 — I/O 없음. dict 리스트 → 리포트. 실 Langfuse 없이 전수 테스트 가능.
# ──────────────────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class Distribution:
    """한 수치 축(토큰·비용·지연)의 분포 요약 — 실측 표본만(None 제외)."""

    count: int
    """실측치가 있는 표본 수(None은 제외). 0이면 분포 통계는 전부 None."""

    p50: float | None = None
    """중앙값(50 백분위). 표본 0이면 None."""

    p90: float | None = None
    """90 백분위(꼬리 비용 감시). 표본 0이면 None."""

    mean: float | None = None
    """평균. 표본 0이면 None."""

    total: float | None = None
    """합계(비용의 누적 파악용). 표본 0이면 None."""


@dataclass(slots=True, frozen=True)
class CostReport:
    """`l3_routing` 이벤트 집계 리포트 — 사람용 출력·JSON 직렬화의 단일 진실."""

    event_count: int
    """집계에 들어온 총 이벤트 수(실측 유무 무관)."""

    input_tokens: Distribution
    output_tokens: Distribution
    cost_krw: Distribution
    latency_ms: Distribution

    local_count: int
    """cost_tier=local 이벤트 수."""

    cloud_count: int
    """cost_tier=cloud_* 이벤트 수(mid+high)."""

    local_ratio: float | None
    """로컬 비중 = local/(local+cloud). 분류 표본 0이면 None. 목표 0.80(80% 로컬)."""

    cost_tier_counts: dict[str, int]
    """cost_tier 값별 카운트(분포 80/18/2 대비). None/미상 tier는 '(unknown)'으로."""

    cache_hits: int
    """cache_hit=True 이벤트 수."""

    cache_total: int
    """cache_hit(bool) 필드가 존재한 이벤트 수(적중률 분모)."""

    cache_hit_rate: float | None
    """캐시 적중률 = cache_hits/cache_total. 분모 0이면 None."""

    suggested_est_input_tokens: int | None
    """실측 input_tokens p50 반올림 — router._EST_ASSUMED_INPUT_TOKENS 튜닝 제안(표본 0=None)."""

    suggested_est_output_tokens: int | None
    """실측 output_tokens p50 반올림 — router._EST_ASSUMED_OUTPUT_TOKENS 튜닝 제안(표본 0=None)."""

    notes: list[str] = field(default_factory=list)
    """집계 한계·주의(표본 부족·미분류 tier 등)를 사람이 읽도록 남긴다."""


def _percentile(sorted_vals: list[float], q: float) -> float | None:
    """정렬된 표본의 q 백분위(q∈[0,1]) — 선형보간(numpy 기본 'linear'/type 7과 동일).

    표본 0이면 None, 1개면 그 값. rank=q·(n-1)의 하한·상한 사이를 선형보간한다.
    이 정의를 고정해 테스트가 손계산 기대값과 정확히 일치하게 한다.
    """
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    rank = q * (n - 1)
    lo = int(rank)  # floor(0 이상)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _distribution(values: list[float]) -> Distribution:
    """실측 값 리스트 → Distribution(p50·p90·평균·합). 빈 리스트면 count=0·전부 None."""
    if not values:
        return Distribution(count=0)
    ordered = sorted(values)
    return Distribution(
        count=len(ordered),
        p50=_percentile(ordered, 0.50),
        p90=_percentile(ordered, 0.90),
        mean=sum(ordered) / len(ordered),
        total=sum(ordered),
    )


def _opt_float(value: object) -> float | None:
    """이벤트 필드값(object) → float|None. bool은 수치가 아니므로 제외(미상은 None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _opt_int(value: object) -> int | None:
    """이벤트 필드값(object) → int|None. bool 제외(미상은 None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def aggregate_l3_events(events: list[dict[str, object]]) -> CostReport:
    """`l3_routing` 메타데이터 dict 리스트 → 집계 리포트 (순수 함수·I/O 없음).

    실측치(input/output_tokens·cost_krw·latency_ms)는 None을 표본에서 제외하고 집계한다
    (캐시 히트·비동기·미계측은 실측이 None — '0'이 아니라 '미상'). cost_tier로 로컬:클라우드
    비율을, cache_hit로 적중률을 낸다. 토큰 p50는 router._EST_ASSUMED_* 튜닝 제안으로 낸다.
    """
    notes: list[str] = []

    input_vals: list[float] = []
    output_vals: list[float] = []
    cost_vals: list[float] = []
    latency_vals: list[float] = []

    local_count = 0
    cloud_count = 0
    tier_counts: dict[str, int] = {}
    cache_hits = 0
    cache_total = 0

    for ev in events:
        # 실측 수치 — None(미상)은 표본에서 빠진다.
        it = _opt_int(ev.get("input_tokens"))
        if it is not None:
            input_vals.append(float(it))
        ot = _opt_int(ev.get("output_tokens"))
        if ot is not None:
            output_vals.append(float(ot))
        ck = _opt_float(ev.get("cost_krw"))
        if ck is not None:
            cost_vals.append(ck)
        lat = _opt_float(ev.get("latency_ms"))
        if lat is not None:
            latency_vals.append(lat)

        # cost_tier 분류 — 값별 카운트 + 로컬/클라우드 이분.
        tier_raw = ev.get("cost_tier")
        tier = tier_raw if isinstance(tier_raw, str) else "(unknown)"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if tier == _LOCAL_TIER:
            local_count += 1
        elif tier.startswith("cloud"):
            cloud_count += 1

        # cache_hit — bool 필드가 있는 이벤트만 분모에 넣는다.
        cache_raw = ev.get("cache_hit")
        if isinstance(cache_raw, bool):
            cache_total += 1
            if cache_raw:
                cache_hits += 1

    classified = local_count + cloud_count
    local_ratio = local_count / classified if classified > 0 else None
    if classified == 0 and events:
        notes.append("cost_tier로 분류된 이벤트가 0건 — 로컬:클라우드 비율 산정 불가.")
    unknown = tier_counts.get("(unknown)", 0)
    if unknown:
        notes.append(f"cost_tier 미상 이벤트 {unknown}건 — 비율·분포에서 제외됨.")

    cache_hit_rate = cache_hits / cache_total if cache_total > 0 else None

    input_dist = _distribution(input_vals)
    output_dist = _distribution(output_vals)

    # 튜닝 제안 — 실측 토큰 p50 반올림(표본 없으면 None). router._EST_ASSUMED_* 대입 대상.
    sug_in = round(input_dist.p50) if input_dist.p50 is not None else None
    sug_out = round(output_dist.p50) if output_dist.p50 is not None else None

    if events and not cost_vals:
        notes.append(
            "실측 cost_krw 표본 0 — 캐시 히트·비동기·미계측만 있었을 수 있음(대표 트래픽 필요)."
        )
    if input_dist.count < 20 and input_dist.count > 0:
        notes.append(
            f"실측 토큰 표본 {input_dist.count}건(<20) — p50 제안은 잠정치(트래픽 더 축적 권장)."
        )

    return CostReport(
        event_count=len(events),
        input_tokens=input_dist,
        output_tokens=output_dist,
        cost_krw=_distribution(cost_vals),
        latency_ms=_distribution(latency_vals),
        local_count=local_count,
        cloud_count=cloud_count,
        local_ratio=local_ratio,
        cost_tier_counts=tier_counts,
        cache_hits=cache_hits,
        cache_total=cache_total,
        cache_hit_rate=cache_hit_rate,
        suggested_est_input_tokens=sug_in,
        suggested_est_output_tokens=sug_out,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────────
# Langfuse read 어댑터 — 지연 import·주입 가능(langfuse_sink._build_default_client 미러).
# 실 조회는 라이브 키 환경(Kiki 머신)에서만 돌며, 테스트는 가짜 클라이언트를 주입한다.
# ──────────────────────────────────────────────────────────────────────────


@runtime_checkable
class _LangfuseReadClient(Protocol):
    """langfuse.Langfuse의 read 부분집합 — 우리가 실제로 쓰는 fetch_observations만 선언.

    langfuse 2.x는 `fetch_observations(name=, type=, from_start_time=, page=, limit=)`으로
    관측을 페이지네이션 조회한다. 반환은 `.data`(관측 리스트)를 가진 응답 객체다. 버전별
    형태 차이를 흡수하려 반환을 Any로 두고 호출측에서 duck-typing으로 좁힌다.
    """

    def fetch_observations(self, **kwargs: Any) -> Any: ...


def _build_default_read_client(settings: Settings) -> _LangfuseReadClient:
    """기본 langfuse read 클라이언트 생성 (지연 import) — langfuse_sink 패턴 그대로.

    라이브러리·키가 없는 환경에서도 모듈 import가 깨지지 않도록 *호출 시점에만* import한다.
    설정이 완비됐을 때만(fetch_l3_events가 보장) 호출된다. 시크릿은 여기서 클라이언트
    생성 인자로 넘길 때만 평문화하고 로그로 남기지 않는다(CLAUDE.md 보안 금기).
    """
    try:
        from langfuse import Langfuse
    except ImportError as exc:  # pragma: no cover — 환경 의존(라이브러리 미설치)
        raise RuntimeError(
            "langfuse Python 클라이언트가 설치되지 않았습니다. `pip install langfuse` 후 재시도."
        ) from exc
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    return cast(_LangfuseReadClient, client)


def _extract_metadata(observation: Any) -> dict[str, object] | None:
    """관측 객체에서 메타데이터 dict를 꺼낸다(속성/딕셔너리 둘 다 흡수·아니면 None)."""
    meta = getattr(observation, "metadata", None)
    if meta is None and isinstance(observation, dict):
        meta = observation.get("metadata")
    if isinstance(meta, dict):
        # 키를 str로 정규화(langfuse가 str 키를 보장하지만 방어적으로).
        return {str(k): v for k, v in meta.items()}
    return None


def fetch_l3_events(
    *,
    days: int = 7,
    limit: int = 100,
    client: _LangfuseReadClient | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """최근 `days`일의 `l3_routing` 이벤트 메타데이터 리스트를 Langfuse에서 가져온다.

    주입 우선(client=)·아니면 설정 완비 시 지연 생성. Langfuse 미설정이면 빈 리스트(no-op).
    페이지네이션으로 전량 수집하되, 안전 상한(빈 페이지·데이터 없음)에서 종료한다. 어떤
    오류도 밖으로 던지지 않는다(판독은 never-break 관측 도구) — 사유만 로그로 남기고
    지금까지 모은 것을 돌려준다.
    """
    resolved_settings = settings if settings is not None else Settings()
    read_client = client
    if read_client is None:
        if not resolved_settings.langfuse_configured:
            logger.info("Langfuse 미설정 — 조회 대상 없음(빈 리포트). 라이브 키 투입 후 재실행.")
            return []
        read_client = _build_default_read_client(resolved_settings)

    reference = now if now is not None else datetime.now(timezone.utc)
    from_start = reference - timedelta(days=days)

    collected: list[dict[str, object]] = []
    page = 1
    try:
        while True:
            response = read_client.fetch_observations(
                name=_L3_EVENT_NAME,
                type="EVENT",
                from_start_time=from_start,
                page=page,
                limit=limit,
            )
            data = getattr(response, "data", None)
            if data is None and isinstance(response, dict):
                data = response.get("data")
            if not data:
                break
            for obs in data:
                meta = _extract_metadata(obs)
                if meta is not None:
                    collected.append(meta)
            if len(data) < limit:
                break  # 마지막 페이지(요청 한도 미만) — 종료.
            page += 1
    except Exception:  # noqa: BLE001 — 조회 장애가 판독을 깨면 안 됨(never-break). 모은 것만 반환.
        logger.warning("Langfuse 조회 실패 — 지금까지 모은 이벤트로 집계(비차단).", exc_info=False)

    return collected


# ──────────────────────────────────────────────────────────────────────────
# 렌더링·CLI — live_preflight.py 관례(사람용 표 + 선택 JSON·얇은 main).
# ──────────────────────────────────────────────────────────────────────────


def _fmt_num(value: float | None, digits: int = 1) -> str:
    """수치|None 표기 — None은 '미상'(0과 구분)."""
    if value is None:
        return "미상"
    return f"{value:.{digits}f}"


def _fmt_ratio(value: float | None) -> str:
    """비율|None 표기(퍼센트) — None은 '미상'."""
    if value is None:
        return "미상"
    return f"{value * 100:.1f}%"


def _dist_line(label: str, dist: Distribution, digits: int = 1) -> str:
    """한 분포를 한 줄로 — p50·p90·평균·합·표본수."""
    return (
        f"  {label:<14}: p50={_fmt_num(dist.p50, digits)} "
        f"p90={_fmt_num(dist.p90, digits)} "
        f"mean={_fmt_num(dist.mean, digits)} "
        f"sum={_fmt_num(dist.total, digits)} (n={dist.count})"
    )


def _render_stdout(report: CostReport) -> str:
    """사람용 stdout 렌더 — 분포·비율·튜닝 제안(시크릿·개별 ID 없음)."""
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("WhyMath L3 비용·토큰 판독 — l3_routing 집계(S1 게이트② 실측)")
    lines.append("=" * 64)
    lines.append(f"총 이벤트: {report.event_count}건")
    lines.append("[분포 — 실측 표본만(None 제외)]")
    lines.append(_dist_line("input_tokens", report.input_tokens, 0))
    lines.append(_dist_line("output_tokens", report.output_tokens, 0))
    lines.append(_dist_line("cost_krw(원)", report.cost_krw, 4))
    lines.append(_dist_line("latency_ms", report.latency_ms, 0))
    lines.append("[로컬:클라우드 — 목표 80% 로컬]")
    lines.append(
        f"  로컬 {report.local_count} / 클라우드 {report.cloud_count} "
        f"→ 로컬 비중 {_fmt_ratio(report.local_ratio)}"
    )
    tier_str = ", ".join(f"{k}={v}" for k, v in sorted(report.cost_tier_counts.items()))
    lines.append(f"  cost_tier 분포: {tier_str or '(없음)'}")
    lines.append("[캐시]")
    lines.append(
        f"  적중 {report.cache_hits} / {report.cache_total} "
        f"→ 적중률 {_fmt_ratio(report.cache_hit_rate)}"
    )
    lines.append("[튜닝 제안 — router._EST_ASSUMED_* 에 대입]")
    lines.append(f"  _EST_ASSUMED_INPUT_TOKENS  ← {report.suggested_est_input_tokens} (input p50)")
    lines.append(
        f"  _EST_ASSUMED_OUTPUT_TOKENS ← {report.suggested_est_output_tokens} (output p50)"
    )
    lines.append(
        "  ↳ 대입 시 CLOUD_MIN_COST_KRW·est_cost_krw·guard_cloud 임계값 자동 재계산(단일 공식)."
    )
    if report.notes:
        lines.append("[주의]")
        for note in report.notes:
            lines.append(f"  · {note}")
    lines.append("=" * 64)
    return "\n".join(lines)


def _write_json(report: CostReport, path: str) -> None:
    """리포트를 JSON으로 저장 — dataclass 직렬화(개별 ID·시크릿 없음)."""
    from pathlib import Path

    Path(path).write_text(
        json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """얇은 CLI — 인자 파싱 → fetch_l3_events → aggregate → 출력. 항상 exit 0(관측 도구).

    Settings()는 lru_cache를 우회해 *지금* 주입된 키를 읽는다(라이브 세션 중 재실행 대비).
    미설정이면 빈 리포트를 깨끗이 출력한다(예외 없음 — never-break).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.cost_report",
        description="라이브 l3_routing 트레이스를 집계해 루프당 비용·토큰 p50·로컬비율을 판독.",
    )
    parser.add_argument(
        "--days", type=int, default=7, help="집계 기간(일). 기본 7. 라이브 세션 직후엔 1 권장."
    )
    parser.add_argument(
        "--limit", type=int, default=100, help="Langfuse 페이지당 조회 수(페이지네이션). 기본 100."
    )
    parser.add_argument(
        "--json", dest="json_path", default=None, help="JSON 리포트 저장 경로(선택)."
    )
    args = parser.parse_args(argv)

    settings = Settings()  # lru_cache 우회 — 방금 주입한 키를 읽는다
    events = fetch_l3_events(days=args.days, limit=args.limit, settings=settings)
    report = aggregate_l3_events(events)

    print(_render_stdout(report))
    if args.json_path is not None:
        _write_json(report, args.json_path)
        print(f"JSON 리포트 저장: {args.json_path}")

    return 0  # 판독은 관측 — 항상 정상 종료(미설정·빈 표본도 정보이지 오류 아님).


if __name__ == "__main__":
    sys.exit(main())
