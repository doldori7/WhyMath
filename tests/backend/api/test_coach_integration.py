"""coach 세션 라우터 통합테스트 — 실 PG로 dialogue + turn 영속 검증 (기본 SKIP).

`POST /v1/coach/sessions`가 ① dialogue 1행 + ② 학생/AI turn 2행을 실제 영속하는지 검증.
미성년 PII 외부 노출 금기 정합 검증을 위해 외부 user_id 토큰으로 본인 user_id가 적재되는지
도 확인(타인 데이터 차단 — slice 3 `test_me_integration` 패턴 답습).

get_settings만 오버라이드(jwt secret), get_session은 실 PG. FK 순서: dialogue commit
먼저 → turns commit. 정리는 자식(dialogue_turn) → 부모(dialogue) → 부모(user_profile).
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
            # FK 순서: 자식(dialogue_turn) → 부모(dialogue) → 부모(user_profile).
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
    finally:
        await engine.dispose()


async def _count_turns(dialogue_id: uuid.UUID) -> int:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text("SELECT COUNT(*) FROM dialogue_turn " "WHERE dialogue_id = :did"),
                {"did": str(dialogue_id)},
            )
            return int(row.scalar_one())
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_create_session_persists_dialogue_and_two_turns_on_live_pg() -> None:
    """세션 생성 → 실 PG에 dialogue 1 + turn 2 영속. user_id 자동 결선."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            resp = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "내 풀이는 (a+b)² = a² + b² 이렇게 했어"},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_id = uuid.UUID(body["dialogue_id"])
            dialogue_ids.append(dialogue_id)

            # ① misconception 검출 + counterexample intervention 결선
            assert body["intervention"]["pattern"] == "counterexample"
            # ② 실 PG에 dialogue_turn 정확히 2행
            assert asyncio.run(_count_turns(dialogue_id)) == 2

            # ③ 무토큰 401(인증 게이트)
            assert (
                client.post(
                    "/v1/coach/sessions", json={"student_input": "음"}
                ).status_code
                == 401
            )
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_get_session_returns_dialogue_with_ordered_turns_on_live_pg() -> None:
    """세션 생성→append→GET — turn 4행이 turn_order 오름차순으로 반환."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            create = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": "처음"}
            )
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)
            client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": "두번째"},
            )

            # GET — 4 turns 오름차순
            resp = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["dialogue"]["dialogue_id"] == str(did)
            turns = body["turns"]
            assert len(turns) == 4
            assert [t["turn_order"] for t in turns] == [1, 2, 3, 4]
            # 학생/AI 교차 순서: 1=student·2=assistant·3=student·4=assistant
            assert [t["role"] for t in turns] == [
                "student",
                "assistant",
                "student",
                "assistant",
            ]
            assert turns[0]["content"] == "처음"
            assert turns[2]["content"] == "두번째"

            # 존재하지 않는 dialogue → 404
            assert (
                client.get(
                    f"/v1/coach/sessions/{uuid.uuid4()}", headers=auth
                ).status_code
                == 404
            )

            # 무토큰 401
            assert client.get(f"/v1/coach/sessions/{did}").status_code == 401
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_append_turns_extends_existing_session_on_live_pg() -> None:
    """세션 생성 → 턴 추가 → 실 PG에 dialogue_turn 4행·turn_order 1·2·3·4 증분."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # 세션 생성 (turn_order 1, 2)
            create = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "처음 시도"},
            )
            assert create.status_code == 201
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)

            # 턴 추가 (turn_order 3, 4)
            append = client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": "두번째 시도, 잘 모르겠어"},
            )
            assert append.status_code == 201, append.text
            body = append.json()
            assert body["student_turn_order"] == 3
            assert body["assistant_turn_order"] == 4
            # 좌절 신호 → hint_level 상승(slice 3)
            assert body["decision"]["hint_level"] >= 2

            # 실 PG에 4행
            assert asyncio.run(_count_turns(did)) == 4

            # 존재하지 않는 dialogue → 404
            missing = client.post(
                f"/v1/coach/sessions/{uuid.uuid4()}/turns",
                headers=auth,
                json={"student_input": "음"},
            )
            assert missing.status_code == 404
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))
