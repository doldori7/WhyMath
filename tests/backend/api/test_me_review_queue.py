"""`GET /v1/me/review-queue`(S4-18) — hermetic(FakeSession·인증 오버라이드).

DISTINCT ON 실 SQL 정확성은 `test_review_queue_integration.py`(실 PG, 이 세션에선 실행 불가)의
몫이다. 여기서는 결선(200·직렬화·401·빈[])과 "감쇠가 실제로 적용됐다"는 도달 신호(⑤)만 본다
— `test_me_learning_metrics.py` 분업 방침과 동일.
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
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


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


class TestGetMyReviewQueue:
    def test_returns_ranked_items_with_decay_applied(self) -> None:
        """도달 축(⑤)의 hermetic 대응 — 아주 오래된 측정은 사전값(0.3) 근처로 감쇠된다."""
        cid = uuid.uuid4()
        ancient = datetime(2000, 1, 1, tzinfo=UTC)
        client = _client([(cid, "UC.limit", "극한", 0.9, ancient)])
        resp = client.get("/v1/me/review-queue")
        assert resp.status_code == 200
        body = resp.json()
        assert body["decay_model"] == "bkt_p_forget"
        assert body["calibrated"] is False
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["concept_code"] == "UC.limit"
        assert item["raw_mastery"] == 0.9
        assert item["due_rank"] == 1
        # 수십 년 경과 → 감쇠가 사전값(0.3)까지 완전히 진행돼 raw보다 훨씬 낮다.
        assert item["decayed_mastery"] < item["raw_mastery"]
        assert abs(item["decayed_mastery"] - 0.3) < 1e-6

    def test_recent_measurement_barely_decays(self) -> None:
        cid = uuid.uuid4()
        recent = datetime.now(UTC) - timedelta(minutes=1)
        client = _client([(cid, "UC.recent", "최근", 0.5, recent)])
        resp = client.get("/v1/me/review-queue")
        body = resp.json()["items"][0]
        assert abs(body["decayed_mastery"] - 0.5) < 1e-3

    def test_empty_when_no_observation_history(self) -> None:
        client = _client([])
        resp = client.get("/v1/me/review-queue")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_requires_auth(self) -> None:
        client = _no_auth_client()
        assert client.get("/v1/me/review-queue").status_code == 401
