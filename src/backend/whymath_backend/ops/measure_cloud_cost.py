"""대표 코칭 부하 측정 — 라이브 클라우드 비용·지연 p50를 router.py 4노브 튜닝용으로 산출.

배경
----
`live_preflight`의 스모크는 `"1+1은?"`(입력 63·출력 5 토큰)이라 **비대표 1콜**이다 — 계측 흐름
검증용이지 코칭 생성 부하가 아니다. router.py의 est 가정 토큰(`_EST_ASSUMED_*`)·클라우드 지연
(`CLOUD_LATENCY_MS`)을 실측으로 튜닝하려면, **대표 코칭 크기의 호출을 여러 번** 흘려 p50(중앙값)를
얻어야 한다(정직성 게이트: 비대표 1건으로 수치 변경 금지 — MEMORY 2026-07 선례).

이 도구는 대표 코칭 프롬프트(문제 + 학생 풀이 + 소크라테스 코칭 지시)를 `--samples N`회 티어별
(CLOUD_MID·CLOUD_HIGH)로 `pipeline.generate` 경유 실행하고, 실측 input/output 토큰·지연의 p50/p90를
집계해 **router.py에 넣을 값**을 그대로 출력한다. `live_preflight`의 pipeline 배선을 재사용한다.

대표성 경계(정직)
----------------
파일럿 전(S3 전)이라 *실 프로덕션 코칭 트래픽*이 없다. 여기 프롬프트는 실 코칭 턴을 근사한
**대표 픽스처**다 — 토큰 p50는 "대표 추정치"이지 프로덕션 실측이 아니다(지연 p50는 프롬프트
크기 의존이라 합리적 추정). 파일럿 트래픽 확보 시 Langfuse `l3_routing` 실분포로 재보정한다.
그래도 프리플라이트 1콜(63/5)보다 훨씬 대표적이라 est 가정 토큰의 1차 보정 근거로 충분하다.

실행
----
    python -m whymath_backend.ops.measure_cloud_cost --samples 12               # MID·HIGH 각 12콜
    python -m whymath_backend.ops.measure_cloud_cost --samples 20 --tier mid    # MID만
    python -m whymath_backend.ops.measure_cloud_cost --samples 12 --json out.json

시크릿 안전: 키 값은 절대 출력하지 않는다 — 토큰 수·지연(ms)·비용(원)만 보고한다.
종료 코드: 0 정상 / 2 클라우드 미설정·전 콜 실패(대표 표본 확보 실패).
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from whymath_backend.config import Settings
from whymath_backend.l3 import pipeline
from whymath_backend.l3.models import CostTier, RoutingRequest
from whymath_backend.l3.providers.anthropic import AnthropicProvider
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import OllamaProvider
from whymath_backend.l3.router import _as_cost_tier
from whymath_backend.l3.trace.langfuse_sink import LangfuseSink
from whymath_backend.ops.live_preflight import (
    PipelineDeps,
    PipelineDepsFactory,
    _CapturingTraceSink,
    _opt_float,
    _opt_int,
)


class _NoCache:
    """항상 미스인 캐시 — 측정은 매 콜이 실 클라우드 호출이어야 한다(캐시 히트=지연 0 오염 방지).

    CacheBackend 표면(get/set)만 충족한다. get은 항상 None(미스), set은 no-op(저장 안 함)이라
    같은 프롬프트가 반복돼도 매번 provider.generate가 불린다 — 반복 픽스처의 캐시 히트로 지연이
    0으로 왜곡되는 것을 막는다.
    """

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        return None


def _default_measure_deps(settings: Settings) -> PipelineDeps:
    """측정용 기본 pipeline 의존성 — `_default_pipeline_deps` 미러 + 캐시만 [_NoCache]로 교체.

    provider·sink는 지연 클라이언트라 여기서 네트워크·키를 요구하지 않는다. crypto/db는 구성하지
    않는다(live_preflight의 환경 회피 유지). 캐시만 항상-미스라 매 표본이 실 클라우드 1콜이 된다.
    """
    provider = CompositeProvider(
        local=OllamaProvider(settings=settings),
        cloud=AnthropicProvider(settings=settings),
    )
    trace = _CapturingTraceSink(LangfuseSink(settings=settings))
    return PipelineDeps(
        provider=provider,
        cache=_NoCache(),  # CacheBackend 표면(get/set) 구조적 충족
        trace=trace,
        generate=pipeline.generate,
    )


# 종료 코드 — 미설정·전 콜 실패는 오류(2), 정상은 0.
_EXIT_OK = 0
_EXIT_ERROR = 2

# 정직성 게이트 — 유효 표본이 이보다 적으면 p50를 "확정 튜닝값"으로 제시하지 않는다.
_MIN_REPRESENTATIVE_SAMPLES = 5


# ──────────────────────────────────────────────────────────────────────────
# 대표 코칭 프롬프트 픽스처 — 실 코칭 턴(문제 + 학생 풀이 + 소크라테스 지시)을 근사.
# 정답을 제공하지 않고 유도 발문을 요청한다(WhyMath 답 미루기·CLAUDE.md). 자체작성(수학 사실·
# 표준 표기)이라 저작권 무관. 길이를 다양화해 median이 현실적 분포를 반영하게 한다.
# ──────────────────────────────────────────────────────────────────────────

_COACH_SYSTEM = (
    "너는 WhyMath의 수학 코치다. 학생이 스스로 답에 도달하도록 Polya 4단계(이해·계획·실행·검토)와 "
    "소크라테스 발문으로 안내한다. 절대 정답이나 최종 수치를 바로 알려주지 않는다 — 학생이 막힌 "
    "지점을 짚고, 다음 한 걸음을 스스로 찾게 하는 유도 질문 1~2개만 제시한다. 틀렸다는 단정·부정 "
    "강화 표현을 쓰지 않는다. 답변은 한국어로 3~5문장 이내."
)

_COACH_PROMPTS: tuple[str, ...] = (
    (
        "문제: 함수 f(x)=x^3-3x^2+2에 대하여 곡선 y=f(x) 위의 점 (1, f(1))에서의 접선의 방정식을 "
        "구하시오.\n"
        "학생 풀이:\n"
        "  1) f(1) = 1 - 3 + 2 = 0\n"
        "  2) f'(x) = 3x^2 - 6x\n"
        "  3) f'(1) = 3 - 6 = -3\n"
        "  4) 접선: y = -3x\n"
        "학생 발화: 접선을 y=-3x라고 했는데 맞는지 모르겠어요.\n"
        "지시: 학생이 접선의 방정식 형태에서 무엇을 빠뜨렸는지 스스로 찾도록 유도 질문을 던져라."
    ),
    (
        "문제: 수열 {a_n}이 a_1=2, a_(n+1)=2a_n+1 (n>=1)로 정의될 때, a_5의 값을 구하시오.\n"
        "학생 풀이:\n"
        "  1) a_2 = 2*2+1 = 5\n"
        "  2) a_3 = 2*5+1 = 11\n"
        "  3) a_4 = 2*11+1 = 23\n"
        "  4) a_5 = 2*23 = 46\n"
        "학생 발화: a_5를 46으로 구했어요.\n"
        "지시: 마지막 단계에서 학생이 점화식을 어떻게 적용했는지 스스로 되짚도록 발문하라."
    ),
    (
        "문제: 정적분 ∫_0^2 (3x^2 - 2x) dx 의 값을 구하시오.\n"
        "학생 풀이:\n"
        "  1) 부정적분: x^3 - x^2\n"
        "  2) 위끝 대입: 8 - 4 = 4\n"
        "  3) 아래끝 대입: 0\n"
        "  4) 답: 4\n"
        "학생 발화: 답이 4가 맞나요? 뭔가 놓친 것 같아요.\n"
        "지시: 학생이 정적분의 계산 과정 중 확인해야 할 단계를 스스로 점검하도록 질문하라."
    ),
    (
        "문제: 지수방정식 2^(2x) - 5*2^x + 4 = 0 의 모든 실근의 합을 구하시오.\n"
        "학생 풀이:\n"
        "  1) 2^x = t로 치환하면 t^2 - 5t + 4 = 0\n"
        "  2) (t-1)(t-4) = 0 이므로 t=1 또는 t=4\n"
        "  3) 2^x = 1 이면 x=0, 2^x=4 이면 x=2\n"
        "  4) 실근의 합: 0 + 2 = 2\n"
        "학생 발화: 실근의 합을 2로 구했어요.\n"
        "지시: 치환·역치환 과정이 타당한지 학생이 스스로 확인하도록 유도 발문하라."
    ),
    (
        "문제: 삼각방정식 2sin^2(x) - 3cos(x) = 0 (0 <= x < 2π)의 해의 개수를 구하시오.\n"
        "학생 풀이:\n"
        "  1) sin^2(x) = 1 - cos^2(x) 대입\n"
        "  2) 2(1 - cos^2 x) - 3cos x = 0\n"
        "  3) -2cos^2 x - 3cos x + 2 = 0, 즉 2cos^2 x + 3cos x - 2 = 0\n"
        "  4) (2cos x - 1)(cos x + 2) = 0\n"
        "  5) cos x = 1/2 또는 cos x = -2\n"
        "학생 발화: cos x = -2도 답이 될 수 있나요?\n"
        "지시: 학생이 코사인 값의 치역을 스스로 떠올려 해의 유효성을 판단하도록 발문하라."
    ),
)


def _cloud_mid_request() -> RoutingRequest:
    """CLOUD_MID(sync)로 라우팅되는 대표 코칭 요청 (router 규칙4: requires_reasoning + premium)."""
    return RoutingRequest(
        task_type="coach",
        difficulty="hard",
        requires_reasoning=True,
        student_subscription="premium",
        budget_krw=1000.0,  # guard_cloud(CLOUD_MID) 통과 여유
        sync=True,
        max_latency_ms=30000,
    )


def _cloud_high_request() -> RoutingRequest:
    """CLOUD_HIGH(sync)로 라우팅되는 대표 코칭 요청 (router 규칙3: killer 또는 prove)."""
    return RoutingRequest(
        task_type="coach",
        difficulty="killer",
        requires_reasoning=True,
        student_subscription="premium",
        budget_krw=1000.0,  # guard_cloud(CLOUD_HIGH) 통과 여유
        sync=True,
        max_latency_ms=30000,
    )


@dataclass(slots=True)
class _Samples:
    """한 티어의 실측 표본 누적 — 토큰·지연 리스트와 실패·라우팅 미스 카운트."""

    input_tokens: list[int] = field(default_factory=list)
    output_tokens: list[int] = field(default_factory=list)
    latency_ms: list[float] = field(default_factory=list)
    errors: int = 0
    misroutes: int = 0  # 목표 티어와 실제 라우팅이 다른 콜(대표성 훼손 — 제외 집계)


@dataclass(slots=True, frozen=True)
class TierStats:
    """한 티어의 p50/p90 집계 — router.py에 넣을 값의 단일 근거."""

    tier: str
    n_valid: int
    n_error: int
    n_misroute: int
    input_p50: int | None
    output_p50: int | None
    latency_p50_ms: float | None
    input_p90: int | None
    output_p90: int | None
    latency_p90_ms: float | None


@dataclass(slots=True, frozen=True)
class MeasureReport:
    """측정 종합 리포트 — 사람용 출력·JSON 직렬화의 단일 진실."""

    cloud_configured: bool
    langfuse_configured: bool
    samples_requested: int
    tiers: list[TierStats]
    representative: bool  # 유효 표본이 최소치 이상인가(정직성 게이트)
    exit_code: int


def _percentile(values: list[float], q: float) -> float | None:
    """정렬 표본의 q분위수(0<q<1)를 최근접 순위법으로 — 표본이 없으면 None.

    작은 N에서도 결정적이도록 statistics.quantiles 대신 nearest-rank를 쓴다.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    # nearest-rank: rank = ceil(q * N), 1-기반 → 인덱스 = rank-1(0-기반), 경계 클램프.
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _stats_for(tier: str, s: _Samples) -> TierStats:
    """티어 표본에서 p50/p90을 집계한다(토큰은 정수 반올림)."""

    def _p(values: list[float], q: float) -> float | None:
        return _percentile(values, q)

    def _pi(values: list[int], q: float) -> int | None:
        p = _percentile([float(v) for v in values], q)
        return int(round(p)) if p is not None else None

    return TierStats(
        tier=tier,
        n_valid=len(s.input_tokens),
        n_error=s.errors,
        n_misroute=s.misroutes,
        input_p50=_pi(s.input_tokens, 0.5),
        output_p50=_pi(s.output_tokens, 0.5),
        latency_p50_ms=_p(s.latency_ms, 0.5),
        input_p90=_pi(s.input_tokens, 0.9),
        output_p90=_pi(s.output_tokens, 0.9),
        latency_p90_ms=_p(s.latency_ms, 0.9),
    )


async def _measure_tier(
    *,
    target: CostTier,
    request_factory: RoutingRequest,
    samples: int,
    deps: PipelineDeps,
) -> _Samples:
    """한 티어를 samples회 호출하고 실측 토큰·지연을 누적한다.

    프롬프트는 픽스처를 순환 사용한다(다양한 길이 → 현실적 median). 각 콜은 trace가 갈무리한
    마지막 record dict에서 input/output 토큰·지연을 읽는다(pipeline은 usage를 결과로 반환 안 함).
    목표 티어와 실제 라우팅이 다르면 misroute로 세고 표본에서 제외한다(대표성 보호).
    """
    acc = _Samples()
    for i in range(samples):
        system = _COACH_SYSTEM
        # 픽스처(문제+학생 풀이+소크라테스 지시)를 순환 사용한다(다양한 길이 → 현실적 median).
        prompt = _COACH_PROMPTS[i % len(_COACH_PROMPTS)]
        try:
            result = await deps.generate(
                request_factory,
                prompt,
                system,
                provider=deps.provider,
                cache=deps.cache,
                trace=deps.trace,
            )
        except Exception:  # noqa: BLE001 — 개별 콜 실패를 흡수(카운트만, 전체 중단 안 함)
            acc.errors += 1
            continue

        routed = _as_cost_tier(result.decision.cost_tier)
        if routed is not target:
            acc.misroutes += 1
            continue

        captured = deps.trace.records[-1] if deps.trace.records else {}
        in_tok = _opt_int(captured.get("input_tokens"))
        out_tok = _opt_int(captured.get("output_tokens"))
        lat = _opt_float(captured.get("latency_ms"))
        # None-vs-0(CLAUDE.md): 토큰·지연이 미상이면 표본에 넣지 않는다(지어내지 않음).
        if in_tok is None or out_tok is None or lat is None:
            acc.errors += 1
            continue
        acc.input_tokens.append(in_tok)
        acc.output_tokens.append(out_tok)
        acc.latency_ms.append(lat)
    return acc


async def run_measure(
    settings: Settings,
    *,
    samples: int,
    tiers: list[CostTier],
    pipeline_deps_factory: PipelineDepsFactory = _default_measure_deps,
) -> MeasureReport:
    """측정 순수 코어 — 라이브 없이 deps 주입으로 태울 수 있다(테스트가 가짜 provider 주입).

    Langfuse 미설정이면 pipeline 경로의 기록 대상이 없어 측정 자체는 하되(토큰·지연은 usage에서
    나옴) 경고한다. 클라우드 미설정이면 대표 클라우드 측정이 불가하므로 exit 2.
    """
    cloud_configured = settings.anthropic_configured
    langfuse_configured = settings.langfuse_configured

    tier_stats: list[TierStats] = []
    if cloud_configured:
        deps = pipeline_deps_factory(settings)
        req_for = {
            CostTier.CLOUD_MID: _cloud_mid_request(),
            CostTier.CLOUD_HIGH: _cloud_high_request(),
        }
        for tier in tiers:
            acc = await _measure_tier(
                target=tier,
                request_factory=req_for[tier],
                samples=samples,
                deps=deps,
            )
            tier_stats.append(_stats_for(tier.value, acc))

    # 정직성 게이트 — 모든 요청 티어가 최소 표본을 확보했는가.
    representative = bool(tier_stats) and all(
        t.n_valid >= _MIN_REPRESENTATIVE_SAMPLES for t in tier_stats
    )
    exit_code = _EXIT_OK
    if not cloud_configured:
        exit_code = _EXIT_ERROR
    elif tier_stats and all(t.n_valid == 0 for t in tier_stats):
        exit_code = _EXIT_ERROR

    return MeasureReport(
        cloud_configured=cloud_configured,
        langfuse_configured=langfuse_configured,
        samples_requested=samples,
        tiers=tier_stats,
        representative=representative,
        exit_code=exit_code,
    )


def _fmt_opt(value: object) -> str:
    """수치|None 표기 — None은 '미상'(지어내지 않음)."""
    if value is None:
        return "미상"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _render_stdout(report: MeasureReport) -> str:
    """사람용 stdout — p50/p90 표 + router.py에 넣을 값 안내(시크릿 없음)."""
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append("WhyMath 대표 코칭 부하 측정 — 클라우드 비용·지연 p50 (router.py 튜닝용)")
    lines.append("=" * 68)
    lines.append(f"  cloud_configured  : {'예' if report.cloud_configured else '아니오'}")
    lines.append(f"  langfuse_configured: {'예' if report.langfuse_configured else '아니오'}")
    lines.append(f"  요청 표본/티어    : {report.samples_requested}")
    if not report.cloud_configured:
        lines.append("-" * 68)
        lines.append("  ✗ Anthropic 미설정 — 대표 클라우드 측정 불가(키 투입 후 재실행). exit 2")
        lines.append("=" * 68)
        return "\n".join(lines)

    for t in report.tiers:
        lines.append("-" * 68)
        lines.append(f"[{t.tier}]  유효 {t.n_valid} · 실패 {t.n_error} · 라우팅미스 {t.n_misroute}")
        lines.append(f"  input_tokens   p50={_fmt_opt(t.input_p50)}  p90={_fmt_opt(t.input_p90)}")
        lines.append(f"  output_tokens  p50={_fmt_opt(t.output_p50)}  p90={_fmt_opt(t.output_p90)}")
        lines.append(
            f"  latency_ms     p50={_fmt_opt(t.latency_p50_ms)}  p90={_fmt_opt(t.latency_p90_ms)}"
        )

    lines.append("-" * 68)
    if report.representative:
        mid = next((t for t in report.tiers if t.tier == CostTier.CLOUD_MID.value), None)
        high = next((t for t in report.tiers if t.tier == CostTier.CLOUD_HIGH.value), None)
        lines.append("→ router.py 반영 값(대표 표본 충족):")
        if mid is not None:
            lines.append(
                f"    _EST_ASSUMED_INPUT_TOKENS  = {_fmt_opt(mid.input_p50)}   "
                f"(CLOUD_MID input p50)"
            )
            lines.append(
                f"    _EST_ASSUMED_OUTPUT_TOKENS = {_fmt_opt(mid.output_p50)}   "
                f"(CLOUD_MID output p50)"
            )
            lines.append(f"    CLOUD_LATENCY_MS[CLOUD_MID]  = {_fmt_opt(mid.latency_p50_ms)}")
        if high is not None:
            lines.append(f"    CLOUD_LATENCY_MS[CLOUD_HIGH] = {_fmt_opt(high.latency_p50_ms)}")
        lines.append(
            "  (USD_TO_KRW는 라이브 환율로 별도 갱신. est 가정 토큰은 대표 추정치 — "
            "파일럿 실트래픽으로 재보정)"
        )
    else:
        lines.append(
            f"  ⚠ 대표 표본 부족(티어별 유효 표본 < {_MIN_REPRESENTATIVE_SAMPLES}) — "
            "튜닝값으로 제시하지 않음. --samples를 늘려 재실행(정직성 게이트)."
        )
    lines.append("=" * 68)
    return "\n".join(lines)


def _write_json(report: MeasureReport, path: Path) -> None:
    """리포트를 JSON으로 저장(시크릿 없이 수치만)."""
    path.write_text(
        json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_tiers(value: str) -> list[CostTier]:
    """--tier 인자를 CostTier 리스트로(both/mid/high)."""
    if value == "mid":
        return [CostTier.CLOUD_MID]
    if value == "high":
        return [CostTier.CLOUD_HIGH]
    return [CostTier.CLOUD_MID, CostTier.CLOUD_HIGH]


def main(argv: list[str] | None = None) -> int:
    """얇은 CLI — 인자 파싱 → Settings() 직접 생성 → run_measure → 출력/종료 코드."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.measure_cloud_cost",
        description="대표 코칭 부하로 클라우드 토큰·지연 p50를 측정(router.py 4노브 튜닝용).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=12,
        help="티어별 호출 수(기본 12). 대표성을 위해 최소 5 이상 권장.",
    )
    parser.add_argument(
        "--tier",
        choices=["both", "mid", "high"],
        default="both",
        help="측정 티어(기본 both=CLOUD_MID·CLOUD_HIGH).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="JSON 리포트 저장 경로(선택).",
    )
    args = parser.parse_args(argv)

    if args.samples < 1:
        parser.error("--samples는 1 이상이어야 합니다.")

    settings = Settings()  # lru_cache 우회 — 방금 주입한 키를 읽는다
    report = asyncio.run(run_measure(settings, samples=args.samples, tiers=_parse_tiers(args.tier)))

    print(_render_stdout(report))
    if args.json_path is not None:
        json_path = Path(args.json_path)
        _write_json(report, json_path)
        print(f"JSON 리포트 저장: {json_path}")

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
