"""WH-1 영속 턴(`harness/wh1_session.py`) — 단위(hermetic·스토어 스텁) + 실 PG 통합.

단위: `run_persisted_turn`의 *오케스트레이션*(웜 스타트 로드 → 순수 루프 → 증거/가설 영속 위임)을
스토어 3종(`get_active_hypotheses`·`log_evidence`·`persist_hypotheses`)을 스텁해 hermetic 검증한다.
★실제 영속(FK·CASCADE·왕복 일관)은 *실 PG 통합테스트*가 검증한다(load→run→persist→reload).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.harness import wh1_session
from whymath_backend.harness.wh1_loop import (
    CurateHypothesisAction,
    EndTurnAction,
    LogEvidenceAction,
    MatchMisconceptionAction,
    ScriptedTutorPolicy,
)
from whymath_backend.l4.misconception.evidence_store import get_evidence_for_student
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.hypothesis_store import get_active_hypotheses
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

# diagnose가 confidence 1.0으로 잡는 실 신호·실 카탈로그 id.
_MATCH_TEXT = "(a+b) a² + b²"
_MID = "distribution-over-power"


def _turn_policy() -> ScriptedTutorPolicy:
    """match → curate → log_evidence(+1) → end_turn(질문) — 가설 1·증거 1 산출 시나리오."""
    return ScriptedTutorPolicy(
        [
            MatchMisconceptionAction(student_text=_MATCH_TEXT),
            CurateHypothesisAction(),
            LogEvidenceAction(misconception_id=_MID, polarity=1, weight=1.0),
            EndTurnAction(action_type="질문", utterance=None),
        ]
    )


# ===========================================================================
# 단위 (hermetic·스토어 스텁) — 로드→실행→영속 오케스트레이션
# ===========================================================================


class TestRunPersistedTurnWiring:
    def _patch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        initial: list[MisconceptionHypothesis],
        ev_sink: list[tuple[str, int, float | None]],
        hyp_sink: list[MisconceptionHypothesis],
    ) -> None:
        async def fake_get_active(
            session: AsyncSession, student_id: uuid.UUID
        ) -> list[MisconceptionHypothesis]:
            return list(initial)

        async def fake_log_evidence(
            session: AsyncSession,
            *,
            session_id: uuid.UUID,
            student_id: uuid.UUID,
            misconception_id: str,
            polarity: int,
            weight: float | None = None,
            **_: Any,
        ) -> None:
            ev_sink.append((misconception_id, polarity, weight))

        async def fake_persist(
            session: AsyncSession,
            user_id: uuid.UUID,
            hypotheses: list[MisconceptionHypothesis],
        ) -> None:
            hyp_sink.extend(hypotheses)

        monkeypatch.setattr(wh1_session, "get_active_hypotheses", fake_get_active)
        monkeypatch.setattr(wh1_session, "log_evidence", fake_log_evidence)
        monkeypatch.setattr(wh1_session, "persist_hypotheses", fake_persist)

    def test_load_run_persist_orchestration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """웜 스타트 로드 → 순수 루프 → 증거·최종 가설 세트를 스토어에 영속 위임."""
        ev_sink: list[tuple[str, int, float | None]] = []
        hyp_sink: list[MisconceptionHypothesis] = []
        self._patch(monkeypatch, initial=[], ev_sink=ev_sink, hyp_sink=hyp_sink)

        outcome = asyncio.run(
            wh1_session.run_persisted_turn(
                cast(AsyncSession, object()),
                student_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                policy=_turn_policy(),
            )
        )
        assert outcome.status == "ended"
        # 증거 1건이 evidence_links로 영속 위임됨(게이트 통과 엣지만).
        assert ev_sink == [(_MID, 1, 1.0)]
        # 최종 활성 가설 세트가 persist_hypotheses로 영속 위임됨(_MID 포함·outcome과 동일).
        persisted_ids = {h.misconception_id for h in hyp_sink}
        assert persisted_ids == {h.misconception_id for h in outcome.hypotheses}
        assert _MID in persisted_ids

    def test_no_evidence_no_log_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """증거 적재가 없으면 log_evidence 호출 0(가설만 영속)."""
        ev_sink: list[tuple[str, int, float | None]] = []
        hyp_sink: list[MisconceptionHypothesis] = []
        self._patch(monkeypatch, initial=[], ev_sink=ev_sink, hyp_sink=hyp_sink)

        outcome = asyncio.run(
            wh1_session.run_persisted_turn(
                cast(AsyncSession, object()),
                student_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                policy=ScriptedTutorPolicy([EndTurnAction(action_type="격려", utterance="ok")]),
            )
        )
        assert outcome.status == "ended"
        assert ev_sink == []  # 증거 0 → log_evidence 미호출


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — load→run→persist→reload 왕복
# ===========================================================================

_SECRET = "integration-jwt-secret-0123456789abcdef"


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


def _build_user(user_id: uuid.UUID) -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(
            user_id=user_id,
            persona_primary=Persona.A_일반고고3,
            nickname="턴학생",
            email_hash=f"HASH-{user_id.hex[:8]}",
            is_minor=True,
        )
    )


async def _seed_user(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(_build_user(user_id))
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :u"), {"u": str(user_id)}
            )
            await conn.execute(
                text("DELETE FROM evidence_links WHERE student_id = :u"), {"u": str(user_id)}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :u"), {"u": str(user_id)}
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_run_persisted_turn_roundtrip_on_live_pg() -> None:
    """한 턴 영속 후 재로드 — 가설 세트·증거가 DB에 실제로 남는다(웜 스타트 연속성)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sid = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                outcome = await wh1_session.run_persisted_turn(
                    session,
                    student_id=uid,
                    session_id=sid,
                    policy=_turn_policy(),
                )
                await session.commit()  # commit은 호출자 책임
                assert outcome.status == "ended"
                assert _MID in {h.misconception_id for h in outcome.hypotheses}

            # 재로드 — 다음 턴 웜 스타트가 볼 스냅샷.
            async with sm() as session:
                reloaded = await get_active_hypotheses(session, uid)
                assert _MID in {h.misconception_id for h in reloaded}
                evidence = await get_evidence_for_student(session, uid)
                assert len(evidence) == 1
                assert evidence[0].misconception_id == _MID
                assert evidence[0].polarity == 1
        finally:
            await engine.dispose()

    try:
        asyncio.run(_seed_user(uid))
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(uid))
