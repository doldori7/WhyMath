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


async def _insert_step(problem_id: uuid.UUID, order: int, title: str) -> None:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO problem_step (problem_id, step_order, step_title) "
                    "VALUES (:pid, :ord, :title)"
                ),
                {"pid": str(problem_id), "ord": order, "title": title},
            )
    finally:
        await engine.dispose()


async def _delete_steps(problem_id: uuid.UUID) -> None:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM problem_step WHERE problem_id = :pid"),
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


def test_problem_steps_nested_read_on_live_pg() -> None:
    """GET /problems/{id}/steps가 step_order 순으로 실 PG에서 반환·404·빈 relations."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    problem_id: str | None = None
    try:
        with TestClient(create_app()) as client:
            problem_id = client.post("/v1/problems", json=_body()).json()["problem_id"]
            # 단계 2건을 역순(2→1)으로 삽입 → 엔드포인트가 step_order로 정렬하는지 확인
            asyncio.run(_insert_step(uuid.UUID(problem_id), 2, "둘째 단계"))
            asyncio.run(_insert_step(uuid.UUID(problem_id), 1, "첫째 단계"))

            steps = client.get(f"/v1/problems/{problem_id}/steps")
            assert steps.status_code == 200
            assert [s["step_order"] for s in steps.json()] == [1, 2]

            # relations는 0건 → 200 + []
            rels = client.get(f"/v1/problems/{problem_id}/relations")
            assert rels.status_code == 200
            assert rels.json() == []

            # 없는 문제의 하위 리소스 → 404
            assert client.get(f"/v1/problems/{uuid.uuid4()}/steps").status_code == 404
    finally:
        if problem_id is not None:
            asyncio.run(_delete_steps(uuid.UUID(problem_id)))
            asyncio.run(_delete_problem(uuid.UUID(problem_id)))


def test_problem_patch_delete_roundtrip_on_live_pg() -> None:
    """POST→PATCH→GET→DELETE(204)→GET(404)이 실 PG에서 왕복."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    problem_id: str | None = None
    deleted = False
    try:
        with TestClient(create_app()) as client:
            problem_id = client.post("/v1/problems", json=_body()).json()["problem_id"]

            patched = client.patch(f"/v1/problems/{problem_id}", json={"answer": "42"})
            assert patched.status_code == 200, patched.text
            assert patched.json()["answer"] == "42"
            assert patched.json()["subject"] == "미적분"  # 기존 필드 보존

            assert client.get(f"/v1/problems/{problem_id}").json()["answer"] == "42"

            assert client.delete(f"/v1/problems/{problem_id}").status_code == 204
            deleted = True
            assert client.get(f"/v1/problems/{problem_id}").status_code == 404
    finally:
        if problem_id is not None and not deleted:
            asyncio.run(_delete_problem(uuid.UUID(problem_id)))
