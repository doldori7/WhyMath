"""WhyMath 영속 레이어(SQLAlchemy 2.0 async) 공개 심볼.

`schema/`(Pydantic, 검증·API)와 *별도*로 세운 SQLAlchemy ORM 영속 레이어다(SQLModel
미사용 — 사용자 결정). 구성:
  - `base.Base` — 선언적 베이스 + alembic 친화 명명 규약(`Base.metadata`).
  - `session` — lazy async 엔진·세션메이커·FastAPI 의존성(`get_session`)·정리(`dispose_engine`).
  - `models` — 도메인 ORM(현재 도메인1 Problem). 변환 헬퍼(`from_schema`/`to_schema`)가
    schema↔db를 잇는다.

설계 정본: `schemas/v1.0/schema_v1.0.md`. 마이그레이션은 `src/backend/alembic`(env.py가
`Base.metadata`를 target으로, `Settings().database_url`을 URL로 사용).
"""

from __future__ import annotations

from whymath_backend.db.base import Base
from whymath_backend.db.models import Problem, ProblemRelation, ProblemStep
from whymath_backend.db.session import (
    dispose_engine,
    get_engine,
    get_session,
    get_sessionmaker,
)

__all__ = [
    "Base",
    "Problem",
    "ProblemStep",
    "ProblemRelation",
    "get_engine",
    "get_sessionmaker",
    "get_session",
    "dispose_engine",
]
