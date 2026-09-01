"""cost_probe 대표 트래픽 프로브 hermetic 테스트 — 라이브 호출 0.

순수 코어(build_probe_plan·summarize_decisions)는 픽스처로 전수 단언하고, run_probe는
가짜 provider·스파이 sink를 ProbeDeps로 주입해 실 파이프라인(pipeline.generate 실물)을
라이브 없이 태운다(test_live_preflight의 주입 패턴 미러). 실 네트워크·실 키 없음.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whymath_backend.harness.wilson import wilson_lower_bound
from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import InMemoryCache
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    RoutingDecision,
    RoutingRequest,
    Usage,
)
from whymath_backend.l3.router import Router, _as_cost_tier
from whymath_backend.ops import cost_probe as cp


# ──────────────────────────────────────────────────────────────────────────
# 가짜 Settings·provider·스파이 sink — 라이브 없이 실 pipeline.generate를 태운다.
# ──────────────────────────────────────────────────────────────────────────
class _FakeSettings:
    """Settings의 최소 표면 — run_probe가 읽는 anthropic_configured만."""

    def __init__(self, *, anthropic: bool) -> None:
        self.anthropic_configured = anthropic


class _FakeProvider:
    """가짜 LLM provider — 결정과 무관하게 고정 결과를 반환(호출 결정을 기록).

    images/temperature/json_schema는 pipeline이 텍스트 호출 시 넘기지 않으므로 선택 인자.
    """

    def __init__(self, *, raise_on: str | None = None) -> None:
        self.calls: list[RoutingDecision] = []
        self._raise_on = raise_on  # 이 cost_tier로 결정된 호출만 실패시킨다(오류 회계 검증)

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
        seed: int | None = None,  # EOS-73 — LLMProvider 계약 정합(대역은 시드를 쓰지 않는다)
    ) -> GenerationResult:
        self.calls.append(decision)
        if self._raise_on is not None and decision.cost_tier == self._raise_on:
            raise RuntimeError("가짜 provider 실패(주입)")
        return GenerationResult(
            text="답", usage=Usage(input_tokens=10, output_tokens=5, latency_ms=42.0)
        )


class _SpySink:
    """record/flush 호출을 세는 스파이 — LangfuseSink 자리(_FlushSink 표면 충족)."""

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self.flush_count = 0

    def record(self, fields: dict[str, object]) -> None:
        self.records.append(fields)

    def flush(self) -> None:
        self.flush_count += 1


def _deps(provider: _FakeProvider, spy: _SpySink) -> cp.ProbeDeps:
    """가짜 provider·스파이 sink로 ProbeDeps 조립 — pipeline.generate는 실물(순수)."""
    return cp.ProbeDeps(
        provider=provider,  # type: ignore[arg-type]
        cache=InMemoryCache(),
        trace=spy,
        generate=pipeline.generate,
    )


# ──────────────────────────────────────────────────────────────────────────
# 순수 코어 — build_probe_plan
# ──────────────────────────────────────────────────────────────────────────
def test_plan_expands_weights_and_rounds() -> None:
    """라운드당 가중치 합만큼 펼쳐지고, rounds가 전체를 배수한다."""
    per_round = sum(a.weight for a in cp.REPRESENTATIVE_MIX)
    plan = cp.build_probe_plan(cp.REPRESENTATIVE_MIX, 3, include_cloud=True)
    assert len(plan) == per_round * 3


def test_plan_excludes_cloud_when_disabled() -> None:
    """include_cloud=False면 클라우드 archetype이 계획에서 빠진다(로컬만)."""
    plan = cp.build_probe_plan(cp.REPRESENTATIVE_MIX, 1, include_cloud=False)
    cloud_labels = {a.label for a in cp.REPRESENTATIVE_MIX if a.routes_cloud}
    assert cloud_labels  # 믹스에 클라우드 archetype이 실제로 존재(전제 검증)
    assert all(item.label not in cloud_labels for item in plan)


def test_plan_prompts_are_unique() -> None:
    """프롬프트가 인스턴스마다 고유 — 캐시 미스 강제(실측 표본 유실 방지)."""
    plan = cp.build_probe_plan(cp.REPRESENTATIVE_MIX, 2, include_cloud=True)
    prompts = [item.prompt for item in plan]
    assert len(prompts) == len(set(prompts))


def test_plan_rejects_zero_rounds() -> None:
    """rounds<1은 명시적 거부(빈 측정을 조용히 만들지 않음)."""
    with pytest.raises(ValueError):
        cp.build_probe_plan(cp.REPRESENTATIVE_MIX, 0, include_cloud=True)


def test_mix_is_local_dominant() -> None:
    """대표 믹스 자체가 free-우세(로컬 가중 ≥80%) — 트래픽 모델 전제의 동결."""
    local_w = sum(a.weight for a in cp.REPRESENTATIVE_MIX if not a.routes_cloud)
    total_w = sum(a.weight for a in cp.REPRESENTATIVE_MIX)
    assert local_w / total_w >= 0.80


# ──────────────────────────────────────────────────────────────────────────
# 순수 코어 — summarize_decisions (판정 = Wilson 단측 하한·점추정 금지)
# ──────────────────────────────────────────────────────────────────────────
def test_summary_local_ratio_and_pass() -> None:
    """로컬 54 : 클라우드 6(n=60) → 점추정 0.9·Wilson 하한 ≈0.82 → 판정선 PASS."""
    tiers = [CostTier.LOCAL.value] * 54 + [CostTier.CLOUD_MID.value] * 6
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=True, rounds=6
    )
    assert report.local_ratio == pytest.approx(0.9)
    assert report.local_ratio_lower == pytest.approx(wilson_lower_bound(54, 60))
    assert report.local_ratio_lower is not None and report.local_ratio_lower >= 0.80
    assert report.gate2_local_pass is True
    assert report.tier_counts == {CostTier.LOCAL.value: 54, CostTier.CLOUD_MID.value: 6}


def test_summary_small_sample_point_at_threshold_fails() -> None:
    """변별력: 로컬 4/5 — 점추정은 정확히 0.80이나 Wilson 하한 ≈0.44 → FAIL.

    점추정 판정이던 시절 '작은 표본 거짓 해금'이 통과하던 바로 그 시나리오
    (2026-07-21 정합성 검토 발견)를 실패 상태로 고정한다.
    """
    tiers = [CostTier.LOCAL.value] * 4 + [CostTier.CLOUD_MID.value]
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=True, rounds=1
    )
    assert report.local_ratio == pytest.approx(0.80)  # 점추정은 임계 도달
    assert report.local_ratio_lower is not None and report.local_ratio_lower < 0.80
    assert report.gate2_local_pass is False  # 그래도 판정은 FAIL — 하한이 판정 기준


def test_summary_all_local_small_sample_fails() -> None:
    """변별력: 전량 로컬이어도 n=9(rounds=1 로컬 믹스)면 하한 ≈0.77 → FAIL.

    소표본은 구조적으로 통과 불가 — 하한 n/(n+z²)이 0.80을 넘으려면 n≥11.
    """
    tiers = [CostTier.LOCAL.value] * 9
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=False, rounds=1
    )
    assert report.local_ratio == pytest.approx(1.0)
    assert report.gate2_local_pass is False


def test_summary_below_threshold_fails() -> None:
    """로컬 7 : 클라우드 3 → 점추정 0.7부터 미달 — 하한은 더 낮아 당연 FAIL."""
    tiers = [CostTier.LOCAL.value] * 7 + [CostTier.CLOUD_MID.value] * 3
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=True, rounds=1
    )
    assert report.gate2_local_pass is False


def test_summary_empty_is_unknown_not_zero() -> None:
    """성공 표본 0 → local_ratio·하한=None·판정 불가(None) — '미상'과 0을 구분(날조 금지)."""
    report = cp.summarize_decisions(
        [], errors=3, error_samples=["[x] E: e"], cloud_included=False, rounds=1
    )
    assert report.local_ratio is None
    assert report.local_ratio_lower is None
    assert report.gate2_local_pass is None
    assert report.total == 3  # 오류도 총 요청 수에는 회계된다


def test_summary_errors_excluded_from_denominator() -> None:
    """오류는 분모(성공분)에서 제외 — 실패를 로컬로도 클라우드로도 세지 않는다."""
    tiers = [CostTier.LOCAL.value] * 4
    report = cp.summarize_decisions(
        tiers, errors=6, error_samples=[], cloud_included=True, rounds=1
    )
    assert report.local_ratio == pytest.approx(1.0)  # 성공분 4/4 전부 로컬
    assert report.total == 10


# ──────────────────────────────────────────────────────────────────────────
# OPS-18 — LOCAL 강등 사유 3버킷(classify_local_reason) + 클라우드 도달 관측.
# ──────────────────────────────────────────────────────────────────────────
def test_classify_local_reason_budget0_beats_free() -> None:
    """규칙1(budget_krw<=0)이 규칙2(free)보다 먼저 — 두 조건이 겹치면 budget0로 분류."""
    req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        budget_krw=0.0,
    )
    assert cp.classify_local_reason(req) == cp.LOCAL_REASON_BUDGET0


def test_classify_local_reason_free_when_budget_positive() -> None:
    """budget_krw>0인데 free면 규칙2 — free 버킷(규칙1은 이미 통과했으므로 미해당)."""
    req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        budget_krw=100.0,
    )
    assert cp.classify_local_reason(req) == cp.LOCAL_REASON_FREE


def test_classify_local_reason_rule6_catchall_when_neither_rule_fires() -> None:
    """budget>0·구독≠free인데 결정이 LOCAL로 귀결된 경우(규칙3·4 미매치 등) — rule6_catchall."""
    req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="basic",
        budget_krw=100.0,
    )
    assert cp.classify_local_reason(req) == cp.LOCAL_REASON_RULE6_CATCHALL
    # 실제로도 이 요청은 LOCAL로 귀결된다(규칙3·4 미매치·규칙6 기본값) — 분류가 허구가 아님.
    assert Router().route(req).cost_tier == CostTier.LOCAL.value


def test_summarize_decisions_local_reason_counts_needs_requests() -> None:
    """requests 없이 호출 → local_reason_counts=None('미계상', '0건'과 구분)."""
    report = cp.summarize_decisions(
        [CostTier.LOCAL.value] * 3, errors=0, error_samples=[], cloud_included=False, rounds=1
    )
    assert report.local_reason_counts is None


def test_summarize_decisions_local_reason_counts_with_requests() -> None:
    """requests를 주면 실 요청 필드로 3버킷을 계상 — CLOUD 성공분은 계상에서 제외."""
    budget0_req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        budget_krw=0.0,
    )
    free_req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        budget_krw=100.0,
    )
    catchall_req = RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="basic",
        budget_krw=100.0,
    )
    cloud_req = RoutingRequest(
        task_type="diagnose",
        difficulty="hard",
        requires_reasoning=True,
        student_subscription="premium",
        budget_krw=1000.0,
    )
    tiers = [
        CostTier.LOCAL.value,
        CostTier.LOCAL.value,
        CostTier.LOCAL.value,
        CostTier.CLOUD_MID.value,
    ]
    requests = [budget0_req, free_req, catchall_req, cloud_req]
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=True, rounds=1, requests=requests
    )
    assert report.local_reason_counts == {
        cp.LOCAL_REASON_BUDGET0: 1,
        cp.LOCAL_REASON_FREE: 1,
        cp.LOCAL_REASON_RULE6_CATCHALL: 1,
    }


def test_cloud_reach_count_derived_from_tier_counts() -> None:
    """cloud_reach_count = CLOUD_MID+CLOUD_HIGH 합 — 기존 tier_counts에서 유도."""
    tiers = (
        [CostTier.LOCAL.value] * 5
        + [CostTier.CLOUD_MID.value] * 2
        + [CostTier.CLOUD_HIGH.value] * 3
    )
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=True, rounds=1
    )
    assert report.cloud_reach_count == 5


def test_next_tier_calls_is_always_zero_and_honestly_labeled() -> None:
    """이 프로브는 next_tier()를 호출하지 않는다 — 0을 '미시행'으로 렌더(침묵 누락 아님)."""
    report = cp.summarize_decisions(
        [CostTier.LOCAL.value] * 3, errors=0, error_samples=[], cloud_included=False, rounds=1
    )
    assert report.next_tier_calls == 0
    text = cp.render_report(report)
    assert "next_tier 호출: 미도달" in text


# ──────────────────────────────────────────────────────────────────────────
# OPS-18 acceptance③ — 변별력: killer+premium+budget 요청 삽입 시 cloud_reach 0→1→0
# (실 Router().route(...) 결정을 뒤집어서 본다 — 하드코딩된 기대값이 아니라 진짜 회로).
# ──────────────────────────────────────────────────────────────────────────
def _cloud_reach_line(rendered: str) -> str:
    """render_report 출력에서 '클라우드 도달' 줄만 뽑는다(다른 '미도달' 줄과 혼동 방지)."""
    for line in rendered.splitlines():
        if line.strip().startswith("클라우드 도달"):
            return line
    raise AssertionError("'클라우드 도달' 줄이 리포트에 없음")


def test_cloud_reach_flips_0_to_1_and_back_with_killer_premium_request() -> None:
    """로컬-우세 대표 믹스만으로는 cloud_reach=0·'미도달' → killer+premium+예산 요청 1건 추가로
    1로 뒤집힘 → 제거하면 다시 0·'미도달'로 복귀(양방향 실측, OPS-18 acceptance③)."""
    router = Router()

    # ── ① 기존 로컬-우세 archetype만(REPRESENTATIVE_MIX의 include_cloud=False 부분집합) ──
    baseline_items = cp.build_probe_plan(cp.REPRESENTATIVE_MIX, rounds=1, include_cloud=False)
    baseline_requests = [item.request for item in baseline_items]
    baseline_tiers = [_as_cost_tier(router.route(req).cost_tier).value for req in baseline_requests]

    report_before = cp.summarize_decisions(
        baseline_tiers,
        errors=0,
        error_samples=[],
        cloud_included=False,
        rounds=1,
        requests=baseline_requests,
    )
    assert report_before.cloud_reach_count == 0
    assert _cloud_reach_line(cp.render_report(report_before)) == (
        "  클라우드 도달: 미도달 (0건 통과가 아니라 승급 사슬이 구조적으로 도달한 적 없음)"
    )

    # ── ② killer+premium+budget_krw=1000 요청 1건 추가 — rule3 guard_cloud(CLOUD_HIGH) 경로 ──
    killer_premium_request = RoutingRequest(
        task_type="diagnose",
        difficulty="killer",
        requires_reasoning=True,
        student_subscription="premium",
        budget_krw=1000.0,
        sync=True,
    )
    killer_decision = router.route(killer_premium_request)
    killer_tier = _as_cost_tier(killer_decision.cost_tier).value
    assert killer_tier == CostTier.CLOUD_HIGH.value  # 전제 확인(진짜 클라우드 도달)

    with_cloud_requests = [*baseline_requests, killer_premium_request]
    with_cloud_tiers = [*baseline_tiers, killer_tier]
    report_with_cloud = cp.summarize_decisions(
        with_cloud_tiers,
        errors=0,
        error_samples=[],
        cloud_included=True,
        rounds=1,
        requests=with_cloud_requests,
    )
    assert report_with_cloud.cloud_reach_count == 1
    assert _cloud_reach_line(cp.render_report(report_with_cloud)) == "  클라우드 도달: 1건"

    # ── ③ 제거하면 원복 — 0/'미도달'로 되돌아온다(양방향 실측) ──
    report_after_removal = cp.summarize_decisions(
        baseline_tiers,
        errors=0,
        error_samples=[],
        cloud_included=False,
        rounds=1,
        requests=baseline_requests,
    )
    assert report_after_removal.cloud_reach_count == 0
    assert _cloud_reach_line(cp.render_report(report_after_removal)) == (
        "  클라우드 도달: 미도달 (0건 통과가 아니라 승급 사슬이 구조적으로 도달한 적 없음)"
    )


# ──────────────────────────────────────────────────────────────────────────
# run_probe — 실 pipeline.generate(순수) + 가짜 provider·스파이 sink.
# ──────────────────────────────────────────────────────────────────────────
def test_run_probe_local_only_when_anthropic_unset() -> None:
    """anthropic 미설정 → 클라우드 archetype 제외·전 요청 LOCAL·판정선 PASS·flush 1회.

    rounds=2(로컬 18건) — Wilson 하한 판정이라 rounds=1(n=9)은 전량 로컬이어도 표본
    부족으로 통과 불가(위 소표본 변별력 테스트가 고정).
    """
    provider = _FakeProvider()
    spy = _SpySink()
    report = asyncio.run(
        cp.run_probe(
            _FakeSettings(anthropic=False),  # type: ignore[arg-type]
            rounds=2,
            deps_factory=lambda _s: _deps(provider, spy),
        )
    )
    assert report.cloud_included is False
    assert report.errors == 0
    assert report.tier_counts == {CostTier.LOCAL.value: report.total}
    assert report.gate2_local_pass is True
    # 파이프라인이 요청마다 l3_routing 필드를 record했고, CLI가 flush를 확정했다.
    assert len(spy.records) == report.total
    assert spy.flush_count == 1
    # record된 필드에 실측 usage가 흘렀다(캐시 미스 생성 — 프롬프트 유일화 검증).
    assert all(r["cache_hit"] is False for r in spy.records)
    assert all(r["input_tokens"] == 10 for r in spy.records)


def test_run_probe_cloud_mix_ratio_measured() -> None:
    """anthropic 설정 → 클라우드 archetype 포함, 라우터 결정 그대로 비율 산출(9:1=0.9).

    rounds=6(n=60) — 점추정 0.9의 Wilson 하한이 0.80을 넘는 최소권 표본으로 PASS까지 검증.
    """
    provider = _FakeProvider()
    spy = _SpySink()
    report = asyncio.run(
        cp.run_probe(
            _FakeSettings(anthropic=True),  # type: ignore[arg-type]
            rounds=6,
            deps_factory=lambda _s: _deps(provider, spy),
        )
    )
    assert report.cloud_included is True
    # 라우터가 premium archetype을 실제 CLOUD_MID로 결정했는가(라운드당 1건×6).
    assert report.tier_counts.get(CostTier.CLOUD_MID.value) == 6
    assert report.local_ratio == pytest.approx(54 / 60)
    assert report.gate2_local_pass is True


def test_run_probe_errors_accounted_never_break() -> None:
    """클라우드 호출만 실패 주입 → 오류 회계·표본 기록, 로컬 측정은 보존(never-break)."""
    provider = _FakeProvider(raise_on=CostTier.CLOUD_MID.value)
    spy = _SpySink()
    report = asyncio.run(
        cp.run_probe(
            _FakeSettings(anthropic=True),  # type: ignore[arg-type]
            rounds=1,
            deps_factory=lambda _s: _deps(provider, spy),
        )
    )
    assert report.errors == 1
    assert report.error_samples and "diagnose-hard-premium" in report.error_samples[0]
    # 성공분(로컬)만으로 비율 산출 — 실패는 분모 제외.
    assert report.local_ratio == pytest.approx(1.0)
    assert spy.flush_count == 1  # 오류가 나도 flush는 확정된다


def test_run_probe_include_cloud_override() -> None:
    """--no-cloud 대응: anthropic 설정돼 있어도 include_cloud=False면 로컬만 태운다."""
    provider = _FakeProvider()
    spy = _SpySink()
    report = asyncio.run(
        cp.run_probe(
            _FakeSettings(anthropic=True),  # type: ignore[arg-type]
            rounds=1,
            include_cloud=False,
            deps_factory=lambda _s: _deps(provider, spy),
        )
    )
    assert report.cloud_included is False
    assert CostTier.CLOUD_MID.value not in report.tier_counts


# ──────────────────────────────────────────────────────────────────────────
# 렌더링·JSON — 시크릿 0·미상 표기·직렬화 왕복.
# ──────────────────────────────────────────────────────────────────────────
def test_render_has_verdict_and_no_secrets() -> None:
    """사람용 출력에 점추정·Wilson 하한·판정선이 있고 키 문자열 패턴이 없다."""
    report = cp.summarize_decisions(
        [CostTier.LOCAL.value] * 54 + [CostTier.CLOUD_MID.value] * 6,
        errors=0,
        error_samples=[],
        cloud_included=True,
        rounds=6,
    )
    text = cp.render_report(report)
    assert "90.0%" in text  # 점추정
    assert "Wilson 하한" in text
    assert "PASS" in text
    assert "sk-" not in text and "pk-" not in text


def test_render_small_sample_guides_to_more_rounds() -> None:
    """변별력 안내: 점추정 ≥80%인데 표본 부족으로 미달이면 --rounds 증량을 안내한다."""
    report = cp.summarize_decisions(
        [CostTier.LOCAL.value] * 4 + [CostTier.CLOUD_MID.value],
        errors=0,
        error_samples=[],
        cloud_included=True,
        rounds=1,
    )
    text = cp.render_report(report)
    assert "미달" in text
    assert "--rounds" in text  # 소표본 안내 줄


def test_render_unknown_ratio() -> None:
    """표본 0이면 '미상'·'판정 불가'로 렌더 — 0%로 위장하지 않는다."""
    report = cp.summarize_decisions([], errors=0, error_samples=[], cloud_included=False, rounds=1)
    text = cp.render_report(report)
    assert "미상" in text
    assert "판정 불가" in text


def test_json_roundtrip(tmp_path: Path) -> None:
    """to_json이 판정선·Wilson 하한 포함 직렬화 — cost_report JSON 관례와 동형(파일 왕복).

    OPS-18: requests 미전달 호출이므로 local_reason_counts는 '미계상'(None→JSON null)으로
    라운드트립돼야 한다 — cloud_reach_count·next_tier_calls는 requests 없이도 유도 가능.
    """
    report = cp.summarize_decisions(
        [CostTier.LOCAL.value] * 54 + [CostTier.CLOUD_MID.value] * 6,
        errors=1,
        error_samples=["[coach-medium-free] RuntimeError: x"],
        cloud_included=True,
        rounds=6,
    )
    out = tmp_path / "probe.json"
    out.write_text(json.dumps(report.to_json(), ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["local_ratio"] == pytest.approx(0.9)
    assert loaded["local_ratio_lower"] == pytest.approx(wilson_lower_bound(54, 60))
    assert loaded["gate2_local_pass"] is True
    assert loaded["errors"] == 1
    assert loaded["rounds"] == 6
    # OPS-18 신규 필드 — requests 미전달이라 사유 계상은 None(JSON null), 도달·next_tier는 유도됨.
    assert loaded["local_reason_counts"] is None
    assert loaded["cloud_reach_count"] == 6
    assert loaded["next_tier_calls"] == 0


def test_json_roundtrip_with_local_reason_counts(tmp_path: Path) -> None:
    """requests를 준 호출은 local_reason_counts도 dict[str,int]로 JSON 왕복한다(OPS-18)."""
    requests = [
        RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",
            budget_krw=0.0,
        ),
        RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="basic",
            budget_krw=100.0,
        ),
    ]
    tiers = [CostTier.LOCAL.value, CostTier.LOCAL.value]
    report = cp.summarize_decisions(
        tiers, errors=0, error_samples=[], cloud_included=False, rounds=1, requests=requests
    )
    out = tmp_path / "probe_reasons.json"
    out.write_text(json.dumps(report.to_json(), ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["local_reason_counts"] == {
        cp.LOCAL_REASON_BUDGET0: 1,
        cp.LOCAL_REASON_FREE: 0,
        cp.LOCAL_REASON_RULE6_CATCHALL: 1,
    }
    assert loaded["cloud_reach_count"] == 0
    assert loaded["next_tier_calls"] == 0
