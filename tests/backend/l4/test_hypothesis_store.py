"""L4 활성 오개념 가설 저장소(`l4/misconception/hypothesis_store.py`) — 단위 + 실 PG 통합.

단위(hermetic): `_to_pydantic`(Record→순수 Pydantic·Numeric→float 변환)를 DB 없이 검증한다.
upsert·가지치기 비활성화·활성 세트 정렬·user 격리·#191 순수 로직과의 영속 왕복 일관성은
*실 PG 통합테스트*가 검증한다(SQL UPSERT·UniqueConstraint·is_active 필터는 실 DB라야 의미가
있다 — node_store/mastery_tracking 분리 선례). FK to user_profile이라 통합은 학생 행을 선적재한다.

**정직 스코프**: evidence_links(증거 연결)·coach 결선·진단 일치율 게이트는 후속 — 본 테스트는
가설 영속(upsert·prune·활성 세트)만 검증한다.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l4.misconception.hypothesis import (
    MisconceptionHypothesis,
    update_hypotheses,
)
from whymath_backend.l4.misconception.hypothesis_store import (
    _to_pydantic,
    apply_matches,
    get_active_hypotheses,
)
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

# ===========================================================================
# 픽스처 — 실 모델 canned 매치/오개념(#191 테스트와 동형)
# ===========================================================================


def _mc(mid: str) -> Misconception:
    """테스트용 실 `Misconception`(id만 의미·나머지는 형식 충족)."""
    return Misconception(
        id=mid,
        name_kr="테스트 오개념",
        domain="대수",
        canonical_statement="(a+b)² = a²+b²",
        counterexample="a=1, b=1",
        signals=("(a+b)^2",),
    )


def _match(mid: str, confidence: float) -> MisconceptionMatch:
    """테스트용 실 `MisconceptionMatch`(증거 1건)."""
    return MisconceptionMatch(misconception=_mc(mid), confidence=confidence)


# ===========================================================================
# 단위 (hermetic) — Record↔Pydantic 변환
# ===========================================================================


class TestToPydanticUnit:
    def test_record_to_pydantic_casts_numeric(self) -> None:
        """Record→순수 Pydantic: Numeric(Decimal) confidence를 float로 캐스팅·필드 1:1."""
        record = MisconceptionHypothesisRecord(
            user_id=uuid.uuid4(),
            misconception_id="distribution-over-power",
            confidence=Decimal("0.75"),
            turns_since_evidence=2,
            evidence_count=3,
            is_active=True,
        )
        hyp = _to_pydantic(record)
        assert isinstance(hyp, MisconceptionHypothesis)
        assert hyp.misconception_id == "distribution-over-power"
        assert isinstance(hyp.confidence, float)
        assert hyp.confidence == 0.75
        assert hyp.turns_since_evidence == 2
        assert hyp.evidence_count == 3


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — upsert·prune·활성 세트·격리·#191 왕복 일관
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
    """FK 충족용 최소 user_profile(test_users_integration 선례)."""
    return UserProfile.from_schema(
        UserProfileSchema(
            user_id=user_id,
            persona_primary=Persona.A_일반고고3,
            nickname="가설학생",
            email_hash=f"HASH-{user_id.hex[:8]}",
            is_minor=True,
        )
    )


async def _seed_users(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for uid in user_ids:
                session.add(_build_user(uid))
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    uids = [str(u) for u in user_ids]
    try:
        async with engine.begin() as conn:
            # 자식(misconception_hypothesis) → 부모(user_profile) 순.
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = ANY(:uids)"),
                {"uids": uids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = ANY(:uids)"),
                {"uids": uids},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_apply_matches_insert_upsert_prune_on_live_pg() -> None:
    """신규 insert → 재호출 upsert(강화·turns 리셋) → 증거 끊긴 가설 prune(is_active=false)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    mid_a = f"mc-a-{uid.hex[:6]}"
    mid_b = f"mc-b-{uid.hex[:6]}"

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # ── 턴1: 가설 2개 신규 insert ──
                t1 = await apply_matches(
                    session,
                    uid,
                    [_match(mid_a, 0.6), _match(mid_b, 0.5)],
                )
                await session.commit()
                by_mid_1 = {h.misconception_id: h for h in t1}
                assert set(by_mid_1) == {mid_a, mid_b}
                assert by_mid_1[mid_a].confidence == 0.6
                assert by_mid_1[mid_a].evidence_count == 1
                assert by_mid_1[mid_a].turns_since_evidence == 0

                # 활성 세트 로드(정렬·활성만)
                active = await get_active_hypotheses(session, uid)
                assert [h.misconception_id for h in active] == [mid_a, mid_b]  # 0.6>0.5

                # ── 턴2: mid_a만 새 증거 → mid_a upsert(강화·turns 리셋), mid_b 감쇠만 ──
                t2 = await apply_matches(session, uid, [_match(mid_a, 0.8)])
                await session.commit()
                by_mid_2 = {h.misconception_id: h for h in t2}
                # mid_a: update_hypotheses는 *감쇠 먼저, 그 다음 강화*(#191 정본) —
                # reinforce(decay(0.6,1), 0.8) ≈ 0.904. evidence_count 2, turns 0.
                assert by_mid_2[mid_a].confidence == pytest.approx(0.904, abs=0.02)
                assert by_mid_2[mid_a].evidence_count == 2
                assert by_mid_2[mid_a].turns_since_evidence == 0
                # mid_b 감쇠(증거 없음): decay(0.5, 1)=0.5*0.5**0.2≈0.435, turns 1
                assert by_mid_2[mid_b].confidence < 0.5
                assert by_mid_2[mid_b].turns_since_evidence == 1

                # DB 행 수: 2행(둘 다 활성·upsert이므로 중복 insert 안 됨)
                rows = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM misconception_hypothesis "
                            "WHERE user_id = :uid"
                        ),
                        {"uid": str(uid)},
                    )
                ).scalar()
                assert rows == 2

                # ── 턴3~: 증거 없이 여러 턴 → mid_b confidence가 임계(0.1) 미만 → prune ──
                #   mid_a에는 계속 증거를 주고 mid_b는 방치해 가지치기를 유도. 반감기 5턴·임계
                #   0.1이라 mid_b(턴2≈0.435)가 0.1 아래로 내려가려면 ~11턴 필요 → 넉넉히 15턴.
                for _ in range(15):
                    await apply_matches(session, uid, [_match(mid_a, 0.5)])
                await session.commit()

                # mid_b는 비활성(가지치기), mid_a는 활성
                active_after = await get_active_hypotheses(session, uid)
                active_mids = {h.misconception_id for h in active_after}
                assert mid_a in active_mids
                assert mid_b not in active_mids  # prune → is_active=false

                # 행은 *삭제되지 않고* 비활성으로 남는다(증거 이력 보존)
                total = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM misconception_hypothesis "
                            "WHERE user_id = :uid"
                        ),
                        {"uid": str(uid)},
                    )
                ).scalar()
                assert total == 2  # mid_a active + mid_b inactive
                inactive = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM misconception_hypothesis "
                            "WHERE user_id = :uid AND is_active = false"
                        ),
                        {"uid": str(uid)},
                    )
                ).scalar()
                assert inactive == 1
        finally:
            await engine.dispose()

    try:
        asyncio.run(_seed_users([uid]))
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([uid]))


@pytest.mark.integration
def test_pruned_hypothesis_reactivates_on_new_evidence_on_live_pg() -> None:
    """가지치기(is_active=false)된 가설이 새 증거로 다시 살아나면 같은 행을 재활성화(upsert)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    mid = f"mc-r-{uid.hex[:6]}"

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 신규 → 증거 끊고 여러 턴 → prune (0.5가 임계 0.1 아래로: 반감기 5턴 기준
                # ~12턴 필요 → 넉넉히 15턴 감쇠)
                await apply_matches(session, uid, [_match(mid, 0.5)])
                for _ in range(15):
                    await apply_matches(session, uid, [])
                await session.commit()
                assert (
                    get_active_mids(await get_active_hypotheses(session, uid)) == set()
                )

                # 새 증거 → 같은 (user_id, mid) 행 재활성화(중복 insert 아님·UniqueConstraint)
                t = await apply_matches(session, uid, [_match(mid, 0.7)])
                await session.commit()
                assert {h.misconception_id for h in t} == {mid}
                # 행은 여전히 1개(insert가 아니라 upsert로 재활성화)
                rows = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM misconception_hypothesis "
                            "WHERE user_id = :uid"
                        ),
                        {"uid": str(uid)},
                    )
                ).scalar()
                assert rows == 1
                active = await get_active_hypotheses(session, uid)
                assert {h.misconception_id for h in active} == {mid}
        finally:
            await engine.dispose()

    try:
        asyncio.run(_seed_users([uid]))
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([uid]))


def get_active_mids(hyps: list[MisconceptionHypothesis]) -> set[str]:
    return {h.misconception_id for h in hyps}


@pytest.mark.integration
def test_user_isolation_on_live_pg() -> None:
    """두 학생의 가설은 격리된다 — apply_matches/get_active는 user_id로만 본다."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid1, uid2 = uuid.uuid4(), uuid.uuid4()
    mid = "shared-mc-id"  # 같은 오개념 id라도 user별 독립 행

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                await apply_matches(session, uid1, [_match(mid, 0.6)])
                await apply_matches(session, uid2, [_match(mid, 0.3)])
                await session.commit()

                a1 = await get_active_hypotheses(session, uid1)
                a2 = await get_active_hypotheses(session, uid2)
                assert len(a1) == 1 and a1[0].confidence == 0.6
                assert len(a2) == 1 and a2[0].confidence == 0.3
        finally:
            await engine.dispose()

    try:
        asyncio.run(_seed_users([uid1, uid2]))
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([uid1, uid2]))


@pytest.mark.integration
def test_persisted_roundtrip_matches_pure_logic_on_live_pg() -> None:
    """영속 왕복 후 confidence가 #191 순수 `update_hypotheses`와 동일(영속이 로직을 안 바꾼다)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    mid_a = f"pp-a-{uid.hex[:6]}"
    mid_b = f"pp-b-{uid.hex[:6]}"

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 영속 경로: 턴1 → 턴2
                await apply_matches(
                    session, uid, [_match(mid_a, 0.6), _match(mid_b, 0.5)]
                )
                persisted = await apply_matches(session, uid, [_match(mid_a, 0.8)])
                await session.commit()
        finally:
            await engine.dispose()

        # 순수 경로(동일 입력)로 기대값 계산.
        pure_t1 = update_hypotheses([], [_match(mid_a, 0.6), _match(mid_b, 0.5)])
        pure_t2 = update_hypotheses(pure_t1, [_match(mid_a, 0.8)])

        persisted_by = {h.misconception_id: h for h in persisted}
        pure_by = {h.misconception_id: h for h in pure_t2}
        assert set(persisted_by) == set(pure_by)
        for mid, pure in pure_by.items():
            # Numeric(3,2) 영속이라 소수 2자리로 비교(confidence 보존).
            assert persisted_by[mid].confidence == pytest.approx(
                pure.confidence, abs=0.01
            )
            assert persisted_by[mid].evidence_count == pure.evidence_count
            assert persisted_by[mid].turns_since_evidence == pure.turns_since_evidence

    try:
        asyncio.run(_seed_users([uid]))
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([uid]))
