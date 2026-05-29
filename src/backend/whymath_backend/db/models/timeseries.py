"""도메인7 시간 시계열(Time Series) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schemas/v1.0/schema_v1.0.md` §9.1(`daily_learning_metrics`·
`problem_solve_time_distribution`·`user_behavior_metrics` DDL 3테이블). 이 ORM은
`schema/timeseries.py`(Pydantic, 검증·API)와 *별도*로 세운 영속 매핑이며 `from_schema`/
`to_schema` 변환 헬퍼가 둘을 잇는다(배치1 `problem.py`·`user.py` 동일 패턴).

§9 세 테이블은 모두 TimescaleDB hypertable·복합 PK다. *hypertable 변환은 마이그레이션
레벨*이라 ORM에서는 전부 일반 테이블로 둔다(복합 PK는 표현하되 create_hypertable 코드는
넣지 않는다). §9 DDL은 어떤 컬럼에도 `REFERENCES` 절이 없어 *전부 FK가 아니다*(느슨참조).

타입 매핑(DDL → ORM, problem.py/user.py 선례 그대로):
  - `UUID`(복합 PK 구성요소, REFERENCES 없음) → required `uuid.UUID` + `primary_key=True`
    (*FK 아님* — user_id·problem_id. assessment.ConceptMasteryHistory 선례와 동형).
  - `DATE`(복합 PK 구성요소) → required `datetime.date` + `primary_key=True`(metric_date —
    user.py target_exam_date가 DATE를 `sa.Date`로 매핑한 선례. TIMESTAMPTZ 아님).
  - `TIMESTAMPTZ`(복합 PK 구성요소) → required `datetime` + `primary_key=True`(measured_at).
  - `persona_enum`(복합 PK 구성요소) → `_pg_enum(Persona, "persona_enum")` + `primary_key=True`
    — *배치1 user.py가 이미 정의한 PG 타입을 동일 name으로 공유*한다(중복 정의 X). 공유 enum의
    create_type 처리는 마이그레이션(메인) 몫. PK 구성요소라 required(Optional 아님).
  - `VARCHAR(n)`(복합 PK 구성요소, metric_name) → required `str` + `primary_key=True`(enum
    아닌 open set — schema network_type/metric_name 선례).
  - `INTEGER` → `int|None`(minutes_active·problems_*·p10/p50/p90_seconds·sample_size).
  - `DECIMAL(p,s)` → `Mapped[float|None] = mapped_column(sa.Numeric(p, s))`(avg_focus_score
    DECIMAL(3,2)·metric_value DECIMAL(10,4)).
  - `TEXT[]`(concepts_practiced) → `ARRAY(sa.Text)`; schema가 default_factory=list(NOT NULL
    의미)라 problem.py tags처럼 `nullable=False, server_default "'{}'::text[]"`.
  - §9.1에는 별도 CREATE INDEX가 없다(세 테이블 모두 인덱스 없음 — hypertable이 measured_at/
    metric_date 시간 차원 인덱스를 자체 관리; ORM/마이그레이션 레벨 인덱스는 메인 몫).

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`activity.py`·`assessment.py`
방침과 동일): 이 시계열들은 *미성년 학생 학습 행동 데이터*(churn_risk 등 행동 분석 포함)다.
미성년 개인정보 분석·마케팅 외부 공유 금지·개인 식별 분석 결과 외부 노출 금지는 *저장·노출·
분석 거버넌스 계층*(PIPA 권한 매트릭스·암호화·미들웨어) 책임이며, ORM에는 컬럼만 두고 가짜
CHECK를 만들지 않는다(schema.timeseries 모듈 docstring·problem.py 방침과 동형 — 문서화만).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum
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


# ──────────────────────────────────────────────────────────────────────────
# 핵심: DailyLearningMetrics (§9.1 daily_learning_metrics — 일별 학습 활동 집계)
# ──────────────────────────────────────────────────────────────────────────
class DailyLearningMetrics(Base):
    """일별 학습 활동 집계 영속 ORM — §9.1 `daily_learning_metrics`(자동 집계).

    복합 PK `(user_id, metric_date)` — DDL 제약. `metric_date`는 DDL `DATE`라 시각이 아닌
    *날짜*다(user.py target_exam_date 선례 — `sa.Date`). `user_id`는 §9.1 DDL에 REFERENCES가
    없어 *FK 아님*(hypertable 느슨참조). `concepts_practiced`(TEXT[])는 schema가
    default_factory=list라 NOT NULL 배열(server_default '{}')로 둔다.

    운영 시 hypertable로 변환되나(`metric_date` 30일 청크) ORM에서는 일반 테이블로 둔다.
    """

    __tablename__ = "daily_learning_metrics"

    # ===== 복합 PK (user_id, metric_date) — REFERENCES 없음 → FK 아님 =====
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    # DATE — 날짜만(TIMESTAMPTZ 아님).
    metric_date: Mapped[date] = mapped_column(sa.Date, primary_key=True)

    # ===== 활동량 집계 =====
    minutes_active: Mapped[int | None] = mapped_column(sa.Integer)
    problems_attempted: Mapped[int | None] = mapped_column(sa.Integer)
    problems_correct: Mapped[int | None] = mapped_column(sa.Integer)
    socratic_turns: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== 학습 내용·품질 (schema default_factory=list → NOT NULL TEXT[]) =====
    concepts_practiced: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    avg_focus_score: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))

    # ── 변환 헬퍼 (schema↔db seam, problem.py 패턴) ──────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaDailyLearningMetrics) -> DailyLearningMetrics:
        """검증된 `schema.DailyLearningMetrics` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaDailyLearningMetrics:
        """영속 ORM → `schema.DailyLearningMetrics`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaDailyLearningMetrics.model_validate(data)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ProblemSolveTimeDistribution
#       (§9.1 problem_solve_time_distribution — 문항별·페르소나별 풀이 시간 분포)
# ──────────────────────────────────────────────────────────────────────────
class ProblemSolveTimeDistribution(Base):
    """풀이 시간 분포 영속 ORM — §9.1 `problem_solve_time_distribution`(문항별·페르소나별).

    복합 PK `(problem_id, persona, measured_at)` — DDL 제약. `persona`는 배치1 user.py가 정의한
    `persona_enum` PG 타입을 공유하며, *복합 PK 구성요소*라 required(Optional 아님). `problem_id`는
    §9.1 DDL에 REFERENCES가 없어 *FK 아님*(hypertable 느슨참조).

    운영 시 hypertable로 변환되나(`measured_at` 7일 청크) ORM에서는 일반 테이블로 둔다.
    """

    __tablename__ = "problem_solve_time_distribution"

    # ===== 복합 PK (problem_id, persona, measured_at) — REFERENCES 없음 → FK 아님 =====
    # problem_id: REFERENCES 없음 → FK 아님(느슨참조).
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    # persona_enum: 배치1 user.py 정의 타입 공유(동일 name). PK 구성요소라 required.
    persona: Mapped[Persona] = mapped_column(_pg_enum(Persona, "persona_enum"), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)

    # ===== 분위수 (단위: 초) =====
    p10_seconds: Mapped[int | None] = mapped_column(sa.Integer)
    p50_seconds: Mapped[int | None] = mapped_column(sa.Integer)
    p90_seconds: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== 표본 =====
    sample_size: Mapped[int | None] = mapped_column(sa.Integer)

    @classmethod
    def from_schema(
        cls, schema: SchemaProblemSolveTimeDistribution
    ) -> ProblemSolveTimeDistribution:
        """검증된 `schema.ProblemSolveTimeDistribution` → 영속 ORM(schema↔db seam)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaProblemSolveTimeDistribution:
        """영속 ORM → `schema.ProblemSolveTimeDistribution`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaProblemSolveTimeDistribution.model_validate(data)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: UserBehaviorMetrics (§9.1 user_behavior_metrics — 학생 학습 행동 시계열)
# ──────────────────────────────────────────────────────────────────────────
class UserBehaviorMetrics(Base):
    """학생 학습 행동 시계열 영속 ORM — §9.1 `user_behavior_metrics`(페르소나 변화·이탈 예측).

    복합 PK `(user_id, metric_name, measured_at)` — DDL 제약. `metric_name`은 DDL `VARCHAR(50)`
    이라 enum이 아니라 `str`(open set — 지표 종류가 운영 중 늘어남; schema 선례). `user_id`는
    §9.1 DDL에 REFERENCES가 없어 *FK 아님*(hypertable 느슨참조). 셋 다 PK 구성요소라 required.

    운영 시 hypertable로 변환되나(`measured_at` 7일 청크) ORM에서는 일반 테이블로 둔다.

    개인정보 메모(모듈 docstring 참조): `churn_risk`(이탈 위험) 등 *행동 분석* 지표를 담는
    *미성년 학습 행동 데이터*다. 저장·노출·분석 거버넌스 계층(PIPA 권한 매트릭스·암호화·
    미들웨어) 책임이라 ORM에는 컬럼만 두고 가짜 CHECK를 만들지 않는다.
    """

    __tablename__ = "user_behavior_metrics"

    # ===== 복합 PK (user_id, metric_name, measured_at) — REFERENCES 없음 → FK 아님 =====
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    # VARCHAR(50) — enum 아닌 open set(metric_name). PK 구성요소라 required.
    metric_name: Mapped[str] = mapped_column(sa.String(50), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)

    # ===== 측정값 =====
    metric_value: Mapped[float | None] = mapped_column(sa.Numeric(10, 4))

    @classmethod
    def from_schema(cls, schema: SchemaUserBehaviorMetrics) -> UserBehaviorMetrics:
        """검증된 `schema.UserBehaviorMetrics` → 영속 ORM(schema↔db seam)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaUserBehaviorMetrics:
        """영속 ORM → `schema.UserBehaviorMetrics`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaUserBehaviorMetrics.model_validate(data)


__all__ = [
    "DailyLearningMetrics",
    "ProblemSolveTimeDistribution",
    "UserBehaviorMetrics",
]
