"""Polya 단계 × 전이 → 소크라테스 카테고리 선택 단위테스트.

스펙 L82-87 PRD 정렬표 + L65-70 본문 정합 검증.
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.models import PolyaStage, StageTransition
from whymath_backend.l4.socratic import SocraticCategory, select_category


class TestStageDefaultsOnStay:
    """stay 전이 + 발화 신호 없음 → 단계 기본 카테고리."""

    @pytest.mark.parametrize(
        ("stage", "expected"),
        [
            (PolyaStage.UNDERSTAND, SocraticCategory.CLARIFICATION),
            (PolyaStage.PLAN, SocraticCategory.PERSPECTIVE),
            (PolyaStage.EXECUTE, SocraticCategory.IMPLICATION),
            (PolyaStage.REVIEW, SocraticCategory.META),
        ],
    )
    def test_default_per_stage(
        self, stage: PolyaStage, expected: SocraticCategory
    ) -> None:
        assert select_category(stage, "stay", "음") == expected


class TestNextAdvancesToNewStageDefault:
    """next 전이 → 다음 단계의 기본 카테고리(단계 진입 발화)."""

    @pytest.mark.parametrize(
        ("from_stage", "expected"),
        [
            # UNDERSTAND→PLAN 진입 = PERSPECTIVE("관점 선택" 마디, 스펙 L84)
            (PolyaStage.UNDERSTAND, SocraticCategory.PERSPECTIVE),
            # PLAN→EXECUTE 진입 = IMPLICATION
            (PolyaStage.PLAN, SocraticCategory.IMPLICATION),
            # EXECUTE→REVIEW 진입 = META
            (PolyaStage.EXECUTE, SocraticCategory.META),
            # REVIEW는 종착 → next도 REVIEW 기본(META)
            (PolyaStage.REVIEW, SocraticCategory.META),
        ],
    )
    def test_next_picks_target_stage_default(
        self, from_stage: PolyaStage, expected: SocraticCategory
    ) -> None:
        assert select_category(from_stage, "next", "함수 최댓값") == expected


class TestInputSignalOverridesOnStay:
    """학생 발화 신호 → 단계 기본보다 우선(stay 한정)."""

    def test_evidence_keyword_overrides(self) -> None:
        # "왜·이유·근거"는 단계 무관 EVIDENCE
        for stage in PolyaStage:
            assert (
                select_category(stage, "stay", "왜 이렇게 되는 건지 모르겠어")
                == SocraticCategory.EVIDENCE
            )
            assert (
                select_category(stage, "stay", "근거가 뭐지")
                == SocraticCategory.EVIDENCE
            )

    def test_assumption_keyword_overrides(self) -> None:
        # "가정·라고 치"는 단계 무관 ASSUMPTION
        for stage in PolyaStage:
            assert (
                select_category(stage, "stay", "이건 양수라고 가정했어")
                == SocraticCategory.ASSUMPTION
            )
            assert (
                select_category(stage, "stay", "f가 연속이라고 치자")
                == SocraticCategory.ASSUMPTION
            )

    def test_assumption_precedes_evidence(self) -> None:
        # 둘 다 있으면 가장 구체적 신호(가정 탐색) 우선 — 매핑 순서 보장.
        text = "왜 가정을 그렇게 두는 거야"
        assert (
            select_category(PolyaStage.PLAN, "stay", text)
            == SocraticCategory.ASSUMPTION
        )


class TestSignalsIgnoredOnNext:
    """next 전이는 발화 신호 무시 — 단계 *진입* 발화는 새 단계 기본 카테고리."""

    def test_evidence_keyword_ignored_on_next(self) -> None:
        # next라 발화에 "왜" 있어도 다음 단계 기본 사용
        assert (
            select_category(PolyaStage.UNDERSTAND, "next", "왜 모르겠어")
            == SocraticCategory.PERSPECTIVE
        )


class TestPreviousTreatedLikeStay:
    """previous 전이는 stay와 동일한 우선순위(현 단계 기본 + 발화 신호 오버라이드)."""

    def test_previous_uses_current_stage_default(self) -> None:
        t: StageTransition = "previous"
        assert select_category(PolyaStage.PLAN, t, "") == SocraticCategory.PERSPECTIVE

    def test_previous_respects_signal(self) -> None:
        t: StageTransition = "previous"
        assert (
            select_category(PolyaStage.PLAN, t, "왜 모르겠어")
            == SocraticCategory.EVIDENCE
        )
