"""concept API 통합테스트 — 실제 PostgreSQL 왕복 (기본 SKIP, Phaiakes9/로컬 전용).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG(마이그레이션 head 적용, WHYMATH_DATABASE_URL)
에서만 실행한다. CI는 이 변수를 설정하지 않아 conftest 게이트가 자동 skip한다. PG 미도달
시에도 graceful skip(redis 통합테스트와 동일 패턴).

검증: POST → GET(단건) → 중복 POST(409) → GET(목록)이 *실 PG*에서 HTTP→get_session→PG로
왕복하는지 — 영속 레이어(ORM·마이그레이션)를 HTTP 표면까지 end-to-end로 결선했음을 증명.
TestClient를 컨텍스트매니저로 써 lifespan(종료 시 dispose_engine)도 함께 발화시킨다.

설정/정리는 전역 캐시 엔진이 아니라 *독립 엔진*으로 수행한다 — TestClient가 자기 이벤트
루프에서 만든 전역 엔진과 루프가 충돌하지 않도록(asyncpg 엔진은 루프 바인딩).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings

pytestmark = pytest.mark.integration


async def _pg_reachable() -> bool:
    """독립 엔진으로 SELECT 1 — 도달 가능하면 True(실패는 False)."""
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _delete_concept(concept_id: uuid.UUID) -> None:
    """테스트가 만든 행을 독립 엔진으로 정리(잔여 방지)."""
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = :cid"),
                {"cid": str(concept_id)},
            )
    finally:
        await engine.dispose()


def test_concept_crud_roundtrip_on_live_pg() -> None:
    """POST→GET→중복(409)→목록이 실 PG에서 HTTP→get_session→PG로 왕복한다."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    code = f"TEST-CONCEPT-{uuid.uuid4().hex[:8]}"
    body = {"code": code, "name_ko": "통합테스트 개념", "level": "세부개념"}
    concept_id: str | None = None
    try:
        with TestClient(create_app()) as client:
            # CREATE → 201
            created = client.post("/v1/concepts", json=body)
            assert created.status_code == 201, created.text
            payload = created.json()
            assert payload["code"] == code
            concept_id = payload["concept_id"]

            # READ → 200, 내용 일치
            got = client.get(f"/v1/concepts/{concept_id}")
            assert got.status_code == 200
            assert got.json()["name_ko"] == "통합테스트 개념"

            # 중복 code POST → 409(UNIQUE 충돌)
            dup = client.post("/v1/concepts", json=body)
            assert dup.status_code == 409, dup.text

            # LIST → 200, 방금 만든 code 포함
            listed = client.get("/v1/concepts?limit=200")
            assert listed.status_code == 200
            assert code in {item["code"] for item in listed.json()}
    finally:
        if concept_id is not None:
            asyncio.run(_delete_concept(uuid.UUID(concept_id)))
