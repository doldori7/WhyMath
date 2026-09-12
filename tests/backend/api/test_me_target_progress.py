"""`GET /v1/me/target-progress`(S4-18) — hermetic(FakeSession·인증 오버라이드).

조인 정합(성취기준 스코프·개념 링크·관측)은 `test_me_target_progress_integration.py`(실 PG,
이 세션에선 실행 불가)의 몫이다. 여기서는 결선(200·직렬화·401)·프로필 부재/`school_type` 없음
폴백·목표 echo만 hermetic으로 검증한다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona, SchoolType
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _consented_user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class FakeSession:
    """`get()`은 프로필 1회, `execute()`는 큐잉 순서대로(스코프→관측)."""

    def __init__(
        self,
        profile: UserProfile | None,
        execute_queue: list[list[Any]] | None = None,
    ) -> None:
        self._profile = profile
        self._queue = list(execute_queue or [])

    async def get(self, _model: Any, _pk: Any) -> UserProfile | None:
        return self._profile

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._queue.pop(0))


def _client(
    profile: UserProfile | None, execute_queue: list[list[Any]] | None = None
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _consented_user
    fake = FakeSession(profile, execute_queue)

    async def _sess() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[FakeSession]:
        yield FakeSession(None)

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class TestGetMyTargetProgress:
    def test_echoes_target_and_computes_dday(self) -> None:
        exam_date = datetime.now(UTC).date() + timedelta(days=15)
        profile = UserProfile.from_schema(
            UserProfileSchema(
                user_id=_UID,
                persona_primary=Persona.A_일반고고3,
                target_exam_date=exam_date,
                target_grade=2,
                target_score=130,
            )
        )
        client = _client(profile)
        resp = client.get("/v1/me/target-progress")
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_exam_date"] == exam_date.isoformat()
        assert body["days_until_exam"] == 15
        assert body["target_grade"] == 2
        assert body["target_score"] == 130
        assert body["standard_coverage_percent"] is None  # school_type 미설정 → 폴백.

    def test_school_type_none_coverage_fields_null(self) -> None:
        profile = UserProfile.from_schema(
            UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
        )
        client = _client(profile)
        resp = client.get("/v1/me/target-progress")
        body = resp.json()
        assert body["standard_coverage_percent"] is None
        assert body["standard_coverage_observed"] is None
        assert body["standard_coverage_scope"] is None
        assert body["standard_coverage_measured_concepts"] is None
        assert body["standard_coverage_matched_concepts"] is None

    def test_school_type_set_computes_coverage_percent(self) -> None:
        """CUR-04 원자 축 — 스코프는 `(norm_id, official_code)`, 관측은 `(concept_id,
        standard_codes, concept_id)` 3-tuple(FakeSession은 실제 SQL을 보지 않고 큐잉된 결과만 반환하므로
        shape만 새 조인과 맞추면 된다·`test_target_progress.py` 단위테스트와 동일 관례)."""
        profile = UserProfile.from_schema(
            UserProfileSchema(
                user_id=_UID,
                persona_primary=Persona.A_일반고고3,
                school_type=SchoolType.일반고,
            )
        )
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        client = _client(
            profile,
            [
                [("N1", "STD-1"), ("N2", "STD-2"), ("N3", "STD-3"), ("N4", "STD-4")],  # 스코프 4건
                # 관측 2개념 — 둘 다 원자 축 매칭+스코프 내. 행 모양은 CUR-12 통합 함수의
                # 원자 축 SELECT 열 순서 `(atom_code, standard_codes, concept_id)`.
                [("A1", ["STD-1"], c1), ("A2", ["STD-2"], c2)],
            ],
        )
        resp = client.get("/v1/me/target-progress")
        body = resp.json()
        assert body["standard_coverage_scope"] == 4
        assert body["standard_coverage_observed"] == 2
        assert body["standard_coverage_percent"] == 50.0
        # 작동 신호(CUR-04) — 측정 이력 2개념 전부 원자 축에 매칭됐다(조인 실패 0건).
        assert body["standard_coverage_measured_concepts"] == 2
        assert body["standard_coverage_matched_concepts"] == 2

    def test_no_prediction_fields_in_response(self) -> None:
        profile = UserProfile.from_schema(
            UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
        )
        client = _client(profile)
        resp = client.get("/v1/me/target-progress")
        body = resp.json()
        for forbidden in ("predicted_score", "predicted_grade", "expected_grade"):
            assert forbidden not in body

    def test_requires_auth(self) -> None:
        client = _no_auth_client()
        assert client.get("/v1/me/target-progress").status_code == 401
