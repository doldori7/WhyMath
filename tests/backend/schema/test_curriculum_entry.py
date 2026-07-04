"""Schema v1.1 CurriculumEntry 모델 단위 테스트 — 생성·extra forbid·범위·required·enum·
validator 2종 분기.

설계 정본: `schemas/v1.1/curriculum_entry.schema.yaml`(31필드·validation_invariants·license).
v1.0 도메인 밖의 v1.1 이식 자산(다국 커리큘럼 매트릭스 셀). 신규 ENUM 2종(RequiredDepth 4종·
CurriculumLicense 5종, 하이픈 값)을 함께 검증한다.

이 모델은 *모델 내부로 강제 가능한* invariant만 validator 2개로 구현한다(cross-dataset
invariant — concept_id 실재·NCIC 코드 실재·복합키 유일성·Phase1 범위 가드 — 는 파이프라인
책임이라 모델·테스트 대상 아님). 따라서 검증 대상은: ① 9개 required 누락 거부, ② confidence
범위([0,1], Field), ③ validator A(is_present=true → source_url 비어있지 않음), ④ validator B
(country_code='IMO' → confidence ≤ 0.7), ⑤ extra forbid, ⑥ use_enum_values(license_id가
하이픈 값 'KR-NCIC'로 직렬화), ⑦ 전 필드 roundtrip(KR·US·IMO 셀), ⑧ subject 축(S1 —
default '수학'·개방 str·비공백 min_length=1·직렬화 포함).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from whymath_backend.schema.curriculum_entry import CurriculumEntry
from whymath_backend.schema.enums import (
    CurriculumLicense,
    RequiredDepth,
)

# ──────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — required 9종을 채운 최소 유효 인자(테스트마다 override)
# ──────────────────────────────────────────────────────────────────────
_NOW = datetime(2024, 3, 1, 9, 0, 0, tzinfo=timezone.utc)


def _minimal_kwargs(**overrides: object) -> dict[str, object]:
    """required 9종(식별 3 + source_name + license_id + is_present + confidence +
    created_at + updated_at)을 채운 기본 인자. is_present=true 기본이므로 source_url도 채운다.
    """
    base: dict[str, object] = {
        "concept_id": "CAL-INT-DEF-FUNDAMENTAL",
        "country_code": "KR",
        "entry_id": "CAL-INT-DEF-FUNDAMENTAL::KR",
        "source_name": "2022 개정 교육과정 — 수학과 교육과정",
        "license_id": CurriculumLicense.KR_NCIC,
        "is_present": True,
        "confidence": 0.95,
        "source_url": "https://ncic.re.kr/2022/math",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# 신규 ENUM 2종 — 값 검증(YAML enum 정본)
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEnumValues:
    def test_required_depth_values(self) -> None:
        """RequiredDepth — YAML required_depth.enum 영어 4종."""
        assert RequiredDepth.awareness.value == "awareness"
        assert RequiredDepth.procedural.value == "procedural"
        assert RequiredDepth.conceptual.value == "conceptual"
        assert RequiredDepth.mastery.value == "mastery"
        assert {e.value for e in RequiredDepth} == {
            "awareness",
            "procedural",
            "conceptual",
            "mastery",
        }

    def test_curriculum_license_values_hyphen(self) -> None:
        """CurriculumLicense — YAML license_id.enum 5종, 값은 하이픈 그대로."""
        assert CurriculumLicense.KR_NCIC.value == "KR-NCIC"
        assert CurriculumLicense.US_CCSS.value == "US-CCSS"
        assert CurriculumLicense.INT_IMO.value == "INT-IMO"
        assert CurriculumLicense.JP_MEXT.value == "JP-MEXT"
        assert CurriculumLicense.GB_NC.value == "GB-NC"
        assert {e.value for e in CurriculumLicense} == {
            "KR-NCIC",
            "US-CCSS",
            "INT-IMO",
            "JP-MEXT",
            "GB-NC",
        }

    def test_curriculum_license_identifier_vs_value(self) -> None:
        """KR_NCIC — 식별자만 언더스코어, 값은 하이픈 그대로('KR-NCIC', slice6 D_100예측 선례)."""
        # 멤버명은 식별자 안전을 위해 언더스코어
        assert CurriculumLicense.KR_NCIC.value == "KR-NCIC"
        # str-Enum이므로 값 문자열과 동등 비교
        assert CurriculumLicense.KR_NCIC == "KR-NCIC"
        # 값(하이픈)으로 역조회 가능
        assert CurriculumLicense("KR-NCIC") is CurriculumLicense.KR_NCIC

    def test_str_enum_equality(self) -> None:
        """str-Enum — 문자열 값과 동등 비교(라우터·필터 안정성)."""
        assert RequiredDepth.conceptual == "conceptual"
        assert CurriculumLicense.US_CCSS == "US-CCSS"


# ──────────────────────────────────────────────────────────────────────
# CurriculumEntry — happy-path roundtrip (KR·US·IMO 셀)
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEntryHappyPath:
    def test_minimal_required_only(self) -> None:
        """required 9종만으로 생성 — 나머지 21필드는 nullable/기본값(list는 빈 리스트)."""
        e = CurriculumEntry(**_minimal_kwargs())  # type: ignore[arg-type]
        # 식별 복합키 + 표면키
        assert e.concept_id == "CAL-INT-DEF-FUNDAMENTAL"
        assert e.country_code == "KR"
        assert e.entry_id == "CAL-INT-DEF-FUNDAMENTAL::KR"
        # required 상태
        assert e.is_present is True
        assert e.confidence == pytest.approx(0.95)
        assert e.created_at == _NOW
        assert e.updated_at == _NOW
        # nullable 기본 None
        assert e.source_code is None
        assert e.source_document is None
        assert e.introduced_grade is None
        assert e.grade_band is None
        assert e.effective_from is None
        assert e.required_depth is None
        assert e.is_assessed is None
        assert e.verified_by is None
        # list 기본 빈 리스트(4종)
        assert e.notation_variants == []
        assert e.prerequisite_concept_ids == []
        assert e.followup_concept_ids == []
        assert e.national_standard_codes == []
        assert e.textbook_unit_refs == []

    def test_full_fields_roundtrip_kr(self) -> None:
        """KR 셀 전 30필드 채움 — 값·list·date·enum 보존(한국 열 = NCIC 성취기준)."""
        e = CurriculumEntry(
            concept_id="CAL-INT-DEF-FUNDAMENTAL",
            country_code="KR",
            entry_id="CAL-INT-DEF-FUNDAMENTAL::KR",
            source_name="2022 개정 교육과정 — 수학과 교육과정",
            source_code="교육부 고시 제2022-33호 [별책 8]",
            source_url="https://ncic.re.kr/2022/math",
            source_document="2022_math_curriculum.hwp",
            license_id=CurriculumLicense.KR_NCIC,
            introduced_grade=12,
            grade_band="고3",
            effective_from=date(2025, 3, 1),
            curriculum_revision="2022 개정",
            introduced_context="미적분 — 정적분의 활용 단원",
            domain_label="미적분",
            sub_domain_label="적분법",
            required_depth=RequiredDepth.mastery,
            cognitive_level="적용",
            is_assessed=True,
            assessment_format="지필·서술형",
            notation_local="∫",
            terminology_local="미적분학의 기본정리",
            notation_variants=["∫f(x)dx", "F(b)-F(a)"],
            prerequisite_concept_ids=["CAL-DIFF-BASIC"],
            followup_concept_ids=["CAL-INT-APPLICATION"],
            national_standard_codes=["[12미적II-03-05]"],
            textbook_unit_refs=["UNIT-CAL-9-3"],
            is_present=True,
            confidence=0.97,
            verified_by="reviewer-kim",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert e.source_code == "교육부 고시 제2022-33호 [별책 8]"
        assert e.source_document == "2022_math_curriculum.hwp"
        assert e.introduced_grade == 12
        assert e.grade_band == "고3"
        assert e.effective_from == date(2025, 3, 1)
        assert e.curriculum_revision == "2022 개정"
        assert e.introduced_context == "미적분 — 정적분의 활용 단원"
        assert e.domain_label == "미적분"
        assert e.sub_domain_label == "적분법"
        assert e.required_depth == RequiredDepth.mastery
        assert e.cognitive_level == "적용"
        assert e.is_assessed is True
        assert e.assessment_format == "지필·서술형"
        assert e.notation_local == "∫"
        assert e.terminology_local == "미적분학의 기본정리"
        assert e.notation_variants == ["∫f(x)dx", "F(b)-F(a)"]
        assert e.prerequisite_concept_ids == ["CAL-DIFF-BASIC"]
        assert e.followup_concept_ids == ["CAL-INT-APPLICATION"]
        assert e.national_standard_codes == ["[12미적II-03-05]"]
        assert e.textbook_unit_refs == ["UNIT-CAL-9-3"]
        assert e.verified_by == "reviewer-kim"

    def test_us_cell(self) -> None:
        """US 셀 — country_code='US', license_id=US-CCSS, 표준 코드는 CCSS."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                country_code="US",
                entry_id="CAL-INT-DEF-FUNDAMENTAL::US",
                license_id=CurriculumLicense.US_CCSS,
                source_name="Common Core State Standards — Mathematics",
                source_url="https://www.thecorestandards.org/Math/",
                national_standard_codes=["HSF-IF.C.7"],
                confidence=0.9,
            )  # type: ignore[arg-type]
        )
        assert e.country_code == "US"
        assert e.license_id == CurriculumLicense.US_CCSS
        assert e.national_standard_codes == ["HSF-IF.C.7"]

    def test_imo_cell_within_confidence_cap(self) -> None:
        """IMO 셀 — country_code='IMO', license_id=INT-IMO, confidence ≤ 0.7(상한 내)."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                country_code="IMO",
                entry_id="CAL-INT-DEF-FUNDAMENTAL::IMO",
                license_id=CurriculumLicense.INT_IMO,
                source_name="IMO Syllabus (WhyMath 자체 정리)",
                source_url="https://www.imo-official.org/",
                confidence=0.7,
            )  # type: ignore[arg-type]
        )
        assert e.country_code == "IMO"
        assert e.confidence == pytest.approx(0.7)

    def test_not_present_cell_allows_empty_source_url(self) -> None:
        """is_present=false 셀 — 그 나라에 개념 없음. source_url 비어도(None) 정당."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                country_code="US",
                entry_id="KR-ONLY-CONCEPT::US",
                license_id=CurriculumLicense.US_CCSS,
                is_present=False,
                source_url=None,
                confidence=0.6,
            )  # type: ignore[arg-type]
        )
        assert e.is_present is False
        assert e.source_url is None


# ──────────────────────────────────────────────────────────────────────
# use_enum_values — license_id가 하이픈 값으로 직렬화
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEntrySerialization:
    def test_license_id_serializes_hyphen(self) -> None:
        """⚠️ use_enum_values → license_id는 하이픈 값 'KR-NCIC'로 직렬화."""
        e = CurriculumEntry(**_minimal_kwargs())  # type: ignore[arg-type]
        assert e.model_dump()["license_id"] == "KR-NCIC"

    def test_required_depth_serializes_value(self) -> None:
        """use_enum_values → required_depth는 영어 값으로 직렬화."""
        e = CurriculumEntry(
            **_minimal_kwargs(required_depth=RequiredDepth.conceptual)  # type: ignore[arg-type]
        )
        assert e.model_dump()["required_depth"] == "conceptual"

    def test_str_strip_whitespace(self) -> None:
        """str_strip_whitespace → 문자열 필드 양끝 공백 제거(ConfigDict 공통)."""
        e = CurriculumEntry(
            **_minimal_kwargs(source_name="  2022 개정 교육과정  ")  # type: ignore[arg-type]
        )
        assert e.source_name == "2022 개정 교육과정"


# ──────────────────────────────────────────────────────────────────────
# required 9종 누락 거부
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEntryRequired:
    @pytest.mark.parametrize(
        "missing",
        [
            "concept_id",
            "country_code",
            "entry_id",
            "source_name",
            "license_id",
            "is_present",
            "confidence",
            "created_at",
            "updated_at",
        ],
    )
    def test_required_field_missing_rejected(self, missing: str) -> None:
        """required 9종(복합키 3 + source_name + license_id + is_present + confidence +
        created_at + updated_at) 각각 누락 시 거부."""
        kwargs = _minimal_kwargs()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            CurriculumEntry(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# confidence 범위([0,1], Field ge/le — validator 아님)
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEntryConfidenceRange:
    def test_confidence_above_one_rejected(self) -> None:
        """confidence는 [0.0,1.0] — 1 초과 거부(Field le=1.0)."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(confidence=1.5))  # type: ignore[arg-type]

    def test_confidence_negative_rejected(self) -> None:
        """confidence는 [0.0,1.0] — 음수 거부(Field ge=0.0)."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(confidence=-0.1))  # type: ignore[arg-type]

    def test_confidence_boundaries_ok(self) -> None:
        """confidence 경계값 0.0·1.0은 허용(KR 셀이라 IMO 상한 무관)."""
        lo = CurriculumEntry(**_minimal_kwargs(confidence=0.0))  # type: ignore[arg-type]
        hi = CurriculumEntry(**_minimal_kwargs(confidence=1.0))  # type: ignore[arg-type]
        assert lo.confidence == pytest.approx(0.0)
        assert hi.confidence == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────
# validator A — is_present=true이면 source_url 비어있지 않음
# ──────────────────────────────────────────────────────────────────────
class TestPresentRequiresSourceUrl:
    def test_present_with_none_source_url_rejected(self) -> None:
        """is_present=true + source_url=None → 거부."""
        with pytest.raises(ValidationError, match="source_url"):
            CurriculumEntry(
                **_minimal_kwargs(is_present=True, source_url=None)  # type: ignore[arg-type]
            )

    def test_present_with_empty_source_url_rejected(self) -> None:
        """is_present=true + source_url='' → 거부(빈 문자열도 금지)."""
        with pytest.raises(ValidationError, match="source_url"):
            CurriculumEntry(
                **_minimal_kwargs(is_present=True, source_url="")  # type: ignore[arg-type]
            )

    def test_present_with_whitespace_source_url_rejected(self) -> None:
        """is_present=true + source_url='   ' → 거부(공백만도 금지; strip 후 빈 값)."""
        # str_strip_whitespace가 양끝 공백을 제거하므로 '   '는 ''가 되어 거부된다.
        with pytest.raises(ValidationError, match="source_url"):
            CurriculumEntry(
                **_minimal_kwargs(is_present=True, source_url="   ")  # type: ignore[arg-type]
            )

    def test_present_with_source_url_ok(self) -> None:
        """is_present=true + source_url 있음 → 통과."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                is_present=True, source_url="https://ncic.re.kr/"
            )  # type: ignore[arg-type]
        )
        assert e.source_url == "https://ncic.re.kr/"

    def test_not_present_with_none_source_url_ok(self) -> None:
        """is_present=false + source_url=None → 통과(없음 주장에는 출처 불필요)."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                country_code="US",
                license_id=CurriculumLicense.US_CCSS,
                is_present=False,
                source_url=None,
                confidence=0.5,
            )  # type: ignore[arg-type]
        )
        assert e.is_present is False
        assert e.source_url is None


# ──────────────────────────────────────────────────────────────────────
# validator B — country_code='IMO'이면 confidence ≤ 0.7
# ──────────────────────────────────────────────────────────────────────
class TestImoConfidenceCap:
    def test_imo_confidence_above_cap_rejected(self) -> None:
        """country_code='IMO' + confidence=0.8 → 거부(상한 0.7 초과)."""
        with pytest.raises(ValidationError, match="IMO"):
            CurriculumEntry(
                **_minimal_kwargs(
                    country_code="IMO",
                    license_id=CurriculumLicense.INT_IMO,
                    source_url="https://www.imo-official.org/",
                    confidence=0.8,
                )  # type: ignore[arg-type]
            )

    def test_imo_confidence_at_cap_ok(self) -> None:
        """country_code='IMO' + confidence=0.7 → 통과(경계값 허용)."""
        e = CurriculumEntry(
            **_minimal_kwargs(
                country_code="IMO",
                license_id=CurriculumLicense.INT_IMO,
                source_url="https://www.imo-official.org/",
                confidence=0.7,
            )  # type: ignore[arg-type]
        )
        assert e.confidence == pytest.approx(0.7)

    def test_kr_confidence_above_cap_ok(self) -> None:
        """country_code='KR' + confidence=0.9 → 통과(IMO 상한은 IMO 셀에만 적용)."""
        e = CurriculumEntry(**_minimal_kwargs(confidence=0.9))  # type: ignore[arg-type]
        assert e.confidence == pytest.approx(0.9)


# ──────────────────────────────────────────────────────────────────────
# subject 축 (과목 확장 S1) — default '수학'·개방 str·비공백·직렬화 포함
# ──────────────────────────────────────────────────────────────────────
class TestSubjectAxis:
    def test_subject_defaults_to_math(self) -> None:
        """subject 미지정 → default '수학'(기존 호출부·payload 무파손 — S1)."""
        e = CurriculumEntry(**_minimal_kwargs())  # type: ignore[arg-type]
        assert e.subject == "수학"

    def test_subject_open_str_accepts_physics(self) -> None:
        """subject는 개방 str(enum 아님) — '물리' 셀 표현 가능(같은 개념·같은 나라·다른 교과).

        Phase 1 산출물 '수학' 외 금지는 *파이프라인* 범위 가드이지 모델 강제가 아니다
        (country_code Phase 1 KR/US/IMO 가드와 동형 — 모듈 docstring cross-dataset 메모).
        """
        e = CurriculumEntry(**_minimal_kwargs(subject="물리"))  # type: ignore[arg-type]
        assert e.subject == "물리"

    def test_subject_empty_rejected(self) -> None:
        """subject='' → 거부(min_length=1 — 비공백 invariant는 모델 강제)."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(subject=""))  # type: ignore[arg-type]

    def test_subject_whitespace_only_rejected(self) -> None:
        """subject='   ' → 거부(str_strip_whitespace로 ''가 된 뒤 min_length=1)."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(subject="   "))  # type: ignore[arg-type]

    def test_subject_included_in_model_dump(self) -> None:
        """model_dump에 subject 포함(직렬화 — ORM from_schema 경유 영속까지 흐르는 값)."""
        e = CurriculumEntry(**_minimal_kwargs())  # type: ignore[arg-type]
        assert e.model_dump()["subject"] == "수학"


# ──────────────────────────────────────────────────────────────────────
# enum 거부·extra forbid
# ──────────────────────────────────────────────────────────────────────
class TestCurriculumEntryValidation:
    def test_invalid_license_id_rejected(self) -> None:
        """license_id에 정의되지 않은 값 거부."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(license_id="ZZ-NONE"))  # type: ignore[arg-type]

    def test_invalid_required_depth_rejected(self) -> None:
        """required_depth에 정의되지 않은 enum 값 거부."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(required_depth="expert"))  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            CurriculumEntry(**_minimal_kwargs(bogus="x"))  # type: ignore[arg-type]
