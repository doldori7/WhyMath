"""alembic 마이그레이션 환경 — async(SQLAlchemy 2.0 + asyncpg).

SQLAlchemy 공식 async 템플릿을 따른다(`create_async_engine` + `connection.run_sync` +
`asyncio.run`). 온라인(라이브 DB) 모드는 async, 오프라인(SQL 출력만) 모드도 지원한다.

핵심 배선:
  - `target_metadata = Base.metadata` — autogenerate가 비교할 모델 메타데이터.
  - `import whymath_backend.db.models` — 모든 ORM 테이블을 메타데이터에 등록(이 import가
    없으면 빈 메타데이터로 diff가 나서 테이블을 못 만든다).
  - URL은 `Settings().database_url`(WHYMATH_DATABASE_URL env 오버라이드)에서 읽는다 —
    alembic.ini에 자격증명을 두지 않는다(CLAUDE.md 보안 금기).
  - `compare_type=True` — 컬럼 타입 변경도 autogenerate가 감지(PG enum·Numeric 등).

마이그레이션 *버전 파일*은 이 슬라이스에서 만들지 않는다 — 메인이 로컬 PostgreSQL로
`alembic revision --autogenerate` 후 검증·커밋한다(README/태스크 명세).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# 모델 등록: 이 import가 Base.metadata에 모든 테이블을 채운다(autogenerate 인식 전제).
# `whymath_backend.db.models` import의 *부작용*(모델 클래스 정의 → 메타데이터 등록)이
# 목적이라 직접 참조하지 않는다(F401 noqa). db.base가 이미 models를 끌어오지 않으므로
# 여기서 명시 import해야 빈 메타데이터로 diff 나는 사고를 막는다.
import whymath_backend.db.models  # noqa: F401  (등록 부작용 목적 import)
from alembic import context
from whymath_backend.config import get_settings
from whymath_backend.db.base import Base

# alembic Config 객체 — alembic.ini 값 접근자.
config = context.config

# 로깅 설정(alembic.ini의 [loggers] 등). config_file_name이 없을 수 있어 가드.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 대상 메타데이터 — 모든 ORM 모델이 등록된 Base.metadata.
target_metadata = Base.metadata


def _database_url() -> str:
    """마이그레이션이 사용할 DB URL — Settings(env 오버라이드)에서 읽는다.

    alembic.ini의 sqlalchemy.url은 비어 있다(자격증명 하드코딩 금지). 프로덕션은
    WHYMATH_DATABASE_URL로 주입된 값이 그대로 쓰인다.
    """
    return get_settings().database_url


def run_migrations_offline() -> None:
    """오프라인 모드 — 실제 DB 연결 없이 마이그레이션 SQL을 생성/출력한다.

    URL만으로 컨텍스트를 구성하고 SQL을 방출한다(DBAPI 불요). CI·미리보기에서 연결 없이
    스크립트를 점검할 때 쓰인다.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """동기 Connection에 마이그레이션을 적용한다(run_sync 콜백 본체).

    async 엔진의 connection을 `run_sync`로 받아 alembic의 동기 마이그레이션 러너를
    구동한다. `compare_type=True`로 타입 변경까지 감지한다(PG native enum·Numeric 정합).
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """async 엔진을 만들어 온라인 마이그레이션을 수행한다(공식 async 템플릿).

    `create_async_engine`으로 asyncpg 엔진을 만들고, connection을 열어 `run_sync`로
    동기 러너(do_run_migrations)에 위임한다. 끝나면 엔진을 dispose한다.
    """
    connectable = create_async_engine(_database_url())

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드 진입점 — async 마이그레이션을 이벤트 루프에서 실행한다."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
