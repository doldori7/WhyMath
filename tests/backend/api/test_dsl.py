"""DSL API 통합 테스트."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_current_user
from whymath_backend.app import create_app
from whymath_backend.db.session import get_session


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


@pytest.fixture
def client(app):
    # 인증 의존성 오버라이드
    app.dependency_overrides[get_current_user] = lambda: _make_test_user()
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
