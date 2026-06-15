"""리프레시 토큰 서버측 취소 통합테스트 — 실 PostgreSQL allowlist/denylist (기본 SKIP·OAuth-a3b).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만. jwt 시크릿은 `get_settings` 오버라이드로 주입
(토큰 mint와 검증이 같은 시크릿)·`get_session`은 *실제*(live PG)로 둬 `/refresh`의 allowlist
확인·`/logout`의 취소를 end-to-end 검증한다. 사용자·세션 행은 독립 엔진으로 ORM 적재/정리한다
(세션 행이 user_profile FK를 참조하므로 정리는 세션 행 → 사용자 순).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_refresh_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_REFRESH_PATH = "/v1/auth/refresh"
_LOGOUT_PATH = "/v1/auth/logout"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _insert_user(user: UserProfile) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(user)
            await session.commit()
    finally:
        await engine.dispose()


async def _insert_session(jti: uuid.UUID, uid: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                RefreshTokenSession(
                    token_session_id=jti,
                    user_id=uid,
                    expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID) -> None:
    """세션 행 → 사용자 순 삭제(FK refresh_token_session.user_id → user_profile)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM refresh_token_session WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
    finally:
        await engine.dispose()


def _build_user(user_id: uuid.UUID) -> UserProfile:
    schema = UserProfileSchema(
        user_id=user_id,
        persona_primary=Persona.A_일반고고3,
        email_hash="HASHED_EMAIL",
        is_minor=False,
    )
    return UserProfile.from_schema(schema)


def _app_with_settings() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings  # jwt 시크릿만 주입(get_session은 실 PG)
    return TestClient(app)


def test_refresh_then_logout_revokes_on_live_pg() -> None:
    """allowlist 히트 → /refresh 200 → /logout 204 → 같은 토큰 /refresh 401(서버측 취소 e2e)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    jti = uuid.uuid4()
    try:
        asyncio.run(_insert_user(_build_user(uid)))
        asyncio.run(_insert_session(jti, uid))
        refresh = create_refresh_token(uid, settings=_settings(), jti=jti)
        with _app_with_settings() as client:
            ok = client.post(_REFRESH_PATH, json={"refresh_token": refresh})
            assert ok.status_code == 200, ok.text
            assert client.post(_LOGOUT_PATH, json={"refresh_token": refresh}).status_code == 204
            revoked = client.post(_REFRESH_PATH, json={"refresh_token": refresh})
            assert revoked.status_code == 401, revoked.text
    finally:
        asyncio.run(_cleanup(uid))


def test_refresh_unknown_session_401_on_live_pg() -> None:
    """세션 행이 없는(미발급·로그아웃됨) 유효 서명 토큰은 allowlist 미스 → 401."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    try:
        asyncio.run(_insert_user(_build_user(uid)))  # 세션 행은 넣지 않음
        refresh = create_refresh_token(uid, settings=_settings(), jti=uuid.uuid4())
        with _app_with_settings() as client:
            resp = client.post(_REFRESH_PATH, json={"refresh_token": refresh})
            assert resp.status_code == 401, resp.text
    finally:
        asyncio.run(_cleanup(uid))
