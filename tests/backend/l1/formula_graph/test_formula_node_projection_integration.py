"""수식 메타 PG 프로젝션 *통합테스트* — Phase 5a (WHYMATH_RUN_INTEGRATION·실 PG).

마이그레이션 head 적용 실 PostgreSQL(`formula_node` 테이블)에 수식 코퍼스
(`data/corpus/formula_graph_v1/graph.json`)를 end-to-end 적재한다. CI `backend — 마이그레이션·
통합 (실 PG)` 잡이 `alembic upgrade head`(→ `formula_node` 포함) 후 수집·실행한다. PG 미도달 또는
코퍼스 미존재 시 graceful skip(problem_type_node 통합테스트 동형).

검증:
  ① 적재 — formula_node 25행(v1 코퍼스)·family 8종 커버
  ② latex·dsl 왕복 — 전 행 비어있지 않음
  ③ review_status 전건 'ai_estimated'(v1 자체작성이나 전문 검수 전·정직 표기)
  ④ 멱등 — 재적재 시 행수 불변
구 concept_node·atom_node·skill_node·problem_type_node와 별개(신규 테이블·additive)를 안 건드린다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.formula_graph.formula_node_projection import (
    load_formulas_from_graph_json,
    populate_formula_nodes,
)

pytestmark = pytest.mark.integration

_CORPUS = (
    Path(__file__).resolve().parents[4] / "data" / "corpus" / "formula_graph_v1" / "graph.json"
)


def _sync_engine() -> object:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM formula_node"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_guard() -> list[str]:
    if not _reachable():
        pytest.skip("PG 미도달 또는 마이그레이션 미적용(formula_node) — 통합 건너뜀")
    if not _CORPUS.exists():
        pytest.skip("수식 코퍼스 미존재(data/corpus/formula_graph_v1/graph.json)")
    payload = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return [str(f["formula_id"]) for f in payload["formulas"]]


def _cleanup(formula_ids: list[str]) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM formula_node WHERE formula_id = ANY(:ids)"),
                {"ids": formula_ids},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_populate_real_corpus_and_roundtrip() -> None:
    """실 코퍼스 적재 → 25행·family 8종·latex/dsl 비어있지 않음·review 상수·멱등."""
    formula_ids = _skip_guard()
    from sqlalchemy import text

    try:
        records = load_formulas_from_graph_json(_CORPUS)
        count = populate_formula_nodes(records, settings=Settings())
        assert count == len(formula_ids)

        engine = _sync_engine()
        try:
            with engine.connect() as conn:  # type: ignore[attr-defined]
                total = conn.execute(
                    text("SELECT count(*) FROM formula_node WHERE formula_id = ANY(:ids)"),
                    {"ids": formula_ids},
                ).scalar_one()
                families = conn.execute(
                    text(
                        "SELECT count(DISTINCT family) FROM formula_node "
                        "WHERE formula_id = ANY(:ids)"
                    ),
                    {"ids": formula_ids},
                ).scalar_one()
                empty_expr = conn.execute(
                    text(
                        "SELECT count(*) FROM formula_node "
                        "WHERE formula_id = ANY(:ids) AND (latex = '' OR dsl = '')"
                    ),
                    {"ids": formula_ids},
                ).scalar_one()
                reviews = (
                    conn.execute(
                        text(
                            "SELECT DISTINCT review_status FROM formula_node "
                            "WHERE formula_id = ANY(:ids)"
                        ),
                        {"ids": formula_ids},
                    )
                    .scalars()
                    .all()
                )
            assert total == len(formula_ids)
            assert families == 8
            assert empty_expr == 0
            assert reviews == ["ai_estimated"]

            # ④ 멱등 — 재적재 후에도 행수 불변.
            recount = populate_formula_nodes(
                load_formulas_from_graph_json(_CORPUS), settings=Settings()
            )
            assert recount == len(formula_ids)
            engine2 = _sync_engine()
            try:
                with engine2.connect() as conn:  # type: ignore[attr-defined]
                    again = conn.execute(
                        text("SELECT count(*) FROM formula_node WHERE formula_id = ANY(:ids)"),
                        {"ids": formula_ids},
                    ).scalar_one()
                assert again == len(formula_ids)
            finally:
                engine2.dispose()  # type: ignore[attr-defined]
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    finally:
        _cleanup(formula_ids)
