"""데이터 무결성 게이트(`ops/integrity_violations_gate.py`, OPS-55) — 실 PostgreSQL 통합테스트.

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG(마이그레이션 head 적용)에서만 실행한다(conftest
게이트가 CI 기본 skip). PG 미도달 시에도 graceful skip(`test_concepts_integration.py`·
`test_role_grant_cli_integration.py` 패턴 미러).

OPS-55 acceptance ②(위반 주입 변별력 실측 — 성공/실패 양쪽 신호)를 6종 전부에 대해 3단
왕복으로 증명한다: ①삽입 전 — 대상 식별자가 위반 목록에 없다(오탐 아님) ②삽입 후 — 있다
(검출) ③cleanup 후 — 다시 없다(오탐류 잔존 없음). 동일 프로세스에서 다른 통합테스트가 같은
DB에 데이터를 남길 수 있으므로 `report.exit_code`(전역 판정)가 아니라 이 테스트가 심은
식별자 하나하나의 존재/부재로 단언한다(격리·재현성).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.ops import integrity_violations_gate as gate

pytestmark = pytest.mark.integration

# 격리 접두사 — 병렬/반복 실행 간 충돌 방지(role_grant_cli_integration.py uuid 선례 미러).
_RUN_TAG = uuid.uuid4().hex[:8]


async def _pg_reachable() -> bool:
    engine = create_async_engine(Settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    if not await _pg_reachable():
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")
    engine = create_async_engine(Settings().database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
    await engine.dispose()


async def _kind_identifiers(session: AsyncSession, kind: str) -> set[str]:
    report = await gate.scan_integrity(session)
    return {v.identifier for v in report.violations_by_kind(kind)}


class TestOrphanConceptDiscrimination:
    async def test_concept_node_without_matching_concept_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        concept_id = f"math.test.{_RUN_TAG}.orphan-concept"
        assert concept_id not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_CONCEPT)
        try:
            await db_session.execute(
                text(
                    "INSERT INTO concept_node (concept_id, name_ko, domain, review_status) "
                    "VALUES (:cid, '테스트', '[중]테스트', 'pending')"
                ),
                {"cid": concept_id},
            )
            await db_session.commit()
            assert concept_id in await _kind_identifiers(db_session, gate.KIND_ORPHAN_CONCEPT)
        finally:
            await db_session.execute(
                text("DELETE FROM concept_node WHERE concept_id = :cid"), {"cid": concept_id}
            )
            await db_session.commit()
        assert concept_id not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_CONCEPT)


class TestOrphanSkillDiscrimination:
    async def test_behavior_skills_reference_to_missing_skill_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        skill_id = f"skill.{_RUN_TAG}-orphan"
        concept_pk = uuid.uuid4()
        code = f"math.test.{_RUN_TAG}.skill-holder"
        assert skill_id not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_SKILL)
        try:
            await db_session.execute(
                text(
                    "INSERT INTO concept (concept_id, code, name_ko, level, behavior_skills) "
                    "VALUES (:pk, :code, '테스트', '세부개념', ARRAY[:sid])"
                ),
                {"pk": concept_pk, "code": code, "sid": skill_id},
            )
            await db_session.commit()
            assert skill_id in await _kind_identifiers(db_session, gate.KIND_ORPHAN_SKILL)
        finally:
            await db_session.execute(
                text("DELETE FROM concept WHERE concept_id = :pk"), {"pk": concept_pk}
            )
            await db_session.commit()
        assert skill_id not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_SKILL)


class TestOrphanProblemDiscrimination:
    async def test_dead_end_log_reference_to_missing_problem_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        problem_id = uuid.uuid4()
        identifier = str(problem_id)
        assert identifier not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_PROBLEM)
        try:
            await db_session.execute(
                text(
                    "INSERT INTO dead_end_log (problem_id, state_hash, action) "
                    "VALUES (:pid, :hash, 'test')"
                ),
                {"pid": problem_id, "hash": f"hash-{_RUN_TAG}"},
            )
            await db_session.commit()
            assert identifier in await _kind_identifiers(db_session, gate.KIND_ORPHAN_PROBLEM)
        finally:
            await db_session.execute(
                text("DELETE FROM dead_end_log WHERE problem_id = :pid"), {"pid": problem_id}
            )
            await db_session.commit()
        assert identifier not in await _kind_identifiers(db_session, gate.KIND_ORPHAN_PROBLEM)


class TestDanglingCurriculumRefDiscrimination:
    async def test_skill_node_standard_code_not_in_achievement_standard_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        code = f"9XX{_RUN_TAG}"
        skill_id = f"skill.{_RUN_TAG}-dangling-curriculum"
        assert code not in await _kind_identifiers(db_session, gate.KIND_DANGLING_CURRICULUM_REF)
        try:
            await db_session.execute(
                text(
                    "INSERT INTO skill_node "
                    "(skill_id, name_ko, behavior_area, family, review_status, standard_codes) "
                    "VALUES (:sid, '테스트', 'COMPUTE', 'test-family', 'ai_estimated', "
                    "ARRAY[:code])"
                ),
                {"sid": skill_id, "code": code},
            )
            await db_session.commit()
            assert code in await _kind_identifiers(db_session, gate.KIND_DANGLING_CURRICULUM_REF)
        finally:
            await db_session.execute(
                text("DELETE FROM skill_node WHERE skill_id = :sid"), {"sid": skill_id}
            )
            await db_session.commit()
        assert code not in await _kind_identifiers(db_session, gate.KIND_DANGLING_CURRICULUM_REF)


class TestDuplicateCanonicalIdDiscrimination:
    async def test_code_claimed_as_alias_by_another_concept_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        code_a = f"math.test.{_RUN_TAG}.canonical-a"
        code_b = f"math.test.{_RUN_TAG}.canonical-b"
        pk_a, pk_b = uuid.uuid4(), uuid.uuid4()
        assert code_a not in await _kind_identifiers(db_session, gate.KIND_DUPLICATE_CANONICAL_ID)
        try:
            await db_session.execute(
                text(
                    "INSERT INTO concept (concept_id, code, name_ko, level) "
                    "VALUES (:pk, :code, '테스트A', '세부개념')"
                ),
                {"pk": pk_a, "code": code_a},
            )
            await db_session.execute(
                text(
                    "INSERT INTO concept (concept_id, code, name_ko, level, aliases) "
                    "VALUES (:pk, :code, '테스트B', '세부개념', ARRAY[:alias])"
                ),
                {"pk": pk_b, "code": code_b, "alias": code_a},
            )
            await db_session.commit()
            assert code_a in await _kind_identifiers(db_session, gate.KIND_DUPLICATE_CANONICAL_ID)
        finally:
            await db_session.execute(
                text("DELETE FROM concept WHERE concept_id IN (:a, :b)"), {"a": pk_a, "b": pk_b}
            )
            await db_session.commit()
        assert code_a not in await _kind_identifiers(db_session, gate.KIND_DUPLICATE_CANONICAL_ID)


class TestEventSchemaInvalidDiscrimination:
    async def test_verify_event_missing_required_field_is_detected(
        self, db_session: AsyncSession
    ) -> None:
        result = await db_session.execute(
            text(
                "INSERT INTO attempt_event (event_at, event_type, event_data) "
                "VALUES (now(), '검산결과', :payload) RETURNING event_id"
            ),
            {"payload": '{"error_kind": "missing_passed_field"}'},
        )
        event_id = result.scalar_one()
        identifier = f"attempt_event#{event_id}"
        try:
            await db_session.commit()
            assert identifier in await _kind_identifiers(db_session, gate.KIND_EVENT_SCHEMA_INVALID)
        finally:
            await db_session.execute(
                text("DELETE FROM attempt_event WHERE event_id = :eid"), {"eid": event_id}
            )
            await db_session.commit()
        assert identifier not in await _kind_identifiers(db_session, gate.KIND_EVENT_SCHEMA_INVALID)

    async def test_verify_event_with_valid_payload_is_not_flagged(
        self, db_session: AsyncSession
    ) -> None:
        result = await db_session.execute(
            text(
                "INSERT INTO attempt_event (event_at, event_type, event_data) "
                "VALUES (now(), '검산결과', :payload) RETURNING event_id"
            ),
            {"payload": '{"passed": true}'},
        )
        event_id = result.scalar_one()
        identifier = f"attempt_event#{event_id}"
        try:
            await db_session.commit()
            assert identifier not in await _kind_identifiers(
                db_session, gate.KIND_EVENT_SCHEMA_INVALID
            )
        finally:
            await db_session.execute(
                text("DELETE FROM attempt_event WHERE event_id = :eid"), {"eid": event_id}
            )
            await db_session.commit()


class TestEventSinceDaysScoping:
    async def test_old_event_excluded_when_since_days_set(self, db_session: AsyncSession) -> None:
        """`--event-since-days` 스코핑이 실제로 범위를 좁힌다(절단 출력 무결성 — 선택 시
        정직하게 일부만 본다는 것 자체를 실측 확인, 전건 스캔이 기본이라는 계약과 대조)."""
        result = await db_session.execute(
            text(
                "INSERT INTO attempt_event (event_at, event_type, event_data) "
                "VALUES (now() - interval '90 days', '검산결과', :payload) "
                "RETURNING event_id"
            ),
            {"payload": '{"error_kind": "old_invalid_event"}'},
        )
        event_id = result.scalar_one()
        identifier = f"attempt_event#{event_id}"
        try:
            await db_session.commit()
            # 기본(전건) — 오래된 이벤트도 잡힌다.
            full_report = await gate.scan_integrity(db_session)
            assert identifier in {
                v.identifier for v in full_report.violations_by_kind(gate.KIND_EVENT_SCHEMA_INVALID)
            }
            # 30일 이내로 제한하면 90일 전 이벤트는 스코프 밖 — 검출되지 않는다.
            scoped_report = await gate.scan_integrity(db_session, event_since_days=30)
            assert identifier not in {
                v.identifier
                for v in scoped_report.violations_by_kind(gate.KIND_EVENT_SCHEMA_INVALID)
            }
        finally:
            await db_session.execute(
                text("DELETE FROM attempt_event WHERE event_id = :eid"), {"eid": event_id}
            )
            await db_session.commit()


class TestCleanDatabaseExitsZeroForGateScopedRows:
    async def test_no_gate_scoped_violations_on_untouched_fixture(
        self, db_session: AsyncSession
    ) -> None:
        """이 테스트 클래스가 심지 않은 임의 식별자는 당연히 어느 kind에도 없다(오탐 없음 —
        전역 exit_code는 병행 실행 중인 다른 통합테스트의 잔존 데이터 영향을 받을 수 있어
        여기서 단언하지 않는다 — 모듈 docstring 참조)."""
        sentinel = f"math.test.{_RUN_TAG}.never-inserted"
        report = await gate.scan_integrity(db_session)
        all_identifiers = {v.identifier for v in report.violations}
        assert sentinel not in all_identifiers
