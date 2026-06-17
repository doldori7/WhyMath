"""Schema v1.0 Assessment 모델 단위 테스트 — 생성·extra forbid·범위·required·enum 직렬화.

설계 정본: `schemas/v1.0/schema_v1.0.md` §8.1(assessment·concept_mastery_history).
2테이블 + 신규 ENUM 2종(AssessmentType·MentalPhase).

이 도메인에는 구조 cross-field 불변식(자기관계 등)이 없어 모델에 validator가 없다
(`concept.py`·`activity.py` 방침 — 없는 게 맞다). 따라서 불변식 분기 테스트 없이
required(ConceptMasteryHistory의 복합 PK 3종)·범위·enum·JSONB 배열 필드·extra forbid를
검증한다. 특히 AssessmentType.D_100예측이 하이픈 값("D-100예측")으로 직렬화되는지 확인한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from whymath_backend.schema.assessment import (
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.schema.enums import (
    AssessmentType,
    MentalPhase,
)


# ──────────────────────────────────────────────────────────────────────
# 신규 ENUM 2종 — 값 검증(§8.1 인라인 DDL 정본, 모두 한글)
# ──────────────────────────────────────────────────────────────────────
class TestAssessmentEnumValues:
    def test_assessment_type_values_korean(self) -> None:
        """AssessmentType — §8.1 한글 5종(L783-784)."""
        assert AssessmentType.초기진단.value == "초기진단"
        assert AssessmentType.실전모의고사.value == "실전모의고사"
        assert {e.value for e in AssessmentType} == {
            "초기진단",
            "주간진단",
            "단원진단",
            "실전모의고사",
            "D-100예측",
        }

    def test_assessment_type_d100_identifier_vs_value(self) -> None:
        """D_100예측 — 식별자만 언더스코어, 값은 하이픈 그대로(정본 'D-100예측')."""
        # 멤버명은 식별자 안전을 위해 언더스코어
        assert AssessmentType.D_100예측.value == "D-100예측"
        # str-Enum이므로 값 문자열과 동등 비교
        assert AssessmentType.D_100예측 == "D-100예측"
        # 값(하이픈)으로 역조회 가능
        assert AssessmentType("D-100예측") is AssessmentType.D_100예측

    def test_mental_phase_values(self) -> None:
        """MentalPhase — §8.1 6종(L810-811, 특성 #50 D-100 코칭)."""
        assert MentalPhase.D_100_PLUS.value == "D_100_PLUS"
        assert MentalPhase.평상시.value == "평상시"
        assert {e.value for e in MentalPhase} == {
            "D_100_PLUS",
            "D_100_50",
            "D_50_30",
            "D_30_7",
            "D_7_0",
            "평상시",
        }

    def test_str_enum_equality(self) -> None:
        """str-Enum — 문자열 값과 동등 비교(라우터·필터 안정성)."""
        assert AssessmentType.단원진단 == "단원진단"
        assert MentalPhase.D_50_30 == "D_50_30"


# ──────────────────────────────────────────────────────────────────────
# Assessment — 생성·기본값·roundtrip·범위·JSONB 배열·개인정보 필드
# ──────────────────────────────────────────────────────────────────────
class TestAssessment:
    def test_minimal_valid(self) -> None:
        """모든 필드 nullable — 빈 생성 시 assessment_id만 자동, JSONB 배열은 빈 리스트."""
        a = Assessment()
        assert isinstance(a.assessment_id, uuid.UUID)
        assert a.user_id is None
        assert a.assessment_type is None
        assert a.started_at is None
        assert a.mental_phase is None
        assert a.notes is None
        assert a.concept_diagnosis == []
        assert a.pattern_diagnosis == []
        assert a.weak_points == []
        assert a.strong_points == []
        assert a.recommended_path == []

    def test_full_fields_roundtrip(self) -> None:
        """전 17필드 채운 진단 — 값·JSONB 배열 보존 확인(특성 #86 합격 예측·#78 권장 경로)."""
        uid = uuid.uuid4()
        univ = uuid.uuid4()
        now = datetime.now(timezone.utc)
        a = Assessment(
            user_id=uid,
            assessment_type=AssessmentType.D_100예측,
            started_at=now,
            completed_at=now,
            estimated_grade=2.5,
            estimated_score=132,
            estimated_percentile=94.5,
            target_university_id=univ,
            admission_probability=0.72,
            concept_diagnosis=[{"concept_id": "CAL-INT-DEF", "mastery": 0.7, "trend": "+0.1"}],
            pattern_diagnosis=[{"pattern": "COMPOSITE_DIFFERENTIABILITY", "mastery": 0.6}],
            weak_points=[{"concept": "수열의 극한", "mastery": 0.3}],
            strong_points=[{"concept": "미분계수", "mastery": 0.9}],
            recommended_path=[{"week": 1, "concept": "정적분", "estimated_hours": 5}],
            mental_phase=MentalPhase.D_100_50,
            notes="실전 감각 양호, 약점 단원 집중 필요",
        )
        assert a.user_id == uid
        assert a.assessment_type == AssessmentType.D_100예측
        assert a.estimated_grade == pytest.approx(2.5)
        assert a.estimated_score == 132
        assert a.estimated_percentile == pytest.approx(94.5)
        assert a.target_university_id == univ
        assert a.admission_probability == pytest.approx(0.72)
        assert a.concept_diagnosis[0]["mastery"] == pytest.approx(0.7)
        assert a.weak_points[0]["concept"] == "수열의 극한"
        assert a.recommended_path[0]["estimated_hours"] == 5
        assert a.mental_phase == MentalPhase.D_100_50
        assert a.notes == "실전 감각 양호, 약점 단원 집중 필요"

    def test_enum_value_serialization_korean(self) -> None:
        """use_enum_values → assessment_type/mental_phase 값 보존."""
        a = Assessment(
            assessment_type=AssessmentType.단원진단,
            mental_phase=MentalPhase.평상시,
        )
        dumped = a.model_dump()
        assert dumped["assessment_type"] == "단원진단"
        assert dumped["mental_phase"] == "평상시"

    def test_assessment_type_d100_serialization_hyphen(self) -> None:
        """⚠️ use_enum_values → AssessmentType.D_100예측은 하이픈 값 'D-100예측'로 직렬화."""
        a = Assessment(assessment_type=AssessmentType.D_100예측)
        assert a.model_dump()["assessment_type"] == "D-100예측"

    def test_admission_probability_too_high_rejected(self) -> None:
        """admission_probability는 0-1(DDL 주석) — 1 초과 거부."""
        with pytest.raises(ValidationError):
            Assessment(admission_probability=1.5)

    def test_admission_probability_negative_rejected(self) -> None:
        """admission_probability는 ge=0 — 음수 거부."""
        with pytest.raises(ValidationError):
            Assessment(admission_probability=-0.1)

    def test_estimated_grade_too_high_rejected(self) -> None:
        """estimated_grade는 1-9(등급 척도) — 9 초과 거부."""
        with pytest.raises(ValidationError):
            Assessment(estimated_grade=9.5)

    def test_estimated_grade_too_low_rejected(self) -> None:
        """estimated_grade는 1-9(등급 척도) — 1 미만 거부."""
        with pytest.raises(ValidationError):
            Assessment(estimated_grade=0.5)

    def test_estimated_percentile_too_high_rejected(self) -> None:
        """estimated_percentile은 0-100(백분위) — 100 초과 거부."""
        with pytest.raises(ValidationError):
            Assessment(estimated_percentile=100.1)

    def test_estimated_score_negative_rejected(self) -> None:
        """estimated_score는 ge=0(점수) — 음수 거부."""
        with pytest.raises(ValidationError):
            Assessment(estimated_score=-1)

    def test_invalid_assessment_type_rejected(self) -> None:
        """assessment_type에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            Assessment(assessment_type="존재하지않는진단")  # type: ignore[arg-type]

    def test_invalid_mental_phase_rejected(self) -> None:
        """mental_phase에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            Assessment(mental_phase="D_200_PLUS")  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            Assessment(bogus="x")  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────
# ConceptMasteryHistory — required(복합 PK 3종)·범위·hypertable
# ──────────────────────────────────────────────────────────────────────
class TestConceptMasteryHistory:
    def test_valid_with_required_pk(self) -> None:
        """복합 PK 3종(user_id·concept_id·measured_at) 필수 — 그것만으로 생성, 측정값 None."""
        uid = uuid.uuid4()
        cid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        h = ConceptMasteryHistory(user_id=uid, concept_id=cid, measured_at=now)
        assert h.user_id == uid
        assert h.concept_id == cid
        assert h.measured_at == now
        assert h.mastery is None
        assert h.confidence is None
        assert h.sample_size is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채운 숙련도 측정 — 값 보존 확인(특성 #16 학습 곡선)."""
        uid = uuid.uuid4()
        cid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        h = ConceptMasteryHistory(
            user_id=uid,
            concept_id=cid,
            measured_at=now,
            mastery=0.65,
            confidence=0.8,
            sample_size=12,
        )
        assert h.mastery == pytest.approx(0.65)
        assert h.confidence == pytest.approx(0.8)
        assert h.sample_size == 12

    def test_user_id_required(self) -> None:
        """user_id는 복합 PK 구성요소 → required — 누락 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(  # type: ignore[call-arg]
                concept_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
            )

    def test_concept_id_required(self) -> None:
        """concept_id는 복합 PK 구성요소 → required — 누락 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(  # type: ignore[call-arg]
                user_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
            )

    def test_measured_at_required(self) -> None:
        """measured_at은 복합 PK 구성요소·hypertable 분할 키 → required — 누락 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(  # type: ignore[call-arg]
                user_id=uuid.uuid4(),
                concept_id=uuid.uuid4(),
            )

    def test_mastery_too_high_rejected(self) -> None:
        """mastery는 0-1(DDL 주석) — 1 초과 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(
                user_id=uuid.uuid4(),
                concept_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
                mastery=1.5,
            )

    def test_confidence_negative_rejected(self) -> None:
        """confidence는 0-1(정규화 신뢰도) — 음수 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(
                user_id=uuid.uuid4(),
                concept_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
                confidence=-0.1,
            )

    def test_sample_size_negative_rejected(self) -> None:
        """sample_size는 ge=0(문제 수) — 음수 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(
                user_id=uuid.uuid4(),
                concept_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
                sample_size=-1,
            )

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            ConceptMasteryHistory(  # type: ignore[call-arg]
                user_id=uuid.uuid4(),
                concept_id=uuid.uuid4(),
                measured_at=datetime.now(timezone.utc),
                bogus="x",
            )
