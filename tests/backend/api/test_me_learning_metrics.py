"""`GET /v1/me/learning-metrics`(COLLAB-03 학생 1인칭 좌석) — hermetic(FakeSession·인증 오버라이드).

`daily_learning_metrics` 결선(200·직렬화·401·빈[]·날짜창 422)만 검증한다. 실제 롤업 적재→
실 PG 조회 왕복(변별력 축 ④⑤)은 `test_me_learning_metrics_integration.py`가 실 PG로 검증한다
(FakeSession은 stmt를 무시하므로 WHERE user_id 스코핑·metric_date 필터 정확성을 못 봄 —
`test_me.py` 모듈 docstring과 동일 분업).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.timeseries import DailyLearningMetrics
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.timeseries import DailyLearningMetrics as DailyLearningMetricsSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class FakeSession:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = list(rows or [])

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._rows)


def _client(rows: list[Any]) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    fake = FakeSession(rows)

    async def _sess() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client() -> TestClient:
    app = create_app()

    async def _sess() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _metrics_row(
    *,
    minutes_active: int | None = 30,
    problems_attempted: int | None = 5,
    problems_correct: int | None = 3,
    socratic_turns: int | None = 8,
    concepts_practiced: list[str] | None = None,
    avg_focus_score: float | None = 0.75,
) -> DailyLearningMetrics:
    return DailyLearningMetrics.from_schema(
        DailyLearningMetricsSchema(
            user_id=_UID,
            metric_date=date(2026, 8, 1),
            minutes_active=minutes_active,
            problems_attempted=problems_attempted,
            problems_correct=problems_correct,
            socratic_turns=socratic_turns,
            concepts_practiced=(
                concepts_practiced if concepts_practiced is not None else ["math.calculus.limit"]
            ),
            avg_focus_score=avg_focus_score,
        )
    )


class TestListMyLearningMetrics:
    def test_returns_rows_with_real_numbers(self) -> None:
        """도달 축(⑤)의 hermetic 대응 — 응답이 기본/빈 값이 아니라 시드한 실제 숫자를 싣는다."""
        client = _client([_metrics_row()])
        resp = client.get("/v1/me/learning-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        row = body[0]
        assert row["minutes_active"] == 30
        assert row["problems_attempted"] == 5
        assert row["problems_correct"] == 3
        assert row["socratic_turns"] == 8
        assert row["concepts_practiced"] == ["math.calculus.limit"]
        assert row["avg_focus_score"] == 0.75
        assert row["metric_date"] == "2026-08-01"

    def test_empty_when_no_rollup_yet(self) -> None:
        """writer가 아직 그 학생을 처리하지 않은 경우 — 가짜 0 대신 빈 배열."""
        client = _client([])
        resp = client.get("/v1/me/learning-metrics")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self) -> None:
        client = _no_auth_client()
        assert client.get("/v1/me/learning-metrics").status_code == 401

    def test_since_after_until_rejected(self) -> None:
        client = _client([_metrics_row()])
        resp = client.get(
            "/v1/me/learning-metrics",
            params={"since": "2026-08-10", "until": "2026-08-01"},
        )
        assert resp.status_code == 422

    def test_since_until_accepted(self) -> None:
        client = _client([_metrics_row()])
        resp = client.get(
            "/v1/me/learning-metrics",
            params={"since": "2026-01-01", "until": "2026-12-31"},
        )
        assert resp.status_code == 200

    def test_invalid_order_rejected(self) -> None:
        client = _client([_metrics_row()])
        resp = client.get("/v1/me/learning-metrics", params={"order": "sideways"})
        assert resp.status_code == 422

    def test_order_asc_accepted(self) -> None:
        client = _client([_metrics_row()])
        resp = client.get("/v1/me/learning-metrics", params={"order": "asc"})
        assert resp.status_code == 200

    def test_null_fields_serialize_as_null_not_zero(self) -> None:
        """활동 부재 필드는 정직하게 null(0 아님) — 가짜 0 금지 원칙의 API 표면 확인."""
        client = _client(
            [
                _metrics_row(
                    minutes_active=None,
                    problems_attempted=None,
                    problems_correct=None,
                    socratic_turns=None,
                    avg_focus_score=None,
                    concepts_practiced=[],
                )
            ]
        )
        resp = client.get("/v1/me/learning-metrics")
        row = resp.json()[0]
        assert row["minutes_active"] is None
        assert row["avg_focus_score"] is None
        assert row["concepts_practiced"] == []
