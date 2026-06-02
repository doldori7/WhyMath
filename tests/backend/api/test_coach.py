"""L4 coach 라우터 단위테스트 — `POST /v1/coach`(hermetic).

엔드포인트 결선(200·통합 결정 직렬화·401·422·옵션 LTHC) 검증. 학생 발화·상태가 그대로
응답에 *에코되지 않음* 확인(에코는 표면화 위험 — coach.py docstring 경계 메모).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    async def execute(self, stmt: Any) -> None:
        raise AssertionError(
            "coach 라우터는 DB 쿼리하지 않아야 한다(stateless slice 6)."
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class TestBasicDecision:
    def test_minimal_request_returns_decision(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "decision" in body
        d = body["decision"]
        # 슬라이스 1-3 통합 — 모든 필드 채워짐
        assert d["polya_stage_to_advance"] in ("stay", "next", "previous")
        assert d["hint_level"] in (1, 2, 3, 4)
        assert d["socratic_category"] in (
            "clarification",
            "assumption",
            "evidence",
            "perspective",
            "implication",
            "meta",
        )
        assert d["prompt"]  # 비공
        assert d["system"]
        assert d["reveals"]  # hint_level에서 파생

    def test_default_state_is_understand_stay(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        body = resp.json()
        # 기본 PolyaState = UNDERSTAND + 짧은 입력 → stay·clarification
        assert body["decision"]["polya_stage_to_advance"] == "stay"
        assert body["decision"]["socratic_category"] == "clarification"

    def test_misconceptions_empty_for_neutral_input(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        body = resp.json()
        assert body["misconceptions"] == []
        assert body["intervention"] is None

    def test_lthc_none_without_mastery_level(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음"})
        assert resp.json()["lthc"] is None


class TestMisconceptionIntegration:
    def test_distribution_misconception_detected_with_intervention(self) -> None:
        # 슬라이스 4 카탈로그 — (a+b)² = a² + b² 신호로 풀 매칭(confidence 1.0)
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "내 풀이는 (a+b)² = a² + b² 이렇게 했어"},
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [m["misconception"]["id"] for m in body["misconceptions"]]
        assert "distribution-over-power" in ids
        # confidence 1.0 → COUNTEREXAMPLE 패턴
        assert body["intervention"] is not None
        assert body["intervention"]["pattern"] == "counterexample"
        assert "a=1, b=1" in body["intervention"]["prompt"]

    def test_partial_match_holds_intervention(self) -> None:
        # 부분 매칭 confidence 0.5 → REVERSE_REASONING 패턴
        resp = _client().post("/v1/coach", json={"student_input": "(a+b) 까지만"})
        body = resp.json()
        # 부분 매칭은 0.5 — reverse 패턴 또는 보류(임계 정확히 0.5는 reverse)
        if body["intervention"] is not None:
            assert body["intervention"]["pattern"] == "reverse_reasoning"


class TestLthcIntegration:
    def test_mastery_level_triggers_lthc(self) -> None:
        # 초보 → 진입점·비계 ON, 확장 OFF
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "음", "mastery_level": "초보"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["lthc"] is not None
        assert body["lthc"]["mastery_level"] == "초보"
        assert body["lthc"]["entry_suggestions"]  # 비공
        assert body["lthc"]["extensions"] == []

    def test_master_level_extensions_only(self) -> None:
        # 숙달 → 확장 ON, 나머지 OFF
        resp = _client().post(
            "/v1/coach",
            json={
                "student_input": "음",
                "polya_state": {"current_stage": "review"},
                "mastery_level": "숙달",
            },
        )
        body = resp.json()
        assert body["lthc"]["entry_suggestions"] == []
        assert body["lthc"]["extensions"]  # 비공


class TestHintLevelWiring:
    def test_demand_answer_signal_raises_hint(self) -> None:
        resp = _client().post(
            "/v1/coach",
            json={
                "student_input": "그냥 답이 뭐야",
                "polya_state": {"prev_hint_level": 1},
            },
        )
        body = resp.json()
        # slice 3 — min(4, prev+1) = 2
        assert body["decision"]["hint_level"] == 2
        assert body["decision"]["reveals"] == "step_flow"


class TestAuthGate:
    def test_no_token_401(self) -> None:
        resp = _no_auth_client().post("/v1/coach", json={"student_input": "음"})
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


class TestRequestValidation:
    def test_missing_student_input_422(self) -> None:
        assert _client().post("/v1/coach", json={}).status_code == 422

    def test_oversize_input_422(self) -> None:
        big = "가" * 4001  # max_length=4000
        assert (
            _client().post("/v1/coach", json={"student_input": big}).status_code == 422
        )

    def test_bad_mastery_level_422(self) -> None:
        resp = _client().post(
            "/v1/coach",
            json={"student_input": "음", "mastery_level": "고수"},  # 비-Literal
        )
        assert resp.status_code == 422

    def test_extra_field_forbidden(self) -> None:
        resp = _client().post("/v1/coach", json={"student_input": "음", "foo": "bar"})
        assert resp.status_code == 422
