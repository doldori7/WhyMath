"""L3 라우터 스키마 단위 테스트 — enum·RoutingRequest·RoutingDecision 불변식.

설계 정본: docs/architecture/03a_l3_router_design.md §G(스키마·불변식)·§B.1(입력 신호).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    RoutingDecision,
    RoutingRequest,
)


# ──────────────────────────────────────────────────────────────────────
# enum 값 — 03a §0.1·§A.1·§B.2 명세와 정확히 일치해야 한다
# ──────────────────────────────────────────────────────────────────────
class TestEnumValues:
    def test_cost_tier_values(self) -> None:
        """축1 CostTier 값 — 명칭 충돌 해소 결과(CLOUD_ 접두사)."""
        assert CostTier.LOCAL.value == "local"
        assert CostTier.CLOUD_MID.value == "cloud_mid"
        assert CostTier.CLOUD_HIGH.value == "cloud_high"

    def test_local_model_tier_values(self) -> None:
        """축2 LocalModelTier 값 — 2026-05-19 벤치 라인업."""
        assert LocalModelTier.FAST.value == "fast"
        assert LocalModelTier.MID.value == "mid"
        assert LocalModelTier.QUALITY.value == "quality"

    def test_call_site_values(self) -> None:
        """5개 핵심 호출지점 ①~⑤ 식별자."""
        assert CallSite.CONCEPT_EXTRACT.value == "extract"
        assert CallSite.DEEP_REASON.value == "depth"
        assert CallSite.TRANSLATE_NORMALIZE.value == "translate"
        assert CallSite.CONCEPT_ID_MATCH.value == "match"
        assert CallSite.SELF_VERIFY.value == "self_verify"

    def test_str_enum_equals_value(self) -> None:
        """str-Enum이므로 멤버는 그 문자열 값과 동등 (라우터 비교 안정성)."""
        assert CostTier.LOCAL == "local"
        assert LocalModelTier.FAST == "fast"


# ──────────────────────────────────────────────────────────────────────
# RoutingRequest — 기본값·extra forbid·필수 필드 (03a §B.1·§G)
# ──────────────────────────────────────────────────────────────────────
class TestRoutingRequest:
    def test_minimal_required_fields(self) -> None:
        """필수 필드만으로 생성 — 신규 신호는 기본값."""
        req = RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",
        )
        assert req.max_latency_ms == 30000  # 기본값
        assert req.budget_krw == 0.0  # 기본값(LOCAL 강제)
        assert req.sync is True  # 기본값
        assert req.conversation_phase is None
        assert req.call_site is None

    def test_call_site_coerced_to_value(self) -> None:
        """use_enum_values=True → call_site는 문자열 값으로 저장된다."""
        req = RoutingRequest(
            task_type="extract",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",
            call_site=CallSite.CONCEPT_EXTRACT,
        )
        # use_enum_values=True: 저장값은 문자열
        assert req.call_site == "extract"

    def test_extra_field_rejected(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            RoutingRequest(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="free",
                unknown_field="x",  # type: ignore[call-arg]
            )

    def test_negative_latency_rejected(self) -> None:
        """max_latency_ms는 음수 불가(ge=0)."""
        with pytest.raises(ValidationError):
            RoutingRequest(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="free",
                max_latency_ms=-1,
            )

    def test_invalid_call_site_rejected(self) -> None:
        """call_site는 CallSite enum 값만 허용."""
        with pytest.raises(ValidationError):
            RoutingRequest(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="free",
                call_site="nonexistent",  # type: ignore[arg-type]
            )


# ──────────────────────────────────────────────────────────────────────
# RoutingDecision 불변식 — 03a §G (정상 케이스)
# ──────────────────────────────────────────────────────────────────────
class TestRoutingDecisionValid:
    def test_local_with_fast_sync(self) -> None:
        """LOCAL + FAST + sync — 불변식 1 충족."""
        d = RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_model=LocalModelTier.FAST,
            mode="sync",
            reason="local/fast",
            est_latency_ms=1010,
        )
        assert d.cost_tier == CostTier.LOCAL
        assert d.local_model == LocalModelTier.FAST

    def test_local_with_quality_async(self) -> None:
        """LOCAL + QUALITY + async — 불변식 3 충족(QUALITY ⟹ async)."""
        d = RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_model=LocalModelTier.QUALITY,
            mode="async",
            est_latency_ms=13886,
        )
        assert d.mode == "async"

    def test_cloud_mid_no_local(self) -> None:
        """CLOUD_MID + local_model None — 불변식 2 충족."""
        d = RoutingDecision(
            cost_tier=CostTier.CLOUD_MID,
            local_model=None,
            mode="sync",
            est_latency_ms=3000,
            est_cost_krw=10.0,
        )
        assert d.local_model is None

    def test_cloud_high_no_local(self) -> None:
        """CLOUD_HIGH + local_model None — 불변식 2 충족."""
        d = RoutingDecision(
            cost_tier=CostTier.CLOUD_HIGH,
            local_model=None,
            est_latency_ms=8000,
            est_cost_krw=50.0,
        )
        assert d.cost_tier == CostTier.CLOUD_HIGH


# ──────────────────────────────────────────────────────────────────────
# RoutingDecision 불변식 — 03a §G (위반 케이스 → ValidationError)
# ──────────────────────────────────────────────────────────────────────
class TestRoutingDecisionInvariants:
    def test_local_without_local_model_rejected(self) -> None:
        """불변식 1 위반: LOCAL인데 local_model None."""
        with pytest.raises(ValidationError) as exc:
            RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_model=None,
                est_latency_ms=1010,
            )
        assert "불변식" in str(exc.value)

    def test_cloud_mid_with_local_model_rejected(self) -> None:
        """불변식 2 위반: CLOUD_MID인데 local_model 존재."""
        with pytest.raises(ValidationError) as exc:
            RoutingDecision(
                cost_tier=CostTier.CLOUD_MID,
                local_model=LocalModelTier.FAST,
                est_latency_ms=3000,
            )
        assert "불변식" in str(exc.value)

    def test_cloud_high_with_local_model_rejected(self) -> None:
        """불변식 2 위반: CLOUD_HIGH인데 local_model 존재."""
        with pytest.raises(ValidationError):
            RoutingDecision(
                cost_tier=CostTier.CLOUD_HIGH,
                local_model=LocalModelTier.QUALITY,
                mode="async",
                est_latency_ms=8000,
            )

    def test_quality_sync_rejected(self) -> None:
        """불변식 3 위반: QUALITY인데 mode='sync' (27b 동기 불가)."""
        with pytest.raises(ValidationError) as exc:
            RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_model=LocalModelTier.QUALITY,
                mode="sync",
                est_latency_ms=13886,
            )
        assert "불변식" in str(exc.value)

    def test_invalid_mode_rejected(self) -> None:
        """mode는 'sync'/'async'만 허용."""
        with pytest.raises(ValidationError):
            RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_model=LocalModelTier.FAST,
                mode="background",  # 잘못된 값
                est_latency_ms=1010,
            )

    def test_negative_latency_rejected(self) -> None:
        """est_latency_ms 음수 불가(ge=0)."""
        with pytest.raises(ValidationError):
            RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_model=LocalModelTier.FAST,
                est_latency_ms=-1,
            )

    def test_negative_cost_rejected(self) -> None:
        """est_cost_krw 음수 불가(ge=0)."""
        with pytest.raises(ValidationError):
            RoutingDecision(
                cost_tier=CostTier.LOCAL,
                local_model=LocalModelTier.FAST,
                est_latency_ms=1010,
                est_cost_krw=-5.0,
            )
