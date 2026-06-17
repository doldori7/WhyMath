"""verify 라우터 단위테스트 — `POST /v1/verify-step`(stateless·hermetic).

엔드포인트 결선(200·3상태 직렬화·401 무토큰·요청 스키마 422·노출 계약) 검증. 기존
endpoint 테스트(`test_coach`)의 인증 오버라이드·`_no_auth_client` 패턴을 미러한다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _settings_override() -> Settings:
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """verify-step(stateless)용 — DB 쿼리 시 AssertionError(real get_session 누수 차단)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("verify-step 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


def _client() -> TestClient:
    """인증 게이트 통과(ConsentedUser 오버라이드) — verify-step은 stateless라 DB 미사용.

    `get_session`도 가짜로 오버라이드해 real lazy 엔진 생성(전역 누수)을 막는다(test_coach 패턴).
    """
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_override

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client() -> TestClient:
    """무토큰 401 — 실 인증 경로가 돌되 `get_session`은 가짜(엔진 누수 차단·test_coach 패턴)."""
    app = create_app()
    app.dependency_overrides[get_settings] = _settings_override

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class TestVerifyStep200:
    def test_correct_equivalence(self) -> None:
        resp = _client().post(
            "/v1/verify-step", json={"expr_before": "2*(x+1)", "expr_after": "2*x+2"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "correct"
        assert body["evidence_weight"] == 1.0
        assert body["reason"] is None
        assert body["step_type"] is None

    def test_incorrect_false_transform(self) -> None:
        # 2x+1 vs 2x+3 — 차이 상수 -2(0 아님 확정) → incorrect.
        resp = _client().post(
            "/v1/verify-step", json={"expr_before": "2*x+1", "expr_after": "2*x+3"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "incorrect"
        assert body["evidence_weight"] == 1.0
        assert body["reason"] is not None
        assert "동치 아님" in body["reason"]

    def test_unverifiable_non_algebraic_step_type(self) -> None:
        resp = _client().post(
            "/v1/verify-step",
            json={
                "expr_before": "어쩌고",
                "expr_after": "저쩌고",
                "step_type": "조건해석",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "unverifiable"
        assert body["evidence_weight"] == 0.5
        assert body["step_type"] == "조건해석"

    def test_unverifiable_unparseable(self) -> None:
        resp = _client().post(
            "/v1/verify-step",
            json={"expr_before": "어쩌고저쩌고", "expr_after": "음음음"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "unverifiable"

    def test_step_type_propagated(self) -> None:
        resp = _client().post(
            "/v1/verify-step",
            json={"expr_before": "3*4", "expr_after": "12", "step_type": "계산"},
        )
        body = resp.json()
        assert body["state"] == "correct"
        assert body["step_type"] == "계산"


class TestVerifyStepExposureContract:
    """노출 계약 — 응답은 판정만(state·reason·evidence_weight·step_type). 정답/본문 누출 0."""

    def test_response_field_set(self) -> None:
        resp = _client().post("/v1/verify-step", json={"expr_before": "2+3", "expr_after": "5"})
        assert set(resp.json().keys()) == {
            "state",
            "step_type",
            "reason",
            "evidence_weight",
        }


class TestVerifyStepAuth:
    def test_no_token_401(self) -> None:
        resp = _no_auth_client().post(
            "/v1/verify-step", json={"expr_before": "2+3", "expr_after": "5"}
        )
        assert resp.status_code == 401


class TestVerifyStepSchema:
    def test_missing_expr_after_422(self) -> None:
        resp = _client().post("/v1/verify-step", json={"expr_before": "2+3"})
        assert resp.status_code == 422

    def test_extra_field_forbidden_422(self) -> None:
        resp = _client().post(
            "/v1/verify-step",
            json={"expr_before": "2+3", "expr_after": "5", "bogus": 1},
        )
        assert resp.status_code == 422

    def test_invalid_step_type_422(self) -> None:
        resp = _client().post(
            "/v1/verify-step",
            json={"expr_before": "2+3", "expr_after": "5", "step_type": "bogus"},
        )
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────
# POST /v1/verify-solution — 연쇄 검증 집계(§3.1). verify-step 패턴 미러.
# ──────────────────────────────────────────────────────────────────────────
class TestVerifySolution200:
    def test_correct_chain(self) -> None:
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2*(x+1)", "2*x+2", "2*(x+1)"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["n_transitions"] == 2
        assert body["n_correct"] == 2
        assert body["has_incorrect"] is False
        assert body["first_incorrect_index"] is None
        assert body["unverified_ratio"] == 0.0
        assert len(body["steps"]) == 2

    def test_chain_with_incorrect(self) -> None:
        # 전이0 correct·전이1 incorrect(2x→2x+1)·전이2 correct → first_incorrect_index=1.
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2*x", "2*x", "2*x+1", "2*x+1"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["has_incorrect"] is True
        assert body["first_incorrect_index"] == 1
        assert body["n_incorrect"] == 1

    def test_unverified_ratio(self) -> None:
        # 전이0 correct(2+3≡5)·전이1 unverifiable(5→산문) → ratio 0.5.
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2+3", "5", "어쩌고저쩌고"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["n_unverifiable"] == 1
        assert body["unverified_ratio"] == 0.5

    def test_step_types_propagated(self) -> None:
        resp = _client().post(
            "/v1/verify-solution",
            json={
                "steps": ["2+3", "5", "5"],
                "step_types": ["계산", "조건해석"],
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["steps"][0]["step_type"] == "계산"
        # 비대수 step_type이면 동치(5≡5)여도 unverifiable(verify_step 보수성 상속).
        assert body["steps"][1]["step_type"] == "조건해석"
        assert body["steps"][1]["state"] == "unverifiable"

    def test_short_sequence_empty_result(self) -> None:
        # 단계 1개 → 전이 0개의 정직한 빈 집계(200·에러 아님).
        resp = _client().post("/v1/verify-solution", json={"steps": ["2+3"]})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["n_transitions"] == 0
        assert body["steps"] == []
        assert body["has_incorrect"] is False


class TestVerifySolutionExposureContract:
    """노출 계약 — 응답은 검증 집계뿐(상태·카운트·비율). 정답/본문 누출 0."""

    def test_response_field_set(self) -> None:
        resp = _client().post("/v1/verify-solution", json={"steps": ["2+3", "5"]})
        assert set(resp.json().keys()) == {
            "steps",
            "n_correct",
            "n_incorrect",
            "n_unverifiable",
            "n_transitions",
            "unverified_ratio",
            "first_incorrect_index",
            "has_incorrect",
        }


class TestVerifySolutionAuth:
    def test_no_token_401(self) -> None:
        resp = _no_auth_client().post("/v1/verify-solution", json={"steps": ["2+3", "5"]})
        assert resp.status_code == 401


class TestVerifySolutionSchema:
    def test_missing_steps_422(self) -> None:
        resp = _client().post("/v1/verify-solution", json={})
        assert resp.status_code == 422

    def test_step_types_optional(self) -> None:
        # step_types 생략 OK(기본 None).
        resp = _client().post("/v1/verify-solution", json={"steps": ["2+3", "5"]})
        assert resp.status_code == 200, resp.text

    def test_extra_field_forbidden_422(self) -> None:
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2+3", "5"], "bogus": 1},
        )
        assert resp.status_code == 422

    def test_step_types_length_mismatch_422(self) -> None:
        # 전이 2개인데 step_types 1개 → verify_solution ValueError → 422.
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2+3", "5", "5"], "step_types": ["계산"]},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_step_type_value_422(self) -> None:
        resp = _client().post(
            "/v1/verify-solution",
            json={"steps": ["2+3", "5"], "step_types": ["bogus"]},
        )
        assert resp.status_code == 422
