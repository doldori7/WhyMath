"""TimeSeries ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem/user ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(복합PK·DATE·TEXT[]·
persona_enum 재사용) / enum values_callable / schema↔ORM 변환 roundtrip. 세 테이블 모두
hypertable이나 변환은 마이그레이션 레벨이라 보지 않는다(ORM은 일반 테이블).

설계 정본: schemas/v1.0/schema_v1.0.md §9.1.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.timeseries import (
    DailyLearningMetrics as OrmDailyLearningMetrics,
)
from whymath_backend.db.models.timeseries import (
    ProblemSolveTimeDistribution as OrmProblemSolveTimeDistribution,
)
from whymath_backend.db.models.timeseries import (
    UserBehaviorMetrics as OrmUserBehaviorMetrics,
)
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.timeseries import (
    DailyLearningMetrics as SchemaDailyLearningMetrics,
)
from whymath_backend.schema.timeseries import (
    ProblemSolveTimeDistribution as SchemaProblemSolveTimeDistribution,
)
from whymath_backend.schema.timeseries import (
    UserBehaviorMetrics as SchemaUserBehaviorMetrics,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_timeseries_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인7 세 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {
        "daily_learning_metrics",
        "problem_solve_time_distribution",
        "user_behavior_metrics",
    } <= tables


def test_timeseries_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §9.1 DDL 테이블명과 일치한다."""
    assert OrmDailyLearningMetrics.__tablename__ == "daily_learning_metrics"
    assert OrmProblemSolveTimeDistribution.__tablename__ == "problem_solve_time_distribution"
    assert OrmUserBehaviorMetrics.__tablename__ == "user_behavior_metrics"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일 — 복합 PK·DATE·TEXT[]·FK 없음(느슨참조)
# ──────────────────────────────────────────────────────────────────────────
def test_daily_learning_metrics_composite_pk_date_array() -> None:
    """daily_learning_metrics: 복합 PK(user_id, metric_date)·DATE
    ·concepts_practiced TEXT[]·FK 없음."""
    ddl = _pg_ddl(OrmDailyLearningMetrics.__table__)
    assert "PRIMARY KEY (user_id, metric_date)" in ddl
    assert "DATE" in ddl  # metric_date (TIMESTAMPTZ 아님)
    assert "TEXT[]" in ddl  # concepts_practiced
    # §9.1 DDL에 REFERENCES 없음 → FK 0개(hypertable 느슨참조).
    assert len(OrmDailyLearningMetrics.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


def test_daily_learning_metrics_concepts_practiced_not_null() -> None:
    """concepts_practiced(TEXT[])는 NOT NULL(schema default_factory=list → server_default '{}')."""
    col = OrmDailyLearningMetrics.__table__.c.concepts_practiced
    assert col.nullable is False
    assert col.server_default is not None


def test_problem_solve_time_distribution_composite_pk_enum() -> None:
    """problem_solve_time_distribution: 복합 PK(problem_id, persona, measured_at)
    ·persona_enum·FK 없음."""
    ddl = _pg_ddl(OrmProblemSolveTimeDistribution.__table__)
    assert "PRIMARY KEY (problem_id, persona, measured_at)" in ddl
    assert "persona_enum" in ddl  # 배치1 공유 enum
    assert len(OrmProblemSolveTimeDistribution.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


def test_user_behavior_metrics_composite_pk_varchar() -> None:
    """user_behavior_metrics: 복합 PK(user_id, metric_name, measured_at)
    ·metric_name VARCHAR·FK 없음."""
    ddl = _pg_ddl(OrmUserBehaviorMetrics.__table__)
    assert "PRIMARY KEY (user_id, metric_name, measured_at)" in ddl
    assert "VARCHAR(50)" in ddl  # metric_name (enum 아님)
    assert "NUMERIC(10, 4)" in ddl  # metric_value DECIMAL(10,4)
    assert len(OrmUserBehaviorMetrics.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable — persona_enum 재사용 값 정합
# ──────────────────────────────────────────────────────────────────────────
def test_persona_enum_reused_values_in_distribution() -> None:
    """persona 컬럼이 배치1 persona_enum 값('A_일반고고3'·'E_홈스쿨링영재' 등)을 공유한다."""
    enums = OrmProblemSolveTimeDistribution.__table__.c.persona.type.enums  # type: ignore[attr-defined]
    assert "A_일반고고3" in enums
    assert "B_자사고N수" in enums
    assert "E_홈스쿨링영재" in enums


def test_persona_column_is_primary_key() -> None:
    """persona는 복합 PK 구성요소(NOT NULL primary_key)다."""
    col = OrmProblemSolveTimeDistribution.__table__.c.persona
    assert col.primary_key is True
    assert col.nullable is False


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_daily_learning_metrics_roundtrip() -> None:
    """DailyLearningMetrics 변환이 복합 PK(user_id·DATE)·TEXT[] 배열을 보존한다."""
    uid = uuid.uuid4()
    md = date(2026, 5, 1)
    s = SchemaDailyLearningMetrics(
        user_id=uid,
        metric_date=md,
        minutes_active=90,
        problems_attempted=12,
        problems_correct=9,
        concepts_practiced=["CAL-INT-DEF", "FUN-COMPOSITE"],
        avg_focus_score=0.78,
    )
    orm = OrmDailyLearningMetrics.from_schema(s)
    assert orm.user_id == uid
    assert orm.metric_date == md
    assert orm.concepts_practiced == ["CAL-INT-DEF", "FUN-COMPOSITE"]
    assert orm.avg_focus_score == 0.78

    back = orm.to_schema()
    assert back.user_id == uid
    assert back.metric_date == md
    assert back.concepts_practiced == s.concepts_practiced
    assert back.minutes_active == 90


def test_daily_learning_metrics_default_concepts() -> None:
    """concepts_practiced 미지정 시 빈 리스트로 보존된다(schema default_factory=list)."""
    s = SchemaDailyLearningMetrics(user_id=uuid.uuid4(), metric_date=date(2026, 5, 1))
    orm = OrmDailyLearningMetrics.from_schema(s)
    assert orm.concepts_practiced == []
    back = orm.to_schema()
    assert back.concepts_practiced == []


def test_problem_solve_time_distribution_roundtrip() -> None:
    """ProblemSolveTimeDistribution 변환이 persona PK enum·분위수를 보존한다."""
    pid = uuid.uuid4()
    at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    s = SchemaProblemSolveTimeDistribution(
        problem_id=pid,
        persona=Persona.B_자사고N수,
        measured_at=at,
        p10_seconds=60,
        p50_seconds=120,
        p90_seconds=300,
        sample_size=240,
    )
    orm = OrmProblemSolveTimeDistribution.from_schema(s)
    assert orm.problem_id == pid
    # use_enum_values=True → 값으로 떨어진다.
    assert orm.persona == "B_자사고N수"
    assert orm.measured_at == at
    assert orm.p50_seconds == 120

    back = orm.to_schema()
    assert back.problem_id == pid
    assert back.persona == s.persona
    assert back.measured_at == at
    assert back.p90_seconds == 300


def test_user_behavior_metrics_roundtrip() -> None:
    """UserBehaviorMetrics 변환이 복합 PK(metric_name str)·metric_value를 보존한다."""
    uid = uuid.uuid4()
    at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    s = SchemaUserBehaviorMetrics(
        user_id=uid,
        metric_name="churn_risk",
        measured_at=at,
        metric_value=0.3142,
    )
    orm = OrmUserBehaviorMetrics.from_schema(s)
    assert orm.user_id == uid
    assert orm.metric_name == "churn_risk"
    assert orm.measured_at == at
    assert orm.metric_value == 0.3142

    back = orm.to_schema()
    assert back.user_id == uid
    assert back.metric_name == "churn_risk"
    assert back.measured_at == at
    assert back.metric_value == 0.3142
