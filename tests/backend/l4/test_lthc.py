"""LTHC 적응 단위테스트 — 단계 × 숙달도 행렬 검증.

핵심 invariant(스펙 L117-119 + LTHC 원칙):
- 초보: 진입점·비계 ON, 확장 OFF(천장 강요 회피)
- 숙달: 확장 ON, 진입·비계 OFF(자명)
- 발전 중: 세 축 *첫 1개씩*만(균형)
- 학생 수준에 따라 *다른 후보 집합*이 반환되어야 LTHC가 작동
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.lthc import LthcAdaptation, adapt_lthc, mastery_to_level
from whymath_backend.l4.lthc.models import MasteryLevel
from whymath_backend.l4.models import PolyaStage


class TestMasteryToLevel:
    """slice 25: BKT 숙달도(0~1) → LTHC 라벨 — 3구간 임계·경계 포함."""

    def test_bands(self) -> None:
        assert mastery_to_level(0.0) == "초보"
        assert mastery_to_level(0.39) == "초보"
        assert mastery_to_level(0.4) == "발전 중"  # 경계 포함(상위)
        assert mastery_to_level(0.79) == "발전 중"
        assert mastery_to_level(0.8) == "숙달"  # 경계 포함(상위)
        assert mastery_to_level(1.0) == "숙달"

    def test_custom_thresholds(self) -> None:
        assert mastery_to_level(0.5, mastered_threshold=0.5) == "숙달"
        assert mastery_to_level(0.3, developing_threshold=0.2) == "발전 중"

    def test_feeds_adapt_lthc(self) -> None:
        """매핑 결과가 adapt_lthc 입력으로 그대로 쓰임(브릿지 계약)."""
        level = mastery_to_level(0.1)  # 초보
        adaptation = adapt_lthc(PolyaStage.PLAN, level)
        assert adaptation.mastery_level == "초보"
        assert adaptation.entry_suggestions  # 초보 → 진입점 노출
        assert adaptation.extensions == ()  # 초보 → 확장 비공


class TestNoviceLowThreshold:
    """초보 → 진입점·비계 노출, 확장은 비공."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_novice_extensions_empty(self, stage: PolyaStage) -> None:
        a = adapt_lthc(stage, "초보")
        assert a.extensions == ()
        assert a.mastery_level == "초보"

    def test_novice_entry_nonempty_on_plan(self) -> None:
        a = adapt_lthc(PolyaStage.PLAN, "초보")
        assert len(a.entry_suggestions) >= 1
        # polya_4step.md 정본 어구 인용
        assert any("작은 경우" in s for s in a.entry_suggestions)

    def test_novice_scaffolds_nonempty(self) -> None:
        a = adapt_lthc(PolyaStage.EXECUTE, "초보")
        assert len(a.scaffolds) >= 1


class TestMasterHighCeiling:
    """숙달 → 확장 노출, 진입·비계는 비공(자명)."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_master_entry_empty(self, stage: PolyaStage) -> None:
        a = adapt_lthc(stage, "숙달")
        assert a.entry_suggestions == ()
        assert a.scaffolds == ()

    def test_master_extensions_rich_at_review(self) -> None:
        # REVIEW 단계의 확장은 NRICH 4종(일반화·변형·증명·다른 풀이) 모두 등장
        a = adapt_lthc(PolyaStage.REVIEW, "숙달")
        joined = "\n".join(a.extensions)
        assert "다른 풀이" in joined
        assert "증명" in joined
        assert "전이" in joined  # 다른 문제에도 쓸 수 있을까

    def test_master_extensions_empty_for_understand_is_minimal(self) -> None:
        # UNDERSTAND 단계 확장은 후보 1개(구조 인식) — 빈 게 아님.
        a = adapt_lthc(PolyaStage.UNDERSTAND, "숙달")
        assert len(a.extensions) == 1


class TestIntermediateBalance:
    """발전 중 → 세 축 *첫 1개씩*만(균형)."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_intermediate_at_most_one_per_axis(self, stage: PolyaStage) -> None:
        a = adapt_lthc(stage, "발전 중")
        assert len(a.entry_suggestions) <= 1
        assert len(a.extensions) <= 1
        assert len(a.scaffolds) <= 1

    def test_intermediate_first_item_matches_novice_master(self) -> None:
        # 발전 중의 첫 항목 = 초보의 첫 진입점 = 숙달의 첫 확장(축별 일관성)
        stage = PolyaStage.PLAN
        novice = adapt_lthc(stage, "초보")
        master = adapt_lthc(stage, "숙달")
        mid = adapt_lthc(stage, "발전 중")
        assert mid.entry_suggestions[:1] == novice.entry_suggestions[:1]
        assert mid.extensions[:1] == master.extensions[:1]


class TestDifferentLevelsDifferentOutput:
    """LTHC 핵심 — 같은 task(단계)인데 *수준에 따라 다른 후보* 반환."""

    def test_novice_vs_master_disjoint_axes(self) -> None:
        stage = PolyaStage.REVIEW
        novice = adapt_lthc(stage, "초보")
        master = adapt_lthc(stage, "숙달")
        # 초보는 진입+비계만, 숙달은 확장만 → 두 결과는 직교
        assert novice.entry_suggestions  # 비공
        assert master.extensions  # 비공
        assert novice.extensions == ()
        assert master.entry_suggestions == ()

    def test_all_four_stages_covered(self) -> None:
        # 각 단계 × 각 숙달도 = 12 조합 모두 LthcAdaptation 인스턴스 반환
        levels: tuple[MasteryLevel, ...] = ("초보", "발전 중", "숙달")
        for stage in PolyaStage:
            for level in levels:
                a = adapt_lthc(stage, level)
                assert isinstance(a, LthcAdaptation)
                assert a.mastery_level == level


class TestExtraForbidden:
    def test_model_extra_forbid(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LthcAdaptation(mastery_level="초보", foo=1)  # type: ignore[call-arg]
