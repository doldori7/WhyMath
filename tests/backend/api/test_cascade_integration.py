"""cascade 삭제 통합테스트 — 실 PG로 GDPR 삭제 시 자식 cascade 검증 (기본 SKIP).

slice 56: `DELETE /v1/me/sessions/{id}` → 자식 problem_attempt **ON DELETE CASCADE** 제거 +
그 attempt를 가리키던 dialogue.attempt_id **SET NULL**(대화 자체는 보존). `DELETE
/v1/me/dialogues/{id}` → 자식 dialogue_turn **CASCADE**. 슬라이스 51/52의 RESTRICT FK 한계
(자식 존재 시 FK 위반)가 해소됐는지 API end-to-end로 확인한다. get_settings만 오버라이드
(jwt 시크릿)·get_session은 실 PG. 데이터는 raw SQL로 적재·정리(스키마 필수필드 최소).
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


async def _count(sql: str, params: dict[str, object]) -> int:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return int(result.scalar() or 0)
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_delete_cascades_children_on_live_pg() -> None:
    """세션 삭제 → attempt CASCADE·dialogue.attempt_id SET NULL; 대화 삭제 → turn CASCADE."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid, sid, aid, did = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
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
                    (
                        "INSERT INTO problem_attempt (attempt_id, user_id, session_id) "
                        "VALUES (:a, :u, :s)",
                        {"a": str(aid), "u": str(uid), "s": str(sid)},
                    ),
                    (
                        "INSERT INTO dialogue (dialogue_id, user_id, attempt_id) "
                        "VALUES (:d, :u, :a)",
                        {"d": str(did), "u": str(uid), "a": str(aid)},
                    ),
                    (
                        "INSERT INTO dialogue_turn (dialogue_id, turn_order) VALUES (:d, 1)",
                        {"d": str(did)},
                    ),
                ]
            )
        )
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # 세션 삭제 → attempt CASCADE 제거, dialogue.attempt_id SET NULL(대화 보존)
            resp = client.delete(f"/v1/me/sessions/{sid}", headers=auth)
            assert resp.status_code == 204, resp.text
            assert (
                asyncio.run(
                    _count(
                        "SELECT count(*) FROM problem_attempt WHERE attempt_id=:a",
                        {"a": str(aid)},
                    )
                )
                == 0
            )
            assert (
                asyncio.run(
                    _count(
                        "SELECT count(*) FROM dialogue "
                        "WHERE dialogue_id=:d AND attempt_id IS NULL",
                        {"d": str(did)},
                    )
                )
                == 1
            )
            # 대화 삭제 → turn CASCADE 제거
            resp2 = client.delete(f"/v1/me/dialogues/{did}", headers=auth)
            assert resp2.status_code == 204, resp2.text
            assert (
                asyncio.run(
                    _count(
                        "SELECT count(*) FROM dialogue_turn WHERE dialogue_id=:d",
                        {"d": str(did)},
                    )
                )
                == 0
            )
    finally:
        # cascade로 일부는 이미 삭제됐을 수 있음 — 자식부터 순서대로 멱등 정리.
        asyncio.run(
            _exec(
                [
                    ("DELETE FROM dialogue_turn WHERE dialogue_id=:d", {"d": str(did)}),
                    ("DELETE FROM dialogue WHERE dialogue_id=:d", {"d": str(did)}),
                    ("DELETE FROM problem_attempt WHERE attempt_id=:a", {"a": str(aid)}),
                    ("DELETE FROM learning_session WHERE session_id=:s", {"s": str(sid)}),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ]
            )
        )


def test_session_delete_cleans_attempt_event_orphans_on_live_pg() -> None:
    """slice 59: 세션 삭제 → attempt CASCADE → 트리거가 attempt_event(loose ref) 고아 정리."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid, sid, aid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
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
                    (
                        "INSERT INTO problem_attempt (attempt_id, user_id, session_id) "
                        "VALUES (:a, :u, :s)",
                        {"a": str(aid), "u": str(uid), "s": str(sid)},
                    ),
                    (
                        "INSERT INTO attempt_event (event_at, attempt_id, user_id) "
                        "VALUES (now(), :a, :u)",
                        {"a": str(aid), "u": str(uid)},
                    ),
                    (
                        "INSERT INTO attempt_event (event_at, attempt_id, user_id) "
                        "VALUES (now(), :a, :u)",
                        {"a": str(aid), "u": str(uid)},
                    ),
                ]
            )
        )
        # 사전 조건: attempt_event 2건 존재
        assert (
            asyncio.run(
                _count(
                    "SELECT count(*) FROM attempt_event WHERE attempt_id=:a",
                    {"a": str(aid)},
                )
            )
            == 2
        )
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            resp = client.delete(f"/v1/me/sessions/{sid}", headers=auth)
            assert resp.status_code == 204, resp.text
        # attempt CASCADE(slice 56) + 트리거(slice 59)로 attempt_event 고아도 제거(0)
        assert (
            asyncio.run(
                _count(
                    "SELECT count(*) FROM attempt_event WHERE attempt_id=:a",
                    {"a": str(aid)},
                )
            )
            == 0
        )
    finally:
        asyncio.run(
            _exec(
                [
                    ("DELETE FROM attempt_event WHERE attempt_id=:a", {"a": str(aid)}),
                    ("DELETE FROM problem_attempt WHERE attempt_id=:a", {"a": str(aid)}),
                    ("DELETE FROM learning_session WHERE session_id=:s", {"s": str(sid)}),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ]
            )
        )
