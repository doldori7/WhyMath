"""성취기준 도달 관측 리포트 — 조인 경로 델타 변별력 통합테스트 (실 PG, 기본 SKIP).

ASM-05 acceptance ⑤: UserProfile(STUDENT)+Concept+AtomNode(standard_codes)+ConceptMasteryHistory
행을 의도적으로 삽입해 `collect_attainment_inputs`→`build_report`의 카운터(학생 분모·측정
사용자·코드별 도달)가 실제로 오르는지 실측 → 삭제해 복원되는지 실측한다. **절대값 0을 어디서도
assert하지 않는다** — 라이브 DB에는 실사용 측정이 있을 수 있어 절대 행 수를 가정하는 것 자체가
위험하다. 오직 `insert 전/후/cleanup 후`의 **델타**만 비교한다(성공/실패가 같은 값을 내면 검증이
아니다 — CLAUDE.md 변별력 원칙·`test_assessment_seat_reach_report_integration.py` 패턴 미러링).

경계 변별을 실 Numeric(3,2) 왕복으로도 확인한다: mastery 0.80(경계 포함 도달)은 도달 카운터를
올리고, 0.79는 측정 사용자만 올리고 도달 카운터는 올리지 않아야 한다 — Decimal→float 정규화
경로(collect)의 라이브 검증이다.

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만 실행. DB 접속 판정(`_pg_reachable()`)·자체 엔진
생성·dispose 패턴은 `test_assessment_seat_reach_report_integration.py`를 그대로 미러링한다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.config import Settings
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.atom_node import ATOM_REVIEW_STATUS_AI_ESTIMATED, AtomNode
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.user import UserProfile
from whymath_backend.harness.problem_bank_coverage import StandardsCatalog, load_standards
from whymath_backend.harness.standard_attainment_report import (
    build_report,
    collect_attainment_inputs,
)
from whymath_backend.schema.enums import ConceptLevel, Persona, Role

pytestmark = pytest.mark.integration

_REVISION = "2022 개정"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _test_catalog(code: str) -> StandardsCatalog:
    """이 테스트 전용 합성 성취기준 대장 — 대상 개정에 합성 코드 1건만 둔다(델타 격리)."""
    return load_standards(
        {
            "standards": [
                {
                    "norm_id": f"2022_{code}",
                    "code": code,
                    "curriculum_revision": _REVISION,
                    "school_type": "고등학교",
                    "domain": "대수",
                }
            ]
        }
    )


async def _measure(code: str) -> tuple[int, int, int]:
    """(학생 분모, 측정 사용자 수, 합성 코드의 도달 사용자 수)를 실측한다."""
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as session:
            inputs = await collect_attainment_inputs(session)
        report = build_report(inputs, _test_catalog(code), revision=_REVISION)
        return (
            report.student_profile_count,
            report.measured_user_count,
            report.attained_users_per_code.get(code, 0),
        )
    finally:
        await engine.dispose()


async def _insert_chain(
    *,
    uid: uuid.UUID,
    cid: uuid.UUID,
    concept_code: str,
    standard_code: str,
    measured_at: datetime,
    mastery: float,
) -> None:
    """조인 경로 4행(UserProfile→Concept→AtomNode→CMH)을 한 트랜잭션으로 삽입한다."""
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as session:
            session.add(
                UserProfile(user_id=uid, persona_primary=Persona.A_일반고고3, role=Role.STUDENT)
            )
            session.add(
                Concept(
                    concept_id=cid,
                    code=concept_code,
                    name_ko="ASM-05 통합테스트 개념",
                    level=ConceptLevel.세부개념,
                )
            )
            session.add(
                AtomNode(
                    code=concept_code,  # Concept.code == AtomNode.code 조인 키(동일 키 공간).
                    name_ko="ASM-05 통합테스트 원자",
                    level="세부개념",
                    standard_codes=[standard_code],
                    review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED,
                )
            )
            session.add(
                ConceptMasteryHistory(
                    user_id=uid,
                    concept_id=cid,
                    measured_at=measured_at,
                    mastery=mastery,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup_chain(
    *, uid: uuid.UUID, cid: uuid.UUID, concept_code: str, measured_at: datetime
) -> None:
    """삽입 4행 전량 삭제(복합 PK/유니크 키 전체로 정리 — 사이드이펙트 0 보장)."""
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                delete(ConceptMasteryHistory).where(
                    ConceptMasteryHistory.user_id == uid,
                    ConceptMasteryHistory.concept_id == cid,
                    ConceptMasteryHistory.measured_at == measured_at,
                )
            )
            await conn.execute(delete(AtomNode).where(AtomNode.code == concept_code))
            await conn.execute(delete(Concept).where(Concept.concept_id == cid))
            await conn.execute(delete(UserProfile).where(UserProfile.user_id == uid))
    finally:
        await engine.dispose()


def test_boundary_mastery_insert_raises_student_measured_and_attained_deltas() -> None:
    """mastery 0.80(경계 포함 도달) 삽입 → 학생 분모·측정 사용자·도달 카운터가 전부 +1,
    삭제 → 복원. Numeric(3,2) 경계값이 실 PG 왕복에서도 도달로 판정되는지의 라이브 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:12]
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    concept_code = f"__asm05it.concept.{sfx}"
    standard_code = f"[10공수__asm05-{sfx}]"
    measured_at = datetime(2026, 1, 1, tzinfo=UTC)

    try:
        before = asyncio.run(_measure(standard_code))
        asyncio.run(
            _insert_chain(
                uid=uid,
                cid=cid,
                concept_code=concept_code,
                standard_code=standard_code,
                measured_at=measured_at,
                mastery=0.8,
            )
        )
        after_insert = asyncio.run(_measure(standard_code))
        asyncio.run(
            _cleanup_chain(uid=uid, cid=cid, concept_code=concept_code, measured_at=measured_at)
        )
        after_cleanup = asyncio.run(_measure(standard_code))
        # 델타만 비교 — 절대값 0 assert 없음.
        assert after_insert[0] == before[0] + 1  # 학생 분모(user_profile role=STUDENT)
        assert after_insert[1] == before[1] + 1  # 측정 사용자(CMH distinct user)
        assert after_insert[2] == before[2] + 1  # 합성 코드 도달 사용자(경계 0.80 포함)
        assert after_cleanup == before
    finally:
        # 테스트 실패로 위 cleanup이 스킵됐을 경우를 대비한 안전망.
        asyncio.run(
            _cleanup_chain(uid=uid, cid=cid, concept_code=concept_code, measured_at=measured_at)
        )


def test_below_threshold_insert_raises_measured_but_not_attained_delta() -> None:
    """mastery 0.79(경계 미만) 삽입 → 측정 사용자는 +1이나 도달 카운터는 **오르지 않는다** —
    경계가 실 DB 경로에서도 도달/미도달을 실제로 가르는지의 델타 변별(양방향)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:12]
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    concept_code = f"__asm05it.concept.{sfx}"
    standard_code = f"[10공수__asm05-{sfx}]"
    measured_at = datetime(2026, 1, 1, tzinfo=UTC)

    try:
        before = asyncio.run(_measure(standard_code))
        asyncio.run(
            _insert_chain(
                uid=uid,
                cid=cid,
                concept_code=concept_code,
                standard_code=standard_code,
                measured_at=measured_at,
                mastery=0.79,
            )
        )
        after_insert = asyncio.run(_measure(standard_code))
        asyncio.run(
            _cleanup_chain(uid=uid, cid=cid, concept_code=concept_code, measured_at=measured_at)
        )
        after_cleanup = asyncio.run(_measure(standard_code))
        assert after_insert[1] == before[1] + 1  # 측정 사용자는 오른다(측정은 실재).
        assert after_insert[2] == before[2]  # 도달 카운터는 오르지 않는다(0.79 < 0.8).
        assert after_cleanup == before
    finally:
        asyncio.run(
            _cleanup_chain(uid=uid, cid=cid, concept_code=concept_code, measured_at=measured_at)
        )
