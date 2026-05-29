"""Assessment ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem/user ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(JSONB·enum·복합PK) /
enum values_callable(특히 AssessmentType의 'D-100예측' 값) / schema↔ORM 변환 roundtrip.
hypertable(concept_mastery_history) 변환은 마이그레이션 레벨이라 보지 않는다.

설계 정본: schemas/v1.0/schema_v1.0.md §8.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.assessment import (
    Assessment as OrmAssessment,
)
from whymath_backend.db.models.assessment import (
    ConceptMasteryHistory as OrmConceptMasteryHistory,
)
from whymath_backend.schema.assessment import (
    Assessment as SchemaAssessment,
)
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as SchemaConceptMasteryHistory,
)
from whymath_backend.schema.enums import (
    AssessmentType,
    MentalPhase,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_assessment_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인6 두 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"assessment", "concept_mastery_history"} <= tables


def test_assessment_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §8.1 DDL 테이블명과 일치한다."""
    assert OrmAssessment.__tablename__ == "assessment"
    assert OrmConceptMasteryHistory.__tablename__ == "concept_mastery_history"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일
# ──────────────────────────────────────────────────────────────────────────
def test_assessment_ddl_fk_jsonb_enum() -> None:
    """assessment: user_profile FK·5개 진단 JSONB·assessment_type/mental_phase enum."""
    ddl = _pg_ddl(OrmAssessment.__table__)
    assert "REFERENCES user_profile" in ddl
    assert "JSONB" in ddl  # concept_diagnosis 등 5개
    assert "assessment_type_enum" in ddl
    assert "mental_phase_enum" in ddl
    assert "gen_random_uuid()" in ddl
    assert "NUMERIC" in ddl  # estimated_grade·estimated_percentile·admission_probability


def test_assessment_loose_ref_target_university() -> None:
    """target_university_id는 §8.1 DDL에 REFERENCES가 없어 FK가 아니다(FK는 user_id 하나뿐)."""
    # FK는 user_id→user_profile 하나뿐(target_university_id는 느슨참조).
    assert len(OrmAssessment.__table__.foreign_keys) == 1
    ddl = _pg_ddl(OrmAssessment.__table__)
    assert "REFERENCES university" not in ddl


def test_assessment_jsonb_fields_not_null() -> None:
    """5개 진단 JSONB는 NOT NULL(schema default_factory=list → server_default '[]')."""
    for name in (
        "concept_diagnosis",
        "pattern_diagnosis",
        "weak_points",
        "strong_points",
        "recommended_path",
    ):
        col = OrmAssessment.__table__.c[name]
        assert col.nullable is False, name
        assert col.server_default is not None, name


def test_concept_mastery_history_composite_pk_no_fk() -> None:
    """concept_mastery_history: 복합 PK(user_id, concept_id, measured_at)·FK 없음(느슨참조)."""
    ddl = _pg_ddl(OrmConceptMasteryHistory.__table__)
    assert "PRIMARY KEY (user_id, concept_id, measured_at)" in ddl
    # §8.1 DDL에 REFERENCES 절이 없어 FK 0개(hypertable 느슨참조).
    assert len(OrmConceptMasteryHistory.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable — 멤버명≠값(D-100예측)인 enum 회귀 방지
# ──────────────────────────────────────────────────────────────────────────
def test_assessment_type_enum_uses_value_with_distinct_member_name() -> None:
    """assessment_type 컬럼이 값 'D-100예측'을 갖는다(멤버명 'D_100예측' 아님).

    values_callable이 빠지면 SQLAlchemy가 멤버명('D_100예측')으로 PG enum을 만들어
    §8.1 DDL 값('D-100예측')과 어긋난다 — 이 테스트가 그 회귀를 막는다(problem의
    curriculum '2015_REVISION' 선례와 동형).
    """
    enums = OrmAssessment.__table__.c.assessment_type.type.enums  # type: ignore[attr-defined]
    assert "D-100예측" in enums
    assert "D_100예측" not in enums  # 멤버명이 라벨로 새지 않았는지
    assert "초기진단" in enums


def test_mental_phase_enum_values() -> None:
    """mental_phase 컬럼 enum이 값('D_100_50'·'평상시' 등)을 갖는다."""
    enums = OrmAssessment.__table__.c.mental_phase.type.enums  # type: ignore[attr-defined]
    assert "D_100_50" in enums
    assert "평상시" in enums


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_assessment_roundtrip_d100_and_jsonb() -> None:
    """Assessment 변환이 D-100예측 enum·진단 JSONB 배열·합격 확률을 보존한다."""
    aid = uuid.uuid4()
    uid = uuid.uuid4()
    s = SchemaAssessment(
        assessment_id=aid,
        user_id=uid,
        assessment_type=AssessmentType.D_100예측,
        mental_phase=MentalPhase.D_100_50,
        estimated_grade=2.0,
        estimated_percentile=88.5,
        admission_probability=0.72,
        weak_points=[{"concept": "수열의극한", "mastery": 0.3}],
        recommended_path=[{"week": 1, "concept": "극한", "estimated_hours": 5}],
    )
    orm = OrmAssessment.from_schema(s)
    assert orm.assessment_id == aid
    # use_enum_values=True → 값('D-100예측')으로 떨어진다(멤버명 아님).
    assert orm.assessment_type == "D-100예측"
    assert orm.mental_phase == "D_100_50"
    assert orm.admission_probability == 0.72
    assert orm.weak_points == [{"concept": "수열의극한", "mastery": 0.3}]
    assert orm.recommended_path == [{"week": 1, "concept": "극한", "estimated_hours": 5}]

    back = orm.to_schema()
    assert back.assessment_id == aid
    assert back.assessment_type == s.assessment_type
    assert back.mental_phase == s.mental_phase
    assert back.weak_points == s.weak_points
    assert back.recommended_path == s.recommended_path


def test_assessment_default_jsonb_lists() -> None:
    """진단 JSONB 미지정 시 빈 리스트로 보존된다(schema default_factory=list)."""
    s = SchemaAssessment()
    orm = OrmAssessment.from_schema(s)
    assert orm.concept_diagnosis == []
    assert orm.strong_points == []
    back = orm.to_schema()
    assert back.concept_diagnosis == []
    assert back.pattern_diagnosis == []


def test_concept_mastery_history_roundtrip() -> None:
    """ConceptMasteryHistory 변환이 복합 PK 구성요소·측정값을 보존한다."""
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    s = SchemaConceptMasteryHistory(
        user_id=uid,
        concept_id=cid,
        measured_at=at,
        mastery=0.7,
        confidence=0.85,
        sample_size=12,
    )
    orm = OrmConceptMasteryHistory.from_schema(s)
    assert orm.user_id == uid
    assert orm.concept_id == cid
    assert orm.measured_at == at
    assert orm.mastery == 0.7
    assert orm.sample_size == 12

    back = orm.to_schema()
    assert back.user_id == uid
    assert back.concept_id == cid
    assert back.measured_at == at
    assert back.mastery == s.mastery
    assert back.confidence == s.confidence
