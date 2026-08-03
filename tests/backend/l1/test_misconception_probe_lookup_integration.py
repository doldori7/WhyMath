"""오개념 표적 프로브 역인덱스 조회 *통합테스트* — REC-02 (WHYMATH_RUN_INTEGRATION).

실 PostgreSQL에 `distractor_map` 태깅된 `Problem` 3건 + `ProblemAttempt` 1건을 적재해
`lookup_probe_candidates_by_mids`가 3사유(kept·missing_difficulty·fully_administered)를
실제로 구분하는지, `matched_target_mids`가 코퍼스에 실재하는 mid만 담는지 라운드트립으로
검증한다. PG 미도달 시 graceful skip(`test_misconception_resolve_integration.py` 미러).

적재 키는 실 데이터와 충돌하지 않도록 문항 id는 매번 새 UUID(`uuid.uuid4()`)를 쓰고, mid는
`IT-`(integration test) 접두 슬러그를 쓴다.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l1.misconception.probe_lookup import lookup_probe_candidates_by_mids
from whymath_backend.schema.enums import Curriculum, Persona, SourceType, Subject
from whymath_backend.schema.problem import DistractorEntry
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema

pytestmark = pytest.mark.integration

_MID_KEPT = "IT-M-KEPT"
_MID_MISSING_DIFFICULTY = "IT-M-MISSING-DIFF"
_MID_ADMINISTERED = "IT-M-ADMINISTERED"
_MID_UNTAGGED = "IT-M-UNTAGGED"  # 코퍼스 어디에도 태깅되지 않음 — matched_target_mids에서 빠져야 함
_TARGET_MIDS = frozenset({_MID_KEPT, _MID_MISSING_DIFFICULTY, _MID_ADMINISTERED, _MID_UNTAGGED})


def _settings() -> Settings:
    return Settings()


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


async def _cleanup(user_id: uuid.UUID, problem_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(p) for p in problem_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: problem_attempt(자식) 먼저, problem·user_profile(부모) 나중.
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = :uid"), {"uid": str(user_id)}
            )
            await conn.execute(
                text("DELETE FROM problem WHERE problem_id = ANY(:ids)"), {"ids": ids}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(user_id)}
            )
    finally:
        await engine.dispose()


def _problem(pid: uuid.UUID, *, mid: str, difficulty_overall: float | None) -> Problem:
    return Problem.from_schema(
        ProblemSchema(
            problem_id=pid,
            source_type=SourceType.자체생성,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.공통,
            unit_codes=[f"IT-{pid.hex[:8]}"],
            difficulty_overall=difficulty_overall,
            distractor_map=[DistractorEntry(choice_index=0, misconception_id=mid)],
        )
    )


class TestLookupProbeCandidatesByMids:
    def test_three_reasons_and_matched_mids(self) -> None:
        if not asyncio.run(_pg_reachable()):
            pytest.skip("실 PostgreSQL 미도달 — 통합테스트 skip")

        uid = uuid.uuid4()
        kept_pid = uuid.uuid4()
        missing_pid = uuid.uuid4()
        administered_pid = uuid.uuid4()
        problem_ids = [kept_pid, missing_pid, administered_pid]

        async def _setup_and_run() -> tuple:
            await _add_all(
                UserProfile.from_schema(
                    UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
                )
            )
            await _add_all(
                _problem(kept_pid, mid=_MID_KEPT, difficulty_overall=3.0),
                _problem(missing_pid, mid=_MID_MISSING_DIFFICULTY, difficulty_overall=None),
                _problem(administered_pid, mid=_MID_ADMINISTERED, difficulty_overall=2.0),
            )
            await _add_all(
                ProblemAttempt(
                    attempt_id=uuid.uuid4(),
                    user_id=uid,
                    problem_id=administered_pid,
                    is_correct=True,
                )
            )

            engine = create_async_engine(_settings().database_url)
            try:
                async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                    return await lookup_probe_candidates_by_mids(
                        session, user_id=uid, target_mids=_TARGET_MIDS
                    )
            finally:
                await engine.dispose()

        try:
            result = asyncio.run(_setup_and_run())
        finally:
            asyncio.run(_cleanup(uid, problem_ids))

        assert [row.problem_id for row in result.kept] == [kept_pid]
        assert result.kept[0].difficulty_overall == 3.0
        assert result.kept[0].misconception_tags == frozenset({_MID_KEPT})
        assert result.missing_difficulty == 1
        assert result.fully_administered == 1
        # 미태깅(_MID_UNTAGGED)은 코퍼스 어디에도 없으니 matched에서 빠진다.
        assert result.matched_target_mids == frozenset(
            {_MID_KEPT, _MID_MISSING_DIFFICULTY, _MID_ADMINISTERED}
        )
