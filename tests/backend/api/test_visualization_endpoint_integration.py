"""POST /v1/visualizations/weak-concept 통합테스트 — 실 PG 진단→시각화 e2e (기본 SKIP). 슬97.

약점 개념(BKT mastery)을 실 PG에 시드하고, 인증 학생 토큰으로 엔드포인트를 부르면 StubProvider가
낸 명세가 200 + Visualization으로 돌아오는지 검증한다(L2 진단→L1 Concept→L3 생성·검증 e2e).
get_settings만 오버라이드(jwt), get_session은 실 PG, provider/cache/trace는 stub/인메모리
(라이브 Ollama·Redis·Langfuse 회피).
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
from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.enums import (
    ConceptLevel,
    ConceptRole,
    Curriculum,
    Persona,
    SourceType,
    Subject,
    VisualizationStyle,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_PATH = "/v1/visualizations/weak-concept"
_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"model": "circle"}, '
    '"caption": "단위원", "interactive": true}'
)


class _StubProvider:
    """가짜 LLMProvider — 항상 유효 Visualization JSON 반환(라이브 Ollama 회피)."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> str:
        return _VALID_JSON


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


def test_weak_concept_visualization_on_live_pg() -> None:
    """약점 개념 시드 → POST /v1/visualizations/weak-concept → 200 + Visualization(e2e·실 PG)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cid = uuid.uuid4()
    pid = uuid.uuid4()
    suffix = uid.hex[:8]
    t1 = datetime(2026, 1, 1, tzinfo=UTC)

    async def _setup() -> None:
        await _add_all(
            UserProfile.from_schema(
                UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
            )
        )
        await _add_all(
            Concept.from_schema(
                ConceptSchema(
                    concept_id=cid,
                    code=f"TRIG-{suffix}",
                    name_ko="삼각함수의 주기성",
                    level=ConceptLevel.세부개념,
                    recommended_visual_styles=[VisualizationStyle.단위원],
                )
            )
        )
        await _add_all(
            Problem.from_schema(
                ProblemSchema(
                    problem_id=pid,
                    source_type=SourceType.자체생성,
                    curriculum_version=Curriculum.REVISION_2022,
                    valid_from_year=2022,
                    subject=Subject.공통,
                    unit_codes=[f"U-{suffix}"],
                    difficulty_overall=3.0,
                )
            )
        )
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY
                )
            )
        )
        await _add_all(
            ProblemAttempt(
                attempt_id=uuid.uuid4(), user_id=uid, problem_id=pid, is_correct=False
            )
        )
        # BKT 낮음(약점) → weakest-first 정렬에서 이 개념이 선택된다.
        await _add_all(
            ConceptMasteryHistory.from_schema(
                ConceptMasteryHistorySchema(
                    user_id=uid,
                    concept_id=cid,
                    measured_at=t1,
                    mastery=0.2,
                    sample_size=1,
                )
            )
        )

    async def _cleanup_all() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            async with engine.begin() as conn:
                for sql, params in (
                    ("DELETE FROM problem_attempt WHERE user_id=:u", {"u": str(uid)}),
                    (
                        "DELETE FROM concept_mastery_history WHERE user_id=:u",
                        {"u": str(uid)},
                    ),
                    (
                        "DELETE FROM problem_concept WHERE problem_id=:p",
                        {"p": str(pid)},
                    ),
                    ("DELETE FROM problem WHERE problem_id=:p", {"p": str(pid)}),
                    ("DELETE FROM concept WHERE concept_id=:c", {"c": str(cid)}),
                    ("DELETE FROM user_profile WHERE user_id=:u", {"u": str(uid)}),
                ):
                    await conn.execute(text(sql), params)
        finally:
            await engine.dispose()

    app = create_app(
        provider=_StubProvider(), cache=InMemoryCache(), trace=RecordingTraceSink()
    )
    app.dependency_overrides[get_settings] = _settings

    try:
        asyncio.run(_setup())
        token = create_access_token(uid, settings=_settings())
        with TestClient(app) as client:
            resp = client.post(_PATH, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["type"] == "interactive_graph_2d"
            assert body["caption"] == "단위원"
            # 인증 없으면 401(레이트 리밋 전에 차단).
            assert client.post(_PATH).status_code == 401
    finally:
        asyncio.run(_cleanup_all())
