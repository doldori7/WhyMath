"""동등문제 수용 게이트 *거버넌스* 테스트 — 저작권 우회 봉인(S2-a).

CLAUDE.md 절대 금기(평가원·EBS·검정교과서 본문 복제 금지·미성년자 우선순위 #2 저작권)를
게이트 계층에서 *기계적으로* 봉인하는지 실증한다. 저작권은 구조적 불변식(Problem·
ContentProvenance)이 강제하므로, 우회 경로가 (i) Problem 생성 (ii) ContentProvenance 생성
(iii) 게이트 값 확인 세 층에서 모두 막히는지 확인한다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem
from whymath_backend.schema.provenance import ContentProvenance

_METADATA_ONLY = [SourceType.평가원, SourceType.EBS, SourceType.교과서]


# ──────────────────────────────────────────────────────────────────────
# (i) 본문 보유 메타 전용 출처는 Problem 생성 자체가 거부된다(본문 불변식).
# ──────────────────────────────────────────────────────────────────────
class TestBodyOnlyForSelfGenerated:
    @pytest.mark.parametrize("source", _METADATA_ONLY)
    def test_metadata_source_with_question_text_rejected(self, source: SourceType) -> None:
        """평가원/EBS/교과서 + question_text 보유 → Problem 생성 거부(코퍼스 진입 불가)."""
        with pytest.raises(ValidationError):
            Problem(
                source_type=source,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
                question_text="평가원 발문 복제 시도",
            )

    @pytest.mark.parametrize("source", _METADATA_ONLY)
    def test_metadata_source_with_answer_explanation_rejected(self, source: SourceType) -> None:
        """평가원/EBS/교과서 + answer_explanation 보유 → Problem 생성 거부."""
        with pytest.raises(ValidationError):
            Problem(
                source_type=source,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
                answer_explanation="평가원 해설 복제 시도",
            )


# ──────────────────────────────────────────────────────────────────────
# (ii) 메타 전용 출처 참조 이력은 license/generation_type 규칙을 강제받는다.
# ──────────────────────────────────────────────────────────────────────
class TestProvenanceLegalInvariants:
    def test_metadata_source_non_whymath_license_rejected(self) -> None:
        """original_source=평가원인데 license≠WHYMATH_GENERATED → 생성 거부(C-1)."""
        with pytest.raises(ValidationError):
            ContentProvenance(
                original_source=SourceType.평가원,
                license=LicenseType.PUBLIC_DOMAIN,
                generation_type=GenerationType.VARIANT_STRUCTURE,
            )

    def test_metadata_source_non_transformed_generation_rejected(self) -> None:
        """original_source=평가원인데 generation_type이 변형류가 아니면(None) 거부(C-2)."""
        with pytest.raises(ValidationError):
            ContentProvenance(
                original_source=SourceType.평가원,
                license=LicenseType.WHYMATH_GENERATED,
                generation_type=None,
            )

    def test_metadata_source_transformed_variant_allowed(self) -> None:
        """평가원 + WHYMATH_GENERATED + VARIANT_STRUCTURE는 합법(동등문제 참조 이력)."""
        prov = ContentProvenance(
            original_source=SourceType.평가원,
            license=LicenseType.WHYMATH_GENERATED,
            generation_type=GenerationType.VARIANT_STRUCTURE,
            original_reference={"year": 2025, "exam": "수능", "number": 30},
        )
        assert prov.license == LicenseType.WHYMATH_GENERATED.value


# ──────────────────────────────────────────────────────────────────────
# (iii) 게이트는 비-자체생성 source_type 후보를 copyright_ok=False로 거부한다.
# ──────────────────────────────────────────────────────────────────────
class TestGateRejectsNonSelfGenerated:
    def test_aihub_candidate_copyright_not_ok(self) -> None:
        """source_type=AIHub 후보(본문 보유 합법)라도 게이트는 자체생성만 수용."""
        candidate = Problem(
            source_type=SourceType.AIHub,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.미적분,
            unit_codes=["CAL-INT-DEF"],
            difficulty_overall=3.0,
            answer_format=AnswerFormat.자연수,
            question_text="AIHub 후보 발문",
            answer="3",
        )
        provenance = ContentProvenance(
            generation_type=GenerationType.FULLY_GENERATED,
            license=LicenseType.WHYMATH_GENERATED,
        )
        spec = EquivalenceSpec(difficulty_overall=3.0)
        verdict = evaluate_equivalent_candidate(
            spec,
            candidate,
            provenance=provenance,
            conditions="x**2 - 5*x + 6 = 0",
            answer_map={"x": "3"},
        )
        assert verdict.copyright_ok is False
        assert verdict.accepted is False
        assert any("source_type" in reason for reason in verdict.reasons)
