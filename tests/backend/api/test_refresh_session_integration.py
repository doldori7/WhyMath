"""리프레시 토큰 서버측 취소 통합테스트 — 실 PostgreSQL allowlist/denylist (기본 SKIP·OAuth-a3b).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만. jwt 시크릿은 `get_settings` 오버라이드로 주입
(토큰 mint와 검증이 같은 시크릿)·`get_session`은 *실제*(live PG)로 둬 `/refresh`의 allowlist
확인·`/logout`의 취소를 end-to-end 검증한다. 사용자·세션 행은 독립 엔진으로 ORM 적재/정리한다
(세션 행이 user_profile FK를 참조하므로 정리는 세션 행 → 사용자 순).

SEC-10(세션 가시성·전체/단건 로그아웃): `GET/DELETE /v1/auth/sessions[...]`은 실 정렬(`ORDER BY
issued_at DESC`)·본인 스코핑·`platform` 영속을 요구해 hermetic 페이크로는 정확히 검증되지 않는다
— 이 파일 하단에 실 PG 케이스를 추가한다(`test_auth_sessions.py`는 hermetic 목록/삭제 로직만).
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
from whymath_backend.security import create_access_token, create_refresh_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_REFRESH_PATH = "/v1/auth/refresh"
_LOGOUT_PATH = "/v1/auth/logout"
_SESSIONS_PATH = "/v1/auth/sessions"


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


async def _insert_session(
    jti: uuid.UUID,
    uid: uuid.UUID,
    *,
    platform: str | None = None,
    issued_at: datetime | None = None,
) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            row = RefreshTokenSession(
                token_session_id=jti,
                user_id=uid,
                expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
                platform=platform,
            )
            if issued_at is not None:
                row.issued_at = issued_at
            session.add(row)
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
    # email_hash는 user_id로부터 유도해 유니크 제약(uq_user_profile_email_hash)을 만족시킨다 —
    # 고정 리터럴("HASHED_EMAIL")은 한 테스트에서 사용자 2명 이상을 넣는 순간(SEC-10 본인
    # 스코핑 테스트처럼 owner/other 2명이 필요한 경우) 두 번째 insert가 UniqueViolation으로
    # 죽는다. 어떤 테스트도 이 값의 리터럴 내용에 의존하지 않는다(grep 확인).
    schema = UserProfileSchema(
        user_id=user_id,
        persona_primary=Persona.A_일반고고3,
        email_hash=f"HASHED_EMAIL_{user_id}",
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


def test_refresh_rotation_and_reuse_on_live_pg() -> None:
    """회전(R1→R2·기존 세션 취소) → R1 재사용 → 재사용 탐지 패닉(전 세션 취소·R2도 401)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    jti = uuid.uuid4()
    try:
        asyncio.run(_insert_user(_build_user(uid)))
        asyncio.run(_insert_session(jti, uid))
        r1 = create_refresh_token(uid, settings=_settings(), jti=jti)
        with _app_with_settings() as client:
            rotated = client.post(_REFRESH_PATH, json={"refresh_token": r1})
            assert rotated.status_code == 200, rotated.text
            r2 = rotated.json()["refresh_token"]
            assert r2 != r1  # 회전된 새 리프레시 토큰
            # R1 재사용(이미 회전됨) → 재사용 탐지 패닉 → 401
            reuse = client.post(_REFRESH_PATH, json={"refresh_token": r1})
            assert reuse.status_code == 401, reuse.text
            # 패닉으로 회전된 R2까지 무효화
            assert client.post(_REFRESH_PATH, json={"refresh_token": r2}).status_code == 401
    finally:
        asyncio.run(_cleanup(uid))


def _auth_header(uid: uuid.UUID) -> dict[str, str]:
    token = create_access_token(uid, settings=_settings())
    return {"Authorization": f"Bearer {token}"}


def test_list_then_revoke_all_sessions_on_live_pg() -> None:
    """실 정렬(issued_at desc) + platform 영속 확인 → 전체 취소 → 목록이 빈다(SEC-10)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    older_jti, newer_jti = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    try:
        asyncio.run(_insert_user(_build_user(uid)))
        asyncio.run(
            _insert_session(older_jti, uid, platform="Android", issued_at=now - timedelta(hours=1))
        )
        asyncio.run(_insert_session(newer_jti, uid, platform="iOS", issued_at=now))
        with _app_with_settings() as client:
            listed = client.get(_SESSIONS_PATH, headers=_auth_header(uid))
            assert listed.status_code == 200, listed.text
            sessions = listed.json()["sessions"]
            assert [s["session_id"] for s in sessions] == [str(newer_jti), str(older_jti)]
            assert sessions[0]["platform"] == "iOS"
            assert sessions[1]["platform"] == "Android"

            revoked = client.delete(_SESSIONS_PATH, headers=_auth_header(uid))
            assert revoked.status_code == 204, revoked.text

            after = client.get(_SESSIONS_PATH, headers=_auth_header(uid))
            assert after.json()["sessions"] == []
    finally:
        asyncio.run(_cleanup(uid))


def test_revoke_single_session_is_ownership_scoped_on_live_pg() -> None:
    """타인 소유 session_id는 404 — 본인 소유만 취소 가능(본인 스코핑)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    owner_uid, other_uid = uuid.uuid4(), uuid.uuid4()
    owner_jti = uuid.uuid4()
    try:
        asyncio.run(_insert_user(_build_user(owner_uid)))
        asyncio.run(_insert_user(_build_user(other_uid)))
        asyncio.run(_insert_session(owner_jti, owner_uid))
        with _app_with_settings() as client:
            # 타인이 소유자의 세션을 지우려 하면 404(존재 유무를 노출하지 않음).
            forbidden = client.delete(
                f"{_SESSIONS_PATH}/{owner_jti}", headers=_auth_header(other_uid)
            )
            assert forbidden.status_code == 404, forbidden.text

            owned = client.delete(f"{_SESSIONS_PATH}/{owner_jti}", headers=_auth_header(owner_uid))
            assert owned.status_code == 204, owned.text
    finally:
        asyncio.run(_cleanup(owner_uid))
        asyncio.run(_cleanup(other_uid))
