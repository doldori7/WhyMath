"""user 라우터 통합테스트 — 실 PostgreSQL + 실 인증 체인 (기본 SKIP).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만. jwt 시크릿은 `get_settings`를 테스트
Settings로 오버라이드해 주입(토큰 mint와 검증이 같은 시크릿). `get_session`은 *실제*(live PG)로
둬 인증→DB 사용자 로드를 end-to-end 검증한다. 사용자 행은 독립 엔진으로 ORM 적재/정리한다.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


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


async def _delete_user(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
    finally:
        await engine.dispose()


def _build_user(user_id: uuid.UUID, **over: object) -> UserProfile:
    data: dict[str, object] = {
        "user_id": user_id,
        "persona_primary": Persona.A_일반고고3,
        "nickname": "원본닉",
        "email_hash": "HASHED_EMAIL",
        "is_minor": False,
    }
    data.update(over)
    return UserProfile.from_schema(UserProfileSchema(**data))  # type: ignore[arg-type]


def _app_with_settings() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings  # jwt 시크릿만 주입(get_session은 실 PG)
    return TestClient(app)


def test_users_me_roundtrip_on_live_pg() -> None:
    """토큰으로 /me 200(PII 제외)→PATCH(nickname)→GET 반영→무토큰 401."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    try:
        asyncio.run(_insert_user(_build_user(uid)))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _app_with_settings() as client:
            me = client.get("/v1/users/me", headers=auth)
            assert me.status_code == 200, me.text
            assert me.json()["nickname"] == "원본닉"
            assert "email_hash" not in me.json()  # PII 제외
            etag = me.headers["ETag"]

            patched = client.patch(
                "/v1/users/me",
                headers={**auth, "If-Match": etag},
                json={"nickname": "수정닉"},
            )
            assert patched.status_code == 200, patched.text
            assert client.get("/v1/users/me", headers=auth).json()["nickname"] == "수정닉"

            assert client.get("/v1/users/me").status_code == 401  # 무토큰
    finally:
        asyncio.run(_delete_user(uid))


def test_users_me_minor_without_consent_403_on_live_pg() -> None:
    """미성년자(동의 미설정) → /me 403(동의 게이트)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    try:
        asyncio.run(
            _insert_user(
                _build_user(
                    uid,
                    email_hash="HASHED_MINOR",
                    is_minor=True,
                    parent_consent_at=None,
                )
            )
        )
        token = create_access_token(uid, settings=_settings())
        with _app_with_settings() as client:
            resp = client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 403
    finally:
        asyncio.run(_delete_user(uid))
