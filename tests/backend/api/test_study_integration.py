"""학습 공급 엔드포인트 관통 — study → outcome → 집계 (PED-03·실 PG·기본 SKIP).

이 슬라이스의 핵심 주장은 "**처치가 실제로 기록되기 시작한다**"이므로, 그 주장을 hermetic 단위로만
받치면 부족하다(단위는 writer가 올바른 행을 *만든다*까지만 보인다). 여기서는 실 PG에 실제로 왕복해:

  ① `/study`가 `supply()` 사슬을 태우고 **처치 행**을 남기는지
  ② `/outcome`이 같은 `session_id`로 **결과 행**을 남기는지
  ③ 집계(`aggregate_effectiveness`)가 그 두 행을 이어 (전략×k_type×objective) 셀을 만드는지

②·③이 이어지는지가 중요하다 — 기록만 되고 집계가 못 읽으면 측정 파이프라인은 끊긴 것이다.

ARCH-13 교훈: 로컬에서 PG 미도달로 skip된 것을 "통과"로 보고하지 않는다. 이 파일은 PG가 없으면
명시적으로 skip되고, 메인은 실 PG를 띄워 실행한 결과로만 통과를 주장한다.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from whymath_backend.config import get_settings
from whymath_backend.db.models.pedagogy_dsl import LearningObjective, UnitSpec
from whymath_backend.l2.pedagogy_evidence import (
    record_pedagogy_outcome,
    record_pedagogy_treatment,
)
from whymath_backend.l4.pedagogy.adaptive.effectiveness import (
    aggregate_effectiveness,
    load_pedagogy_events,
)

pytestmark = pytest.mark.integration


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


def test_pedagogy_evidence_round_trip_and_aggregation_on_live_pg() -> None:
    """처치·결과 행을 실 PG에 쓰고, 집계가 둘을 이어 셀을 만드는지 확인한다.

    엔드포인트 대신 L2 writer를 직접 부르는 이유: 인증·레이트리밋·DSL 적재까지 얽히면 실패 시
    원인이 흐려진다. 여기서 못 박을 것은 **기록 → 집계 배선이 실 스키마에서 성립하는가**이며
    (JSONB meta 왕복·복합 PK·이벤트 유형 필터), 엔드포인트 계약은 hermetic 단위가 담당한다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    unit_id = f"UNIT.test.{sfx}"
    objective_id = f"OBJ.test.{sfx}"
    code = f"atom.test.{sfx}"
    session_id = uuid.uuid4()

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
                # ① 처치 — 학생에게 SOCRATIC이 렌더됐다고 기록.
                await record_pedagogy_treatment(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=session_id,
                    strategy="SOCRATIC",
                    content_source="dsl_render",
                    concept_code=code,
                )
                # ② 결과 — 같은 세션의 시도 결과.
                await record_pedagogy_outcome(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=session_id,
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


def test_orphan_outcome_is_not_aggregated_on_live_pg() -> None:
    """**변별력** — 처치 없이 결과만 있으면 실 PG 경로에서도 집계되지 않는다.

    위 테스트가 "행이 있으면 무조건 센다"는 느슨한 검사가 아님을 보인다. 처치 미상 결과를 세면
    "어떤 교수법이 효과적인가"에 근거 없는 답이 생긴다.
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
            async with sm() as session:
                await record_pedagogy_outcome(
                    session,
                    objective_id=objective_id,
                    k_type="CONCEPT",
                    session_id=uuid.uuid4(),  # 처치 없는 세션
                    correct=True,
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
