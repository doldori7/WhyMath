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


async def _insert_edge(from_id: uuid.UUID, to_id: uuid.UUID) -> None:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO concept_edge (from_concept_id, to_concept_id, edge_type) "
                    "VALUES (:f, :t, 'PREREQUISITE')"
                ),
                {"f": str(from_id), "t": str(to_id)},
            )
    finally:
        await engine.dispose()


async def _delete_concepts_and_edges(concept_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(Settings().database_url)
    ids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: 엣지 먼저, 그다음 노드
            await conn.execute(
                text(
                    "DELETE FROM concept_edge WHERE from_concept_id = ANY(:ids) "
                    "OR to_concept_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:ids)"),
                {"ids": ids},
            )
    finally:
        await engine.dispose()


def test_concept_edges_nested_read_on_live_pg() -> None:
    """GET /concepts/{id}/edges가 outgoing 엣지를 실 PG에서 반환·방향·404 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    suffix = uuid.uuid4().hex[:8]
    ids: list[str] = []
    try:
        with TestClient(create_app()) as client:
            a = client.post(
                "/v1/concepts",
                json={"code": f"CG-A-{suffix}", "name_ko": "가", "level": "단원"},
            ).json()["concept_id"]
            b = client.post(
                "/v1/concepts",
                json={"code": f"CG-B-{suffix}", "name_ko": "나", "level": "단원"},
            ).json()["concept_id"]
            ids = [a, b]
            asyncio.run(_insert_edge(uuid.UUID(a), uuid.UUID(b)))

            # a의 나가는 엣지 1건(→b)
            edges = client.get(f"/v1/concepts/{a}/edges")
            assert edges.status_code == 200
            body = edges.json()
            assert len(body) == 1
            assert body[0]["to_concept_id"] == b

            # b는 나가는 엣지 없음 → [](방향성 확인)
            assert client.get(f"/v1/concepts/{b}/edges").json() == []

            # 없는 개념 → 404
            assert client.get(f"/v1/concepts/{uuid.uuid4()}/edges").status_code == 404
    finally:
        if ids:
            asyncio.run(_delete_concepts_and_edges([uuid.UUID(c) for c in ids]))


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


def test_concept_patch_delete_roundtrip_on_live_pg() -> None:
    """POST→PATCH(부분수정)→GET(반영확인)→DELETE(204)→GET(404)이 실 PG에서 왕복."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    code = f"TEST-PATCH-{uuid.uuid4().hex[:8]}"
    concept_id: str | None = None
    deleted = False
    try:
        with TestClient(create_app()) as client:
            concept_id = client.post(
                "/v1/concepts", json={"code": code, "name_ko": "원본", "level": "단원"}
            ).json()["concept_id"]

            # PATCH: name_en만 추가(부분 수정), 병합 재검증
            patched = client.patch(
                f"/v1/concepts/{concept_id}", json={"name_en": "Patched"}
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["name_en"] == "Patched"
            assert patched.json()["name_ko"] == "원본"  # 기존 필드 보존

            # GET으로 영속 반영 확인
            assert (
                client.get(f"/v1/concepts/{concept_id}").json()["name_en"] == "Patched"
            )

            # DELETE → 204, 이후 GET → 404
            assert client.delete(f"/v1/concepts/{concept_id}").status_code == 204
            deleted = True
            assert client.get(f"/v1/concepts/{concept_id}").status_code == 404
    finally:
        if concept_id is not None and not deleted:
            asyncio.run(_delete_concept(uuid.UUID(concept_id)))


def test_concept_optimistic_lock_on_live_pg() -> None:
    """GET ETag로 PATCH→200·ETag 갱신→옛 ETag 재PATCH→412(동시수정 차단)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    code = f"TEST-LOCK-{uuid.uuid4().hex[:8]}"
    concept_id: str | None = None
    try:
        with TestClient(create_app()) as client:
            created = client.post(
                "/v1/concepts", json={"code": code, "name_ko": "원본", "level": "단원"}
            )
            concept_id = created.json()["concept_id"]
            etag1 = client.get(f"/v1/concepts/{concept_id}").headers["ETag"]

            # 일치 If-Match → 200, ETag가 새 값으로 바뀜
            patched = client.patch(
                f"/v1/concepts/{concept_id}",
                json={"name_en": "First"},
                headers={"If-Match": etag1},
            )
            assert patched.status_code == 200
            etag2 = patched.headers["ETag"]
            assert etag2 != etag1

            # 옛 ETag(etag1)로 다시 PATCH → 412(그사이 변경됨)
            stale = client.patch(
                f"/v1/concepts/{concept_id}",
                json={"name_en": "Second"},
                headers={"If-Match": etag1},
            )
            assert stale.status_code == 412
            # 412 후 내용 미변경 확인
            assert client.get(f"/v1/concepts/{concept_id}").json()["name_en"] == "First"
    finally:
        if concept_id is not None:
            asyncio.run(_delete_concept(uuid.UUID(concept_id)))


def test_concept_conditional_get_304_on_live_pg() -> None:
    """GET ETag→If-None-Match로 GET→304→PATCH 변경 후 옛 ETag→200(내용 바뀜)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    code = f"TEST-INM-{uuid.uuid4().hex[:8]}"
    concept_id: str | None = None
    try:
        with TestClient(create_app()) as client:
            concept_id = client.post(
                "/v1/concepts", json={"code": code, "name_ko": "원본", "level": "단원"}
            ).json()["concept_id"]
            etag = client.get(f"/v1/concepts/{concept_id}").headers["ETag"]

            # 변하지 않았으면 304(빈 본문)
            not_mod = client.get(
                f"/v1/concepts/{concept_id}", headers={"If-None-Match": etag}
            )
            assert not_mod.status_code == 304
            assert not_mod.content == b""

            # PATCH로 내용 변경 → 옛 ETag로 조건부 GET은 이제 200(본문)
            client.patch(f"/v1/concepts/{concept_id}", json={"name_en": "Changed"})
            refetched = client.get(
                f"/v1/concepts/{concept_id}", headers={"If-None-Match": etag}
            )
            assert refetched.status_code == 200
            assert refetched.json()["name_en"] == "Changed"
    finally:
        if concept_id is not None:
            asyncio.run(_delete_concept(uuid.UUID(concept_id)))
