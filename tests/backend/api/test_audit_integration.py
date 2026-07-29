"""GDPR 삭제 감사 통합테스트 — 실 PG로 deletion_audit 적재 검증 (기본 SKIP).

slice 57: `DELETE /v1/me/{sessions,dialogues,assessments}/{id}` 성공 시 `deletion_audit`에
부모 삭제 이벤트 1행이 적재되는지(누가·무엇·언제) end-to-end 확인. 감사 행은 리소스(및 그
소유자)와 무관하게 잔존(user_id FK 아님)한다. get_settings만 오버라이드·get_session은 실 PG.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
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


async def _exec(stmts: list[tuple[str, dict[str, object]]]) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            for sql, params in stmts:
                await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _fetchone(sql: str, params: dict[str, object]) -> tuple[object, ...] | None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            row = result.first()
            return tuple(row) if row is not None else None
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_delete_writes_audit_on_live_pg() -> None:
    """세션 삭제 → deletion_audit에 (user_id, learning_session, session_id) 1행 적재."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid, sid = uuid.uuid4(), uuid.uuid4()
    try:
        asyncio.run(
            _exec(
                [
                    (
                        "INSERT INTO user_profile (user_id, persona_primary) "
                        "VALUES (:u, 'A_일반고고3')",
                        {"u": str(uid)},
                    ),
                    (
                        "INSERT INTO learning_session (session_id, user_id) VALUES (:s, :u)",
                        {"s": str(sid), "u": str(uid)},
                    ),
                ]
            )
        )
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            resp = client.delete(f"/v1/me/sessions/{sid}", headers=auth)
            assert resp.status_code == 204, resp.text

        # 감사 1행: resource_type·resource_id·user_id 정확, deleted_at 채워짐
        audit = asyncio.run(
            _fetchone(
                "SELECT resource_type, resource_id, user_id, deleted_at "
                "FROM deletion_audit WHERE user_id=:u AND resource_id=:s",
                {"u": str(uid), "s": str(sid)},
            )
        )
        assert audit is not None
        assert audit[0] == "learning_session"
        assert str(audit[1]) == str(sid)
        assert str(audit[2]) == str(uid)
        assert audit[3] is not None  # deleted_at 자동 기록

        # 감사 행은 원본 세션이 삭제된 뒤에도 잔존(독립성)
        still = asyncio.run(
            _fetchone(
                "SELECT count(*) FROM learning_session WHERE session_id=:s",
                {"s": str(sid)},
            )
        )
        assert still is not None and still[0] == 0

        # slice 58: 본인 삭제 이력 조회 API가 그 감사를 반환(GDPR 투명성·end-to-end)
        with _client() as client:
            listed = client.get("/v1/me/deletions", headers=auth)
            assert listed.status_code == 200, listed.text
            assert any(
                it["resource_id"] == str(sid) and it["resource_type"] == "learning_session"
                for it in listed.json()
            )
    finally:
        asyncio.run(
            _exec(
                [
                    ("DELETE FROM deletion_audit WHERE user_id=:u", {"u": str(uid)}),
                    (
                        "DELETE FROM learning_session WHERE session_id=:s",
                        {"s": str(sid)},
                    ),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ]
            )
        )
