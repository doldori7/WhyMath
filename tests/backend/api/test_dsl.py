"""DSL API 통합 테스트."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_current_user
from whymath_backend.app import create_app
from whymath_backend.db.session import get_session


class _FakeResult:
    """`get_alignments`가 읽는 다중 컬럼 행 결과(CUR-12 — 라이브 PG 불요)."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """execute 큐 기반 AsyncSession 모사 — 큐가 비면 빈 결과(축 조회 0건)."""

    def __init__(self, execute_queue: list[list[Any]] | None = None) -> None:
        self._queue = list(execute_queue or [])
        self.execute_calls = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        self.execute_calls += 1
        if not self._queue:
            return _FakeResult([])
        return _FakeResult(self._queue.pop(0))


def _make_test_user():
    user = MagicMock()
    user.user_id = uuid4()
    user.is_active = True
    user.is_deleted = False
    user.is_minor = False
    user.role = "student"
    return user


@pytest.fixture
def app():
    return create_app()


def _override_session(app, fake: _FakeSession) -> None:
    """세션 의존성 주입 — /v1/dsl/generate는 CUR-12 정렬 조회 때문에 세션을 받는다."""

    async def _yield() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _yield


@pytest.fixture
def client(app):
    # 인증 의존성 오버라이드
    app.dependency_overrides[get_current_user] = lambda: _make_test_user()
    # 정렬 조회는 기본 빈 결과(정렬 미착지) — 채워지는 경로는 별도 테스트가 대조군으로 덮는다.
    _override_session(app, _FakeSession())
    return TestClient(app)


def test_generate_endpoint_exists(client: TestClient) -> None:
    response = client.post(
        "/v1/dsl/generate",
        json={
            "spec": {
                "subject": "mathematics",
                "grade": "middle_2",
                "concept": "linear_equation",
                "difficulty": 3,
                "count": 1,
                "purpose": "practice",
            }
        },
    )
    assert response.status_code in (200, 201)
    data = response.json()
    assert "generation_id" in data
    assert "contents" in data


class TestGenerateCurriculumAlignment:
    """CUR-12 — 생성 표면이 통합 함수(`get_alignments`)를 경유해 성취기준을 싣는가.

    변별력 양방향: 정렬이 없으면 빈 채로 남고(정직한 결과), 있으면 실린다. 한쪽만 보면
    "항상 비어 있는 슬롯"과 구분되지 않는다.
    """

    def _post(self, client: TestClient) -> dict[str, Any]:
        response = client.post(
            "/v1/dsl/generate",
            json={
                "spec": {
                    "subject": "mathematics",
                    "grade": "middle_2",
                    "concept": "2수01-01-1",
                    "difficulty": 3,
                    "count": 1,
                    "purpose": "practice",
                }
            },
        )
        assert response.status_code in (200, 201), response.text
        body: dict[str, Any] = response.json()
        return body

    def test_no_alignment_leaves_codes_empty(self, app) -> None:
        """정렬 0건 → 빈 튜플. 0%를 가짜 코드로 채우지 않는다."""
        app.dependency_overrides[get_current_user] = lambda: _make_test_user()
        _override_session(app, _FakeSession())
        body = self._post(TestClient(app))
        assert body["contents"][0]["curriculum"]["standard_codes"] == []

    def test_alignment_hit_populates_codes(self, app) -> None:
        """정렬이 있으면 실린다 — 정렬·중복 제거된 결정론 순서로."""
        app.dependency_overrides[get_current_user] = lambda: _make_test_user()
        # 축 순서(2축 curriculum_entry → 3축 atom_node)대로 큐잉.
        entry = MagicMock()
        entry.concept_id = "2수01-01-1"
        entry.national_standard_codes = ["[2수01-03]"]
        entry.framework_id = "KR_NC_2022"
        fake = _FakeSession(
            execute_queue=[
                [(entry, None)],  # 2축: (CurriculumEntry, concept_id)
                [("2수01-01-1", ["[2수01-02]", "[2수01-01]"], None)],  # 3축 열 순서
            ]
        )
        _override_session(app, fake)

        body = self._post(TestClient(app))

        assert body["contents"][0]["curriculum"]["standard_codes"] == [
            "[2수01-01]",
            "[2수01-02]",
            "[2수01-03]",
        ]
        assert fake.execute_calls == 2  # 요청 축 2개 = 쿼리 2회

    def test_norm_id_vocabulary_never_leaks_into_the_slot(self, app) -> None:
        """#933 리뷰 P2 — `2022_...`(norm_id)가 슬롯에 섞이면 어느 쪽 조회도 성립하지 않는다.

        생성 표면은 official_code 축만 조회하고 `kind` 필터까지 건다(이중 방어). 이 테스트는
        그 계약이 풀렸을 때 실제로 실패한다 — 축 집합에 concept_standard_link가 다시 들어가면
        norm_id가 새어 나온다.
        """
        app.dependency_overrides[get_current_user] = lambda: _make_test_user()
        # 큐에 norm_id를 내는 링크 행을 *일부러* 섞어 둔다. 요청 축이 official_code 계열
        # 2개뿐이므로 이 행은 2축 자리에서 소비되지만, kind 필터가 norm_id를 걸러낸다.
        link = MagicMock()
        link.concept_id = "2수01-01-1"
        link.national_standard_codes = ["[2수01-09]"]
        link.framework_id = None
        fake = _FakeSession(
            execute_queue=[
                [(link, None)],
                [("2수01-01-1", ["[2수01-01]"], None)],
            ]
        )
        _override_session(app, fake)

        codes = self._post(TestClient(app))["contents"][0]["curriculum"]["standard_codes"]

        assert codes  # 비어 있으면 이 테스트가 아무것도 검사하지 못한다(자기검사)
        assert all(code.startswith("[") for code in codes), codes


def test_validate_endpoint_exists(client: TestClient) -> None:
    response = client.post(
        "/v1/dsl/validate",
        json={
            "dsl": {
                "content_id": "TEST-API-001",
                "curriculum": {
                    "subject": "mathematics",
                    "grade": "middle_2",
                    "concept": "linear_equation",
                },
                "difficulty": {"level": 3},
                "problem": {"statement": "x + 2 = 5"},
                "answer": {"type": "integer", "value": "3"},
            }
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert data["report"]["syntax"] == "PASS"


def test_compile_endpoint_exists(client: TestClient) -> None:
    response = client.post(
        "/v1/dsl/compile",
        json={
            "dsl": {
                "content_id": "TEST-API-002",
                "curriculum": {
                    "subject": "mathematics",
                    "grade": "middle_2",
                    "concept": "linear_equation",
                },
                "difficulty": {"level": 3},
                "problem": {"statement": "x + 2 = 5"},
                "answer": {"type": "integer", "value": "3"},
            }
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert data["content"]["problem_text"] == "x + 2 = 5"
    assert data["content"]["answer"] == "3"


def test_compile_rejects_invalid_dsl(client: TestClient) -> None:
    # 초등학교에 미적분 개념 배정 → semantic FAIL → 422
    response = client.post(
        "/v1/dsl/compile",
        json={
            "dsl": {
                "content_id": "TEST-API-003",
                "curriculum": {
                    "subject": "mathematics",
                    "grade": "elementary_3",
                    "concept": "calculus",
                },
                "difficulty": {"level": 3},
                "problem": {"statement": "미분을 구하여라."},
                "answer": {"type": "expression", "expression": "x"},
            }
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert "검증을 통과하지 못해" in data["detail"]["message"]


def test_endpoints_require_authentication() -> None:
    app = create_app()
    # DB 엔진 생성을 막기 위해 get_session을 가짜로 오버라이드한다.
    app.dependency_overrides[get_session] = lambda: AsyncMock()
    client = TestClient(app)
    response = client.post(
        "/v1/dsl/validate",
        json={"dsl": {}},
    )
    assert response.status_code == 401
