"""오개념 느슨참조 해소 *통합테스트* — 해소 슬라이스 (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에 *합성 대표 부분집합*(concept·standard·
misconception)을 적재해 `resolve_many`가 느슨참조를 실 행에 잇는지 본다. PG 미도달 시 graceful
skip(`test_misconception_loader_integration.py` 미러).

합성 부분집합 채택 근거: 백엔드 concept 로더는 raw `concepts.jsonl`이 아니라 슬1 transform이
산출하는 `graph.json`(repo 미체크인)을 읽으므로, "실 concept 코퍼스 한 방 적재" 경로가 없다.
따라서 기존 통합테스트의 확립된 패턴(합성 대표 row를 실-형태 값으로 빌드→populate→단언→cleanup)을
답습하되, 계획의 핵심 단언을 보존한다:
  ① concept 해소 — concept_src_id 가진 행 → `Concept`(source_id) 적재 → orphan 0(100% 해소)
  ② standard 단일 해소 — 한 official_code에 한 norm_id
  ③ 다중 revision — 같은 official_code(2015·2022) 2 norm_id → `len(standards)>1`·norm_id 정렬
  ④ 다중코드 행 — `;` 들어간 standard_code → `len(standard_codes)>1`·코드별 해소/orphan 정직
  ⑤ orphan 보고 — 적재 안 한 standard_code 1건 → standard_orphan_codes에 보고(조용한 누락 아님)
  ⑥ resolve_many → summarize 집계 단언

적재 키는 실 데이터와 충돌하지 않도록 `it`-슬러그(mis_id `MIT...`·norm_id `2022_99it_...`·
official_code `[99it01-01]`·concept source_id `ZZIT...`)를 쓴다.
"""

from __future__ import annotations

import asyncio

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.backend_concept import (
    BackendConceptRecord,
    populate_backend_concepts,
)
from whymath_backend.l1.misconception.catalog_loader import load_misconceptions
from whymath_backend.l1.misconception.resolve import (
    ResolvedMisconceptionLinks,
    resolve_many,
    summarize,
)
from whymath_backend.l1.standards.standard_loader import load_standards
from whymath_backend.schema.enums import ConceptLevel

pytestmark = pytest.mark.integration

# ── 적재 키(it 슬러그·실 데이터 비충돌) ──
_SRC_A = "ZZIT01"  # 해소되는 concept_src_id(시드 concept.source_id)
_SRC_B = "ZZIT02"
_CODE_A = "[99it01-01]"  # 단일 해소 official_code(한 norm_id)
_CODE_MULTI = "[99it02-02]"  # 다중 revision official_code(2015·2022 2 norm_id)
_CODE_ORPHAN = "[99it09-09]"  # 적재 안 함 → orphan 보고

_NORM_A = "2022_99it_01_01"
_NORM_MULTI_2022 = "2022_99it_02_02"
_NORM_MULTI_2015 = "2015_99it_02_02"

_CONCEPT_CODE_A = "HIGH-ZZIT-001"  # 시드 concept.code(source_id=_SRC_A)
_CONCEPT_CODE_B = "HIGH-ZZIT-002"  # 시드 concept.code(source_id=_SRC_B)

# 오개념 행 — 해소·다중코드·orphan을 한 번에 본다.
_MIS_RESOLVED = "MIT001"  # concept+standard 둘 다 해소
_MIS_MULTI_CODE = "MIT002"  # standard_code에 ; → 부분 해소·orphan 보고
_MIS_CONCEPT_NONE = "MIT003"  # concept_src_id None → orphan 아님
_ALL_MIS = [_MIS_RESOLVED, _MIS_MULTI_CODE, _MIS_CONCEPT_NONE]
_ALL_NORM = [_NORM_A, _NORM_MULTI_2022, _NORM_MULTI_2015]
_ALL_CONCEPT = [_CONCEPT_CODE_A, _CONCEPT_CODE_B]


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·도달 점검용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + 세 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM misconception_catalog"))
            conn.execute(text("SELECT count(*) FROM concept"))
            conn.execute(text("SELECT count(*) FROM achievement_standard"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _cleanup() -> None:
    """세 테이블 적재 행 정리(misconception·standard·concept)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM misconception_catalog WHERE mis_id = ANY(:ids)"),
                {"ids": _ALL_MIS},
            )
            conn.execute(
                text("DELETE FROM achievement_standard WHERE norm_id = ANY(:ids)"),
                {"ids": _ALL_NORM},
            )
            conn.execute(
                text("DELETE FROM concept WHERE code = ANY(:codes)"),
                {"codes": _ALL_CONCEPT},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _seed_concepts() -> None:
    """concept_src_id 해소용 backend concept 시드(source_id 컬럼 채움·멱등 upsert)."""
    populate_backend_concepts(
        [
            BackendConceptRecord(
                code=_CONCEPT_CODE_A,
                name_ko="통합테스트 개념 A",
                source_id=_SRC_A,
                aliases=[],
                level=ConceptLevel.세부개념,
                subject=None,
                intrinsic_difficulty=None,
                common_misconceptions=[],
            ),
            BackendConceptRecord(
                code=_CONCEPT_CODE_B,
                name_ko="통합테스트 개념 B",
                source_id=_SRC_B,
                aliases=[],
                level=ConceptLevel.세부개념,
                subject=None,
                intrinsic_difficulty=None,
                common_misconceptions=[],
            ),
        ],
        settings=Settings(),
    )


def _standard_row(norm_id: str, code: str, *, curriculum_revision: str) -> dict[str, object]:
    """코퍼스 성취기준 dict — 코퍼스 키 `code`(로더가 official_code로 rename)."""
    return {
        "norm_id": norm_id,
        "code": code,
        "grade_band": "고등학교",
        "school_type": "고등학교",
        "subject": "공통수학1",
        "domain": "다항식",
        "sub_domain": None,
        "statement": "다항식의 사칙연산을 할 수 있다.",
        "commentary": None,
        "big_idea": None,
        "curriculum_revision": curriculum_revision,
        "effective_from": None,
        "parent_codes": [],
        "source_url": "https://www.ncic.go.kr/x",
        "source_document": None,
    }


def _standards_collection(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "collected_at": "2026-06-20T00:00:00+00:00",
        "crawler_version": "0.1.0",
        "standards": rows,
    }


def _seed_standards() -> None:
    """성취기준 시드 — 단일(_CODE_A)·다중 revision(_CODE_MULTI 2022+2015). orphan은 미적재."""
    load_standards(
        None,
        _standards_collection(
            [
                _standard_row(_NORM_A, _CODE_A, curriculum_revision="2022 개정"),
                _standard_row(_NORM_MULTI_2022, _CODE_MULTI, curriculum_revision="2022 개정"),
                _standard_row(_NORM_MULTI_2015, _CODE_MULTI, curriculum_revision="2015 개정"),
            ]
        ),
        settings=Settings(),
    )


def _mis_row(
    mis_id: str,
    *,
    concept_src_id: str | None,
    standard_code: str | None,
) -> dict[str, object]:
    """코퍼스 오개념 dict — rename 0(코퍼스 키=schema 필드·느슨참조 원천 저장)."""
    return {
        "mis_id": mis_id,
        "canonical_statement": "통합테스트 오개념.",
        "error_type": "개념오류",
        "difficulty": "중",
        "concept_src_id": concept_src_id,
        "standard_code": standard_code,
    }


def _mis_collection(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "collected_at": "2026-06-20T00:00:00+00:00",
        "count": len(rows),
        "misconceptions": rows,
    }


def _seed_misconceptions() -> None:
    """오개념 시드 — 해소·다중코드(_CODE_MULTI 해소 + _CODE_ORPHAN orphan)·concept None."""
    load_misconceptions(
        None,
        _mis_collection(
            [
                _mis_row(_MIS_RESOLVED, concept_src_id=_SRC_A, standard_code=_CODE_A),
                _mis_row(
                    _MIS_MULTI_CODE,
                    concept_src_id=_SRC_B,
                    standard_code=f"{_CODE_MULTI}; {_CODE_ORPHAN}",
                ),
                _mis_row(_MIS_CONCEPT_NONE, concept_src_id=None, standard_code=None),
            ]
        ),
        settings=Settings(),
    )


async def _resolve() -> list[ResolvedMisconceptionLinks]:
    """페치 → resolve_many(같은 AsyncSession에서 적재 행 해소)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog

    engine = create_async_engine(Settings().database_url)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            stmt = (
                select(MisconceptionCatalog)
                .where(MisconceptionCatalog.mis_id.in_(_ALL_MIS))
                .order_by(MisconceptionCatalog.mis_id)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return await resolve_many(session, rows)
    finally:
        await engine.dispose()


class TestResolveIntegration:
    """합성 대표 부분집합 적재 → resolve_many 핵심 단언(concept·standard·다중·orphan·집계)."""

    def test_resolve_many_links_loose_refs(self) -> None:
        _skip_if_unreachable()
        try:
            _seed_concepts()
            _seed_standards()
            _seed_misconceptions()

            results = asyncio.run(_resolve())
            by_id = {r.mis_id: r for r in results}
            assert set(by_id) == set(_ALL_MIS)

            # ① concept 해소 + ② standard 단일 해소(orphan 0).
            r_resolved = by_id[_MIS_RESOLVED]
            assert r_resolved.concept is not None
            assert r_resolved.concept.code == _CONCEPT_CODE_A
            assert r_resolved.concept_resolved is True
            assert r_resolved.concept_orphan is False
            assert len(r_resolved.standard_codes) == 1
            single = r_resolved.standard_codes[0]
            assert single.code == _CODE_A
            assert len(single.standards) == 1  # 한 official_code에 한 norm_id
            assert single.standards[0].norm_id == _NORM_A
            assert r_resolved.standard_resolved is True
            assert r_resolved.standard_orphan_codes == ()

            # ③ 다중 revision + ④ 다중코드 + ⑤ orphan 보고.
            r_multi = by_id[_MIS_MULTI_CODE]
            assert r_multi.concept is not None
            assert r_multi.concept.code == _CONCEPT_CODE_B
            # 다중코드(;) → 2개 코드.
            assert len(r_multi.standard_codes) == 2
            multi_map = {sc.code: sc for sc in r_multi.standard_codes}
            # _CODE_MULTI는 2015·2022 두 norm_id → norm_id 정렬.
            multi_standards = multi_map[_CODE_MULTI].standards
            assert len(multi_standards) > 1
            norm_ids = [s.norm_id for s in multi_standards]
            assert norm_ids == sorted(norm_ids)
            assert set(norm_ids) == {_NORM_MULTI_2015, _NORM_MULTI_2022}
            # _CODE_ORPHAN은 미적재 → orphan 보고(조용한 누락 아님).
            assert multi_map[_CODE_ORPHAN].standards == ()
            assert _CODE_ORPHAN in r_multi.standard_orphan_codes
            # 부분 해소 → 전체 standard_resolved False.
            assert r_multi.standard_resolved is False

            # concept_src_id None → orphan 아님.
            r_none = by_id[_MIS_CONCEPT_NONE]
            assert r_none.concept is None
            assert r_none.concept_orphan is False
            assert r_none.standard_codes == ()

            # ⑥ summarize 집계.
            summary = summarize(results)
            assert summary["total"] == 3
            # 두 행(_MIS_RESOLVED·_MIS_MULTI_CODE)이 concept 해소.
            assert summary["concept_resolved_n"] == 2
            # concept orphan 0(N1 100% 겹침 가정·시드 정합).
            assert summary["concept_orphan_n"] == 0
            # 단일 코드 행만 전체 standard_resolved(_MIS_RESOLVED).
            assert summary["standard_resolved_n"] == 1
            # orphan 코드 1건(_CODE_ORPHAN).
            assert summary["standard_orphan_code_n"] == 1
        finally:
            _cleanup()
