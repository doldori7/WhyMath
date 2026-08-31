"""운영자 계정 부트스트랩 ops CLI(`ops/account_bootstrap_cli.py`, ADMIN-11) — 실 PostgreSQL 통합.

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG(마이그레이션 head 적용)에서만 실행한다(conftest
게이트가 CI 기본 skip). PG 미도달 시에도 graceful skip(`test_role_grant_cli_integration.py` 미러).

검증하는 것(ADMIN-11 완료조건 ②·④·⑤):
  ① **멱등**(④) — 같은 이메일로 두 번 돌리면 계정이 2개가 되지 않고 같은 `user_id`에
     `created=false`가 나온다. 대소문자만 다른 주소도 같은 계정이어야 한다.
  ② **★ 로그인 경로 연결**(②) — 부트스트랩한 행을 `api/auth.py`의 `resolve_user`가 같은
     이메일로 조회해 **같은 `user_id`**를 돌려준다. 이 태스크의 존재 이유가 바로 이 계약이다:
     깨지면 나중에 실제 로그인이 새 계정을 만들고, 부여해 둔 좌석은 아무도 쓰지 않는 유령
     행에 남는다. 단위 테스트는 `email_hash` 값이 같다는 것까지만 볼 수 있고, *로그인 경로가
     실제로 그 행을 집어 온다*는 것은 실 DB 왕복에서만 증명된다.
  ③ **프리플라이트 통과**(⑤) — head 스키마에서 `_default_preflight_fn`이 통과한다(hermetic
     테스트가 주입으로 우회하는 실 DB 경로를 여기서 한 번 실제로 태운다).

CLI는 모듈 전역 캐시 엔진(`db.session.get_engine`)을 쓰고 `main()`은 호출마다 새
`asyncio.run()` 루프를 연다 — `WHYMATH_DB_DISABLE_POOL=1`(NullPool)이 "다른 루프에 바인딩된
연결" 오류를 막는 표준 처방이다(`test_role_grant_cli_integration.py` 동일 사유).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api.auth import OAuthIdentity, email_hash, resolve_user
from whymath_backend.config import Settings
from whymath_backend.ops import account_bootstrap_cli as cli

pytestmark = pytest.mark.integration

_EMAIL = "admin11-bootstrap@whymath.example"


async def _pg_reachable() -> bool:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _delete_by_email(email: str) -> None:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM user_profile WHERE email_hash = :h"), {"h": email_hash(email)}
            )
    finally:
        await engine.dispose()


async def _count_by_email(email: str) -> int:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT count(*) FROM user_profile WHERE email_hash = :h"),
                {"h": email_hash(email)},
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def _resolve_via_login_path(email: str) -> uuid.UUID:
    """로그인 경로(`resolve_user`)가 이 이메일로 집어 오는 `user_id`."""
    settings = Settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            user = await resolve_user(
                session,
                OAuthIdentity(provider="demo", subject="admin11", email=email, birth_year=None),
                settings=settings,
            )
            await session.commit()
            return uuid.UUID(str(user.user_id))
    finally:
        await engine.dispose()


@pytest.fixture
def clean_email() -> Iterator[str]:
    """대상 이메일의 잔재를 앞뒤로 지운다 — 이전 실행의 행을 이번 결과로 오독하지 않게."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")
    asyncio.run(_delete_by_email(_EMAIL))
    try:
        yield _EMAIL
    finally:
        asyncio.run(_delete_by_email(_EMAIL))


def test_create_is_idempotent(clean_email: str, capsys: pytest.CaptureFixture[str]) -> None:
    """① 1회차 created=true, 2회차 같은 user_id + created=false, 행은 끝까지 1개."""
    assert cli.main(["create", clean_email]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["created"] is True
    assert first["role"] == "student", "부트스트랩은 권한을 만들지 않는다"

    assert cli.main(["create", clean_email]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second == {"user_id": first["user_id"], "created": False, "role": "student"}
    assert asyncio.run(_count_by_email(clean_email)) == 1


def test_case_differing_email_is_the_same_account(
    clean_email: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """① 대소문자만 다른 주소로 두 번째 계정이 생기면 안 된다(email_hash가 소문자 정규화)."""
    assert cli.main(["create", clean_email]) == 0
    created = json.loads(capsys.readouterr().out)

    assert cli.main(["create", clean_email.upper()]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again["user_id"] == created["user_id"]
    assert again["created"] is False
    assert asyncio.run(_count_by_email(clean_email)) == 1


def test_login_path_resolves_to_the_bootstrapped_row(
    clean_email: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """② ★ 핵심 계약 — `resolve_user`가 부트스트랩한 바로 그 행을 집어 온다.

    이 단언이 깨지면 좌석은 유령 행에 남는다: 운영자가 실제로 로그인해도 새 계정이 만들어져
    `content_admin`이 붙지 않은 상태로 403을 계속 받는다.
    """
    assert cli.main(["create", clean_email]) == 0
    bootstrapped = uuid.UUID(json.loads(capsys.readouterr().out)["user_id"])

    resolved = asyncio.run(_resolve_via_login_path(clean_email))

    assert resolved == bootstrapped, "로그인 경로가 다른 행을 만들었다 — 좌석이 유령이 된다"
    assert asyncio.run(_count_by_email(clean_email)) == 1
