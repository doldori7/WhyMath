"""Schema v1.0 Provenance 모델 단위 테스트 — 생성·extra forbid·법적 교정 불변식.

설계 정본: `schemas/v1.0/schema_v1.0.md` §10.1(content_provenance·generation_log).
법적 교정 근거: MEMORY 2026-05-28 속편 "스키마 법적 교정"(저작권 가이드 v2.0 §32 단서·
§136·§140 영리 비친고죄).

법적 validator 분기 커버리지(클래스 docstring 참조):
  (A) ORIGINAL 거부 / (B) EBS_LICENSED 거부 /
  (C-1) 메타출처+비WHYMATH license 거부 / (C-2) 메타출처+None·비변형 거부 /
  (C-3) 메타출처+original_reference 본문키 거부 / (C-통과) 평가원+WHYMATH+VARIANT 통과 /
  비메타출처(AIHub 등) 규칙 비적용 통과.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from whymath_backend.schema.enums import (
    GenerationType,
    LicenseType,
    SourceType,
)
from whymath_backend.schema.provenance import ContentProvenance, GenerationLog


def _valid_metadata_provenance(**overrides: object) -> ContentProvenance:
    """메타 전용 출처(평가원) 기준의 *법적으로 유효한* 최소 이력(테스트 헬퍼).

    기본값: 평가원 + WHYMATH_GENERATED + VARIANT_STRUCTURE + 구조 메타 original_reference.
    각 분기 테스트는 이 베이스에서 한 필드만 바꿔 위반을 유발한다.
    """
    kwargs: dict[str, object] = {
        "original_source": SourceType.평가원,
        "license": LicenseType.WHYMATH_GENERATED,
        "generation_type": GenerationType.VARIANT_STRUCTURE,
        "original_reference": {"year": 2025, "exam": "수능", "number": 30},
    }
    kwargs.update(overrides)
    return ContentProvenance(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# ContentProvenance — 생성·기본값
# ──────────────────────────────────────────────────────────────────────
class TestContentProvenanceCreation:
    def test_empty_provenance_valid(self) -> None:
        """모든 필드 Optional — 빈 이력도 생성 가능(UUID 자동 생성)."""
        p = ContentProvenance()
        assert isinstance(p.provenance_id, uuid.UUID)
        assert p.problem_id is None
        assert p.original_source is None
        assert p.generation_type is None
        assert p.license is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드를 채운 합법 인스턴스 — 값 보존 확인."""
        pid = uuid.uuid4()
        parent = uuid.uuid4()
        approver = uuid.uuid4()
        now = datetime.now(timezone.utc)
        p = ContentProvenance(
            problem_id=pid,
            original_source=SourceType.AIHub,
            original_reference={"dataset": "aihub-math", "id": "A-1"},
            generation_type=GenerationType.FULLY_GENERATED,
            transformation={"operations": [{"type": "swap_numbers", "from": 3, "to": 5}]},
            parent_problem_id=parent,
            transformation_pipeline={"steps": ["Qwen3-32B 초안", "Claude 검증"]},
            auto_validation={"sympy": "passed"},
            human_review={"reviewer_id": "r1", "score": 4.5},
            approved_at=now,
            approved_by=approver,
            license=LicenseType.AIHUB_OPEN,
            copyright_notice="© WhyMath",
            usage_restrictions={"resale": False},
            created_at=now,
        )
        assert p.problem_id == pid
        assert p.parent_problem_id == parent
        assert p.approved_by == approver
        assert p.generation_type == GenerationType.FULLY_GENERATED

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            ContentProvenance(bogus="x")  # type: ignore[call-arg]

    def test_enum_value_serialization(self) -> None:
        """use_enum_values → enum 필드가 문자열 값으로 직렬화."""
        p = _valid_metadata_provenance()
        dumped = p.model_dump()
        assert dumped["original_source"] == "평가원"
        assert dumped["license"] == "WHYMATH_GENERATED"
        assert dumped["generation_type"] == "VARIANT_STRUCTURE"


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (A) ORIGINAL 전면 차단
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantA_Original:  # noqa: N801  (불변식 ID 'A'를 가독성 위해 밑줄로 분리)
    def test_original_generation_rejected(self) -> None:
        """(A) generation_type=ORIGINAL → ValueError (메타출처 아니어도 차단)."""
        with pytest.raises(ValidationError, match="위반\\(A\\)"):
            ContentProvenance(
                original_source=SourceType.AIHub,
                generation_type=GenerationType.ORIGINAL,
            )

    def test_original_rejected_even_with_whymath_license(self) -> None:
        """(A)는 license와 무관하게 ORIGINAL을 차단한다."""
        with pytest.raises(ValidationError, match="위반\\(A\\)"):
            ContentProvenance(
                generation_type=GenerationType.ORIGINAL,
                license=LicenseType.WHYMATH_GENERATED,
            )

    def test_original_as_string_value_rejected(self) -> None:
        """use_enum_values 환경: 문자열 'ORIGINAL'로 줘도 (A)가 작동."""
        with pytest.raises(ValidationError, match="위반\\(A\\)"):
            ContentProvenance(generation_type="ORIGINAL")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (B) EBS_LICENSED 전면 차단
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantB_EbsLicensed:  # noqa: N801  (불변식 ID 'B'를 가독성 위해 밑줄로 분리)
    def test_ebs_licensed_rejected(self) -> None:
        """(B) license=EBS_LICENSED → ValueError (출처 무관 차단)."""
        with pytest.raises(ValidationError, match="위반\\(B\\)"):
            ContentProvenance(
                original_source=SourceType.AIHub,
                license=LicenseType.EBS_LICENSED,
            )

    def test_ebs_licensed_as_string_value_rejected(self) -> None:
        """use_enum_values 환경: 문자열 'EBS_LICENSED'로 줘도 (B)가 작동."""
        with pytest.raises(ValidationError, match="위반\\(B\\)"):
            ContentProvenance(license="EBS_LICENSED")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (C-1) 메타출처 + 비WHYMATH license 거부
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantC1_License:  # noqa: N801  (불변식 ID 'C1'을 가독성 위해 밑줄로 분리)
    @pytest.mark.parametrize("source", [SourceType.평가원, SourceType.EBS, SourceType.교과서])
    def test_metadata_source_requires_whymath_license(self, source: SourceType) -> None:
        """(C-1) 평가원/EBS/교과서 + license≠WHYMATH_GENERATED → ValueError."""
        with pytest.raises(ValidationError, match="위반\\(C-1\\)"):
            _valid_metadata_provenance(
                original_source=source,
                license=LicenseType.PUBLIC_DOMAIN,
            )

    def test_metadata_source_with_none_license_rejected(self) -> None:
        """(C-1) 메타출처 + license=None → ValueError(지배 license 미지정 불가)."""
        with pytest.raises(ValidationError, match="위반\\(C-1\\)"):
            _valid_metadata_provenance(license=None)

    def test_metadata_source_aihub_open_license_rejected(self) -> None:
        """(C-1) 메타출처 + AIHUB_OPEN → ValueError(원본 license는 통과 못 함)."""
        with pytest.raises(ValidationError, match="위반\\(C-1\\)"):
            _valid_metadata_provenance(license=LicenseType.AIHUB_OPEN)


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (C-2) 메타출처 + None·비변형 generation_type 거부
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantC2_GenerationType:  # noqa: N801  (불변식 ID 'C2'를 가독성 위해 밑줄로 분리)
    def test_metadata_source_with_none_generation_rejected(self) -> None:
        """(C-2) 메타출처 + generation_type=None → ValueError."""
        with pytest.raises(ValidationError, match="위반\\(C-2\\)"):
            _valid_metadata_provenance(generation_type=None)

    @pytest.mark.parametrize(
        "gen",
        [
            GenerationType.VARIANT_NUMBER,
            GenerationType.VARIANT_STRUCTURE,
            GenerationType.VARIANT_CONTEXT,
            GenerationType.COMPOSED,
            GenerationType.FULLY_GENERATED,
        ],
    )
    def test_metadata_source_all_transformed_types_pass(self, gen: GenerationType) -> None:
        """(C-2 통과) 변형류 5종은 모두 메타출처에서 허용된다."""
        p = _valid_metadata_provenance(generation_type=gen)
        assert p.generation_type == gen

    def test_metadata_source_original_blocked_by_a_first(self) -> None:
        """메타출처 + ORIGINAL은 (A)에서 먼저 차단된다(ValidationError 발생 확인)."""
        with pytest.raises(ValidationError, match="위반\\(A\\)"):
            _valid_metadata_provenance(generation_type=GenerationType.ORIGINAL)


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (C-3) 메타출처 + original_reference 본문키 거부
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantC3_OriginalReference:  # noqa: N801  (불변식 ID 'C3'을 가독성 위해 밑줄로 분리)
    @pytest.mark.parametrize(
        "body_ref",
        [
            {"question": "발문 본문..."},
            {"statement": "..."},
            {"body": "..."},
            {"content": "..."},
            {"answer": "16"},
            {"solution": "..."},
            {"explanation": "..."},
            {"choice": ["①", "②"]},
            {"passage": "..."},
            {"본문": "..."},
            {"문제": "..."},
            {"풀이": "..."},
            {"정답": "16"},
            {"보기": ["①"]},
            {"지문": "..."},
            {"해설": "..."},
        ],
    )
    def test_body_keys_rejected(self, body_ref: dict[str, object]) -> None:
        """(C-3) original_reference에 본문성 키가 있으면 → ValueError."""
        with pytest.raises(ValidationError, match="위반\\(C-3\\)"):
            _valid_metadata_provenance(original_reference=body_ref)

    def test_body_key_partial_match_rejected(self) -> None:
        """(C-3) 부분일치 — 'answer_text' 같은 키도 'answer' 포함으로 거부."""
        with pytest.raises(ValidationError, match="위반\\(C-3\\)"):
            _valid_metadata_provenance(original_reference={"answer_text": "..."})

    def test_body_key_case_insensitive_rejected(self) -> None:
        """(C-3) 대소문자 무관 — 'QUESTION' 키도 소문자화 후 거부."""
        with pytest.raises(ValidationError, match="위반\\(C-3\\)"):
            _valid_metadata_provenance(original_reference={"QUESTION": "..."})

    def test_structural_meta_reference_passes(self) -> None:
        """(C-3 통과) DDL 예시 {"year":2025,"exam":"수능","number":30}는 통과."""
        p = _valid_metadata_provenance(
            original_reference={"year": 2025, "exam": "수능", "number": 30}
        )
        assert p.original_reference == {"year": 2025, "exam": "수능", "number": 30}

    def test_extended_structural_meta_passes(self) -> None:
        """(C-3 통과) unit/code/page/문항번호 등 구조 메타도 통과."""
        ref = {"unit": "미적분", "code": "CAL-INT-DEF", "page": 47, "문항번호": 30}
        p = _valid_metadata_provenance(original_reference=ref)
        assert p.original_reference == ref

    def test_none_original_reference_passes(self) -> None:
        """(C-3 통과) original_reference=None은 검사 대상 아님 → 통과."""
        p = _valid_metadata_provenance(original_reference=None)
        assert p.original_reference is None


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 — (C-통과) 합법 메타출처 레코드
# ──────────────────────────────────────────────────────────────────────
class TestLegalInvariantCPass:
    def test_pyeonggawon_whymath_variant_structure_passes(self) -> None:
        """(C-통과) 평가원 + WHYMATH_GENERATED + VARIANT_STRUCTURE + 구조 메타 → 통과."""
        p = ContentProvenance(
            original_source=SourceType.평가원,
            license=LicenseType.WHYMATH_GENERATED,
            generation_type=GenerationType.VARIANT_STRUCTURE,
            original_reference={"year": 2025, "exam": "수능", "number": 30},
        )
        assert p.original_source == SourceType.평가원
        assert p.license == LicenseType.WHYMATH_GENERATED
        assert p.generation_type == GenerationType.VARIANT_STRUCTURE

    def test_metadata_source_as_string_value_enforced(self) -> None:
        """use_enum_values 환경: original_source를 문자열 '평가원'로 줘도 (C) 작동.

        문자열 출처 + 비WHYMATH license → (C-1) 위반으로 거부되는지 확인.
        """
        with pytest.raises(ValidationError, match="위반\\(C-1\\)"):
            ContentProvenance(
                original_source="평가원",  # type: ignore[arg-type]
                license=LicenseType.PUBLIC_DOMAIN,
                generation_type=GenerationType.VARIANT_STRUCTURE,
            )


# ──────────────────────────────────────────────────────────────────────
# 비메타출처 — 규칙 비적용(통과)
# ──────────────────────────────────────────────────────────────────────
class TestNonMetadataSourceExempt:
    @pytest.mark.parametrize(
        "source",
        [
            SourceType.AIHub,
            SourceType.자체생성,
            SourceType.사용자자작,
            SourceType.교육청학평,
        ],
    )
    def test_non_metadata_source_any_license_passes(self, source: SourceType) -> None:
        """비메타출처는 (C) 규칙 비적용 — 임의 license/generation_type 허용."""
        p = ContentProvenance(
            original_source=source,
            license=LicenseType.AIHUB_OPEN,
            generation_type=GenerationType.VARIANT_NUMBER,
            original_reference={"any": "value", "answer": "본문키여도 무관(비메타)"},
        )
        assert p.original_source == source

    def test_none_source_exempt_from_c_rules(self) -> None:
        """original_source=None은 (C) 비적용 — 본문키 reference도 통과."""
        p = ContentProvenance(
            original_source=None,
            original_reference={"question": "비메타라 (C-3) 비적용"},
        )
        assert p.original_reference is not None

    def test_non_metadata_source_still_blocks_original(self) -> None:
        """비메타출처여도 (A) ORIGINAL은 전면 차단(전역 규칙)."""
        with pytest.raises(ValidationError, match="위반\\(A\\)"):
            ContentProvenance(
                original_source=SourceType.AIHub,
                generation_type=GenerationType.ORIGINAL,
            )


# ──────────────────────────────────────────────────────────────────────
# GenerationLog
# ──────────────────────────────────────────────────────────────────────
class TestGenerationLog:
    def test_empty_log_valid(self) -> None:
        """모든 필드 Optional — 빈 로그도 생성 가능(UUID 자동 생성)."""
        log = GenerationLog()
        assert isinstance(log.log_id, uuid.UUID)
        assert log.problem_id is None
        assert log.success is None

    def test_full_fields(self) -> None:
        """전 필드 채운 로그 — 값 보존."""
        pid = uuid.uuid4()
        prov = uuid.uuid4()
        tmpl = uuid.uuid4()
        log = GenerationLog(
            problem_id=pid,
            provenance_id=prov,
            model_name="claude-opus-4-7",
            prompt_template_id=tmpl,
            input_tokens=120,
            output_tokens=340,
            cost_usd=0.0123,
            latency_ms=1500,
            success=True,
            error_detail=None,
            generated_at=datetime.now(timezone.utc),
        )
        assert log.model_name == "claude-opus-4-7"
        assert log.input_tokens == 120
        assert log.cost_usd == 0.0123

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            GenerationLog(bogus="x")  # type: ignore[call-arg]

    def test_negative_tokens_rejected(self) -> None:
        """input_tokens는 ge=0 — 음수 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(input_tokens=-1)

    def test_negative_output_tokens_rejected(self) -> None:
        """output_tokens는 ge=0 — 음수 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(output_tokens=-1)

    def test_negative_cost_rejected(self) -> None:
        """cost_usd는 ge=0 — 음수 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(cost_usd=-0.01)

    def test_negative_latency_rejected(self) -> None:
        """latency_ms는 ge=0 — 음수 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(latency_ms=-5)

    def test_model_name_max_length(self) -> None:
        """model_name은 max_length=64 — 초과 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(model_name="x" * 65)
