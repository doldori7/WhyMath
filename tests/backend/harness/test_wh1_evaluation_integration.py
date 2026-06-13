"""WH-1 0단계 대리 지표 — 실 PG 통합테스트 (기본 SKIP).

`GET /v1/me/harness-metrics`를 실 PostgreSQL로 검증한다:
  - ① verify 통과율: user A의 검산결과 attempt_event N개(passed 일부) → MEASURED·정확값.
  - ③ 세션 완주율: user A의 세션 N개(일부 ended·일부 NULL) 적재 → MEASURED·정확값.
  - ④ 턴당 토큰: user A의 Dialogue(일부 total_tokens/total_turns 채움) → MEASURED 또는 NO_DATA.
  - ⑤ 도움 감소 곡선: user A의 힌트제공 attempt_event N개(event_at 순서·hint_level 하강) →
    MEASURED·음수 기울기. 데이터 없으면 NO_DATA(날조 0).
  - ②⑥⑦ 미계측 3종: 고정 status·value None(날조 0).
  - 401(무토큰)·user 스코핑(타 user B 세션은 A 집계에서 제외).

직전 슬라이스(`api/test_me_integration.py`) 헬퍼 패턴 재사용 — 독립 엔진으로 ORM 적재·정리,
get_settings만 오버라이드(jwt 시크릿)·get_session은 실 PG. `@pytest.mark.integration`(기본 skip).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import (
    AttemptEvent,
    LearningSession,
    ProblemAttempt,
)
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import EventType, Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

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


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    ids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: 자식(dialogue·problem_attempt·learning_session·attempt_event) 먼저,
            # 부모(user_profile) 나중. problem_attempt는 learning_session 자식이므로 먼저 지운다.
            await conn.execute(
                text("DELETE FROM dialogue WHERE user_id = ANY(:ids)"), {"ids": ids}
            )
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM attempt_event WHERE user_id = ANY(:ids)"),
                {"ids": ids},
            )
            await conn.execute(
                text("DELETE FROM learning_session WHERE user_id = ANY(:ids)"),
                {"ids": ids},
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


def _session_row(uid: uuid.UUID, *, ended: bool) -> LearningSession:
    return LearningSession.from_schema(
        LearningSessionSchema(
            session_id=uuid.uuid4(),
            user_id=uid,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) if ended else None,
        )
    )


def _dialogue_row(
    uid: uuid.UUID, *, total_tokens: int | None, total_turns: int | None
) -> Dialogue:
    return Dialogue.from_schema(
        DialogueSchema(
            dialogue_id=uuid.uuid4(),
            user_id=uid,
            started_at=datetime.now(UTC),
            total_tokens=total_tokens,
            total_turns=total_turns,
        )
    )


def _verify_event_row(uid: uuid.UUID, *, passed: bool) -> AttemptEvent:
    """검산결과 attempt_event 1행(event_data.passed) — ① 통과율 표본."""
    return AttemptEvent(
        event_at=datetime.now(UTC),
        user_id=uid,
        event_type=EventType.검산결과,
        event_data={"passed": passed, "error_kind": (None if passed else "arithmetic")},
    )


def _hint_event_row(uid: uuid.UUID, *, hint_level: int, order: int) -> AttemptEvent:
    """힌트제공 attempt_event 1행(event_data.hint_level) — ⑤ 도움 감소 곡선 표본.

    `order`로 event_at을 서로 다르게 어긋내(now + order초) event_at 오름차순 정렬이 결정적이게
    한다 — OLS x축이 적재 순서와 일치하도록.
    """
    return AttemptEvent(
        event_at=datetime.now(UTC) + timedelta(seconds=order),
        user_id=uid,
        event_type=EventType.힌트제공,
        event_data={"hint_level": hint_level},
    )


def _attempt_row(uid: uuid.UUID, *, is_correct: bool, order: int) -> ProblemAttempt:
    """ProblemAttempt 1행(is_correct) — R15 정답률 추세 표본.

    `order`로 started_at을 서로 다르게 어긋내(now + order초) started_at 오름차순 정렬이
    결정적이게 한다 — 정답률 OLS x축이 적재 순서와 일치하도록. problem_id는 nullable FK라
    None으로 둔다(별도 problem 행 적재 회피·집계는 is_correct만 본다).
    """
    return ProblemAttempt.from_schema(
        ProblemAttemptSchema(
            attempt_id=uuid.uuid4(),
            user_id=uid,
            started_at=datetime.now(UTC) + timedelta(seconds=order),
            is_correct=is_correct,
        )
    )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_harness_metrics_measured_and_scoped_on_live_pg() -> None:
    """A: 세션 4개(완주 3·미완주 1)·대화 토큰 채움 → ③ MEASURED 0.75·④ MEASURED. B는 제외. 401."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid_a), _user(uid_b)))
        # A: 세션 4개 중 3개 완주(ended_at NOT NULL) → 완주율 0.75.
        asyncio.run(
            _add_all(
                _session_row(uid_a, ended=True),
                _session_row(uid_a, ended=True),
                _session_row(uid_a, ended=True),
                _session_row(uid_a, ended=False),
            )
        )
        # B: 세션 2개 전부 완주 — A 집계에 *섞이면 안 됨*(user 스코핑 핵심).
        asyncio.run(
            _add_all(_session_row(uid_b, ended=True), _session_row(uid_b, ended=True))
        )
        # A: 대화 2개 토큰 채움(100/10=10, 60/6=10) + 토큰 없는 1개(집계 제외).
        asyncio.run(
            _add_all(
                _dialogue_row(uid_a, total_tokens=100, total_turns=10),
                _dialogue_row(uid_a, total_tokens=60, total_turns=6),
                _dialogue_row(uid_a, total_tokens=None, total_turns=None),
            )
        )
        # A: 검산결과 이벤트 4개(passed 3·실패 1) → ① 통과율 0.75. B는 1개(섞이면 안 됨·스코핑).
        asyncio.run(
            _add_all(
                _verify_event_row(uid_a, passed=True),
                _verify_event_row(uid_a, passed=True),
                _verify_event_row(uid_a, passed=True),
                _verify_event_row(uid_a, passed=False),
                _verify_event_row(uid_b, passed=False),
            )
        )
        # A: 힌트제공 이벤트 4개(event_at 순서 hint_level 4→3→2→1·등차) → ⑤ OLS 기울기 −1.0.
        # B는 1개(섞이면 안 됨·스코핑).
        asyncio.run(
            _add_all(
                _hint_event_row(uid_a, hint_level=4, order=0),
                _hint_event_row(uid_a, hint_level=3, order=1),
                _hint_event_row(uid_a, hint_level=2, order=2),
                _hint_event_row(uid_a, hint_level=1, order=3),
                _hint_event_row(uid_b, hint_level=4, order=0),
            )
        )
        # A: ProblemAttempt 4개(is_correct F→T→T→T·started_at 순서) → 정답률 추세 상승(양수
        # 기울기). 도움↓(−1.0)·정답률↑ 교차 → R15 GENUINE_IMPROVEMENT. B는 1개(스코핑·제외).
        asyncio.run(
            _add_all(
                _attempt_row(uid_a, is_correct=False, order=0),
                _attempt_row(uid_a, is_correct=True, order=1),
                _attempt_row(uid_a, is_correct=True, order=2),
                _attempt_row(uid_a, is_correct=True, order=3),
                _attempt_row(uid_b, is_correct=False, order=0),
            )
        )
        token_a = create_access_token(uid_a, settings=_settings())
        auth = {"Authorization": f"Bearer {token_a}"}
        with _client() as client:
            resp = client.get("/v1/me/harness-metrics", headers=auth)
            assert resp.status_code == 200, resp.text
            body = resp.json()

            # ③ 세션 완주율 — MEASURED·정확값(3/4=0.75)·A만(B의 2건 제외 → 표본 4).
            scr = body["session_completion_rate"]
            assert scr["status"] == "measured"
            assert scr["value"] == 0.75
            assert body["sample_sessions"] == 4  # A의 4건만(B 제외 — 스코핑 핵심)

            # ④ 턴당 토큰 — MEASURED·AVG(10,10)=10·표본 2(토큰 없는 1개 제외).
            tpt = body["tokens_per_turn"]
            assert tpt["status"] == "measured"
            assert tpt["value"] == 10.0
            assert body["sample_dialogues"] == 2

            # ① verify 통과율 — MEASURED·passed 3/4=0.75·표본 4(B의 1건 제외 — 스코핑).
            vpr = body["verify_pass_rate"]
            assert vpr["status"] == "measured"
            assert vpr["value"] == 0.75
            assert body["sample_verify_events"] == 4
            assert "미적발" in vpr["note"]  # binary 검산 정직 note(3-state 아님)

            # ⑤ 도움 감소 곡선 — MEASURED·기울기 −1.0(4→3→2→1 등차 하강·도움 감소)·표본 4
            # (B의 1건 제외 — 스코핑). raw 기울기·R15 미반영 정직 note.
            hrs = body["help_reduction_slope"]
            assert hrs["status"] == "measured"
            assert hrs["value"] == -1.0
            assert hrs["value"] < 0  # 음수=도움 감소=개선
            assert body["sample_hint_events"] == 4
            assert "R15" in hrs["note"]  # 정확률 교차검증 미반영 정직 표기
            assert "종단" in hrs["note"]

            # R15 결합 판정 — 도움↓(−1.0)·정답률↑(F→T→T→T) → GENUINE_IMPROVEMENT·표본 4
            # (B의 1건 제외 — 스코핑). is_correct 추세(① 검산 proxy 아님)로 교차.
            hrv = body["help_reduction_validated"]
            assert hrv["verdict"] == "genuine_improvement"
            assert hrv["help_slope"] == -1.0
            assert hrv["accuracy_slope"] is not None and hrv["accuracy_slope"] > 0
            assert body["sample_accuracy_attempts"] == 4

            # 미계측 3종(②⑥⑦) — value None·고정 status(날조 0).
            assert body["diagnosis_agreement_rate"]["status"] == "requires_data"
            assert body["calibration_brier"]["status"] == "requires_tool"
            assert body["transfer_score"]["status"] == "requires_tool"
            for key in (
                "diagnosis_agreement_rate",
                "calibration_brier",
                "transfer_score",
            ):
                assert body[key]["value"] is None

            assert body["user_scoped"] is True

            # 무토큰 401.
            assert client.get("/v1/me/harness-metrics").status_code == 401
    finally:
        asyncio.run(_cleanup([uid_a, uid_b]))


def test_harness_metrics_no_data_when_empty_on_live_pg() -> None:
    """데이터 없는 user → ①③④⑤ NO_DATA·value None(가짜 0 금지)·표본 0."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    try:
        asyncio.run(_add_all(_user(uid)))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            resp = client.get("/v1/me/harness-metrics", headers=auth)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["session_completion_rate"]["status"] == "no_data"
            assert body["session_completion_rate"]["value"] is None
            assert body["tokens_per_turn"]["status"] == "no_data"
            assert body["tokens_per_turn"]["value"] is None
            assert body["verify_pass_rate"]["status"] == "no_data"
            assert body["verify_pass_rate"]["value"] is None
            # ⑤ 도움 감소 곡선 — 힌트제공 0건 → NO_DATA·value None(가짜 기울기/0 금지).
            assert body["help_reduction_slope"]["status"] == "no_data"
            assert body["help_reduction_slope"]["value"] is None
            # R15 결합 판정 — 도움/정답률 둘 다 표본 0 → INSUFFICIENT_DATA(날조 판정 금지).
            hrv = body["help_reduction_validated"]
            assert hrv["verdict"] == "insufficient_data"
            assert hrv["help_slope"] is None
            assert hrv["accuracy_slope"] is None
            assert body["sample_sessions"] == 0
            assert body["sample_dialogues"] == 0
            assert body["sample_verify_events"] == 0
            assert body["sample_hint_events"] == 0
            assert body["sample_accuracy_attempts"] == 0
    finally:
        asyncio.run(_cleanup([uid]))
