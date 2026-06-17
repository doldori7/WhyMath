"""WH-1 학습 증거 저장소(`l4/misconception/evidence_store.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `log_evidence` 게이트(미등록 오개념·잘못된 극성 거부)·정상 적재·조회/집계/파기
래퍼를 hermetic 검증한다. ★삭제권 FK CASCADE·polarity CHECK·net_support 집계·retention 파기는
*실 PG 통합테스트*가 검증한다(제약·CASCADE는 실 DB라야 의미).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from whymath_backend.config import Settings
from whymath_backend.db.models.evidence_link import EvidenceLink
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.evidence_store import (
    EvidenceValidationError,
    get_evidence_for_misconception,
    get_evidence_for_student,
    log_evidence,
    net_support,
    purge_expired,
)
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

# 정본 카탈로그의 실제 오개념 id(미등록 거부 테스트 대비 — 동적 취득).
_VALID_MID = next(iter(CATALOG_BY_ID))

# ===========================================================================
# 단위 (hermetic·FakeSession)
# ===========================================================================


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeResult:
    def __init__(
        self, *, scalars_list: list[Any] | None = None, scalar_one: Any = None, rowcount: int = 0
    ) -> None:
        self._scalars_list = scalars_list or []
        self._scalar_one = scalar_one
        self.rowcount = rowcount

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)

    def scalar_one(self) -> Any:
        return self._scalar_one


class _FakeSession:
    def __init__(
        self, *, scalars_list: list[Any] | None = None, scalar_one: Any = None, rowcount: int = 0
    ) -> None:
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self._scalars_list = scalars_list or []
        self._scalar_one = scalar_one
        self._rowcount = rowcount

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        if getattr(obj, "link_id", None) is None:
            obj.link_id = 1  # BIGSERIAL 시뮬

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(
            scalars_list=self._scalars_list, scalar_one=self._scalar_one, rowcount=self._rowcount
        )


def _log(session: Any, **kw: Any) -> Any:
    base: dict[str, Any] = dict(
        session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        misconception_id=_VALID_MID,
        polarity=1,
    )
    base.update(kw)
    return asyncio.run(log_evidence(cast(AsyncSession, session), **base))


class TestLogEvidenceGate:
    def test_rejects_unknown_misconception(self) -> None:
        """미등록 misconception_id → EvidenceValidationError(적재 안 함)."""
        session = _FakeSession()
        with pytest.raises(EvidenceValidationError, match="카탈로그"):
            _log(session, misconception_id="nonexistent-mc-xyz")
        assert session.added == []

    @pytest.mark.parametrize("bad", [0, 2, -2, 5])
    def test_rejects_invalid_polarity(self, bad: int) -> None:
        """polarity ∉ {−1,+1} → EvidenceValidationError(적재 안 함)."""
        session = _FakeSession()
        with pytest.raises(EvidenceValidationError, match="극성"):
            _log(session, polarity=bad)
        assert session.added == []

    @pytest.mark.parametrize("good", [1, -1])
    def test_valid_builds_and_persists(self, good: int) -> None:
        """유효 게이트 통과 → EvidenceLink 구성·add/flush/refresh·link_id 채움."""
        session = _FakeSession()
        link = _log(session, polarity=good, node_id="HIGH-ALG-001", weight=0.8)
        assert isinstance(link, EvidenceLink)
        assert link.misconception_id == _VALID_MID
        assert link.polarity == good
        assert link.node_id == "HIGH-ALG-001"
        assert link.weight == 0.8
        assert link.link_id == 1
        assert session.added == [link]


class TestQueriesUnit:
    def test_get_for_student_returns_scalars(self) -> None:
        rows = [EvidenceLink(student_id=uuid.uuid4(), misconception_id=_VALID_MID, polarity=1)]
        session = _FakeSession(scalars_list=rows)
        out = asyncio.run(get_evidence_for_student(cast(AsyncSession, session), uuid.uuid4()))
        assert out == rows

    def test_get_for_misconception_returns_scalars(self) -> None:
        session = _FakeSession(scalars_list=[])
        out = asyncio.run(
            get_evidence_for_misconception(cast(AsyncSession, session), uuid.uuid4(), _VALID_MID)
        )
        assert out == []

    def test_net_support_returns_float(self) -> None:
        session = _FakeSession(scalar_one=2.5)
        out = asyncio.run(net_support(cast(AsyncSession, session), uuid.uuid4(), _VALID_MID))
        assert out == 2.5

    def test_purge_returns_rowcount(self) -> None:
        session = _FakeSession(rowcount=3)
        out = asyncio.run(purge_expired(cast(AsyncSession, session), as_of=date(2026, 1, 1)))
        assert out == 3


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — FK CASCADE 삭제권·polarity CHECK·net_support·retention
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
            nickname="증거학생",
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


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    uids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            # evidence_links는 user 삭제 CASCADE로 사라지지만, 안전하게 명시 삭제 후 user.
            await conn.execute(
                text("DELETE FROM evidence_links WHERE student_id = ANY(:uids)"), {"uids": uids}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = ANY(:uids)"), {"uids": uids}
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_evidence_persist_aggregate_retention_and_cascade_on_live_pg() -> None:
    """적재·polarity CHECK·net_support 집계·retention 파기·★삭제권 FK CASCADE."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sid = uuid.uuid4()
    asyncio.run(_seed_user(uid))  # student_id FK 충족(user_profile 선적재)

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 지지(+1, w=2.0)·반박(−1, w=0.5)·만료 증거(retention 과거)
                await log_evidence(
                    session,
                    session_id=sid,
                    student_id=uid,
                    misconception_id=_VALID_MID,
                    polarity=1,
                    weight=2.0,
                )
                await log_evidence(
                    session,
                    session_id=sid,
                    student_id=uid,
                    misconception_id=_VALID_MID,
                    polarity=-1,
                    weight=0.5,
                )
                await log_evidence(
                    session,
                    session_id=sid,
                    student_id=uid,
                    misconception_id=_VALID_MID,
                    polarity=1,
                    retention_until=date.today() - timedelta(days=1),
                )
                await session.commit()

                # net_support = +1*2.0 + (−1)*0.5 + +1*1.0(weight None→1) = 2.5
                assert await net_support(session, uid, _VALID_MID) == pytest.approx(2.5)
                assert len(await get_evidence_for_misconception(session, uid, _VALID_MID)) == 3

                # retention 파기 — 만료 1건만
                purged = await purge_expired(session, as_of=date.today())
                await session.commit()
                assert purged == 1
                assert len(await get_evidence_for_student(session, uid)) == 2

            # ★삭제권 — user_profile 삭제 → evidence_links CASCADE 제거
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM user_profile WHERE user_id = :u"), {"u": str(uid)}
                )
            async with sm() as session:
                remaining = await get_evidence_for_student(session, uid)
                assert remaining == []  # CASCADE로 전부 사라짐
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([uid]))
