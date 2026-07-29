"""WH-1 학습 증거 저장소(`l4/misconception/evidence_store.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `log_evidence` 게이트(미등록 오개념·잘못된 극성 거부)·정상 적재·조회/집계/파기
래퍼를 hermetic 검증한다. ★삭제권 FK CASCADE·polarity CHECK·net_support 집계·retention 파기는
*실 PG 통합테스트*가 검증한다(제약·CASCADE는 실 DB라야 의미).
"""

from __future__ import annotations

import asyncio
import logging
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
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.evidence_link import EvidenceLink
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.evidence_store import (
    EvidenceValidationError,
    default_retention_until,
    get_evidence_for_misconception,
    get_evidence_for_student,
    log_evidence,
    net_support,
    net_support_by_misconception,
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
        self,
        *,
        scalars_list: list[Any] | None = None,
        scalar_one: Any = None,
        rowcount: int = 0,
        all_rows: list[Any] | None = None,
    ) -> None:
        self._scalars_list = scalars_list or []
        self._scalar_one = scalar_one
        self.rowcount = rowcount
        self._all_rows = all_rows or []

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)

    def scalar_one(self) -> Any:
        return self._scalar_one

    def all(self) -> list[Any]:
        return self._all_rows


class _FakeSession:
    def __init__(
        self,
        *,
        scalars_list: list[Any] | None = None,
        scalar_one: Any = None,
        rowcount: int = 0,
        all_rows: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self._scalars_list = scalars_list or []
        self._scalar_one = scalar_one
        self._rowcount = rowcount
        self._all_rows = all_rows or []

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
            scalars_list=self._scalars_list,
            scalar_one=self._scalar_one,
            rowcount=self._rowcount,
            all_rows=self._all_rows,
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


class _SpyResolver:
    """resolve 호출 여부·인자를 기록하는 스파이 resolver(crosswalk shadow 배선 검증용)."""

    def __init__(self, mis_ids: list[str] | None = None) -> None:
        self.calls: list[str] = []
        self._mis_ids = mis_ids or []

    def resolve(self, kebab_id: str, *, min_confidence: float | None = None) -> list[str]:
        self.calls.append(kebab_id)
        return self._mis_ids


class _BoomResolver:
    """resolve가 항상 raise — never-break(적재 무결성) 단언용."""

    def resolve(self, *args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("crosswalk DB 미도달")


_RECORD_LOGGER = "whymath.l4.misconception.crosslink_shadow.record"


class TestCrosslinkShadowWiring:
    """게이트 공존 배선 — mode off/shadow에서 적재 본류 불변·shadow 비차단(비노출 측정)."""

    def test_off_skips_resolver_and_persists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """off(기본) → resolver 미호출(crosswalk 조회 0)·kebab-id 그대로 적재."""
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_CROSSLINK_MODE", "off")
        get_settings.cache_clear()
        spy = _SpyResolver(mis_ids=["M1"])
        try:
            session = _FakeSession()
            link = _log(session, crosslink_resolver=cast(Any, spy))
            assert spy.calls == []  # off → resolve 미호출
            assert link.misconception_id == _VALID_MID  # kebab 그대로
            assert session.added == [link]
        finally:
            get_settings.cache_clear()

    def test_shadow_resolves_but_persists_kebab(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """shadow → resolver 호출·record 로깅하되 적재는 kebab-id 그대로(노출·저장 불변)."""
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_CROSSLINK_MODE", "shadow")
        get_settings.cache_clear()
        spy = _SpyResolver(mis_ids=["M1", "M2"])
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                session = _FakeSession()
                link = _log(session, crosslink_resolver=cast(Any, spy))
            assert spy.calls == [_VALID_MID]  # shadow → kebab으로 resolve 호출
            assert link.misconception_id == _VALID_MID  # 저장은 여전히 kebab
            records = [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]
            assert len(records) == 1  # shadow 관측 1건 기록
        finally:
            get_settings.cache_clear()

    def test_shadow_resolver_failure_does_not_break_persist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """shadow에서 resolve raise → 적재는 정상(never-break·증거 무결성 우선)."""
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_CROSSLINK_MODE", "shadow")
        get_settings.cache_clear()
        try:
            session = _FakeSession()
            link = _log(session, crosslink_resolver=cast(Any, _BoomResolver()))
            assert isinstance(link, EvidenceLink)
            assert link.misconception_id == _VALID_MID
            assert session.added == [link]
        finally:
            get_settings.cache_clear()


class TestRetentionDefault:
    """GDPR 데이터 최소화 — 적재 시 보존기한 *자동* 채움(무기한 보존 금지)."""

    def test_default_retention_until_pure(self) -> None:
        """순수 헬퍼 — +years년·2/29는 비윤년 2/28 클램프."""
        assert default_retention_until(date(2026, 1, 15), years=3) == date(2029, 1, 15)
        assert default_retention_until(date(2024, 2, 29), years=3) == date(2027, 2, 28)
        assert default_retention_until(date(2026, 6, 18), years=1) == date(2027, 6, 18)

    def test_log_evidence_fills_retention_when_absent(self) -> None:
        """retention_until 미제공 → logged_on + Settings 기본(3년)으로 *반드시* 채움."""
        session = _FakeSession()
        link = _log(session, logged_on=date(2026, 1, 15))
        # 기본 evidence_retention_years=3 → 2029-01-15(무기한 None 금지).
        assert link.retention_until == date(2029, 1, 15)

    def test_log_evidence_respects_explicit_retention(self) -> None:
        """retention_until 명시 제공 → 그 값 존중(자동 기본 덮어쓰지 않음)."""
        session = _FakeSession()
        explicit = date(2030, 12, 31)
        link = _log(session, retention_until=explicit, logged_on=date(2026, 1, 15))
        assert link.retention_until == explicit

    def test_log_evidence_default_logged_on_is_today(self) -> None:
        """logged_on 미제공 → 오늘 기준 +3년(무기한 None 아님)."""
        session = _FakeSession()
        link = _log(session)
        assert link.retention_until == default_retention_until(date.today(), years=3)
        assert link.retention_until is not None


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

    def test_net_support_by_misconception_maps_rows(self) -> None:
        """GROUP BY 행 (mid, support) → {mid: float} 매핑·증거 없는 오개념은 키 부재."""
        session = _FakeSession(all_rows=[("mc-a", 2.5), ("mc-b", -1.0)])
        out = asyncio.run(net_support_by_misconception(cast(AsyncSession, session), uuid.uuid4()))
        assert out == {"mc-a": 2.5, "mc-b": -1.0}

    def test_net_support_by_misconception_empty(self) -> None:
        session = _FakeSession(all_rows=[])
        out = asyncio.run(net_support_by_misconception(cast(AsyncSession, session), uuid.uuid4()))
        assert out == {}

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
                # 배치 GROUP BY 집계가 단건 net_support와 일치(실 SQL 검증).
                by_mc = await net_support_by_misconception(session, uid)
                assert by_mc == {_VALID_MID: pytest.approx(2.5)}
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
