"""문제 코퍼스 → backend 적재 *통합테스트*(WHYMATH_RUN_INTEGRATION·실 PG).

마이그레이션 head가 적용된 **실 PostgreSQL**(`problem`·`problem_concept`·`concept`)에 실 코퍼스
(`data/corpus/problem_bank_v1/problems.jsonl`)를 적재해 S2-b 파이프라인이 실제로 서는지 본다:
  ① 개념 선적재(HK06/HK10/HK11/HK09 source_id) → 코퍼스 적재 → `problem` 행 + `problem_concept`
     태깅 행 존재(concept 해석 성공).
  ② 멱등 — 2회 적재 후 slug 기준 `problem` 행 수·`problem_concept` 행 수 불변(count 안정).
PG 미도달 시 graceful skip(`test_misconception_loader_integration.py` 미러). 정리는 전건 DELETE.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.problem_bank.populate import populate_problem_bank

pytestmark = pytest.mark.integration

# 통합 전용 개념 src_id → 실 데이터와 충돌 안 나게 it 슬러그 code로 삽입.
_CONCEPT_SRC_IDS = ["HK06", "HK10", "HK11", "HK09"]
_SLUGS = [
    "wm-quad-eq-larger-root",
    "wm-quad-eq-smaller-root",
    "wm-quad-fn-axis",
    "wm-quad-eq-root-count-mc",
]


def _corpus_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "corpus"
        / "problem_bank_v1"
        / "problems.jsonl"
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
            conn.execute(text("SELECT count(*) FROM problem"))
            conn.execute(text("SELECT count(*) FROM problem_concept"))
            conn.execute(text("SELECT count(*) FROM concept"))
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


def _seed_concepts() -> None:
    """통합 전용 개념 4건 삽입 — source_id로 문제 태깅이 concept_id를 해석하게 한다."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            for src_id in _CONCEPT_SRC_IDS:
                conn.execute(
                    text(
                        "INSERT INTO concept (concept_id, code, name_ko, level, source_id) "
                        "VALUES (:cid, :code, :name, '세부개념', :src) "
                        "ON CONFLICT (code) DO NOTHING"
                    ),
                    {
                        "cid": uuid.uuid4(),
                        "code": f"IT-PROBBANK-{src_id}",
                        "name": f"통합테스트 개념 {src_id}",
                        "src": src_id,
                    },
                )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup() -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text(
                    "DELETE FROM problem_concept WHERE problem_id IN "
                    "(SELECT problem_id FROM problem WHERE slug = ANY(:slugs))"
                ),
                {"slugs": _SLUGS},
            )
            conn.execute(text("DELETE FROM problem WHERE slug = ANY(:slugs)"), {"slugs": _SLUGS})
            conn.execute(
                text("DELETE FROM concept WHERE source_id = ANY(:srcs)"),
                {"srcs": _CONCEPT_SRC_IDS},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _count(sql: str, params: dict[str, object]) -> int:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            return int(conn.execute(text(sql), params).scalar_one())
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestRealCorpusLoad:
    def test_load_creates_problems_and_concept_tags(self) -> None:
        _skip_if_unreachable()
        corpus = _corpus_path()
        if not corpus.exists():
            pytest.skip("실 코퍼스 미존재(data/corpus/problem_bank_v1/problems.jsonl)")
        try:
            _cleanup()  # 선행 잔여 제거
            _seed_concepts()
            report = populate_problem_bank(None, problems_path=corpus, settings=Settings())
            assert report.problems_loaded == 4
            # 개념 선적재 → 태깅 전건 해석(orphan 0). 시드 태깅 총 6건(HK06×3+HK10+HK11+HK09).
            assert report.concepts_skipped == 0
            assert report.problem_concepts_loaded == 6

            prob_rows = _count(
                "SELECT count(*) FROM problem WHERE slug = ANY(:slugs)", {"slugs": _SLUGS}
            )
            pc_rows = _count(
                "SELECT count(*) FROM problem_concept WHERE problem_id IN "
                "(SELECT problem_id FROM problem WHERE slug = ANY(:slugs))",
                {"slugs": _SLUGS},
            )
            assert prob_rows == 4
            assert pc_rows == 6
        finally:
            _cleanup()

    def test_reload_is_idempotent(self) -> None:
        _skip_if_unreachable()
        corpus = _corpus_path()
        if not corpus.exists():
            pytest.skip("실 코퍼스 미존재(data/corpus/problem_bank_v1/problems.jsonl)")
        try:
            _cleanup()
            _seed_concepts()
            populate_problem_bank(None, problems_path=corpus, settings=Settings())
            first_prob = _count(
                "SELECT count(*) FROM problem WHERE slug = ANY(:slugs)", {"slugs": _SLUGS}
            )
            first_pc = _count(
                "SELECT count(*) FROM problem_concept WHERE problem_id IN "
                "(SELECT problem_id FROM problem WHERE slug = ANY(:slugs))",
                {"slugs": _SLUGS},
            )
            # 2회차 재적재 — slug/복합 PK 충돌 upsert라 행 수 불변.
            populate_problem_bank(None, problems_path=corpus, settings=Settings())
            second_prob = _count(
                "SELECT count(*) FROM problem WHERE slug = ANY(:slugs)", {"slugs": _SLUGS}
            )
            second_pc = _count(
                "SELECT count(*) FROM problem_concept WHERE problem_id IN "
                "(SELECT problem_id FROM problem WHERE slug = ANY(:slugs))",
                {"slugs": _SLUGS},
            )
            assert first_prob == 4
            assert second_prob == 4  # 멱등(문제 행 안정)
            assert first_pc == 6
            assert second_pc == 6  # 멱등(태깅 행 안정)
        finally:
            _cleanup()
