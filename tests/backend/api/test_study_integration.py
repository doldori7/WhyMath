"""학습 공급 엔드포인트 관통 — study → outcome → 집계 + SEC-16 소유권 (실 PG·기본 SKIP).

이 슬라이스의 핵심 주장은 "**처치가 실제로 기록되기 시작한다**"이므로, 그 주장을 hermetic 단위로만
받치면 부족하다(단위는 writer가 올바른 행을 *만든다*까지만 보인다). 여기서는 실 PG에 실제로 왕복해:

  ① `/study`가 `supply()` 사슬을 태우고 **처치 행**을 남기는지
  ② `/outcome`이 같은 `session_id`로 **결과 행**을 남기는지
  ③ 집계(`aggregate_effectiveness`)가 그 두 행을 이어 (전략×k_type×objective) 셀을 만드는지
  ④ **SEC-16**: 위조·타인 세션의 outcome이 실 스키마·실 HTTP 경로에서 403으로, 중복이 409로
     거부되는지(hermetic 큐 fake는 WHERE를 실행하지 않으므로 실 PG에서만 완결 검증된다 —
     `docs/reviews/functional_security_audit_2026-08-08.md` M2)

②·③이 이어지는지가 중요하다 — 기록만 되고 집계가 못 읽으면 측정 파이프라인은 끊긴 것이다.

ARCH-13 교훈: 로컬에서 PG 미도달로 skip된 것을 "통과"로 보고하지 않는다. 이 파일은 PG가 없으면
명시적으로 skip되고, 메인은 실 PG를 띄워 실행한 결과로만 통과를 주장한다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.db.models.pedagogy_dsl import LearningObjective, UnitSpec
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    SessionOwnershipError,
    record_pedagogy_outcome,
    record_pedagogy_treatment,
)
from whymath_backend.l4.pedagogy.adaptive.effectiveness import (
    aggregate_effectiveness,
    load_pedagogy_events,
)
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    """SEC-16 바인딩 HMAC 키(jwt_secret)를 채운 설정 — writer·앱(오버라이드) 양쪽이 공유."""
    return Settings(jwt_secret_key=SecretStr(_SECRET))


def _unit_spec(unit_id: str) -> UnitSpec:
    """NOT NULL 전 컬럼을 채운 최소 소단원 명세(컴파일러 산출 형태 모사)."""
    return UnitSpec(
        unit_id=unit_id,
        unit_version=1,
        api_version="v0.1",
        title="테스트 소단원",
        curriculum_rev="2022",
        standard_codes=[],
        concept_nodes=[],
        yaml_sha256="0" * 64,
        compiler_ver="test",
    )


def _objective(objective_id: str, unit_id: str, code: str) -> LearningObjective:
    """`k_type`(팩 축)·`concept_nodes`(원자 code)가 이 슬라이스의 배선 축이다."""
    return LearningObjective(
        id=objective_id,
        unit_id=unit_id,
        unit_version=1,
        statement="테스트 학습목표",
        achievement_std="[9수02-01]",
        k_type="CONCEPT",
        concept_nodes=[code],
        slot_manifest={},
        exit_evidence={},
    )


async def _pg_reachable() -> bool:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _cleanup(objective_id: str, unit_id: str, code: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM evidence_event WHERE objective_id = :oid"), {"oid": objective_id}
            )
            await conn.execute(
                text("DELETE FROM learning_objective WHERE id = :oid"), {"oid": objective_id}
            )
            await conn.execute(text("DELETE FROM unit_spec WHERE unit_id = :uid"), {"uid": unit_id})
            await conn.execute(
                text("DELETE FROM concept_content WHERE code = :code"), {"code": code}
            )
    finally:
        await engine.dispose()


async def _cleanup_users(*user_ids: uuid.UUID) -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.begin() as conn:
            for uid in user_ids:
                await conn.execute(
                    text("DELETE FROM user_profile WHERE user_id = :u"), {"u": str(uid)}
                )
    finally:
        await engine.dispose()


def test_pedagogy_evidence_round_trip_and_aggregation_on_live_pg() -> None:
    """처치·결과 행을 실 PG에 쓰고, 집계가 둘을 이어 셀을 만드는지 확인한다.

    엔드포인트 대신 L2 writer를 직접 부르는 이유: 인증·레이트리밋·DSL 적재까지 얽히면 실패 시
    원인이 흐려진다. 여기서 못 박을 것은 **기록 → 집계 배선이 실 스키마에서 성립하는가**이며
    (JSONB meta 왕복·복합 PK·이벤트 유형 필터·SEC-16 소유권 SELECT), 엔드포인트 계약은
    hermetic 단위가 담당한다. outcome은 같은 트랜잭션의 처치를 autoflush로 되읽어 소유권을
    통과한다(정당 경로가 SEC-16 이후에도 계속 성립함의 실측).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    unit_id = f"UNIT.test.{sfx}"
    objective_id = f"OBJ.test.{sfx}"
    code = f"atom.test.{sfx}"
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    settings = _settings()

    async def _run() -> None:
        engine = create_async_engine(get_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(_unit_spec(unit_id))
                await session.flush()
                session.add(_objective(objective_id, unit_id, code))
                await session.commit()

            async with sm() as session:
                # ① 처치 — 학생에게 SOCRATIC이 렌더됐다고 기록(meta에 소유권 바인딩 동봉).
                await record_pedagogy_treatment(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=session_id,
                    user_id=user_id,
                    settings=settings,
                    strategy="SOCRATIC",
                    content_source="dsl_render",
                    concept_code=code,
                )
                # ② 결과 — 같은 세션·같은 학생의 시도 결과(소유권 검증 통과 경로).
                await record_pedagogy_outcome(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=session_id,
                    user_id=user_id,
                    settings=settings,
                    correct=True,
                    rt_ms=5100,
                )
                await session.commit()

            async with sm() as session:
                rows = await load_pedagogy_events(session, objective_id=objective_id)
                assert len(rows) == 2, f"처치+결과 2행이어야 한다: {len(rows)}"
                # ③ 집계 — 두 행이 세션 축으로 이어져 하나의 셀이 된다.
                report = aggregate_effectiveness(rows)
                assert report.total_trials == 1
                cell = next(iter(report.stats.items()))
                key, stat = cell
                assert key.strategy == "SOCRATIC"
                assert key.objective_id == objective_id
                assert stat.successes == 1
                assert stat.mean_rt_ms == 5100
                # JSONB meta가 왕복했는지(전략명이 DB를 거쳐 되읽힌다).
                treatment = next(r for r in rows if r.meta)
                assert treatment.meta is not None
                assert treatment.meta["pedagogy_strategy"] == "SOCRATIC"
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(objective_id, unit_id, code))


def test_orphan_outcome_is_rejected_and_excluded_on_live_pg() -> None:
    """**변별력** — 처치 없는 outcome은 ⓐ writer가 기입 자체를 거부하고(SEC-16 승격),
    ⓑ 우회로 삽입돼도 집계가 세지 않는다(이중 방어 유지).

    ⓐ만 있으면 writer를 우회한 직접 삽입(마이그레이션·수동 조작)이 집계를 오염시키고,
    ⓑ만 있으면 무제한 고아 행 적재(저장소 오염)가 열린다 — 둘 다 실 PG에서 못 박는다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    unit_id = f"UNIT.test.{sfx}"
    objective_id = f"OBJ.test.{sfx}"
    code = f"atom.test.{sfx}"

    async def _run() -> None:
        engine = create_async_engine(get_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(_unit_spec(unit_id))
                await session.flush()
                session.add(_objective(objective_id, unit_id, code))
                await session.commit()
            # ⓐ writer 경로 — 처치 없는 세션의 outcome 기입은 실 스키마에서도 거부된다.
            async with sm() as session:
                with pytest.raises(SessionOwnershipError):
                    await record_pedagogy_outcome(
                        session,
                        objective_id=objective_id,
                        k_type="CONCEPT",
                        session_id=uuid.uuid4(),  # 처치 없는 세션
                        user_id=uuid.uuid4(),
                        settings=_settings(),
                        correct=True,
                    )
            # ⓑ 집계 경로 — writer를 우회한 직접 삽입(결함주입)도 집계에는 들지 않는다.
            async with sm() as session:
                session.add(
                    EvidenceEvent(
                        time=datetime.now(UTC),
                        session_id=uuid.uuid4(),
                        objective_id=objective_id,
                        k_type="CONCEPT",
                        event_type=EVENT_TYPE_OUTCOME,
                        correct=True,
                    )
                )
                await session.commit()
            async with sm() as session:
                rows = await load_pedagogy_events(session, objective_id=objective_id)
                assert len(rows) == 1  # 행은 남아 있다
                assert aggregate_effectiveness(rows).total_trials == 0  # 그러나 집계엔 안 든다
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(objective_id, unit_id, code))


def test_outcome_ownership_http_on_live_pg() -> None:
    """SEC-16 HTTP 관통 — 위조 403 · 타 학생 403(동일 detail) · 정당 201 · 중복 409 (실 PG).

    hermetic 큐 fake는 소유권 SELECT의 WHERE를 실행하지 않으므로, 실 스키마 위에서 실 인증
    토큰(`create_access_token`)으로 엔드포인트를 때려 거부 사슬 전체(JWT → user → writer 검증
    → HTTP 번역)를 완결 검증한다. get_settings만 오버라이드(jwt 시크릿), get_session은 실 PG
    (`test_visualization_endpoint_integration.py` 관례).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    unit_id = f"UNIT.test.{sfx}"
    objective_id = f"OBJ.test.{sfx}"
    code = f"atom.test.{sfx}"
    path = f"/v1/me/objectives/{objective_id}/outcome"
    session_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    settings = _settings()

    async def _setup() -> None:
        engine = create_async_engine(get_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(_unit_spec(unit_id))
                await session.flush()
                session.add(_objective(objective_id, unit_id, code))
                session.add(
                    UserProfile.from_schema(
                        UserProfileSchema(user_id=owner_id, persona_primary=Persona.A_일반고고3)
                    )
                )
                session.add(
                    UserProfile.from_schema(
                        UserProfileSchema(user_id=attacker_id, persona_primary=Persona.A_일반고고3)
                    )
                )
                await session.commit()
            async with sm() as session:
                # `/study`가 owner에게 발급했을 처치(바인딩 동봉)를 시드한다.
                await record_pedagogy_treatment(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=session_id,
                    user_id=owner_id,
                    settings=settings,
                    strategy="SOCRATIC",
                    content_source="dsl_render",
                    concept_code=code,
                )
                await session.commit()
        finally:
            await engine.dispose()

    app = create_app()
    app.dependency_overrides[get_settings] = _settings

    def _headers(user_id: uuid.UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user_id, settings=settings)}"}

    try:
        asyncio.run(_setup())
        with TestClient(app) as client:
            body = {"session_id": str(session_id), "correct": True}
            # ① 위조 session_id — 처치가 없는 세션 → 403.
            forged = client.post(
                path,
                json={"session_id": str(uuid.uuid4()), "correct": True},
                headers=_headers(owner_id),
            )
            assert forged.status_code == 403, forged.text
            # ② 타 학생 — owner의 세션에 attacker 토큰 → 403 + ①과 동일 detail(오라클 차단).
            stolen = client.post(path, json=body, headers=_headers(attacker_id))
            assert stolen.status_code == 403, stolen.text
            assert stolen.json()["detail"] == forged.json()["detail"]
            # ③ 정당 소유자 → 201(기존 study→outcome 흐름이 SEC-16 이후에도 성립).
            legit = client.post(path, json=body, headers=_headers(owner_id))
            assert legit.status_code == 201, legit.text
            assert legit.json() == {"recorded": True}
            # ④ 같은 세션 재기입 → 409(자기 가중 게이밍 거부).
            duplicate = client.post(path, json=body, headers=_headers(owner_id))
            assert duplicate.status_code == 409, duplicate.text
    finally:
        asyncio.run(_cleanup(objective_id, unit_id, code))
        asyncio.run(_cleanup_users(owner_id, attacker_id))
