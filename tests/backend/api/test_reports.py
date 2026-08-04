"""결함 신고 API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic). RPT-01.

`test_problems.py`(concept 라우터 동형) 패턴을 따른다. 다른 점: `DefectReport`는 `report_id`/
`reported_at`을 **DB `server_default`**(gen_random_uuid()·now())로만 채운다(schema에
default_factory가 없다 — 클라이언트가 채울 수 없게 하기 위함). 실 PostgreSQL이라면
`session.refresh(obj)`가 이 값을 채워주지만, hermetic `FakeSession.refresh`는 실제 DB가 없으므로
*그 서버측 기본값 채움을 시뮬레이션*한다(다른 라우터 테스트의 no-op refresh와 다른 이유를
docstring에 명시).

실제 DB round-trip(진짜 `gen_random_uuid()`/`now()`)·rate limit 결선·append-only(PATCH/DELETE
부재)의 왕복 검증은 `test_reports_integration.py`(@integration·실 PG)가 담당한다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.app import create_app
from whymath_backend.db.models.audit import DefectReport
from whymath_backend.db.session import get_session


class FakeSession:
    """AsyncSession 표면 일부 모사 — 라우터가 부르는 메서드만.

    `refresh`는 다른 라우터 테스트(no-op)와 달리 **DB server_default를 시뮬레이션**한다 —
    `DefectReport`는 report_id/reported_at을 Python 쪽 default_factory가 아니라 DB
    `gen_random_uuid()`/`now()`로만 채우므로, 실 DB 없이는 이 값이 채워지는 지점이 refresh
    뿐이다(실 PG 왕복은 통합테스트가 검증).
    """

    def __init__(self, *, commit_error: Exception | None = None) -> None:
        self._commit_error = commit_error
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: DefectReport) -> None:
        # DB server_default 시뮬레이션(모듈 docstring 참조).
        if obj.report_id is None:
            obj.report_id = uuid.uuid4()
        if obj.reported_at is None:
            obj.reported_at = datetime.now(UTC)


def _client(fake: FakeSession) -> TestClient:
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


class TestCreateDefectReport:
    def test_minimal_body_returns_201_and_commits(self) -> None:
        fake = FakeSession()
        resp = _client(fake).post("/v1/reports/defects", json={"category": "수식오류"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["category"] == "수식오류"
        assert body["problem_id"] is None
        assert body["report_id"] is not None
        assert body["reported_at"] is not None
        assert fake.committed is True
        assert len(fake.added) == 1
        assert isinstance(fake.added[0], DefectReport)

    def test_with_problem_id_is_persisted(self) -> None:
        fake = FakeSession()
        pid = str(uuid.uuid4())
        resp = _client(fake).post(
            "/v1/reports/defects", json={"category": "오답의심", "problem_id": pid}
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["problem_id"] == pid
        assert fake.added[0].problem_id == uuid.UUID(pid)

    def test_no_auth_header_required(self) -> None:
        """무인증 표면 — Authorization 헤더 없이도 통과(`ConsentedUser` 등 인증 의존성 없음)."""
        fake = FakeSession()
        resp = _client(fake).post("/v1/reports/defects", json={"category": "UI문제"})
        assert resp.status_code == 201, resp.text

    def test_all_six_categories_accepted(self) -> None:
        for category in ["콘텐츠오류", "AI응답오류", "수식오류", "오답의심", "UI문제", "기타"]:
            fake = FakeSession()
            resp = _client(fake).post("/v1/reports/defects", json={"category": category})
            assert resp.status_code == 201, (category, resp.text)
            assert resp.json()["category"] == category

    def test_invalid_category_returns_422(self) -> None:
        fake = FakeSession()
        resp = _client(fake).post("/v1/reports/defects", json={"category": "존재하지않는카테고리"})
        assert resp.status_code == 422
        assert fake.committed is False

    def test_missing_category_returns_422(self) -> None:
        fake = FakeSession()
        resp = _client(fake).post("/v1/reports/defects", json={})
        assert resp.status_code == 422
        assert fake.committed is False

    def test_user_id_in_body_is_rejected_not_silently_dropped(self) -> None:
        """`extra=\"forbid\"` — user_id를 보내면 422(자유서술·신원 필드가 스키마에 아예 없음)."""
        fake = FakeSession()
        resp = _client(fake).post(
            "/v1/reports/defects",
            json={"category": "기타", "user_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422
        assert fake.committed is False

    def test_free_text_field_is_rejected(self) -> None:
        """자유서술 필드(예: `description`)도 스키마에 없어 422 — v0 범위 밖 동결."""
        fake = FakeSession()
        resp = _client(fake).post(
            "/v1/reports/defects",
            json={"category": "기타", "description": "자유서술 시도"},
        )
        assert resp.status_code == 422
        assert fake.committed is False

    def test_invalid_problem_id_returns_422(self) -> None:
        fake = FakeSession()
        resp = _client(fake).post(
            "/v1/reports/defects", json={"category": "기타", "problem_id": "not-a-uuid"}
        )
        assert resp.status_code == 422
        assert fake.committed is False


class TestAppendOnly:
    """append-only — PATCH/PUT/DELETE 라우터가 노출되지 않았음을 회귀 동결(RPT-01 설계)."""

    def test_no_update_or_delete_route_registered(self) -> None:
        app = create_app()
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        path_item = spec["paths"].get("/v1/reports/defects", {})
        assert set(path_item.keys()) == {"post"}, (
            f"append-only 원칙 위반 — /v1/reports/defects에 POST 외 메서드가 노출됨: "
            f"{set(path_item.keys())}"
        )

    def test_patch_and_delete_by_id_are_404_no_such_route(self) -> None:
        """id 하위 경로 자체가 없다 — 라우트 부재(404)로 확인(수정/삭제 표면 자체가 없음)."""
        fake = FakeSession()
        client = _client(fake)
        some_id = str(uuid.uuid4())
        assert client.patch(f"/v1/reports/defects/{some_id}", json={}).status_code == 404
        assert client.delete(f"/v1/reports/defects/{some_id}").status_code == 404

    def test_collection_path_rejects_get(self) -> None:
        """GET(목록 조회)도 노출하지 않는다 — v0는 접수(POST)만(405, 경로는 존재)."""
        fake = FakeSession()
        resp = _client(fake).get("/v1/reports/defects")
        assert resp.status_code == 405
