"""SQLAlchemy 2.0 async 엔진·세션 — 지연(lazy) 생성 + FastAPI 의존성 주입.

설계 정본: `schemas/v1.0/schema_v1.0.md`(영속 대상). lazy 패턴은 `l3/providers/
anthropic.py`(`AnthropicProvider._get_client` — import 시 연결 안 함, 첫 호출에서
생성·캐시)를 미러링한다.

왜 lazy인가:
  - 모듈 import 시점에 `create_async_engine`을 부르면 그 자체로는 네트워크를 타지 않으나,
    *import만으로 DB URL을 확정·엔진을 물게* 하면 테스트(연결 없는 단위테스트)·alembic
    오프라인 모드가 부담을 진다. 그래서 엔진은 *첫 사용 시점*(`get_engine()` 최초 호출)에
    만들고 모듈 전역에 캐시한다. anthropic.py가 클라이언트를 첫 호출에서 만드는 것과 동형.
  - `create_async_engine`은 *연결 풀만* 준비할 뿐 즉시 connect 하지 않는다(첫 쿼리에서
    연결). 따라서 `get_engine()` 호출 자체는 살아있는 PostgreSQL을 요구하지 않는다 —
    실제 연결은 `get_session()`의 첫 쿼리에서 발생(그 경로는 메인이 실 PG로 통합검증).

PoC 범위: 풀 튜닝(pool_size·max_overflow 등)은 범위 밖(config.py database_url 주석과
정합). 여기서는 async 엔진·세션메이커·FastAPI 의존성·정리(dispose)만 배선한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from whymath_backend.config import Settings, get_settings

# 모듈 전역 캐시 — 첫 사용에서 생성하고 재사용(lazy). dispose_engine()이 비운다.
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """async 엔진을 지연 생성·캐시해 반환한다(anthropic._get_client 패턴).

    첫 호출에서 `create_async_engine(settings.database_url)`로 엔진을 만들고 모듈 전역에
    캐시한다. 이후 호출은 같은 엔진을 돌려준다. `create_async_engine`은 풀만 준비하므로
    이 호출 자체는 살아있는 PostgreSQL을 요구하지 않는다(실제 연결은 첫 쿼리에서).

    `settings`를 주입하지 않으면 캐시된 전역 Settings(`get_settings()`)를 쓴다. 엔진이
    이미 있으면 주입 settings는 무시된다(이미 만들어진 풀을 재구성하지 않음 — 재구성이
    필요하면 `dispose_engine()` 후 다시 부른다).
    """
    global _engine
    if _engine is None:
        resolved = settings if settings is not None else get_settings()
        # future=True는 SQLAlchemy 2.0 기본이라 명시 불필요. async 엔진은 asyncpg 드라이버
        # (database_url의 +asyncpg)를 통해 동작한다. echo는 PoC 기본 off.
        _engine = create_async_engine(resolved.database_url)
    return _engine


def get_sessionmaker(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """async 세션 팩토리를 지연 생성·캐시해 반환한다.

    `expire_on_commit=False`: 커밋 후에도 ORM 객체 속성에 추가 쿼리 없이 접근할 수 있게
    한다(async 환경에서 commit 직후 lazy-load 재발화를 막는 표준 설정 — FastAPI 응답
    직렬화 중 만료된 속성 재로딩이 await 밖에서 터지는 사고를 예방).
    """
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성 — 요청 수명 동안 살아있는 AsyncSession을 yield한다.

    `async with` 블록으로 세션을 열고, 핸들러가 끝나면(또는 예외 시) 컨텍스트 매니저가
    세션을 닫는다. 트랜잭션 커밋/롤백은 *호출자(서비스·핸들러) 책임*으로 둔다(여기서
    자동 commit 하지 않음 — 읽기 전용 요청까지 강제 commit하지 않기 위함). 사용 예:

        @router.get("/problems/{pid}")
        async def read(pid: UUID, db: AsyncSession = Depends(get_session)) -> ...:
            ...

    이 경로는 살아있는 PostgreSQL을 요구하므로(첫 쿼리에서 connect) 단위테스트가 아니라
    메인의 실 PG 통합검증에서 동작 확인한다.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def dispose_engine() -> None:
    """캐시된 엔진을 정리하고 전역 캐시를 비운다(테스트·앱 종료용).

    `engine.dispose()`는 풀의 모든 연결을 반납·종료한다. 전역 캐시(`_engine`·
    `_sessionmaker`)도 None으로 되돌려, 다음 `get_engine()`이 새 엔진을 만들게 한다
    (테스트에서 settings를 바꿔 재배선하거나, FastAPI lifespan 종료에서 호출).
    """
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
