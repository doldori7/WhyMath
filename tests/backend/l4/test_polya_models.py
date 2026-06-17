"""L4 Polya 모델 단위테스트 — 기본값·라운드트립·검증."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l3.models import CostTier
from whymath_backend.l4.models import (
    PedagogyDecision,
    PolyaStage,
    PolyaState,
    ToneReport,
)


class TestPolyaStage:
    def test_four_stages_with_canonical_values(self) -> None:
        assert PolyaStage.UNDERSTAND.value == "understand"
        assert PolyaStage.PLAN.value == "plan"
        assert PolyaStage.EXECUTE.value == "execute"
        assert PolyaStage.REVIEW.value == "review"
        assert len(list(PolyaStage)) == 4


class TestPolyaState:
    def test_default_starts_at_understand(self) -> None:
        s = PolyaState()
        assert s.current_stage is PolyaStage.UNDERSTAND
        assert s.history == []
        assert s.turn_count == 0

    def test_turn_count_must_be_nonnegative(self) -> None:
        with pytest.raises(ValidationError):
            PolyaState(turn_count=-1)

    def test_history_records_transitions(self) -> None:
        s = PolyaState(
            current_stage=PolyaStage.PLAN,
            history=[PolyaStage.UNDERSTAND],
            turn_count=2,
        )
        assert s.history == [PolyaStage.UNDERSTAND]


class TestPedagogyDecision:
    def test_defaults_hint_level_1_local_tier(self) -> None:
        d = PedagogyDecision(polya_stage_to_advance="stay", prompt="p", system="s")
        assert d.hint_level == 1  # 가장 은근 — 답 미루기 우선
        assert d.recommended_cost_tier is CostTier.LOCAL  # 로컬 우선
        assert d.socratic_category == ""  # 슬라이스 2서 채움
        assert d.suggested_actions == []

    def test_hint_level_range_validation(self) -> None:
        with pytest.raises(ValidationError):
            PedagogyDecision(polya_stage_to_advance="stay", prompt="p", system="s", hint_level=0)
        with pytest.raises(ValidationError):
            PedagogyDecision(polya_stage_to_advance="stay", prompt="p", system="s", hint_level=5)

    def test_stage_transition_literal(self) -> None:
        for t in ("stay", "next", "previous"):
            d = PedagogyDecision(polya_stage_to_advance=t, prompt="p", system="s")  # type: ignore[arg-type]
            assert d.polya_stage_to_advance == t
        with pytest.raises(ValidationError):
            PedagogyDecision(
                polya_stage_to_advance="skip",  # type: ignore[arg-type]
                prompt="p",
                system="s",
            )

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PedagogyDecision(
                polya_stage_to_advance="stay", prompt="p", system="s", foo=1  # type: ignore[call-arg]
            )


class TestToneReport:
    def test_default_clean(self) -> None:
        r = ToneReport()
        assert r.violations == []
        assert r.rewritten is False
