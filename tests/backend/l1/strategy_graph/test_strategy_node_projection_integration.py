"""전략 메타 PG 프로젝션 *통합테스트* — Phase 6a (WHYMATH_RUN_INTEGRATION·실 PG).

마이그레이션 head 적용 실 PostgreSQL(`strategy_node` 테이블)에 전략 코퍼스
(`data/corpus/strategy_graph_v1/graph.json`)를 end-to-end 적재한다. CI `backend — 마이그레이션·
통합 (실 PG)` 잡이 `alembic upgrade head`(→ `strategy_node` 포함) 후 수집·실행한다. PG 미도달 또는
코퍼스 미존재 시 graceful skip(formula_node 통합테스트 동형).

검증:
  ① 적재 — strategy_node 8행(v1 코퍼스)·family 4종 커버
  ② name_ko·description 왕복 — 전 행 비어있지 않음
  ③ review_status 전건 'ai_estimated'(v1 자체작성이나 전문 검수 전·정직 표기)
  ④ 멱등 — 재적재 시 행수 불변
구 concept_node·atom_node·skill_node·problem_type_node·formula_node와 별개(신규 테이블·additive).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.strategy_graph.strategy_node_projection import (
    load_strategies_from_graph_json,
    populate_strategy_nodes,
)

pytestmark = pytest.mark.integration

_CORPUS = (
    Path(__file__).resolve().parents[4] / "data" / "corpus" / "strategy_graph_v1" / "graph.json"
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
            conn.execute(text("SELECT count(*) FROM strategy_node"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_guard() -> list[str]:
    if not _reachable():
        pytest.skip("PG 미도달 또는 마이그레이션 미적용(strategy_node) — 통합 건너뜀")
    if not _CORPUS.exists():
        pytest.skip("전략 코퍼스 미존재(data/corpus/strategy_graph_v1/graph.json)")
    payload = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return [str(s["strategy_id"]) for s in payload["strategies"]]


def _cleanup(strategy_ids: list[str]) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM strategy_node WHERE strategy_id = ANY(:ids)"),
                {"ids": strategy_ids},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_populate_real_corpus_and_roundtrip() -> None:
    """실 코퍼스 적재 → 8행·family 4종·name_ko/description 비어있지 않음·review 상수·멱등."""
    strategy_ids = _skip_guard()
    from sqlalchemy import text

    try:
        records = load_strategies_from_graph_json(_CORPUS)
        count = populate_strategy_nodes(records, settings=Settings())
        assert count == len(strategy_ids)

        engine = _sync_engine()
        try:
            with engine.connect() as conn:  # type: ignore[attr-defined]
                total = conn.execute(
                    text("SELECT count(*) FROM strategy_node WHERE strategy_id = ANY(:ids)"),
                    {"ids": strategy_ids},
                ).scalar_one()
                families = conn.execute(
                    text(
                        "SELECT count(DISTINCT family) FROM strategy_node "
                        "WHERE strategy_id = ANY(:ids)"
                    ),
                    {"ids": strategy_ids},
                ).scalar_one()
                empty_text = conn.execute(
                    text(
                        "SELECT count(*) FROM strategy_node "
                        "WHERE strategy_id = ANY(:ids) AND (name_ko = '' OR description = '')"
                    ),
                    {"ids": strategy_ids},
                ).scalar_one()
                reviews = (
                    conn.execute(
                        text(
                            "SELECT DISTINCT review_status FROM strategy_node "
                            "WHERE strategy_id = ANY(:ids)"
                        ),
                        {"ids": strategy_ids},
                    )
                    .scalars()
                    .all()
                )
            assert total == len(strategy_ids)
            assert families == 4
            assert empty_text == 0
            assert reviews == ["ai_estimated"]

            # ④ 멱등 — 재적재 후에도 행수 불변.
            recount = populate_strategy_nodes(
                load_strategies_from_graph_json(_CORPUS), settings=Settings()
            )
            assert recount == len(strategy_ids)
            engine2 = _sync_engine()
            try:
                with engine2.connect() as conn:  # type: ignore[attr-defined]
                    again = conn.execute(
                        text("SELECT count(*) FROM strategy_node WHERE strategy_id = ANY(:ids)"),
                        {"ids": strategy_ids},
                    ).scalar_one()
                assert again == len(strategy_ids)
            finally:
                engine2.dispose()  # type: ignore[attr-defined]
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    finally:
        _cleanup(strategy_ids)
