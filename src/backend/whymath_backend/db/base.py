"""SQLAlchemy 2.0 선언적 베이스 — 모든 ORM 모델의 공통 부모 + 메타데이터 명명 규약.

설계 정본: `schemas/v1.0/schema_v1.0.md`(테이블 DDL의 영속 매핑 대상). 이 영속 레이어는
`schema/`(Pydantic, 검증·API)와 *별도*로 세운 SQLAlchemy ORM이다 — schema는 그대로 두고
db ORM이 영속을 맡으며 변환 헬퍼(`models/problem.py`의 from_schema/to_schema)로 잇는다
(SQLModel 미사용 — 사용자 결정).

명명 규약(naming_convention): alembic이 *결정적(deterministic)*으로 제약·인덱스 이름을
짓도록 메타데이터에 컨벤션을 박는다. 이게 없으면 PostgreSQL이 자동 생성한 제약명에
의존하게 돼 autogenerate diff가 불안정해지고, 무명 제약은 마이그레이션에서
`op.drop_constraint(...)` 시 이름을 못 짚는다. SQLAlchemy 공식 권장 토큰:
  - ix(인덱스)·uq(UNIQUE)·ck(CHECK)·fk(FOREIGN KEY)·pk(PRIMARY KEY)
`%(column_0_label)s`·`%(table_name)s`·`%(constraint_name)s`·`%(referred_table_name)s`는
SQLAlchemy가 제약 종류별로 채우는 토큰이다(공식 문서 "Configuring Constraint Naming
Conventions").
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# alembic 친화 제약·인덱스 명명 규약 (SQLAlchemy 공식 권장 5종 토큰).
# 결정적 제약명 → autogenerate diff 안정 + 마이그레이션에서 이름으로 drop 가능.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """모든 WhyMath ORM 모델의 선언적 베이스(SQLAlchemy 2.0 DeclarativeBase).

    `metadata`에 명명 규약을 주입해 alembic autogenerate가 제약·인덱스 이름을
    결정적으로 짓게 한다. 모든 ORM 모델은 이 `Base`를 상속하며, alembic env.py는
    `Base.metadata`를 target_metadata로 삼아 테이블 전체를 인식한다.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
