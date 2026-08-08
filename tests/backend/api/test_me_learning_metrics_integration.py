"""`GET /v1/me/learning-metrics` — 실 PG 통합테스트 (기본 SKIP).

**도달 축(변별력 ⑤)**: 활동 데이터를 적재 → `run_daily_rollup`으로 롤업(같은 writer가
`test_learning_metrics_writer_integration.py`가 검증하는 그 함수) → *인증된 학생 토큰*으로
`GET /v1/me/learning-metrics`를 실제로 호출해 응답에 시드한 실제 숫자가 실리는지 확인한다
(빈/기본 응답이 아님 — "테이블만 차고 도달 0"이 아니라는 것을 실측). 타인 데이터 차단
(user_id 스코핑)도 함께 확인한다(다른 /me 통합테스트와 동형 — `test_me_integration.py`).

Kiki 머신에서 실행:
    cd C:\\Users\\kiki\\Desktop\\__AI\\WhyMath\\src\\backend
    $env:WHYMATH_RUN_INTEGRATION = "1"
    python -m pytest -c pyproject.toml `
      ../../tests/backend/api/test_me_learning_metrics_integration.py -q
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.learning_metrics_writer import run_daily_rollup
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_TARGET_DATE = datetime(2026, 8, 1, tzinfo=UTC).date()
_DAY = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


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


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _run_rollup() -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await run_daily_rollup(session, _TARGET_DATE)
    finally:
        await engine.dispose()


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM daily_learning_metrics WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM user_behavior_metrics WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
            await conn.execute(
                text("DELETE FROM learning_session WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
    finally:
        await engine.dispose()


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
    )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_me_learning_metrics_reaches_real_numbers_and_scopes_to_current_user_on_live_pg() -> None:
    """도달 축(⑤) — 시드→롤업→인증 GET 왕복에서 *실제 숫자*가 실리고, 타인(B) 데이터는 안 실린다.

    A는 세션(20분)+정답 풀이 1건을 갖고, B는 아무 활동도 없다. 롤업 후 A 토큰으로 조회하면
    A의 실제 집계(0/기본값이 아님)만 보이고 B 토큰 조회는 빈 배열([])이어야 한다(스코핑).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    pid = uuid.uuid4()

    async def _setup() -> None:
        await _add_all(_user(uid_a), _user(uid_b))
        await _add_all(
            LearningSession.from_schema(
                LearningSessionSchema(
                    session_id=uuid.uuid4(),
                    user_id=uid_a,
                    started_at=_DAY,
                    duration_seconds=1200,  # 20분
                    focus_score=0.9,
                )
            )
        )
        await _add_all(
            ProblemAttempt.from_schema(
                ProblemAttemptSchema(
                    attempt_id=uuid.uuid4(),
                    user_id=uid_a,
                    problem_id=pid,
                    started_at=_DAY,
                    is_correct=True,
                )
            )
        )

    try:
        asyncio.run(_setup())
        asyncio.run(_run_rollup())

        token_a = create_access_token(uid_a, settings=_settings())
        token_b = create_access_token(uid_b, settings=_settings())
        with _client() as client:
            resp = client.get(
                "/v1/me/learning-metrics",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            assert len(rows) == 1
            row = rows[0]
            # ── 도달 축 핵심 단언 — 기본/빈 값이 아니라 시드한 *실제* 숫자 ──
            assert row["minutes_active"] == 20
            assert row["problems_attempted"] == 1
            assert row["problems_correct"] == 1
            assert row["avg_focus_score"] == 0.9
            assert row["metric_date"] == _TARGET_DATE.isoformat()

            # 타인(B)은 활동이 없었으니 B 토큰으로는 빈 배열(스코핑도 함께 확인)
            resp_b = client.get(
                "/v1/me/learning-metrics",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert resp_b.status_code == 200, resp_b.text
            assert resp_b.json() == []

            # 무토큰 401
            assert client.get("/v1/me/learning-metrics").status_code == 401

            # 날짜창 필터 — since가 대상일 이후면 빈 배열
            resp_future = client.get(
                "/v1/me/learning-metrics",
                headers={"Authorization": f"Bearer {token_a}"},
                params={"since": "2099-01-01"},
            )
            assert resp_future.json() == []
    finally:
        asyncio.run(_cleanup([uid_a, uid_b]))
