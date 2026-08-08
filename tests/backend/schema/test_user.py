"""Schema v1.0 User 모델 단위 테스트 — 생성·extra forbid·범위·required·enum 직렬화.

설계 정본: `schemas/v1.0/schema_v1.0.md` §5.1(user_profile·user_track_history·
user_persona_history)·§5.2(user_state_snapshot). 4테이블 + 신규 ENUM 7종(SchoolType·
TrackType·MajorCategory·Device·NoteApp·SubscriptionTier·Accessibility).

이 도메인에는 구조 cross-field 불변식(자기관계 등)이 없어 모델에 validator가 없다
(`concept.py` 방침 — 없는 게 맞다). 따라서 불변식 분기 테스트 없이 required·범위·enum·
타입(date)·extra forbid를 검증한다. gender/school_region이 str로 자유롭게 들어가는지도 확인.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import (
    Accessibility,
    Device,
    MajorCategory,
    NoteApp,
    Persona,
    Role,
    SchoolType,
    SubscriptionTier,
    TrackType,
)
from whymath_backend.schema.user import (
    UserPersonaHistory,
    UserProfile,
    UserStateSnapshot,
    UserTrackHistory,
)


# ──────────────────────────────────────────────────────────────────────
# 신규 ENUM 7종 — 값 검증(§14.3 school_type_enum·§5.1 인라인 DDL 정본)
# ──────────────────────────────────────────────────────────────────────
class TestUserEnumValues:
    def test_school_type_values_korean(self) -> None:
        """SchoolType — §14.3 한글 12종(완전한 CREATE TYPE)."""
        assert SchoolType.일반고.value == "일반고"
        assert SchoolType.자사고_전국.value == "자사고_전국"
        assert SchoolType.검정고시.value == "검정고시"
        assert {e.value for e in SchoolType} == {
            "일반고",
            "자사고_전국",
            "자사고_광역",
            "외고",
            "국제고",
            "영재고",
            "과학고",
            "특성화고",
            "대안학교_인가",
            "대안학교_비인가",
            "홈스쿨링",
            "검정고시",
        }

    def test_track_type_values(self) -> None:
        """TrackType — 한글 7종 + MMI(영어)."""
        assert TrackType.MMI.value == "MMI"
        assert {e.value for e in TrackType} == {
            "정시",
            "수시학종",
            "수시교과",
            "수시논술",
            "MMI",
            "특기자",
            "농어촌",
            "특례",
        }

    def test_major_category_values_korean(self) -> None:
        """MajorCategory — 한글 8종."""
        assert {e.value for e in MajorCategory} == {
            "의대",
            "약대",
            "치대",
            "한의대",
            "이공계",
            "인문계",
            "경상계",
            "예체능",
        }

    def test_device_values(self) -> None:
        """Device — 아이패드/iPhone/안드로이드폰/PC."""
        assert Device.iPhone.value == "iPhone"
        assert Device.PC.value == "PC"
        assert {e.value for e in Device} == {"아이패드", "iPhone", "안드로이드폰", "PC"}

    def test_note_app_values_korean(self) -> None:
        """NoteApp — 굿노트/노타빌리티/플렉슬/없음."""
        assert {e.value for e in NoteApp} == {"굿노트", "노타빌리티", "플렉슬", "없음"}

    def test_subscription_tier_values_english(self) -> None:
        """SubscriptionTier — free/basic/premium."""
        assert {e.value for e in SubscriptionTier} == {"free", "basic", "premium"}

    def test_accessibility_values_korean(self) -> None:
        """Accessibility — 시각약자/색약/큰글씨/음성안내/시간연장."""
        assert {e.value for e in Accessibility} == {
            "시각약자",
            "색약",
            "큰글씨",
            "음성안내",
            "시간연장",
        }

    def test_str_enum_equality(self) -> None:
        """str-Enum — 문자열 값과 동등 비교(라우터·필터 안정성)."""
        assert SchoolType.일반고 == "일반고"
        assert SubscriptionTier.premium == "premium"
        assert TrackType.정시 == "정시"


# ──────────────────────────────────────────────────────────────────────
# UserProfile — 생성·기본값·roundtrip·required
# ──────────────────────────────────────────────────────────────────────
class TestUserProfileCreation:
    def test_minimal_profile_valid(self) -> None:
        """필수(persona_primary)만으로 생성 — 나머지 기본값."""
        u = UserProfile(persona_primary=Persona.A_일반고고3)
        assert isinstance(u.user_id, uuid.UUID)
        assert u.persona_primary == Persona.A_일반고고3
        assert u.email_hash is None
        assert u.nickname is None
        assert u.gender is None
        assert u.school_type is None
        assert u.school_region is None
        assert u.track_type == []
        assert u.target_universities == []
        assert u.inkang_provider == []
        assert u.accessibility_needs == []
        # BOOLEAN DEFAULT
        assert u.diagnostic_completed is False
        assert u.is_active is True
        assert u.is_deleted is False
        # role(SEC-07 D1) — 기본 STUDENT, validate_default=True라 미지정이어도 문자열로 검증됨.
        assert u.role == "student"
        # 기본값 없는 BOOLEAN → None
        assert u.has_apple_pencil is None
        assert u.is_minor is None
        assert u.uses_inkang is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드를 채운 합법 인스턴스 — 값 보존 확인."""
        now = datetime.now(timezone.utc)
        u = UserProfile(
            email_hash="a" * 64,
            nickname="민준",
            birth_year=2007,
            gender="남",
            school_type=SchoolType.일반고,
            school_region="강남",
            grade=12,
            track_type=[TrackType.정시, TrackType.수시학종],
            target_universities=[{"univ": "서울대", "major": "의예", "priority": 1}],
            target_major_category=MajorCategory.의대,
            target_grade=1,
            target_score=140,
            target_exam_date=date(2026, 11, 19),
            persona_primary=Persona.A_일반고고3,
            persona_secondary=Persona.B_자사고N수,
            persona_confidence=0.87,
            primary_device=Device.아이패드,
            has_apple_pencil=True,
            note_app=NoteApp.굿노트,
            current_grade_estimate=2.5,
            current_grade_updated_at=now,
            diagnostic_completed=True,
            diagnostic_completed_at=now,
            uses_inkang=True,
            inkang_provider=["메가스터디", "이투스"],
            uses_offline_academy=False,
            monthly_education_spend=500000,
            is_minor=True,
            parent_consent_at=now,
            parent_email_hash="b" * 64,
            accessibility_needs=[Accessibility.색약, Accessibility.시간연장],
            created_at=now,
            last_active_at=now,
            is_active=True,
            is_deleted=False,
        )
        assert u.track_type == [TrackType.정시, TrackType.수시학종]
        assert u.target_universities[0]["univ"] == "서울대"
        assert u.target_exam_date == date(2026, 11, 19)
        assert u.persona_secondary == Persona.B_자사고N수
        assert u.persona_confidence == pytest.approx(0.87)
        assert u.inkang_provider == ["메가스터디", "이투스"]
        assert u.accessibility_needs == [Accessibility.색약, Accessibility.시간연장]

    def test_persona_primary_required(self) -> None:
        """persona_primary는 NOT NULL → 유일한 required — 누락 거부."""
        with pytest.raises(ValidationError):
            UserProfile()  # type: ignore[call-arg]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, bogus="x")  # type: ignore[call-arg]

    def test_role_content_admin_accepted(self) -> None:
        """role=CONTENT_ADMIN 명시 지정 — validate_default=True와 무관하게(지정값이므로) 문자열
        보존(use_enum_values=True)."""
        u = UserProfile(persona_primary=Persona.A_일반고고3, role=Role.CONTENT_ADMIN)
        assert u.role == "content_admin"

    def test_role_invalid_value_rejected(self) -> None:
        """v0 2값 밖 문자열(예: 'teacher')은 거부 — 7단 서열 재도입을 스키마 층에서도 차단."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, role="teacher")  # type: ignore[arg-type]

    def test_enum_value_serialization_korean(self) -> None:
        """use_enum_values → 한글 enum 값 보존(school_type='일반고' 등)."""
        u = UserProfile(
            persona_primary=Persona.A_일반고고3,
            school_type=SchoolType.일반고,
            primary_device=Device.아이패드,
            note_app=NoteApp.굿노트,
            target_major_category=MajorCategory.이공계,
        )
        dumped = u.model_dump()
        assert dumped["persona_primary"] == "A_일반고고3"
        assert dumped["school_type"] == "일반고"
        assert dumped["primary_device"] == "아이패드"
        assert dumped["note_app"] == "굿노트"
        assert dumped["target_major_category"] == "이공계"

    def test_list_enum_serialization(self) -> None:
        """use_enum_values → track_type·accessibility_needs 배열이 문자열 값 배열로 직렬화."""
        u = UserProfile(
            persona_primary=Persona.A_일반고고3,
            track_type=[TrackType.수시논술, TrackType.MMI],
            accessibility_needs=[Accessibility.시각약자, Accessibility.음성안내],
        )
        dumped = u.model_dump()
        assert dumped["track_type"] == ["수시논술", "MMI"]
        assert dumped["accessibility_needs"] == ["시각약자", "음성안내"]

    def test_gender_and_region_free_string(self) -> None:
        """gender·school_region은 str(enum 아님) — 자유 문자열 허용."""
        u = UserProfile(
            persona_primary=Persona.A_일반고고3,
            gender="응답거부",
            school_region="SEOUL-GANGNAM-제3교육지원청",
        )
        assert u.gender == "응답거부"
        assert u.school_region == "SEOUL-GANGNAM-제3교육지원청"

    def test_target_exam_date_is_date(self) -> None:
        """target_exam_date는 date 타입(TIMESTAMPTZ 아님) — ISO 문자열도 date로 파싱."""
        u = UserProfile(
            persona_primary=Persona.A_일반고고3,
            target_exam_date="2026-11-19",  # type: ignore[arg-type]
        )
        assert u.target_exam_date == date(2026, 11, 19)
        assert isinstance(u.target_exam_date, date)


# ──────────────────────────────────────────────────────────────────────
# UserProfile — 범위·길이 제약
# ──────────────────────────────────────────────────────────────────────
class TestUserProfileRanges:
    def test_target_grade_too_high_rejected(self) -> None:
        """target_grade는 1-9 — 10 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, target_grade=10)

    def test_target_grade_too_low_rejected(self) -> None:
        """target_grade는 1-9 — 0 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, target_grade=0)

    def test_persona_confidence_too_high_rejected(self) -> None:
        """persona_confidence는 0-1 — 1 초과 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, persona_confidence=1.5)

    def test_grade_out_of_range_rejected(self) -> None:
        """grade는 10-14(DDL 주석) — 9 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, grade=9)

    def test_current_grade_estimate_out_of_range_rejected(self) -> None:
        """current_grade_estimate는 1.0-9.0 — 9.5 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, current_grade_estimate=9.5)

    def test_monthly_education_spend_negative_rejected(self) -> None:
        """monthly_education_spend는 ge=0(금액) — 음수 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, monthly_education_spend=-1)

    def test_birth_year_out_of_range_rejected(self) -> None:
        """birth_year는 1900-2100(보수 설정) — 1800 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, birth_year=1800)

    def test_email_hash_max_length(self) -> None:
        """email_hash는 max_length=64 — 초과 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, email_hash="a" * 65)

    def test_nickname_max_length(self) -> None:
        """nickname은 max_length=50 — 초과 거부."""
        with pytest.raises(ValidationError):
            UserProfile(persona_primary=Persona.A_일반고고3, nickname="가" * 51)

    def test_invalid_track_type_rejected(self) -> None:
        """track_type 배열에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            UserProfile(
                persona_primary=Persona.A_일반고고3,
                track_type=["존재하지않는트랙"],  # type: ignore[list-item]
            )

    def test_invalid_accessibility_rejected(self) -> None:
        """accessibility_needs 배열에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            UserProfile(
                persona_primary=Persona.A_일반고고3,
                accessibility_needs=["존재하지않는접근성"],  # type: ignore[list-item]
            )


# ──────────────────────────────────────────────────────────────────────
# UserTrackHistory — 생성·기본값(PK만 자동)
# ──────────────────────────────────────────────────────────────────────
class TestUserTrackHistory:
    def test_minimal_valid(self) -> None:
        """모든 필드 nullable — 빈 생성 시 history_id만 자동 채워짐."""
        h = UserTrackHistory()
        assert isinstance(h.history_id, uuid.UUID)
        assert h.user_id is None
        assert h.changed_at is None
        assert h.track_before is None
        assert h.track_after is None
        assert h.reason is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채운 이력 — JSONB 스냅샷 값 보존."""
        uid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        h = UserTrackHistory(
            user_id=uid,
            changed_at=now,
            track_before={"track": ["정시"]},
            track_after={"track": ["정시", "수시학종"]},
            reason="모의고사 성적 상승으로 수시 병행 결정",
        )
        assert h.user_id == uid
        assert h.track_before == {"track": ["정시"]}
        assert h.track_after["track"] == ["정시", "수시학종"]
        assert h.reason == "모의고사 성적 상승으로 수시 병행 결정"

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            UserTrackHistory(bogus="x")  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────
# UserPersonaHistory — 복합 PK (user_id, detected_at) required
# ──────────────────────────────────────────────────────────────────────
class TestUserPersonaHistory:
    def test_valid_with_composite_pk(self) -> None:
        """user_id·detected_at(복합 PK) 필수 + 선택 필드."""
        uid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        h = UserPersonaHistory(
            user_id=uid,
            detected_at=now,
            persona=Persona.A_일반고고3,
            confidence=0.9,
            signals={"avg_session_minutes": 45, "device": "아이패드"},
        )
        assert h.user_id == uid
        assert h.detected_at == now
        assert h.persona == Persona.A_일반고고3
        assert h.confidence == pytest.approx(0.9)
        assert h.signals["avg_session_minutes"] == 45

    def test_user_id_required(self) -> None:
        """user_id는 복합 PK 구성요소라 required — 누락 거부."""
        with pytest.raises(ValidationError):
            UserPersonaHistory(detected_at=datetime.now(timezone.utc))  # type: ignore[call-arg]

    def test_detected_at_required(self) -> None:
        """detected_at은 복합 PK 구성요소라 required — 누락 거부."""
        with pytest.raises(ValidationError):
            UserPersonaHistory(user_id=uuid.uuid4())  # type: ignore[call-arg]

    def test_confidence_range_rejected(self) -> None:
        """confidence는 0-1 — 1 초과 거부."""
        with pytest.raises(ValidationError):
            UserPersonaHistory(
                user_id=uuid.uuid4(),
                detected_at=datetime.now(timezone.utc),
                confidence=1.5,
            )

    def test_persona_optional(self) -> None:
        """persona는 Optional — 생략 가능."""
        h = UserPersonaHistory(
            user_id=uuid.uuid4(),
            detected_at=datetime.now(timezone.utc),
        )
        assert h.persona is None
        assert h.confidence is None
        assert h.signals is None

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            UserPersonaHistory(  # type: ignore[call-arg]
                user_id=uuid.uuid4(),
                detected_at=datetime.now(timezone.utc),
                bogus="x",
            )

    def test_persona_enum_value_serialization(self) -> None:
        """use_enum_values → persona 한글 값 보존."""
        h = UserPersonaHistory(
            user_id=uuid.uuid4(),
            detected_at=datetime.now(timezone.utc),
            persona=Persona.E_홈스쿨링영재,
        )
        assert h.model_dump()["persona"] == "E_홈스쿨링영재"


# ──────────────────────────────────────────────────────────────────────
# UserStateSnapshot — 생성·범위·맵 필드
# ──────────────────────────────────────────────────────────────────────
class TestUserStateSnapshot:
    def test_minimal_valid(self) -> None:
        """모든 필드 nullable — 빈 생성 시 snapshot_id만 자동 채워짐."""
        s = UserStateSnapshot()
        assert isinstance(s.snapshot_id, uuid.UUID)
        assert s.user_id is None
        assert s.snapshot_at is None
        assert s.concept_mastery is None
        assert s.pattern_mastery is None
        assert s.avg_solve_time_by_difficulty is None
        assert s.embedding_id is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채운 스냅샷 — 맵 값 보존."""
        uid = uuid.uuid4()
        emb = uuid.uuid4()
        now = datetime.now(timezone.utc)
        s = UserStateSnapshot(
            user_id=uid,
            snapshot_at=now,
            estimated_grade=2.0,
            estimated_score=135,
            estimated_percentile=96.5,
            concept_mastery={"CAL-INT-DEF": 0.8, "FUN-COMPOSITE": 0.5},
            pattern_mastery={"COMPOSITE_DIFFERENTIABILITY": 0.6},
            avg_solve_time_by_difficulty={"easy": 60, "medium": 180, "hard": 600},
            time_management_score=0.7,
            consecutive_active_days=14,
            avg_session_quality=0.85,
            embedding_id=emb,
        )
        assert s.user_id == uid
        assert s.concept_mastery == {"CAL-INT-DEF": 0.8, "FUN-COMPOSITE": 0.5}
        assert s.pattern_mastery["COMPOSITE_DIFFERENTIABILITY"] == pytest.approx(0.6)
        assert s.avg_solve_time_by_difficulty["hard"] == 600
        assert s.estimated_percentile == pytest.approx(96.5)
        assert s.embedding_id == emb

    def test_estimated_percentile_too_high_rejected(self) -> None:
        """estimated_percentile은 0-100(DECIMAL(5,2) 백분위) — 100 초과 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(estimated_percentile=100.5)

    def test_estimated_grade_out_of_range_rejected(self) -> None:
        """estimated_grade는 1-9(보수 설정) — 9.5 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(estimated_grade=9.5)

    def test_estimated_score_negative_rejected(self) -> None:
        """estimated_score는 ge=0(점수) — 음수 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(estimated_score=-1)

    def test_time_management_score_range_rejected(self) -> None:
        """time_management_score는 0-1 — 1 초과 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(time_management_score=1.5)

    def test_avg_session_quality_range_rejected(self) -> None:
        """avg_session_quality는 0-1(보수 설정) — 1 초과 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(avg_session_quality=1.2)

    def test_consecutive_active_days_negative_rejected(self) -> None:
        """consecutive_active_days는 ge=0(일수) — 음수 거부."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(consecutive_active_days=-1)

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            UserStateSnapshot(bogus="x")  # type: ignore[call-arg]
