"""결함 신고 API 통합테스트 — 실 PostgreSQL 왕복 (기본 SKIP). RPT-01.

`test_audit_integration.py`(GDPR 삭제 감사)와 동일 게이트(`@integration`·
`WHYMATH_RUN_INTEGRATION=1`·PG 도달성 skip). 이 파일이 acceptance의 **변별력 실측**을
직접 수행한다:

  ① 앱 버튼(POST) 1회 → `defect_report` 1행 적재를 실측(`test_single_post_appends_exactly_one_row`).
  ② append-only라 "철회"(0행 복귀) 경로 자체가 없다 — 이 설계 결정을 `TestNoRevertPath`가
     실측 확인한다(PATCH/DELETE가 라우트 자체로 존재하지 않음 → 405/404, 어떤 경로도 행을
     지우지 못함). "철회 기능을 새로 만들라"는 뜻이 아니라 **철회 부재 자체가 설계**임을
     확인하는 것이다.
  ③(qa_pipeline 이중 회계 실측)은 `tests/backend/harness/test_qa_pipeline.py`의
     `TestAxisDefectReportIntake`가 담당한다(no_snapshot/ok+0/error 세 상태를 세션 팩토리
     주입으로 결정론적으로 재현) — 이 파일은 실 PG 왕복(①②)에 집중한다.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings

pytestmark = pytest.mark.integration

_JWT_SECRET = "reports-integration-jwt-secret-0123456789ab"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_JWT_SECRET))


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


async def _fetchall(sql: str, params: dict[str, object]) -> list[tuple[object, ...]]:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return [tuple(row) for row in result.all()]
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


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    with TestClient(app) as c:
        yield c


# 이 파일이 만든 신고는 category에 고유 마커를 섞어 다른 병렬 테스트/실행과 행을 구분한다
# (problem_id로 스코프 — 다른 테스트가 같은 테이블을 공유해도 서로 다른 problem_id로 격리).


def test_single_post_appends_exactly_one_row(client: TestClient) -> None:
    """① 앱 버튼(POST) 1회 → `defect_report` 1행 적재 실측."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — WHYMATH_DATABASE_URL 확인")

    problem_id = uuid.uuid4()
    try:
        resp = client.post(
            "/v1/reports/defects",
            json={"category": "수식오류", "problem_id": str(problem_id)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["category"] == "수식오류"
        assert body["problem_id"] == str(problem_id)
        assert body["report_id"] is not None
        assert body["reported_at"] is not None

        rows = asyncio.run(
            _fetchall(
                "SELECT category, problem_id, reported_at FROM defect_report WHERE problem_id=:p",
                {"p": str(problem_id)},
            )
        )
        assert len(rows) == 1, f"버튼 1회 POST가 정확히 1행을 적재해야 한다(실측 {len(rows)}행)"
        assert rows[0][0] == "수식오류"
        assert str(rows[0][1]) == str(problem_id)
        assert rows[0][2] is not None
        # user_id 컬럼 자체가 없다 — 이 컬럼을 조회하면 UndefinedColumn(설계 재확인).
    finally:
        asyncio.run(
            _exec([("DELETE FROM defect_report WHERE problem_id=:p", {"p": str(problem_id)})])
        )


def test_report_id_is_server_generated_and_unique_per_post(client: TestClient) -> None:
    """서버가 매 POST마다 새 report_id를 생성 — 클라이언트가 지정할 수 없다(스키마에 필드 없음)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — WHYMATH_DATABASE_URL 확인")

    problem_id = uuid.uuid4()
    try:
        r1 = client.post(
            "/v1/reports/defects", json={"category": "기타", "problem_id": str(problem_id)}
        )
        r2 = client.post(
            "/v1/reports/defects", json={"category": "기타", "problem_id": str(problem_id)}
        )
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["report_id"] != r2.json()["report_id"]

        rows = asyncio.run(
            _fetchall(
                "SELECT report_id FROM defect_report WHERE problem_id=:p",
                {"p": str(problem_id)},
            )
        )
        assert len(rows) == 2, "동일 problem_id에 대해 신고 2건이 각각 별도 행으로 적재돼야 한다"
    finally:
        asyncio.run(
            _exec([("DELETE FROM defect_report WHERE problem_id=:p", {"p": str(problem_id)})])
        )


def test_user_id_column_does_not_exist_in_live_schema() -> None:
    """실 PG 스키마에도 `user_id` 컬럼이 없다(ORM 동결 테스트의 실측 대응짝)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — WHYMATH_DATABASE_URL 확인")

    rows = asyncio.run(
        _fetchall(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='defect_report'",
            {},
        )
    )
    columns = {r[0] for r in rows}
    assert "user_id" not in columns
    assert columns == {"report_id", "category", "problem_id", "reported_at"}


class TestNoRevertPath:
    """② append-only — "철회"(0행 복귀) 경로가 존재하지 않음을 실측 확인.

    새 철회 기능을 만들라는 뜻이 아니다(태스크 명세) — append-only 설계상 되돌리는 API 자체가
    없다는 *부재*를 실측으로 고정한다. 어떤 HTTP 경로로도 이미 적재된 행을 지울 수 없다.
    """

    def test_no_delete_or_patch_route_reduces_row_count(self, client: TestClient) -> None:
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — WHYMATH_DATABASE_URL 확인")

        problem_id = uuid.uuid4()
        try:
            resp = client.post(
                "/v1/reports/defects", json={"category": "UI문제", "problem_id": str(problem_id)}
            )
            assert resp.status_code == 201
            report_id = resp.json()["report_id"]

            before = asyncio.run(
                _fetchall(
                    "SELECT count(*) FROM defect_report WHERE problem_id=:p",
                    {"p": str(problem_id)},
                )
            )[0][0]
            assert before == 1

            # 철회를 시도할 만한 모든 경로가 404/405(라우트 자체가 없음) — 어느 것도 행을
            # 지우지 못한다.
            assert client.delete(f"/v1/reports/defects/{report_id}").status_code == 404
            assert client.patch(f"/v1/reports/defects/{report_id}", json={}).status_code == 404
            assert client.delete("/v1/reports/defects").status_code == 405

            after = asyncio.run(
                _fetchall(
                    "SELECT count(*) FROM defect_report WHERE problem_id=:p",
                    {"p": str(problem_id)},
                )
            )[0][0]
            assert after == 1, "철회 경로가 없으므로 행 수는 POST 이전과 동일하게 유지돼야 한다"
        finally:
            asyncio.run(
                _exec([("DELETE FROM defect_report WHERE problem_id=:p", {"p": str(problem_id)})])
            )
