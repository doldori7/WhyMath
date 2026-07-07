"""문제유형 메타 PG 프로젝션 *통합테스트* — Phase 3 (WHYMATH_RUN_INTEGRATION·실 PG).

마이그레이션 head 적용 실 PostgreSQL(`problem_type_node` 테이블)에 문제유형 코퍼스
(`data/corpus/problem_type_graph_v1/graph.json`)를 end-to-end 적재한다. CI `backend — 마이그레이션·
통합 (실 PG)` 잡이 `alembic upgrade head`(→ `problem_type_node` 포함) 후 수집·실행한다. PG 미도달
또는 코퍼스 미존재 시 graceful skip(skill_node 통합테스트 동형).

검증:
  ① 적재 — problem_type_node 17행(v1 코퍼스)·family 6종 커버
  ② behavior_skills TEXT[] 왕복 — 전 행 ≥1 스킬 참조
  ③ review_status 전건 'ai_estimated'(v1 자체작성이나 전문 검수 전·정직 표기)
  ④ 멱등 — 재적재 시 행수 불변
구 concept_node·atom_node·skill_node와 별개(신규 테이블·additive)를 건드리지 않는다. 정리는 전건.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.problem_type_graph.problem_type_node_projection import (
    load_problem_types_from_graph_json,
    populate_problem_type_nodes,
)

pytestmark = pytest.mark.integration

_CORPUS = (
    Path(__file__).resolve().parents[4] / "data" / "corpus" / "problem_type_graph_v1" / "graph.json"
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
            conn.execute(text("SELECT count(*) FROM problem_type_node"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_guard() -> list[str]:
    if not _reachable():
        pytest.skip("PG 미도달 또는 마이그레이션 미적용(problem_type_node) — 통합 건너뜀")
    if not _CORPUS.exists():
        pytest.skip("문제유형 코퍼스 미존재(data/corpus/problem_type_graph_v1/graph.json)")
    payload = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return [str(p["problem_type_id"]) for p in payload["problem_types"]]


def _cleanup(ptype_ids: list[str]) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM problem_type_node WHERE problem_type_id = ANY(:ids)"),
                {"ids": ptype_ids},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_populate_real_corpus_and_array_roundtrip() -> None:
    """실 코퍼스 적재 → 17행·family 6종·behavior_skills ≥1 왕복·review 상수·멱등."""
    ptype_ids = _skip_guard()
    from sqlalchemy import text

    try:
        records = load_problem_types_from_graph_json(_CORPUS)
        count = populate_problem_type_nodes(records, settings=Settings())
        assert count == len(ptype_ids)

        engine = _sync_engine()
        try:
            with engine.connect() as conn:  # type: ignore[attr-defined]
                total = conn.execute(
                    text(
                        "SELECT count(*) FROM problem_type_node WHERE problem_type_id = ANY(:ids)"
                    ),
                    {"ids": ptype_ids},
                ).scalar_one()
                # ① family 커버(6종·자유 라벨).
                families = conn.execute(
                    text(
                        "SELECT count(DISTINCT family) FROM problem_type_node "
                        "WHERE problem_type_id = ANY(:ids)"
                    ),
                    {"ids": ptype_ids},
                ).scalar_one()
                # ② behavior_skills TEXT[] 왕복 — 전 행 ≥1 스킬.
                min_skills = conn.execute(
                    text(
                        "SELECT min(array_length(behavior_skills, 1)) FROM problem_type_node "
                        "WHERE problem_type_id = ANY(:ids)"
                    ),
                    {"ids": ptype_ids},
                ).scalar_one()
                # ③ review_status 전건 'ai_estimated'.
                reviews = (
                    conn.execute(
                        text(
                            "SELECT DISTINCT review_status FROM problem_type_node "
                            "WHERE problem_type_id = ANY(:ids)"
                        ),
                        {"ids": ptype_ids},
                    )
                    .scalars()
                    .all()
                )
            assert total == len(ptype_ids)
            assert families == 6
            assert min_skills >= 1
            assert reviews == ["ai_estimated"]

            # ④ 멱등 — 재적재 후에도 행수 불변.
            recount = populate_problem_type_nodes(
                load_problem_types_from_graph_json(_CORPUS), settings=Settings()
            )
            assert recount == len(ptype_ids)
            engine2 = _sync_engine()
            try:
                with engine2.connect() as conn:  # type: ignore[attr-defined]
                    again = conn.execute(
                        text(
                            "SELECT count(*) FROM problem_type_node "
                            "WHERE problem_type_id = ANY(:ids)"
                        ),
                        {"ids": ptype_ids},
                    ).scalar_one()
                assert again == len(ptype_ids)
            finally:
                engine2.dispose()  # type: ignore[attr-defined]
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    finally:
        _cleanup(ptype_ids)
