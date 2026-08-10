"""학습 지표 롤업 적재·도달 통합테스트 (COLLAB-03 acceptance ④⑤) — 실 PG 필요(기본 SKIP).

이 파일이 COLLAB-03의 **변별력 장치**다. 두 축을 *같은 실행 안에서* 대조한다:

  ④ **적재 축** — 롤업 실행 *전* `daily_learning_metrics` 행수 0을 실측하고, 실행 *후* N행을
     실측한다. 전/후가 같은 값이면 검증이 아니라 위장이다(CLAUDE.md 「변별력 없는 검증 스텝
     금지」). 세 테이블 모두 같은 방식으로 대조한다.
  ⑤ **도달 축** — 인증 학생 토큰으로 `GET /v1/me/learning-metrics`를 호출해 응답 본문에 통계가
     실제로 실리는지 실측한다. 테이블만 차고 응답이 비면 목표 미달이므로, 호출 *전*(롤업 전)
     빈 응답과 *후* 채워진 응답을 함께 단언한다.

추가로 ⑦(제3자 노출 금지)의 기계 확인: 타 학생 B의 데이터가 A 토큰 응답에 섞이지 않는지,
`user_id` 질의 파라미터로 타인 조회가 되지 않는지 단언한다.

샌드박스에는 라이브 PG가 없어 `_pg_reachable()` 가드로 skip된다(`test_me_integration.py`와
동일 패턴). CI의 "backend — 마이그레이션·통합 (실 PG)" 잡이 실제로 돌린다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import AttemptEvent, LearningSession, ProblemAttempt
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.timeseries import (
    DailyLearningMetrics,
    ProblemSolveTimeDistribution,
    UserBehaviorMetrics,
)
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.learning_metrics_rollup import KST, run_daily_rollup
from whymath_backend.schema.activity import AttemptEvent as AttemptEventSchema
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema
from whymath_backend.schema.enums import (
    Curriculum,
    EventType,
    Persona,
    ReviewStatus,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"

# 집계 대상 날짜 — 과거 고정일(다른 테스트의 '오늘' 데이터와 섞이지 않게).
_DAY = date(2026, 3, 17)


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


def _kst(hour: int, minute: int = 0) -> datetime:
    """집계 대상일의 KST 시각(원천 TIMESTAMPTZ)."""
    return datetime(_DAY.year, _DAY.month, _DAY.day, hour, minute, tzinfo=KST)


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _count_rows() -> dict[str, int]:
    """세 시계열 테이블의 *집계 대상일* 행수 — ④의 전/후 대조 계측기."""
    engine = create_async_engine(_settings().database_url)
    day_start = datetime.combine(_DAY, datetime.min.time(), tzinfo=KST).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            daily = await session.scalar(
                select(func.count())
                .select_from(DailyLearningMetrics)
                .where(DailyLearningMetrics.metric_date == _DAY)
            )
            behavior = await session.scalar(
                select(func.count())
                .select_from(UserBehaviorMetrics)
                .where(
                    UserBehaviorMetrics.measured_at >= day_start,
                    UserBehaviorMetrics.measured_at < day_end,
                )
            )
            solve = await session.scalar(
                select(func.count())
                .select_from(ProblemSolveTimeDistribution)
                .where(
                    ProblemSolveTimeDistribution.measured_at >= day_start,
                    ProblemSolveTimeDistribution.measured_at < day_end,
                )
            )
            return {
                "daily_learning_metrics": int(daily or 0),
                "user_behavior_metrics": int(behavior or 0),
                "problem_solve_time_distribution": int(solve or 0),
            }
    finally:
        await engine.dispose()


async def _run_rollup() -> dict[str, object]:
    """프로덕션 롤업 경로 실행(커밋 포함) — CLI가 부르는 함수와 *같은* 함수다."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            report = await run_daily_rollup(
                session,
                start_date=_DAY,
                end_date=_DAY,
                # 표본이 적은 테스트 픽스처에서도 분포 축을 검증하기 위해 하한 1로 낮춘다
                # (운영 기본은 5 — 하한 자체는 hermetic 테스트가 별도로 봉인).
                min_solve_time_sample=1,
            )
            await session.commit()
            return report.to_json()
    finally:
        await engine.dispose()


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            for table in (
                "attempt_event",
                "problem_attempt",
                "learning_session",
                "daily_learning_metrics",
                "user_behavior_metrics",
            ):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE user_id = ANY(:ids)"), {"ids": ids}
                )
            # 풀이 시간 분포는 user_id가 없다(교차집계) — 이 테스트가 만든 problem_id로 정리.
            await conn.execute(
                text("DELETE FROM problem_solve_time_distribution WHERE problem_id = ANY(:pids)"),
                {"pids": [str(_PROBLEM_ID)]},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
            await conn.execute(
                text("DELETE FROM problem WHERE problem_id = :pid"), {"pid": str(_PROBLEM_ID)}
            )
    finally:
        await engine.dispose()


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
    )


# `problem_attempt.problem_id`는 problem FK라 실제 문항 행이 있어야 시도를 넣을 수 있다.
# 풀이 시간 분포(problem_id×persona 교차집계)의 적재 축을 실측하려면 이 문항이 필요하다.
_PROBLEM_ID = uuid.UUID("0f0f0f0f-0000-4000-8000-00000000feed")


def _problem() -> Problem:
    """풀이 시간 분포 집계의 FK 대상 문항 — 자체생성·승인 상태(저작권 위생 규약)."""
    return Problem.from_schema(
        ProblemSchema(
            problem_id=_PROBLEM_ID,
            source_type=SourceType.자체생성,
            review_status=ReviewStatus.approved,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.공통,
            unit_codes=["U-COLLAB03"],
            difficulty_overall=3.0,
        )
    )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def _seed_rows(uid: uuid.UUID, sid: uuid.UUID) -> list[object]:
    """한 학생의 하루치 원천 활동 — 세션 2개(총 45분)·시도 3건(정답 1)·소크라테스 이벤트 2건."""
    return [
        LearningSession.from_schema(
            LearningSessionSchema(
                session_id=sid,
                user_id=uid,
                started_at=_kst(9),
                ended_at=_kst(9, 30),
                duration_seconds=1800,
                focus_score=0.8,
            )
        ),
        LearningSession.from_schema(
            LearningSessionSchema(
                session_id=uuid.uuid4(),
                user_id=uid,
                started_at=_kst(14),
                ended_at=_kst(14, 15),
                duration_seconds=900,
                focus_score=0.6,
            )
        ),
    ]


def _seed_attempts(uid: uuid.UUID, sid: uuid.UUID) -> list[object]:
    specs = ((True, 120), (False, 240), (None, 60))
    return [
        ProblemAttempt.from_schema(
            ProblemAttemptSchema(
                attempt_id=uuid.uuid4(),
                user_id=uid,
                session_id=sid,
                problem_id=_PROBLEM_ID,
                started_at=_kst(9, 5 + idx),
                duration_seconds=seconds,
                is_correct=correct,
                used_hint=idx == 0,
                used_solution_view=False,
            )
        )
        for idx, (correct, seconds) in enumerate(specs)
    ]


def _seed_events(uid: uuid.UUID) -> list[object]:
    return [
        AttemptEvent.from_schema(
            AttemptEventSchema(user_id=uid, event_at=_kst(9, 10), event_type=EventType.막힘)
        ),
        AttemptEvent.from_schema(
            AttemptEventSchema(user_id=uid, event_at=_kst(9, 11), event_type=EventType.힌트요청)
        ),
        # 소크라테스 아님 — socratic_turns에 세지 않는다(변별력).
        AttemptEvent.from_schema(
            AttemptEventSchema(user_id=uid, event_at=_kst(9, 12), event_type=EventType.계산)
        ),
    ]


def test_rollup_loads_metrics_and_me_endpoint_serves_them() -> None:
    """④ 적재 전 0행 → 후 N행 실측 + ⑤ /v1/me 응답에 통계가 실제로 실리는지 실측."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a), _user(uid_b), _problem()))
        asyncio.run(_add_all(*_seed_rows(uid_a, sid_a), *_seed_rows(uid_b, sid_b)))
        asyncio.run(_add_all(*_seed_attempts(uid_a, sid_a), *_seed_attempts(uid_b, sid_b)))
        asyncio.run(_add_all(*_seed_events(uid_a)))

        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        params = {"since": _DAY.isoformat(), "until": _DAY.isoformat()}

        # ── ④ before: 원천은 적재됐지만 지표 테이블은 0행 ──
        before = asyncio.run(_count_rows())
        assert before["daily_learning_metrics"] == 0, (
            "집계 실행 전인데 daily_learning_metrics에 행이 있다 — 전/후 대조가 무의미해진다 "
            f"(before={before})"
        )
        assert before["user_behavior_metrics"] == 0, before
        assert before["problem_solve_time_distribution"] == 0, before

        # ── ⑤ before: 도달 축도 비어 있어야 한다(응답이 항상 차 있으면 변별력 0) ──
        with _client() as client:
            empty = client.get("/v1/me/learning-metrics", headers=auth, params=params)
            assert empty.status_code == 200, empty.text
            assert empty.json()["days"] == []
            assert empty.json()["summary"]["days_counted"] == 0
            assert empty.json()["summary"]["total_minutes_active"] is None

        # ── 집계 실행 (프로덕션 writer) ──
        report = asyncio.run(_run_rollup())
        assert report["scanned"]["learning_session"] >= 4, report
        assert report["scanned"]["problem_attempt"] >= 6, report

        # ── ④ after: 세 테이블 모두 0 → N ──
        after = asyncio.run(_count_rows())
        assert after["daily_learning_metrics"] >= 2, after  # 학생 A·B 각 1행
        assert after["user_behavior_metrics"] >= 2, after
        for table, count in after.items():
            assert count > before[table], f"{table}: 집계 전후 행수가 같다({count}) — 위장 통과"

        # ── ⑤ after: 인증 학생 응답에 통계가 실제로 실린다 ──
        with _client() as client:
            resp = client.get("/v1/me/learning-metrics", headers=auth, params=params)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body["days"]) == 1, body
            day = body["days"][0]
            assert day["metric_date"] == _DAY.isoformat()
            assert day["minutes_active"] == 45  # 1800+900초
            assert day["problems_attempted"] == 3
            assert day["problems_correct"] == 1  # 미채점 NULL은 정답 아님
            assert day["socratic_turns"] == 2  # 계산 이벤트 제외
            assert day["avg_focus_score"] == pytest.approx(0.7)

            summary = body["summary"]
            assert summary["days_counted"] == 1
            assert summary["total_minutes_active"] == 45
            assert summary["accuracy_rate"] == pytest.approx(1 / 3, abs=1e-4)
            assert summary["avg_minutes_per_active_day"] == pytest.approx(45.0)

            # ⑦ 타인 데이터 차단 — B의 user_id를 넘겨도 A의 통계만(파라미터 자체가 없다).
            leak = client.get(
                "/v1/me/learning-metrics",
                headers=auth,
                params={**params, "user_id": str(uid_b)},
            )
            assert leak.status_code == 200, leak.text
            assert leak.json()["days"] == body["days"], "user_id 파라미터로 타인 조회가 됐다"

            # 무토큰 401
            assert client.get("/v1/me/learning-metrics").status_code == 401
    finally:
        asyncio.run(_cleanup([uid_a, uid_b]))


def test_rollup_is_idempotent_and_reconciles() -> None:
    """② 멱등 — 재실행해도 행수가 늘지 않고, 원천이 줄면 재집계가 지표를 정정한다."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    sid = uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid), _problem()))
        asyncio.run(_add_all(*_seed_rows(uid, sid)))
        asyncio.run(_add_all(*_seed_attempts(uid, sid)))

        asyncio.run(_run_rollup())
        first = asyncio.run(_count_rows())
        assert first["daily_learning_metrics"] == 1, first

        # 재실행 — 같은 PK에 DO UPDATE라 행수 불변(중복 적재면 2가 되어 빨개진다).
        asyncio.run(_run_rollup())
        second = asyncio.run(_count_rows())
        assert second == first, f"재실행이 멱등하지 않다: {first} → {second}"

        # 원천 시도를 지우고 재집계 → 지표가 정정된다(스테일 잔존 금지).
        async def _drop_attempts() -> None:
            engine = create_async_engine(_settings().database_url)
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text("DELETE FROM problem_attempt WHERE user_id = :uid"), {"uid": str(uid)}
                    )
            finally:
                await engine.dispose()

        asyncio.run(_drop_attempts())
        asyncio.run(_run_rollup())

        token = create_access_token(uid, settings=_settings())
        with _client() as client:
            body = client.get(
                "/v1/me/learning-metrics",
                headers={"Authorization": f"Bearer {token}"},
                params={"since": _DAY.isoformat(), "until": _DAY.isoformat()},
            ).json()
        assert (
            body["days"][0]["problems_attempted"] is None
        ), "원천 시도가 사라졌는데 지표에 옛 시도 수가 남아 있다 — 재집계가 정합을 회복하지 못함"
        assert body["days"][0]["minutes_active"] == 45  # 세션은 그대로라 학습 시간은 유지
    finally:
        asyncio.run(_cleanup([uid]))
