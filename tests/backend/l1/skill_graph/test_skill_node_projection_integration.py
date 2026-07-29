"""스킬 메타 PG 프로젝션 *통합테스트* — Phase 2a (WHYMATH_RUN_INTEGRATION·실 PG).

마이그레이션 head 적용 실 PostgreSQL(`skill_node` 테이블·`behavior_area_enum`)에 스킬 코퍼스
(`data/corpus/skill_graph_v1/graph.json`)를 end-to-end 적재한다. CI `backend — 마이그레이션·통합
(실 PG)` 잡이 `alembic upgrade head`(→ `skill_node` 포함) 후 수집·실행한다. PG 미도달 또는 코퍼스
미존재 시 graceful skip(atom_node 통합테스트 동형).

검증:
  ① 적재 — skill_node 27행(v1 코퍼스)·behavior_area 6종 커버
  ② behavior_area native enum 왕복 — 조회 값이 6종 폐쇄 집합 내
  ③ review_status 전건 'ai_estimated'(v1 자체작성이나 전문 검수 전·정직 표기)
  ④ 멱등 — 재적재 시 행수 불변
구 concept_node·atom_node와 별개(신규 테이블·additive)를 건드리지 않는다. 정리는 skill_node 전건.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.config import Settings
from whymath_backend.l1.skill_graph.skill_node_projection import (
    load_skill_nodes_from_graph_json,
    populate_skill_nodes,
)

pytestmark = pytest.mark.integration

_CORPUS = Path(__file__).resolve().parents[4] / "data" / "corpus" / "skill_graph_v1" / "graph.json"

_EXPECTED_AREAS = {"COMPUTE", "TRANSFORM", "INTERPRET", "REPRESENT", "REASON", "VERIFY"}


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
            conn.execute(text("SELECT count(*) FROM skill_node"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_guard() -> list[str]:
    if not _reachable():
        pytest.skip("PG 미도달 또는 마이그레이션 미적용(skill_node) — 통합 건너뜀")
    if not _CORPUS.exists():
        pytest.skip("스킬 코퍼스 미존재(data/corpus/skill_graph_v1/graph.json)")
    payload = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return [str(s["skill_id"]) for s in payload["skills"]]


def _cleanup(skill_ids: list[str]) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM skill_node WHERE skill_id = ANY(:ids)"), {"ids": skill_ids}
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_populate_real_corpus_and_enum_roundtrip() -> None:
    """실 코퍼스 적재 → 27행·behavior_area 6종 커버·enum 왕복·review 상수·멱등."""
    skill_ids = _skip_guard()
    from sqlalchemy import text

    try:
        records = load_skill_nodes_from_graph_json(_CORPUS)
        count = populate_skill_nodes(records, settings=Settings())
        assert count == len(skill_ids)

        engine = _sync_engine()
        try:
            with engine.connect() as conn:  # type: ignore[attr-defined]
                total = conn.execute(
                    text("SELECT count(*) FROM skill_node WHERE skill_id = ANY(:ids)"),
                    {"ids": skill_ids},
                ).scalar_one()
                # ② behavior_area native enum 왕복 — 6종 폐쇄 집합 내.
                areas = (
                    conn.execute(
                        text(
                            "SELECT DISTINCT behavior_area::text FROM skill_node "
                            "WHERE skill_id = ANY(:ids)"
                        ),
                        {"ids": skill_ids},
                    )
                    .scalars()
                    .all()
                )
                # ③ review_status 전건 'ai_estimated'.
                reviews = (
                    conn.execute(
                        text(
                            "SELECT DISTINCT review_status FROM skill_node "
                            "WHERE skill_id = ANY(:ids)"
                        ),
                        {"ids": skill_ids},
                    )
                    .scalars()
                    .all()
                )
            assert total == len(skill_ids)
            assert set(areas) == _EXPECTED_AREAS  # 6종 전부 커버(v1)
            assert reviews == ["ai_estimated"]

            # ④ 멱등 — 재적재 후에도 행수 불변.
            recount = populate_skill_nodes(
                load_skill_nodes_from_graph_json(_CORPUS), settings=Settings()
            )
            assert recount == len(skill_ids)
            engine2 = _sync_engine()
            try:
                with engine2.connect() as conn:  # type: ignore[attr-defined]
                    again = conn.execute(
                        text("SELECT count(*) FROM skill_node WHERE skill_id = ANY(:ids)"),
                        {"ids": skill_ids},
                    ).scalar_one()
                assert again == len(skill_ids)
            finally:
                engine2.dispose()  # type: ignore[attr-defined]
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    finally:
        _cleanup(skill_ids)
