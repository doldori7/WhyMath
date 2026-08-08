"""L2 학습시간·행동 집계 writer(COLLAB-03) — 실 PG 통합테스트 (기본 SKIP).

`run_daily_rollup`이 `learning_session`·`problem_attempt`·`dialogue`(+ `problem_concept`·
`user_profile` 조인)를 읽어 `daily_learning_metrics`·`problem_solve_time_distribution`·
`user_behavior_metrics` 세 테이블에 실제로 행을 적재하는지 **적재 축(변별력 ④)**을 검증한다:
이 테스트가 스코핑한 user_id/problem_id로 *적재 전 0행 실측 → 롤업 실행 후 N행 실측*을
같은 assert 블록 안에서 수행한다(같은 값이면 위장 — CLAUDE.md "변별력 없는 검증 금지").
멱등성(같은 날짜 재실행 시 행수 불변·값 갱신)도 함께 확인한다.

Kiki 머신에서 실행:
    cd C:\\Users\\kiki\\Desktop\\__AI\\WhyMath\\src\\backend
    $env:WHYMATH_RUN_INTEGRATION = "1"
    python -m pytest -c pyproject.toml `
      ../../tests/backend/l2/test_learning_metrics_writer_integration.py -q
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.learning_metrics_writer import (
    BEHAVIOR_METRIC_DAYS_ACTIVE_7D,
    BEHAVIOR_METRIC_SESSION_COUNT_7D,
    run_daily_rollup,
)
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import (
    ConceptLevel,
    ConceptRole,
    Curriculum,
    Persona,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"
_TARGET_DATE = datetime(2026, 8, 1, tzinfo=UTC).date()
_DAY = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)  # 대상 날짜 안의 한 시각


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


async def _row_counts(uid: uuid.UUID, pid: uuid.UUID) -> tuple[int, int, int]:
    """(daily_learning_metrics, problem_solve_time_distribution, user_behavior_metrics) 행수
    — 이 테스트가 스코핑한 user_id/problem_id로 한정(공유 테이블 — 타 실행 데이터와 분리)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            daily = (
                await conn.execute(
                    text("SELECT count(*) FROM daily_learning_metrics WHERE user_id = :u"),
                    {"u": str(uid)},
                )
            ).scalar()
            solve = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM problem_solve_time_distribution "
                        "WHERE problem_id = :p"
                    ),
                    {"p": str(pid)},
                )
            ).scalar()
            behavior = (
                await conn.execute(
                    text("SELECT count(*) FROM user_behavior_metrics WHERE user_id = :u"),
                    {"u": str(uid)},
                )
            ).scalar()
        return int(daily or 0), int(solve or 0), int(behavior or 0)
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID, pid: uuid.UUID, cid: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM daily_learning_metrics WHERE user_id = :u"), {"u": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM problem_solve_time_distribution WHERE problem_id = :p"),
                {"p": str(pid)},
            )
            await conn.execute(
                text("DELETE FROM user_behavior_metrics WHERE user_id = :u"), {"u": str(uid)}
            )
            await conn.execute(text("DELETE FROM dialogue WHERE user_id = :u"), {"u": str(uid)})
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = :u"), {"u": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM learning_session WHERE user_id = :u"), {"u": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM problem_concept WHERE problem_id = :p"), {"p": str(pid)}
            )
            await conn.execute(text("DELETE FROM problem WHERE problem_id = :p"), {"p": str(pid)})
            await conn.execute(text("DELETE FROM concept WHERE concept_id = :c"), {"c": str(cid)})
            await conn.execute(text("DELETE FROM user_profile WHERE user_id = :u"), {"u": str(uid)})
    finally:
        await engine.dispose()


def test_run_daily_rollup_populates_all_three_tables_from_zero_on_live_pg() -> None:
    """적재 축(④) — 롤업 전 0행 실측 → 실행 후 N행 실측(같은 assert 블록·같은 스코프).

    학습 세션(집중도·시간)·채점 풀이(정답 1·오답 1·PRIMARY 개념 태깅)·소크라테스 대화를
    한 사용자에 적재하고 `run_daily_rollup`을 돌린다. 세 테이블 모두 적재 전 0 → 적재 후
    >0을 실측하고, 핵심 집계값(분·문제수·턴수·개념코드·퍼센타일·행동지표)도 검증한다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    pid_correct, pid_wrong = uuid.uuid4(), uuid.uuid4()
    cid = uuid.uuid4()
    sid = uuid.uuid4()
    suffix = uid.hex[:8]

    async def _setup() -> None:
        await _add_all(
            UserProfile.from_schema(
                UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
            )
        )
        await _add_all(
            Problem.from_schema(
                ProblemSchema(
                    problem_id=pid_correct,
                    source_type=SourceType.자체생성,
                    curriculum_version=Curriculum.REVISION_2022,
                    valid_from_year=2022,
                    subject=Subject.공통,
                    unit_codes=[f"U-{suffix}"],
                )
            ),
            Problem.from_schema(
                ProblemSchema(
                    problem_id=pid_wrong,
                    source_type=SourceType.자체생성,
                    curriculum_version=Curriculum.REVISION_2022,
                    valid_from_year=2022,
                    subject=Subject.공통,
                    unit_codes=[f"U-{suffix}"],
                )
            ),
            Concept.from_schema(
                ConceptSchema(
                    concept_id=cid,
                    code=f"C-{suffix}",
                    name_ko="집계테스트개념",
                    level=ConceptLevel.세부개념,
                )
            ),
        )
        await _add_all(
            ProblemConcept.from_schema(
                ProblemConceptSchema(
                    problem_id=pid_correct, concept_id=cid, role=ConceptRole.PRIMARY
                )
            )
        )
        # 세션: 10분(600초)·집중도 0.8
        await _add_all(
            LearningSession.from_schema(
                LearningSessionSchema(
                    session_id=sid,
                    user_id=uid,
                    started_at=_DAY,
                    duration_seconds=600,
                    focus_score=0.8,
                )
            )
        )
        # 풀이 2건(정답 1·오답 1) — 정답 건은 60초(퍼센타일 표본).
        await _add_all(
            ProblemAttempt.from_schema(
                ProblemAttemptSchema(
                    attempt_id=uuid.uuid4(),
                    user_id=uid,
                    problem_id=pid_correct,
                    started_at=_DAY,
                    is_correct=True,
                    duration_seconds=60,
                )
            ),
            ProblemAttempt.from_schema(
                ProblemAttemptSchema(
                    attempt_id=uuid.uuid4(),
                    user_id=uid,
                    problem_id=pid_wrong,
                    started_at=_DAY,
                    is_correct=False,
                )
            ),
        )
        # 소크라테스 대화 — 턴 5개.
        await _add_all(
            Dialogue.from_schema(
                DialogueSchema(
                    dialogue_id=uuid.uuid4(),
                    user_id=uid,
                    started_at=_DAY,
                    total_turns=5,
                )
            )
        )

    async def _run_rollup_once() -> tuple[int, int, int]:
        engine = create_async_engine(_settings().database_url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                report = await run_daily_rollup(session, _TARGET_DATE)
            return (
                report.daily_learning_metrics_rows,
                report.problem_solve_time_distribution_rows,
                report.user_behavior_metrics_rows,
            )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())

        # ── 적재 전 실측: 이 스코프(uid/pid_correct)는 0행이어야 한다 ──
        before = asyncio.run(_row_counts(uid, pid_correct))
        assert before == (0, 0, 0), f"적재 전인데 이미 행이 있음(테스트 오염 의심): {before}"

        # ── 롤업 실행 ──
        n1, n2, n3 = asyncio.run(_run_rollup_once())
        assert n1 == 1  # daily_learning_metrics: 사용자 1명
        assert n2 == 1  # problem_solve_time_distribution: (pid_correct, persona) 1쌍
        assert n3 == 2  # user_behavior_metrics: 지표 2종

        # ── 적재 후 실측: 0 → N (같은 스코프) ──
        after = asyncio.run(_row_counts(uid, pid_correct))
        assert after == (1, 1, 2), f"적재 후 행수 불일치: {after}"
        assert after != before  # 변별력 — 전/후가 같은 값이면 위장

        # ── 값 검증 ──
        engine = create_async_engine(_settings().database_url)
        try:

            async def _fetch_values() -> tuple[Any, Any]:
                async with engine.connect() as conn:
                    daily_row = (
                        await conn.execute(
                            text(
                                "SELECT minutes_active, problems_attempted, problems_correct, "
                                "socratic_turns, concepts_practiced, avg_focus_score "
                                "FROM daily_learning_metrics WHERE user_id = :u"
                            ),
                            {"u": str(uid)},
                        )
                    ).one()
                    solve_row = (
                        await conn.execute(
                            text(
                                "SELECT p10_seconds, p50_seconds, p90_seconds, sample_size "
                                "FROM problem_solve_time_distribution WHERE problem_id = :p"
                            ),
                            {"p": str(pid_correct)},
                        )
                    ).one()
                return daily_row, solve_row

            daily_row, solve_row = asyncio.run(_fetch_values())
        finally:
            asyncio.run(engine.dispose())

        assert daily_row[0] == 10  # minutes_active = 600초/60
        assert daily_row[1] == 2  # problems_attempted = 2건
        assert daily_row[2] == 1  # problems_correct = 1건
        assert daily_row[3] == 5  # socratic_turns
        assert list(daily_row[4]) == [f"C-{suffix}"]  # concepts_practiced(PRIMARY 개념 코드)
        assert float(daily_row[5]) == 0.8  # avg_focus_score
        # 표본 1개 퍼센타일은 그 값 그대로(모든 백분위 = 60초)
        assert (solve_row[0], solve_row[1], solve_row[2], solve_row[3]) == (60, 60, 60, 1)

        # ── 행동 지표 값 확인 ──
        async def _behavior_values() -> dict[str, float]:
            engine2 = create_async_engine(_settings().database_url)
            try:
                async with engine2.connect() as conn:
                    rows = (
                        await conn.execute(
                            text(
                                "SELECT metric_name, metric_value FROM user_behavior_metrics "
                                "WHERE user_id = :u"
                            ),
                            {"u": str(uid)},
                        )
                    ).all()
                return {name: float(value) for name, value in rows}
            finally:
                await engine2.dispose()

        behavior = asyncio.run(_behavior_values())
        assert behavior[BEHAVIOR_METRIC_SESSION_COUNT_7D] == 1.0
        assert behavior[BEHAVIOR_METRIC_DAYS_ACTIVE_7D] == 1.0

        # ── 멱등성: 같은 날짜 재실행 → 행수 불변(upsert가 갱신이지 중복 삽입이 아님) ──
        n1b, n2b, n3b = asyncio.run(_run_rollup_once())
        assert (n1b, n2b, n3b) == (n1, n2, n3)
        after_rerun = asyncio.run(_row_counts(uid, pid_correct))
        assert after_rerun == after  # 행수 불변(갱신이지 추가 아님)
    finally:
        asyncio.run(_cleanup(uid, pid_correct, cid))
        asyncio.run(_cleanup(uid, pid_wrong, cid))
