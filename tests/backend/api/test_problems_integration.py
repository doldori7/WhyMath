"""problem API 통합테스트 — 실 PostgreSQL 왕복 (기본 SKIP).

test_concepts_integration.py와 동일 게이트(`@integration`·`WHYMATH_RUN_INTEGRATION=1`·PG
도달성 skip). POST→GET→목록(subject 필터)이 실 PG에서 HTTP→get_session→PG로 왕복하는지 검증.
설정/정리는 독립 엔진으로(전역 캐시 엔진 루프 충돌 회피).
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


def _body(subject: str = "미적분") -> dict[str, object]:
    return {
        "source_type": "자체생성",
        "curriculum_version": "2015_REVISION",
        "valid_from_year": 2014,
        "subject": subject,
        "unit_codes": ["CAL-INT-DEF"],
    }


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


async def _delete_problem(problem_id: uuid.UUID) -> None:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM problem WHERE problem_id = :pid"),
                {"pid": str(problem_id)},
            )
    finally:
        await engine.dispose()


def test_problem_crud_roundtrip_on_live_pg() -> None:
    """POST→GET→subject 목록이 실 PG에서 왕복한다."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    problem_id: str | None = None
    try:
        with TestClient(create_app()) as client:
            created = client.post("/v1/problems", json=_body())
            assert created.status_code == 201, created.text
            payload = created.json()
            assert payload["subject"] == "미적분"
            problem_id = payload["problem_id"]

            got = client.get(f"/v1/problems/{problem_id}")
            assert got.status_code == 200
            assert got.json()["source_type"] == "자체생성"

            listed = client.get("/v1/problems?subject=미적분&limit=200")
            assert listed.status_code == 200
            assert problem_id in {item["problem_id"] for item in listed.json()}

            # 다른 과목 필터엔 안 잡혀야(필터 SQL 동작 확인)
            other = client.get("/v1/problems?subject=기하&limit=200")
            assert other.status_code == 200
            assert problem_id not in {item["problem_id"] for item in other.json()}
    finally:
        if problem_id is not None:
            asyncio.run(_delete_problem(uuid.UUID(problem_id)))
