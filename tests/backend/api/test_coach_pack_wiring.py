"""(c-1) GA 배선 테스트 — coach `_pack_for` 팩 해석 seam.

두 축:
- **OFF 단락(hermetic)**: `pedagogy_pack_prompt_enabled` off면 `_pack_for`가 DB를 건드리지 않고
  즉시 None(완전 no-op·회귀 0 보장). PG 불요.
- **ON 해석(@integration·PG)**: 플래그 on일 때 문항 PRIMARY 개념 code→k_type→팩을 실제로 해석하고,
  미매핑 문항은 graceful None(fail-soft).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import whymath_backend.api.coach as coach
from whymath_backend.api.coach import _pack_for
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.problem import Problem
from whymath_backend.l1.pedagogy.unit_compiler import (
    UnitSpecStore,
    compile_unit,
    load_statements_by_code,
    load_valid_atom_codes,
)
from whymath_backend.l1.pedagogy.unit_compiler import load_packs as load_packs_mem
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.enums import (
    ConceptLevel,
    ConceptRole,
    Curriculum,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema

_SECRET = "integration-jwt-secret-0123456789abcdef"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "data" / "corpus"
_UNIT_ID = "10공수1-이차함수-최대최소"
_PRIMARY_CODE = "10공수1-02-06-1"  # 파일럿 OBJ-01(CONCEPT) concept_node


# ──────────────────────────────────────────────────────────────────────────
# OFF 단락 (hermetic — 플래그 off면 DB 미접촉·즉시 None)
# ──────────────────────────────────────────────────────────────────────────
async def test_pack_for_off_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    # 플래그 off로 강제 → problem_id 있어도 즉시 None(DB 미접촉).
    monkeypatch.setattr(
        coach, "get_settings", lambda: SimpleNamespace(pedagogy_pack_prompt_enabled=False)
    )
    session = AsyncMock()
    result = await _pack_for(session, uuid.uuid4())
    assert result is None
    session.scalar.assert_not_awaited()


# ──────────────────────────────────────────────────────────────────────────
# ON 해석 (@integration·PG)
# ──────────────────────────────────────────────────────────────────────────
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


@pytest.mark.integration
async def test_pack_for_resolves_on_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    if not await _pg_reachable():
        pytest.skip("실 PG 미도달 — WHYMATH_DATABASE_URL 확인(통합 잡에서 실행)")

    settings = _settings()
    cid = uuid.uuid4()
    pid = uuid.uuid4()
    pid_unmapped = uuid.uuid4()
    sync_engine = create_engine(settings.sync_database_url)

    def _cleanup() -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM problem_concept WHERE problem_id = ANY(:p)"),
                {"p": [pid, pid_unmapped]},
            )
            conn.execute(
                text("DELETE FROM problem WHERE problem_id = ANY(:p)"),
                {"p": [pid, pid_unmapped]},
            )
            conn.execute(text("DELETE FROM concept WHERE concept_id = :c"), {"c": cid})
            conn.execute(text("DELETE FROM unit_spec WHERE unit_id = :u"), {"u": _UNIT_ID})

    async_engine = create_async_engine(settings.database_url)
    try:
        _cleanup()
        # 파일럿 unit+objective 시드(OBJ-01 concept_nodes=[_PRIMARY_CODE]·k_type CONCEPT).
        compiled = compile_unit(
            (_CORPUS / "units_v1" / "quadratic_maxmin.unit.yaml").read_text(encoding="utf-8"),
            packs=load_packs_mem(_CORPUS / "pedagogy_packs_v1"),
            valid_atom_codes=load_valid_atom_codes(_CORPUS / "atom_graph_v1" / "graph.json"),
            statements_by_code=load_statements_by_code(_CORPUS / "standards_v1" / "standards.json"),
        )
        UnitSpecStore(engine=sync_engine).seed(compiled)
        # FK 순서 보장: ① Concept·Problem 먼저 커밋 → ② ProblemConcept(느슨 FK·관계 미정의라
        # 한 세션 내 flush 순서 미보장이므로 분리 — vertical-slice E2E와 동형).
        maker = async_sessionmaker(async_engine, expire_on_commit=False)
        async with maker() as s:
            s.add(
                Concept.from_schema(
                    ConceptSchema(
                        concept_id=cid,
                        code=_PRIMARY_CODE,
                        name_ko="정의역 제한 최대·최소",
                        level=ConceptLevel.세부개념,
                    )
                )
            )
            for p in (pid, pid_unmapped):
                s.add(
                    Problem.from_schema(
                        ProblemSchema(
                            problem_id=p,
                            source_type=SourceType.자체생성,
                            curriculum_version=Curriculum.REVISION_2022,
                            valid_from_year=2022,
                            subject=Subject.공통,
                            unit_codes=["U-PACKWIRE"],
                            difficulty_overall=3.0,
                            answer="42",
                        )
                    )
                )
            await s.commit()
        async with maker() as s:
            s.add(
                ProblemConcept.from_schema(
                    ProblemConceptSchema(problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY)
                )
            )
            await s.commit()

        # 플래그 ON으로 전환(env + 캐시 클리어).
        monkeypatch.setenv("WHYMATH_PEDAGOGY_PACK_PROMPT_ENABLED", "true")
        get_settings.cache_clear()
        assert get_settings().pedagogy_pack_prompt_enabled is True

        async with async_sessionmaker(async_engine, expire_on_commit=False)() as s:
            pack = await _pack_for(s, pid)
            assert pack is not None
            assert pack.k_type == "CONCEPT"  # 파일럿 OBJ-01 유형
            # fail-soft — 개념 미매핑 문항은 None.
            assert await _pack_for(s, pid_unmapped) is None
            # problem_id None(stateless) → None.
            assert await _pack_for(s, None) is None
    finally:
        get_settings.cache_clear()
        _cleanup()
        await async_engine.dispose()
        sync_engine.dispose()
