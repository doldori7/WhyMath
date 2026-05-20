"""L3 Router 결정 로직 단위 테스트 — 축1(C.1)·축2(C.2)·가드·추정·키·에스컬레이션.

설계 정본: docs/architecture/03a_l3_router_design.md
  §C.1(축1 6규칙)·§C.2(축2 7규칙)·§D(에스컬레이션·guard_cloud)·§E(예산)·§F(캐시·태그)·§A.1(지연).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.router import (
    CLOUD_LATENCY_MS,
    CLOUD_MIN_COST_KRW,
    DAILY_LIMIT_KRW,
    ESCALATION_CHAIN,
    LOCAL_LATENCY_MS,
    SLA_GATE_MS,
    Router,
    cache_key,
    cache_key_for,
    cloud_cost,
    cloud_latency,
    cloud_min_cost,
    guard_cloud,
    langfuse_fields,
    local_latency,
    next_tier,
)


def _req(**overrides: object) -> RoutingRequest:
    """테스트용 RoutingRequest 빌더 — 기본은 *LOCAL로 떨어지는* 요청.

    budget_krw=0 → 축1 규칙1이 LOCAL 강제하므로, 명시적으로 budget을 주지 않는 한
    축2 분기를 독립적으로 검증할 수 있다. 클라우드 경로 테스트는 budget을 채운다.
    """
    defaults: dict[str, object] = {
        "task_type": "explain",
        "difficulty": "medium",
        "requires_reasoning": False,
        "student_subscription": "premium",
        "budget_krw": 0.0,  # 기본: LOCAL 강제
        "max_latency_ms": 30000,
        "sync": True,
    }
    defaults.update(overrides)
    return RoutingRequest(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def router() -> Router:
    return Router()


# ══════════════════════════════════════════════════════════════════════
# 축1 결정표 (03a §C.1) — 6규칙 각각
# ══════════════════════════════════════════════════════════════════════
class TestAxis1CostTier:
    def test_rule1_budget_exhausted_forces_local(self, router: Router) -> None:
        """규칙1: budget_krw<=0 → LOCAL (쿼터 소진, 비용 0원 강제)."""
        # killer + premium이지만 예산 0이라 클라우드 차단
        d = router.route(
            _req(difficulty="killer", student_subscription="premium", budget_krw=0.0)
        )
        assert d.cost_tier == CostTier.LOCAL
        assert d.est_cost_krw == 0.0

    def test_rule1_negative_budget_forces_local(self, router: Router) -> None:
        """규칙1 경계: budget_krw<0도 LOCAL."""
        d = router.route(_req(task_type="prove", budget_krw=-10.0))
        assert d.cost_tier == CostTier.LOCAL

    def test_rule2_free_always_local(self, router: Router) -> None:
        """규칙2: free 구독은 예산이 있어도 항상 LOCAL."""
        d = router.route(
            _req(
                difficulty="killer",
                student_subscription="free",
                budget_krw=99999.0,
            )
        )
        assert d.cost_tier == CostTier.LOCAL

    def test_rule3_killer_to_cloud_high(self, router: Router) -> None:
        """규칙3: killer 난이도 → CLOUD_HIGH (예산·구독 가드 통과 시)."""
        d = router.route(
            _req(
                difficulty="killer",
                student_subscription="gifted",
                budget_krw=1000.0,
            )
        )
        assert d.cost_tier == CostTier.CLOUD_HIGH
        assert d.local_model is None
        assert d.mode == "sync"

    def test_rule3_prove_to_cloud_high(self, router: Router) -> None:
        """규칙3: task_type=prove → CLOUD_HIGH."""
        d = router.route(
            _req(
                task_type="prove",
                difficulty="hard",
                student_subscription="premium",
                budget_krw=1000.0,
            )
        )
        assert d.cost_tier == CostTier.CLOUD_HIGH

    def test_rule4_reasoning_premium_to_cloud_mid(self, router: Router) -> None:
        """규칙4: requires_reasoning + premium → CLOUD_MID."""
        d = router.route(
            _req(
                task_type="diagnose",
                difficulty="hard",
                requires_reasoning=True,
                student_subscription="premium",
                budget_krw=1000.0,
            )
        )
        assert d.cost_tier == CostTier.CLOUD_MID
        assert d.local_model is None

    def test_rule4_reasoning_gifted_to_cloud_mid(self, router: Router) -> None:
        """규칙4: requires_reasoning + gifted → CLOUD_MID."""
        d = router.route(
            _req(requires_reasoning=True, student_subscription="gifted", budget_krw=1000.0)
        )
        assert d.cost_tier == CostTier.CLOUD_MID

    def test_rule4_reasoning_basic_stays_local(self, router: Router) -> None:
        """규칙4 미적용: basic은 premium↑이 아니므로 LOCAL로 떨어진다."""
        d = router.route(
            _req(requires_reasoning=True, student_subscription="basic", budget_krw=1000.0)
        )
        assert d.cost_tier == CostTier.LOCAL

    def test_rule6_default_local(self, router: Router) -> None:
        """규칙6: 그 외 기본 LOCAL (목표 분포 80%)."""
        d = router.route(
            _req(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="premium",
                budget_krw=1000.0,
            )
        )
        assert d.cost_tier == CostTier.LOCAL


# ══════════════════════════════════════════════════════════════════════
# 축2 결정표 (03a §C.2) — 7규칙 각각 (축1=LOCAL 전제, budget_krw=0)
# ══════════════════════════════════════════════════════════════════════
class TestAxis2LocalTier:
    def test_rule1_self_verify_quality_async(self, router: Router) -> None:
        """규칙1: call_site=⑤ 자기검증 → QUALITY/async."""
        d = router.route(_req(call_site=CallSite.SELF_VERIFY))
        assert d.cost_tier == CostTier.LOCAL
        assert d.local_model == LocalModelTier.QUALITY
        assert d.mode == "async"
        assert d.est_latency_ms == LOCAL_LATENCY_MS[LocalModelTier.QUALITY]

    def test_rule2_async_generate_quality(self, router: Router) -> None:
        """규칙2: 비동기 + generate → QUALITY/async (27b 비동기 전용)."""
        d = router.route(_req(task_type="generate", sync=False))
        assert d.local_model == LocalModelTier.QUALITY
        assert d.mode == "async"

    def test_rule2_async_verify_quality(self, router: Router) -> None:
        """규칙2: 비동기 + verify → QUALITY/async."""
        d = router.route(_req(task_type="verify", sync=False))
        assert d.local_model == LocalModelTier.QUALITY

    def test_rule2_async_hard_quality(self, router: Router) -> None:
        """규칙2: 비동기 + hard 난이도 → QUALITY/async."""
        d = router.route(_req(task_type="explain", difficulty="hard", sync=False))
        assert d.local_model == LocalModelTier.QUALITY

    def test_rule2_async_killer_quality(self, router: Router) -> None:
        """규칙2: 비동기 + killer 난이도(예산 0이라 축1 LOCAL) → QUALITY/async."""
        d = router.route(_req(difficulty="killer", sync=False, budget_krw=0.0))
        assert d.local_model == LocalModelTier.QUALITY

    def test_rule3_sync_tight_sla_fast(self, router: Router) -> None:
        """규칙3: 동기 + max_latency<2000 → FAST (FAST만 SLA 게이트 통과)."""
        d = router.route(
            _req(task_type="explain", difficulty="hard", requires_reasoning=True, max_latency_ms=1500)
        )
        assert d.local_model == LocalModelTier.FAST
        assert d.mode == "sync"
        assert d.est_latency_ms == LOCAL_LATENCY_MS[LocalModelTier.FAST]

    def test_rule3_boundary_exactly_2000_not_fast(self, router: Router) -> None:
        """규칙3 경계: max_latency==2000은 <2000이 아니므로 규칙3 미적용."""
        # explain+reasoning이라 규칙5로 떨어져 MID
        d = router.route(
            _req(task_type="explain", requires_reasoning=True, max_latency_ms=SLA_GATE_MS)
        )
        assert d.local_model == LocalModelTier.MID

    def test_rule4_greeting_phase_fast(self, router: Router) -> None:
        """규칙4: conversation_phase=greeting → FAST."""
        d = router.route(_req(task_type="coach", conversation_phase="greeting"))
        assert d.local_model == LocalModelTier.FAST

    def test_rule4_followup_phase_fast(self, router: Router) -> None:
        """규칙4: conversation_phase=followup → FAST."""
        d = router.route(_req(conversation_phase="followup"))
        assert d.local_model == LocalModelTier.FAST

    @pytest.mark.parametrize("task", ["extract", "match", "translate"])
    def test_rule4_light_callsites_fast(self, router: Router, task: str) -> None:
        """규칙4: extract/match/translate(①③④ 경량) → FAST."""
        d = router.route(_req(task_type=task, difficulty="medium"))
        assert d.local_model == LocalModelTier.FAST

    def test_rule4_easy_no_reasoning_fast(self, router: Router) -> None:
        """규칙4: easy + not requires_reasoning → FAST (1단계 산술)."""
        d = router.route(_req(task_type="explain", difficulty="easy", requires_reasoning=False))
        assert d.local_model == LocalModelTier.FAST

    @pytest.mark.parametrize("task", ["explain", "coach", "diagnose"])
    def test_rule5_reasoning_main_dialogue_mid(self, router: Router, task: str) -> None:
        """규칙5: explain/coach/diagnose + reasoning → MID (정밀 풀이·메인 대화)."""
        d = router.route(_req(task_type=task, difficulty="medium", requires_reasoning=True))
        assert d.local_model == LocalModelTier.MID
        assert d.mode == "sync"
        assert d.est_latency_ms == LOCAL_LATENCY_MS[LocalModelTier.MID]

    def test_rule6_sync_medium_mid(self, router: Router) -> None:
        """규칙6: 동기 + medium(규칙4·5 미해당) → MID."""
        # task_type=generate(규칙5 set 밖), sync=True(규칙2 밖), medium → 규칙6
        d = router.route(_req(task_type="generate", difficulty="medium", sync=True))
        assert d.local_model == LocalModelTier.MID

    def test_rule6_sync_hard_mid(self, router: Router) -> None:
        """규칙6: 동기 + hard(규칙4·5 미해당) → MID."""
        d = router.route(
            _req(task_type="generate", difficulty="hard", requires_reasoning=False, sync=True)
        )
        assert d.local_model == LocalModelTier.MID

    def test_rule7_fallback_fast(self, router: Router) -> None:
        """규칙7: 어떤 규칙에도 안 걸리는 안전 기본값 → FAST."""
        # generate + easy + reasoning + sync: 규칙2(sync), 규칙3(latency), 규칙4(easy인데 reasoning),
        # 규칙5(generate 아님), 규칙6(easy 아님) 모두 미해당 → 규칙7
        d = router.route(
            _req(task_type="generate", difficulty="easy", requires_reasoning=True, sync=True)
        )
        assert d.local_model == LocalModelTier.FAST
        assert d.mode == "sync"


# ══════════════════════════════════════════════════════════════════════
# 축1·축2 상호작용 — 축1이 먼저, 권위적 (03a §C.4 순서)
# ══════════════════════════════════════════════════════════════════════
class TestAxisInteraction:
    def test_axis1_wins_over_selfverify(self, router: Router) -> None:
        """축1이 먼저 평가 — reasoning+premium이면 ⑤여도 CLOUD_MID로 승급.

        C.2(축2)는 '축1=LOCAL로 확정된 요청만' 평가하므로, call_site=⑤가
        QUALITY를 강제하는 것은 LOCAL로 남았을 때 뿐이다(03a §C.2 전제).
        """
        d = router.route(
            _req(
                call_site=CallSite.SELF_VERIFY,
                requires_reasoning=True,
                student_subscription="premium",
                budget_krw=1000.0,
            )
        )
        assert d.cost_tier == CostTier.CLOUD_MID
        assert d.local_model is None

    def test_selfverify_stays_local_when_budget_zero(self, router: Router) -> None:
        """예산 0이면 축1이 LOCAL 강제 → ⑤가 QUALITY/async로 작동."""
        d = router.route(
            _req(
                call_site=CallSite.SELF_VERIFY,
                requires_reasoning=True,
                student_subscription="premium",
                budget_krw=0.0,
            )
        )
        assert d.cost_tier == CostTier.LOCAL
        assert d.local_model == LocalModelTier.QUALITY
        assert d.mode == "async"


# ══════════════════════════════════════════════════════════════════════
# guard_cloud (03a §D.4)
# ══════════════════════════════════════════════════════════════════════
class TestGuardCloud:
    def test_free_demoted_to_local(self) -> None:
        """free 구독은 클라우드 금지 → LOCAL 강등."""
        req = _req(student_subscription="free", budget_krw=99999.0)
        assert guard_cloud(req, CostTier.CLOUD_HIGH) == CostTier.LOCAL

    def test_insufficient_budget_demoted(self) -> None:
        """잔여 예산 < 1회 최소 비용 → LOCAL 강등."""
        # CLOUD_HIGH 최소비용보다 작은 예산
        req = _req(
            student_subscription="premium",
            budget_krw=CLOUD_MIN_COST_KRW[CostTier.CLOUD_HIGH] - 1.0,
        )
        assert guard_cloud(req, CostTier.CLOUD_HIGH) == CostTier.LOCAL

    def test_basic_high_limited_to_mid(self) -> None:
        """basic 구독 + CLOUD_HIGH 희망 → CLOUD_MID로 제한."""
        req = _req(student_subscription="basic", budget_krw=1000.0)
        assert guard_cloud(req, CostTier.CLOUD_HIGH) == CostTier.CLOUD_MID

    def test_premium_high_allowed(self) -> None:
        """premium + 충분 예산 → CLOUD_HIGH 그대로 통과."""
        req = _req(student_subscription="premium", budget_krw=1000.0)
        assert guard_cloud(req, CostTier.CLOUD_HIGH) == CostTier.CLOUD_HIGH

    def test_mid_allowed_with_budget(self) -> None:
        """충분 예산이면 CLOUD_MID 통과."""
        req = _req(student_subscription="basic", budget_krw=1000.0)
        assert guard_cloud(req, CostTier.CLOUD_MID) == CostTier.CLOUD_MID

    def test_route_killer_basic_demoted_to_mid(self, router: Router) -> None:
        """통합: killer + basic → 규칙3이 CLOUD_HIGH 희망하나 가드가 CLOUD_MID로 제한."""
        d = router.route(
            _req(difficulty="killer", student_subscription="basic", budget_krw=1000.0)
        )
        assert d.cost_tier == CostTier.CLOUD_MID

    def test_route_killer_low_budget_demoted_to_local(self, router: Router) -> None:
        """통합: killer지만 예산이 HIGH 최소비용 미만 → LOCAL 강등."""
        d = router.route(
            _req(
                difficulty="killer",
                student_subscription="premium",
                budget_krw=CLOUD_MIN_COST_KRW[CostTier.CLOUD_HIGH] - 1.0,
            )
        )
        # 단 budget>0이라 규칙1은 통과, 규칙3 가드에서 LOCAL 강등
        assert d.cost_tier == CostTier.LOCAL
        assert d.local_model is not None  # 불변식 1: LOCAL이면 local_model 존재


# ══════════════════════════════════════════════════════════════════════
# 캐시 키 (03a §F.1) — 두 축 포함
# ══════════════════════════════════════════════════════════════════════
class TestCacheKey:
    def test_key_has_prefix(self) -> None:
        key = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        assert key.startswith("llm:cache:")

    def test_local_tiers_produce_different_keys(self) -> None:
        """같은 프롬프트라도 FAST vs MID는 다른 키 (캐시 정체성에 축2 포함)."""
        k_fast = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        k_mid = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.MID)
        assert k_fast != k_mid

    def test_cost_tiers_produce_different_keys(self) -> None:
        """LOCAL vs CLOUD는 다른 키 (축1 포함)."""
        k_local = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        k_cloud = cache_key("p", "s", CostTier.CLOUD_MID, None)
        assert k_local != k_cloud

    def test_same_inputs_stable_key(self) -> None:
        """동일 입력 → 동일 키 (해시 안정성)."""
        k1 = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        k2 = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        assert k1 == k2

    def test_none_local_model_uses_dash(self) -> None:
        """local_model None(클라우드)도 안정적으로 키 생성."""
        key = cache_key("p", "s", CostTier.CLOUD_HIGH, None)
        assert key.startswith("llm:cache:")

    def test_accepts_string_values(self) -> None:
        """use_enum_values=True로 문자열이 들어와도 동작 (정규화)."""
        k_enum = cache_key("p", "s", CostTier.LOCAL, LocalModelTier.FAST)
        k_str = cache_key("p", "s", "local", "fast")  # type: ignore[arg-type]
        assert k_enum == k_str

    def test_cache_key_for_decision(self, router: Router) -> None:
        """cache_key_for(decision)는 cache_key와 동일 결과."""
        d = router.route(_req(task_type="extract"))
        k1 = cache_key_for("p", "s", d)
        k2 = cache_key("p", "s", d.cost_tier, d.local_model)
        assert k1 == k2

    def test_different_prompt_different_key(self) -> None:
        """프롬프트가 다르면 키도 다르다."""
        k1 = cache_key("p1", "s", CostTier.LOCAL, LocalModelTier.FAST)
        k2 = cache_key("p2", "s", CostTier.LOCAL, LocalModelTier.FAST)
        assert k1 != k2


# ══════════════════════════════════════════════════════════════════════
# 추정기 (03a §A.1·§E)
# ══════════════════════════════════════════════════════════════════════
class TestEstimators:
    def test_local_latency_values(self) -> None:
        """로컬 지연 — 03a §A.1 벤치 p50."""
        assert local_latency(LocalModelTier.FAST) == 1010
        assert local_latency(LocalModelTier.MID) == 3918
        assert local_latency(LocalModelTier.QUALITY) == 13886

    def test_cloud_latency_values(self) -> None:
        """클라우드 지연 — placeholder 상수."""
        assert cloud_latency(CostTier.CLOUD_MID) == CLOUD_LATENCY_MS[CostTier.CLOUD_MID]
        assert cloud_latency(CostTier.CLOUD_HIGH) == CLOUD_LATENCY_MS[CostTier.CLOUD_HIGH]

    def test_cloud_min_cost_high_gt_mid(self) -> None:
        """CLOUD_HIGH 최소비용 > CLOUD_MID (Opus가 Sonnet보다 비쌈)."""
        assert cloud_min_cost(CostTier.CLOUD_HIGH) > cloud_min_cost(CostTier.CLOUD_MID)

    def test_cloud_cost_matches_min(self) -> None:
        """현재 cloud_cost는 placeholder로 최소비용 사용."""
        req = _req(student_subscription="premium", budget_krw=1000.0)
        assert cloud_cost(req, CostTier.CLOUD_MID) == CLOUD_MIN_COST_KRW[CostTier.CLOUD_MID]

    def test_route_local_cost_zero(self, router: Router) -> None:
        """로컬 경로는 비용 0원."""
        d = router.route(_req(task_type="extract"))
        assert d.est_cost_krw == 0.0

    def test_route_cloud_cost_positive(self, router: Router) -> None:
        """클라우드 경로는 비용 > 0."""
        d = router.route(
            _req(difficulty="killer", student_subscription="gifted", budget_krw=1000.0)
        )
        assert d.est_cost_krw > 0.0

    def test_daily_limits_match_spec(self) -> None:
        """구독별 일일 한도 — 03a §E.2 확정값."""
        assert DAILY_LIMIT_KRW == {
            "free": 100,
            "basic": 500,
            "premium": 2000,
            "gifted": 5000,
        }


# ══════════════════════════════════════════════════════════════════════
# Langfuse 태그 dict (03a §F.2) — dict만 생성, 전송 X
# ══════════════════════════════════════════════════════════════════════
class TestLangfuseFields:
    def test_local_decision_fields(self, router: Router) -> None:
        """로컬 결정의 태그 — cost_tier·local_model·mode 포함."""
        d = router.route(_req(task_type="extract"))
        f = langfuse_fields(d)
        assert f["cost_tier"] == "local"
        assert f["local_model"] == "fast"
        assert f["mode"] == "sync"
        assert f["cache_hit"] is False
        assert f["escalated_from"] is None
        assert f["call_site"] is None
        assert f["student_id_hash"] is None

    def test_cloud_decision_local_model_null(self, router: Router) -> None:
        """클라우드 결정 태그 — local_model None."""
        d = router.route(
            _req(difficulty="killer", student_subscription="gifted", budget_krw=1000.0)
        )
        f = langfuse_fields(d)
        assert f["cost_tier"] == "cloud_high"
        assert f["local_model"] is None

    def test_optional_fields_recorded(self, router: Router) -> None:
        """cache_hit·escalated_from·call_site·student_id_hash 기록."""
        d = router.route(_req(task_type="extract"))
        f = langfuse_fields(
            d,
            cache_hit=True,
            escalated_from=LocalModelTier.FAST,
            call_site=CallSite.CONCEPT_EXTRACT,
            student_id_hash="abc123",
        )
        assert f["cache_hit"] is True
        assert f["escalated_from"] == "fast"
        assert f["call_site"] == "extract"
        assert f["student_id_hash"] == "abc123"

    def test_escalated_from_cost_tier_enum(self, router: Router) -> None:
        """escalated_from에 CostTier enum도 허용 (값으로 정규화)."""
        d = router.route(_req(task_type="extract"))
        f = langfuse_fields(d, escalated_from=CostTier.CLOUD_MID)
        assert f["escalated_from"] == "cloud_mid"

    def test_escalated_from_string(self, router: Router) -> None:
        """escalated_from에 문자열도 그대로 허용."""
        d = router.route(_req(task_type="extract"))
        f = langfuse_fields(d, escalated_from="mid")
        assert f["escalated_from"] == "mid"

    def test_call_site_string_accepted(self, router: Router) -> None:
        """call_site에 문자열도 허용 (정규화)."""
        d = router.route(_req(task_type="extract"))
        f = langfuse_fields(d, call_site="extract")
        assert f["call_site"] == "extract"


# ══════════════════════════════════════════════════════════════════════
# 에스컬레이션 사슬 (03a §D.1·§D.2) — next_tier 로직
# ══════════════════════════════════════════════════════════════════════
class TestEscalationChain:
    def test_chain_order(self) -> None:
        """사슬 순서 — FAST→MID→QUALITY→CLOUD_MID→CLOUD_HIGH."""
        assert ESCALATION_CHAIN[0] == (CostTier.LOCAL, LocalModelTier.FAST)
        assert ESCALATION_CHAIN[-1] == (CostTier.CLOUD_HIGH, None)
        assert len(ESCALATION_CHAIN) == 5

    def test_fast_to_mid(self) -> None:
        assert next_tier(CostTier.LOCAL, LocalModelTier.FAST) == (
            CostTier.LOCAL,
            LocalModelTier.MID,
        )

    def test_mid_to_quality(self) -> None:
        assert next_tier(CostTier.LOCAL, LocalModelTier.MID) == (
            CostTier.LOCAL,
            LocalModelTier.QUALITY,
        )

    def test_quality_to_cloud_mid(self) -> None:
        """로컬 천장(QUALITY)에서 CLOUD로 넘어감."""
        assert next_tier(CostTier.LOCAL, LocalModelTier.QUALITY) == (
            CostTier.CLOUD_MID,
            None,
        )

    def test_cloud_mid_to_cloud_high(self) -> None:
        assert next_tier(CostTier.CLOUD_MID, None) == (CostTier.CLOUD_HIGH, None)

    def test_cloud_high_is_ceiling(self) -> None:
        """천장(CLOUD_HIGH)에서는 더 승급 불가 → None."""
        assert next_tier(CostTier.CLOUD_HIGH, None) is None

    def test_unknown_pair_returns_none(self) -> None:
        """사슬에 없는 조합(예: CLOUD_MID+FAST)은 None."""
        assert next_tier(CostTier.CLOUD_MID, LocalModelTier.FAST) is None

    def test_accepts_string_values(self) -> None:
        """문자열 입력도 정규화하여 동작."""
        assert next_tier("local", "fast") == (CostTier.LOCAL, LocalModelTier.MID)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════
# 결정 객체 불변식 — route()는 항상 유효한 RoutingDecision 반환
# ══════════════════════════════════════════════════════════════════════
class TestRouteProducesValidDecisions:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"task_type": "extract", "budget_krw": 0.0},
            {"task_type": "verify", "sync": False, "budget_krw": 0.0},
            {"call_site": CallSite.SELF_VERIFY, "budget_krw": 0.0},
            {"difficulty": "killer", "student_subscription": "gifted", "budget_krw": 1000.0},
            {"requires_reasoning": True, "student_subscription": "premium", "budget_krw": 1000.0},
            {"task_type": "coach", "requires_reasoning": True, "budget_krw": 0.0},
            {"task_type": "generate", "difficulty": "medium", "sync": True, "budget_krw": 0.0},
        ],
    )
    def test_decision_is_valid(self, router: Router, overrides: dict[str, object]) -> None:
        """모든 경로의 결정이 RoutingDecision 불변식을 만족한다(생성 자체가 검증)."""
        d = router.route(_req(**overrides))
        assert isinstance(d, RoutingDecision)
        # 불변식 1·2: LOCAL ⟺ local_model 존재
        if d.cost_tier == CostTier.LOCAL:
            assert d.local_model is not None
        else:
            assert d.local_model is None
        # 불변식 3: QUALITY ⟹ async
        if d.local_model == LocalModelTier.QUALITY:
            assert d.mode == "async"
        # 추정치 타당성
        assert d.est_latency_ms > 0
        assert d.est_cost_krw >= 0.0
        assert d.reason  # 비어있지 않음
