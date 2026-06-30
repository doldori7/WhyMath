"""교육과정 Overlay 적재 *통합테스트* — graph.json → curriculum_entry KR 셀 (실 PG 통합).

마이그레이션 head가 적용된 **실 PostgreSQL**(`curriculum_entry` 테이블)에 KR 교육과정 셀을 적재해
Overlay가 실제로 서는지 본다. CI `backend — 마이그레이션·통합 (실 PG)` 잡이 `pgvector/pgvector:pg16`
+ `alembic upgrade head` 후 `WHYMATH_RUN_INTEGRATION=1`로 수집·실행한다(신규 CI 잡 불요 — 기존 잡이
`tests/backend/l1/`를 수집). PG 미도달 시 graceful skip(backend_concept 통합테스트 미러).

검증:
  ① 적재 → `curriculum_entry` row 존재·entry_id=`{concept_id}:KR`·매핑 필드 반영(domain_label·
     grade_band·introduced_grade·national_standard_codes·confidence·KR 상수)
  ② 멱등 — 같은 셀 재적재 시 행 1개·값 갱신·**created_at 보존**(updated_at은 갱신)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.curriculum.curriculum_loader import (
    load_kr_curriculum_entries_from_graph_json,
    populate_kr_curriculum_entries,
)

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(정리 대상). 실 데이터와 충돌하지 않도록 9xx 순번 slug.
_NID = "HIGH-CALC-941"
_ENTRY_ID = f"{_NID}:KR"
_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 7, 1, 9, 30, 0, tzinfo=timezone.utc)


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·조회용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + `curriculum_entry` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM curriculum_entry"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(entry_ids: list[str]) -> None:
    """curriculum_entry 적재 행 정리(entry_id 기준)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM curriculum_entry WHERE entry_id = ANY(:ids)"),
                {"ids": entry_ids},
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _graph(tmp_path: Path) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "concept_id": _NID,
                        "name_ko": "정적분",
                        "domain": "적분",
                        "grade_band_hint": "고등학교",
                        "standard_codes": ["[12미적02-05]"],
                        "prerequisite_concept_ids": ["HIGH-CALC-940"],
                        "review_status": "reviewed",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


class TestCurriculumEntryRoundtrip:
    def test_populate_creates_kr_cell(self, tmp_path: Path) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        try:
            entries = load_kr_curriculum_entries_from_graph_json(_graph(tmp_path), now=_NOW)
            count = populate_kr_curriculum_entries(entries, settings=Settings())
            assert count == 1

            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    row = conn.execute(
                        text(
                            "SELECT entry_id, concept_id, country_code, domain_label, grade_band, "
                            "introduced_grade, national_standard_codes, curriculum_revision, "
                            "license_id, is_present, confidence, source_url, required_depth, "
                            "created_at, updated_at FROM curriculum_entry WHERE entry_id = :e"
                        ),
                        {"e": _ENTRY_ID},
                    ).one()
                assert row.entry_id == _ENTRY_ID
                assert row.concept_id == _NID
                assert row.country_code == "KR"
                assert row.domain_label == "적분"
                assert row.grade_band == "고등학교"
                assert row.introduced_grade == 10
                assert row.national_standard_codes == ["[12미적02-05]"]
                assert row.curriculum_revision == "2022 개정"
                assert row.license_id == "KR-NCIC"
                assert row.is_present is True
                assert float(row.confidence) == pytest.approx(0.9)
                assert row.source_url == "https://www.ncic.go.kr"
                assert row.required_depth is None  # 코퍼스에 깊이 신호 없음(날조 금지)
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup([_ENTRY_ID])

    def test_reload_preserves_created_at_updates_updated_at(self, tmp_path: Path) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        try:
            # 1차 적재(now=_NOW).
            first = load_kr_curriculum_entries_from_graph_json(_graph(tmp_path), now=_NOW)
            populate_kr_curriculum_entries(first, settings=Settings())

            # 2차 적재(now=_LATER) → 같은 entry_id 갱신·created_at 보존·updated_at 갱신.
            second = load_kr_curriculum_entries_from_graph_json(_graph(tmp_path), now=_LATER)
            populate_kr_curriculum_entries(second, settings=Settings())

            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT created_at, updated_at FROM curriculum_entry "
                            "WHERE entry_id = :e"
                        ),
                        {"e": _ENTRY_ID},
                    ).all()
                assert len(rows) == 1  # 멱등(행 1개)
                # created_at 보존(최초 _NOW)·updated_at 갱신(_LATER).
                assert rows[0].created_at == _NOW
                assert rows[0].updated_at == _LATER
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup([_ENTRY_ID])
