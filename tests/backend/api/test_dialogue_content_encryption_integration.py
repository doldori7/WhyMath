"""미성년 대화 본문 봉투 암호화 통합테스트 — 실 PG (감사상환 #2·기본 SKIP).

키 설정 시: `POST /v1/coach/sessions` write가 DB `content=NULL`·`content_encrypted=bytes`로
저장(평문 원문 부재), GET·export가 복호해 원문 반환. 키 미설정 시: 평문 폴백 왕복(기존 배포·CI
무영향·회귀 0). 백필: 평문 행을 배치 재암호화 후 복호 왕복.

get_settings 캐시: 코치 핸들러·export는 *직접* `get_settings()`(env 기반·lru_cache)를 부르고
auth만 Depends 오버라이드를 쓴다(기존 통합테스트 아키텍처). 따라서 대화 키는 **env + cache_clear**
로 주입하고, auth jwt는 dependency_overrides로 준다. finally에서 env·캐시를 원복(격리).
"""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.privacy.dialogue_content_backfill import (
    reencrypt_plaintext_dialogue_content,
)
from whymath_backend.privacy.export import export_user_data
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_ENC_KEY_B64 = base64.b64encode(os.urandom(32)).decode()
_STUDENT_TEXT = "내 풀이는 (a+b)² = a² + b² 이렇게 했어"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


@contextmanager
def _dialogue_key_env(key_b64: str | None) -> Iterator[None]:
    """대화 본문 암호화 키를 env로 주입(또는 제거)하고 get_settings 캐시를 리셋·원복."""
    var = "WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY"
    prev = os.environ.get(var)
    if key_b64 is None:
        os.environ.pop(var, None)
    else:
        os.environ[var] = key_b64
    get_settings.cache_clear()
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = prev
        get_settings.cache_clear()


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


async def _add_user(uid: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                UserProfile.from_schema(
                    UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID, dialogue_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    dids = [str(d) for d in dialogue_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"), {"ids": dids}
            )
            await conn.execute(
                text("DELETE FROM attempt_event WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"), {"ids": dids}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(uid)}
            )
    finally:
        await engine.dispose()


async def _turn_storage(
    dialogue_id: uuid.UUID,
) -> list[tuple[str | None, bytes | None, bytes | None]]:
    """dialogue_turn의 (content, content_encrypted, content_nonce) 원시 저장 표현(turn_order순)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT content, content_encrypted, content_nonce FROM dialogue_turn "
                    "WHERE dialogue_id = :did ORDER BY turn_order"
                ),
                {"did": str(dialogue_id)},
            )
            out: list[tuple[str | None, bytes | None, bytes | None]] = []
            for r in rows.all():
                enc = bytes(r[1]) if r[1] is not None else None
                nonce = bytes(r[2]) if r[2] is not None else None
                out.append((r[0], enc, nonce))
            return out
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_key_set_stores_ciphertext_and_reads_plaintext_on_live_pg() -> None:
    """키 설정 시: DB content=NULL·content_encrypted=bytes(프라이버시 단언)·GET/export 복호 원문."""  # noqa: E501
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _dialogue_key_env(_ENC_KEY_B64), _client() as client:
            resp = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": _STUDENT_TEXT}
            )
            assert resp.status_code == 201, resp.text
            did = uuid.UUID(resp.json()["dialogue_id"])
            dialogue_ids.append(did)

            # 프라이버시 단언: 평문 content 컬럼은 NULL, content_encrypted는 bytes(원문 부재).
            storage = asyncio.run(_turn_storage(did))
            assert len(storage) == 2
            for content, encrypted, nonce in storage:
                assert content is None
                assert isinstance(encrypted, bytes) and len(encrypted) > 0
                assert isinstance(nonce, bytes) and len(nonce) == 12

            # GET이 복호해 학생 원문을 그대로 반환(student 턴 = turn_order 1).
            got = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert got.status_code == 200
            turns = got.json()["turns"]
            assert turns[0]["content"] == _STUDENT_TEXT

            # export도 복호해 원문 반환(본인 열람권).
            engine = create_async_engine(_settings().database_url)
            try:

                async def _export() -> object:
                    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
                        return await export_user_data(s, user_id=uid)

                exported = asyncio.run(_export())
            finally:
                asyncio.run(engine.dispose())
            contents = [t["content"] for t in exported.data["dialogue_turns"]]  # type: ignore[attr-defined]
            assert _STUDENT_TEXT in contents
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_key_unset_plaintext_fallback_round_trip_on_live_pg() -> None:
    """키 미설정 시: content 평문 저장·GET 평문 반환(기존 배포·CI 무영향·회귀 0)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _dialogue_key_env(None), _client() as client:
            resp = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": _STUDENT_TEXT}
            )
            assert resp.status_code == 201, resp.text
            did = uuid.UUID(resp.json()["dialogue_id"])
            dialogue_ids.append(did)

            storage = asyncio.run(_turn_storage(did))
            assert storage[0][0] == _STUDENT_TEXT  # content 평문 저장
            assert storage[0][1] is None and storage[0][2] is None  # 암호화 컬럼 미사용

            got = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert got.json()["turns"][0]["content"] == _STUDENT_TEXT
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_backfill_reencrypts_plaintext_rows_on_live_pg() -> None:
    """백필: 평문 저장 행을 배치 재암호화 → content=NULL·content_encrypted 세팅·복호 왕복."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        # 1) 키 미설정으로 평문 행 생성.
        with _dialogue_key_env(None), _client() as client:
            resp = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": _STUDENT_TEXT}
            )
            did = uuid.UUID(resp.json()["dialogue_id"])
            dialogue_ids.append(did)
        pre = asyncio.run(_turn_storage(did))
        assert pre[0][0] == _STUDENT_TEXT and pre[0][1] is None  # 평문 잔존

        # 2) 키 도입 후 백필 배치 → 평문 행 재암호화.
        from whymath_backend.api._crypto import build_dialogue_content_cipher

        with _dialogue_key_env(_ENC_KEY_B64):
            cipher = build_dialogue_content_cipher(get_settings())
            assert cipher is not None
            engine = create_async_engine(_settings().database_url)

            async def _run_backfill() -> int:
                total = 0
                while True:
                    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
                        n = await reencrypt_plaintext_dialogue_content(s, cipher, batch_size=1)
                    total += n
                    if n == 0:
                        break
                return total

            try:
                reencrypted = asyncio.run(_run_backfill())
            finally:
                asyncio.run(engine.dispose())
            assert reencrypted >= 2  # 학생/AI 2턴 이상 재암호화

            # 3) 재암호화 후 content=NULL·content_encrypted 세팅·GET 복호 원문.
            post = asyncio.run(_turn_storage(did))
            for content, encrypted, nonce in post:
                assert content is None
                assert isinstance(encrypted, bytes) and isinstance(nonce, bytes)
            with _client() as client:
                got = client.get(f"/v1/coach/sessions/{did}", headers=auth)
                assert got.json()["turns"][0]["content"] == _STUDENT_TEXT
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))
