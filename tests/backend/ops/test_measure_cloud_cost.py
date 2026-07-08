"""measure_cloud_cost hermetic 테스트 — 라이브 호출 0.

가짜 Settings(키 유/무)·가짜 provider(고정 usage)로 p50 집계·대표성 게이트·None-vs-0·라우팅
정합·stdout 렌더를 단언한다. 실 pipeline.generate(순수)를 실물로 태우되 provider·cache·trace만
가짜로 주입한다(live_preflight via-pipeline 테스트와 동형).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from whymath_backend.l3 import pipeline
from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision, Usage
from whymath_backend.ops import live_preflight as lp
from whymath_backend.ops import measure_cloud_cost as mc


class _FakeSettings:
    """Settings의 최소 표면 — 두 판정 프로퍼티만 필요하다."""

    def __init__(self, *, anthropic: bool, langfuse: bool) -> None:
        self.anthropic_configured = anthropic
        self.langfuse_configured = langfuse


class _FakePipelineProvider:
    """가짜 LLMProvider — 고정 usage를 돌려준다(라이브 0). live_preflight 테스트와 동형 표면."""

    def __init__(self, result: GenerationResult) -> None:
        self._result = result
        self.calls: list[RoutingDecision] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        self.calls.append(decision)
        return self._result


class _SpyInnerSink:
    """record/flush 카운트만 세는 스파이 — _CapturingTraceSink 내부 싱크로 주입."""

    def __init__(self) -> None:
        self.record_count = 0
        self.flush_count = 0

    def record(self, fields: dict[str, object]) -> None:
        self.record_count += 1

    def flush(self) -> None:
        self.flush_count += 1


def _deps(result: GenerationResult) -> lp.PipelineDeps:
    """가짜 provider·항상-미스 캐시·스파이 trace로 측정 deps 조립 — pipeline.generate는 실물."""
    return lp.PipelineDeps(
        provider=_FakePipelineProvider(result),  # type: ignore[arg-type]
        cache=mc._NoCache(),  # type: ignore[arg-type]
        trace=lp._CapturingTraceSink(_SpyInnerSink()),  # type: ignore[arg-type]
        generate=pipeline.generate,
    )


def _settings(*, anthropic: bool = True, langfuse: bool = True) -> _FakeSettings:
    return _FakeSettings(anthropic=anthropic, langfuse=langfuse)


async def test_measures_p50_both_tiers() -> None:
    """CLOUD_MID·HIGH 각각 실 라우팅되고, 고정 usage의 p50가 그대로 집계된다."""
    usage = Usage(input_tokens=1200, output_tokens=400, latency_ms=2500.0)
    deps = _deps(GenerationResult(text="유도 질문", usage=usage))

    report = await mc.run_measure(
        _settings(),  # type: ignore[arg-type]
        samples=6,
        tiers=[CostTier.CLOUD_MID, CostTier.CLOUD_HIGH],
        pipeline_deps_factory=lambda _s: deps,
    )

    assert report.cloud_configured is True
    assert report.exit_code == 0
    assert report.representative is True
    assert len(report.tiers) == 2
    for t in report.tiers:
        assert t.n_valid == 6  # 캐시 항상-미스라 6콜 전부 실호출·집계
        assert t.n_error == 0
        assert t.n_misroute == 0
        assert t.input_p50 == 1200
        assert t.output_p50 == 400
        assert t.latency_p50_ms == 2500.0
    # 목표 티어대로 실제 라우팅됐는가.
    assert {t.tier for t in report.tiers} == {
        CostTier.CLOUD_MID.value,
        CostTier.CLOUD_HIGH.value,
    }


async def test_single_tier_mid() -> None:
    """--tier mid는 CLOUD_MID만 측정한다."""
    usage = Usage(input_tokens=900, output_tokens=300, latency_ms=1800.0)
    deps = _deps(GenerationResult(text="q", usage=usage))

    report = await mc.run_measure(
        _settings(),  # type: ignore[arg-type]
        samples=5,
        tiers=[CostTier.CLOUD_MID],
        pipeline_deps_factory=lambda _s: deps,
    )
    assert [t.tier for t in report.tiers] == [CostTier.CLOUD_MID.value]
    assert report.tiers[0].input_p50 == 900


async def test_unconfigured_cloud_exits_error() -> None:
    """anthropic 미설정이면 대표 측정 불가 — 티어 0·exit 2."""
    report = await mc.run_measure(
        _settings(anthropic=False),  # type: ignore[arg-type]
        samples=6,
        tiers=[CostTier.CLOUD_MID],
        pipeline_deps_factory=lambda _s: _deps(GenerationResult(text="x")),
    )
    assert report.cloud_configured is False
    assert report.tiers == []
    assert report.exit_code == mc._EXIT_ERROR
    assert report.representative is False


async def test_none_tokens_excluded_and_not_representative() -> None:
    """토큰 미상(None)이면 표본에서 제외(지어내지 않음) — 유효 0이면 대표성 False·exit 2."""
    usage = Usage(input_tokens=None, output_tokens=None, latency_ms=None)
    deps = _deps(GenerationResult(text="x", usage=usage))

    report = await mc.run_measure(
        _settings(),  # type: ignore[arg-type]
        samples=6,
        tiers=[CostTier.CLOUD_MID],
        pipeline_deps_factory=lambda _s: deps,
    )
    t = report.tiers[0]
    assert t.n_valid == 0
    assert t.n_error == 6  # 전부 미상 → 제외
    assert t.input_p50 is None
    assert report.representative is False
    assert report.exit_code == mc._EXIT_ERROR


async def test_below_min_samples_not_representative() -> None:
    """유효 표본이 최소치 미만이면 대표성 게이트 False(튜닝값 미제시) — 하지만 exit 0(유효>0)."""
    usage = Usage(input_tokens=1000, output_tokens=350, latency_ms=2000.0)
    deps = _deps(GenerationResult(text="q", usage=usage))

    report = await mc.run_measure(
        _settings(),  # type: ignore[arg-type]
        samples=2,  # < _MIN_REPRESENTATIVE_SAMPLES(5)
        tiers=[CostTier.CLOUD_MID],
        pipeline_deps_factory=lambda _s: deps,
    )
    assert report.tiers[0].n_valid == 2
    assert report.representative is False
    assert report.exit_code == 0  # 유효 표본이 있으므로 실패는 아니다


def test_percentile_nearest_rank() -> None:
    """p50/p90 최근접 순위 계산이 결정적이다(작은 N 포함)."""
    assert mc._percentile([], 0.5) is None
    assert mc._percentile([5.0], 0.5) == 5.0
    assert mc._percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert mc._percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.9) == 5.0


def test_stdout_shows_router_values_and_no_secrets() -> None:
    """대표 표본 충족 시 router.py 반영 값을 출력하고, 시크릿(키)은 노출하지 않는다."""
    report = mc.MeasureReport(
        cloud_configured=True,
        langfuse_configured=True,
        samples_requested=12,
        tiers=[
            mc.TierStats(
                tier=CostTier.CLOUD_MID.value,
                n_valid=12,
                n_error=0,
                n_misroute=0,
                input_p50=1180,
                output_p50=420,
                latency_p50_ms=2450.0,
                input_p90=1600,
                output_p90=800,
                latency_p90_ms=4100.0,
            ),
            mc.TierStats(
                tier=CostTier.CLOUD_HIGH.value,
                n_valid=12,
                n_error=0,
                n_misroute=0,
                input_p50=1180,
                output_p50=650,
                latency_p50_ms=6200.0,
                input_p90=1600,
                output_p90=1100,
                latency_p90_ms=9000.0,
            ),
        ],
        representative=True,
        exit_code=0,
    )
    out = mc._render_stdout(report)
    assert "_EST_ASSUMED_INPUT_TOKENS  = 1180" in out
    assert "_EST_ASSUMED_OUTPUT_TOKENS = 420" in out
    assert "CLOUD_LATENCY_MS[CLOUD_MID]  = 2450" in out
    assert "CLOUD_LATENCY_MS[CLOUD_HIGH] = 6200" in out
    # 시크릿(키 값)은 어디에도 없다.
    assert "sk-" not in out and "pk-" not in out


def test_stdout_warns_when_not_representative() -> None:
    """대표 표본 부족 시 튜닝값 대신 경고를 낸다(정직성 게이트)."""
    report = mc.MeasureReport(
        cloud_configured=True,
        langfuse_configured=True,
        samples_requested=2,
        tiers=[
            mc.TierStats(
                tier=CostTier.CLOUD_MID.value,
                n_valid=2,
                n_error=0,
                n_misroute=0,
                input_p50=1000,
                output_p50=350,
                latency_p50_ms=2000.0,
                input_p90=1000,
                output_p90=350,
                latency_p90_ms=2000.0,
            )
        ],
        representative=False,
        exit_code=0,
    )
    out = mc._render_stdout(report)
    assert "대표 표본 부족" in out
    assert "_EST_ASSUMED_INPUT_TOKENS" not in out
