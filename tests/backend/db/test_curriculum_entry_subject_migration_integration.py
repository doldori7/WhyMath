"""curriculum_entry subject 축(S1) 마이그레이션 *왕복 통합테스트* — 실 PG (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에서 subject 축 리비전(a4b5c6d7e8f9)을 검증한다.
CI `backend — 마이그레이션·통합 (실 PG)` 잡이 전구간 왕복을 돌리므로, 이 테스트는 그 위에서
*이 리비전이 3-튜플 의미키를 정확히 세우고/되돌림*을 못 박는다. PG 미도달 시 graceful skip
(`test_parental_consent_migration_integration.py` 미러).

검증(S1 핵심 — subject_expansion_readiness.md §9 invariant):
  ① head에서 subject 컬럼 존재 + subject 미지정 INSERT가 server_default '수학'으로 백필
     (기존 INSERT 경로 무파손).
  ② **같은 (concept_id, KR)에 subject '수학'·'물리' 두 행 공존 허용** — 교과가 다르면 별개 셀
     (벡터: 수학·물리학).
  ③ **동일 (concept_id, country_code, subject) 3-튜플 중복 거부**(IntegrityError — UNIQUE).
  ④ downgrade -1 → subject 컬럼 사라짐·2-튜플 UNIQUE 복원 → upgrade head → 3-튜플 복귀
     (왕복 안전 — 왕복 전 비수학 행 정리: downgrade의 2-튜플 UNIQUE 복원 전제).

alembic은 `Config`(절대 script_location·주입 URL)로 프로그램 구동한다 — pytest rootdir·cwd와
무관(자격증명 0 하드코딩 — Settings에서).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REVISION = "a4b5c6d7e8f9"  # 이 슬라이스가 추가한 리비전(head)
_PREV_REVISION = "f3a4b5c6d7e8"  # 직전 리비전(downgrade -1 도착점)

_TABLE = "curriculum_entry"

# 통합테스트 적재 키(정리 대상). 실 데이터와 충돌하지 않도록 9xx 순번 slug.
_NID = "HIGH-VEC-951"
_NOW = datetime(2026, 7, 2, 10, 0, 0, tzinfo=timezone.utc)

# alembic 디렉토리 절대 경로(src/backend/alembic) — 이 테스트 파일 기준 ../../../src/backend.
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "src" / "backend"
_ALEMBIC_DIR = _BACKEND_DIR / "alembic"


def _sync_engine() -> object:
    """조회·시드·정리용 sync(psycopg) 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from whymath_backend.config import Settings

    settings = Settings()
    if settings.db_disable_pool:
        return create_engine(settings.sync_database_url, poolclass=NullPool)
    return create_engine(settings.sync_database_url)


def _reachable() -> bool:
    """실 PG 도달 + `curriculum_entry` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text(f"SELECT count(*) FROM {_TABLE}"))
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


def _alembic_config() -> object:
    """절대 script_location·주입 URL로 구성한 alembic Config(cwd·rootdir 무관)."""
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", "")
    return cfg


def _subject_column_exists() -> bool:
    """curriculum_entry.subject 컬럼 존재 여부(information_schema)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            found = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = 'subject' "
                    "AND table_schema = 'public'"
                ),
                {"t": _TABLE},
            ).first()
        return found is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _insert_cell(
    conn: object,
    *,
    entry_id: str,
    concept_id: str = _NID,
    country_code: str = "KR",
    subject: str | None = None,
) -> None:
    """최소 required 컬럼으로 셀 1행 INSERT — subject=None이면 컬럼 자체를 생략(default 검증)."""
    from sqlalchemy import text

    cols = (
        "entry_id, concept_id, country_code, source_name, license_id, "
        "is_present, confidence, source_url, created_at, updated_at"
    )
    vals = (
        ":e, :cid, :cc, '2022 개정 교육과정', 'KR-NCIC', true, 0.9, "
        "'https://www.ncic.go.kr', :ts, :ts"
    )
    params: dict[str, object] = {"e": entry_id, "cid": concept_id, "cc": country_code, "ts": _NOW}
    if subject is not None:
        cols += ", subject"
        vals += ", :subj"
        params["subj"] = subject
    conn.execute(  # type: ignore[attr-defined]
        text(f"INSERT INTO {_TABLE} ({cols}) VALUES ({vals})"), params
    )


def _cleanup() -> None:
    """이 테스트가 적재한 행 정리(concept_id 기준 — subject 축 전 행)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(text(f"DELETE FROM {_TABLE} WHERE concept_id = :cid"), {"cid": _NID})
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestCurriculumEntrySubjectAxis:
    """S1 3-튜플 의미키 — default 백필·수학/물리 공존·동일 3-튜플 거부·왕복."""

    def test_head_has_subject_column_with_default_backfill(self) -> None:
        """① head에서 subject 컬럼 존재 + 미지정 INSERT → server_default '수학' 백필."""
        _skip_if_unreachable()
        from sqlalchemy import text

        assert _subject_column_exists(), "subject 컬럼 미존재"
        engine = _sync_engine()
        try:
            with engine.begin() as conn:  # type: ignore[attr-defined]
                # subject 컬럼 생략 INSERT — 기존(S1 이전) 경로 그대로.
                _insert_cell(conn, entry_id=f"{_NID}:KR")
                row = conn.execute(
                    text(f"SELECT subject FROM {_TABLE} WHERE entry_id = :e"),
                    {"e": f"{_NID}:KR"},
                ).one()
            assert row.subject == "수학"  # server_default 백필
        finally:
            engine.dispose()  # type: ignore[attr-defined]
            _cleanup()

    def test_same_concept_country_two_subjects_coexist(self) -> None:
        """② 같은 (concept_id, KR)에 '수학'·'물리' 두 행 공존 — 교과가 다르면 별개 셀."""
        _skip_if_unreachable()
        from sqlalchemy import text

        engine = _sync_engine()
        try:
            with engine.begin() as conn:  # type: ignore[attr-defined]
                _insert_cell(conn, entry_id=f"{_NID}:KR", subject="수학")
                # 비수학 셀은 `:{subject}` 접미(S1 entry_id 규약 — 수학만 무접미).
                _insert_cell(conn, entry_id=f"{_NID}:KR:물리", subject="물리")
                count = conn.execute(
                    text(f"SELECT count(*) FROM {_TABLE} WHERE concept_id = :cid"),
                    {"cid": _NID},
                ).scalar_one()
            assert count == 2  # 공존 허용(2-튜플 UNIQUE였다면 IntegrityError)
        finally:
            engine.dispose()  # type: ignore[attr-defined]
            _cleanup()

    def test_duplicate_three_tuple_rejected(self) -> None:
        """③ 동일 (concept_id, country_code, subject) 3-튜플 중복 → IntegrityError(UNIQUE)."""
        _skip_if_unreachable()
        from sqlalchemy.exc import IntegrityError

        engine = _sync_engine()
        try:
            with engine.begin() as conn:  # type: ignore[attr-defined]
                _insert_cell(conn, entry_id=f"{_NID}:KR", subject="수학")
            # 같은 3-튜플·다른 entry_id — PK는 다르지만 의미키 UNIQUE가 막아야 한다.
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:  # type: ignore[attr-defined]
                    _insert_cell(conn, entry_id=f"{_NID}:KR:dup", subject="수학")
        finally:
            engine.dispose()  # type: ignore[attr-defined]
            _cleanup()

    def test_downgrade_then_upgrade_roundtrip(self) -> None:
        """④ downgrade -1 → subject 부재·2-튜플 복원 → upgrade head → 3-튜플 복귀."""
        _skip_if_unreachable()
        from sqlalchemy.exc import IntegrityError

        from alembic import command

        _cleanup()  # downgrade의 2-튜플 UNIQUE 복원 전제 — 비수학 잔여 행 정리
        cfg = _alembic_config()
        try:
            assert _subject_column_exists()
            # downgrade -1(이 리비전 역적용) — subject 컬럼 사라짐.
            command.downgrade(cfg, _PREV_REVISION)  # type: ignore[arg-type]
            assert not _subject_column_exists(), "subject 컬럼 downgrade 후 잔존"
            # 2-튜플 UNIQUE 복원 확인 — 같은 (concept_id, KR) 두 번째 행이 거부돼야 한다.
            engine = _sync_engine()
            try:
                with engine.begin() as conn:  # type: ignore[attr-defined]
                    _insert_cell(conn, entry_id=f"{_NID}:KR")
                with pytest.raises(IntegrityError):
                    with engine.begin() as conn:  # type: ignore[attr-defined]
                        _insert_cell(conn, entry_id=f"{_NID}:KR:dup")
            finally:
                engine.dispose()  # type: ignore[attr-defined]
                _cleanup()
            # upgrade head(재적용) — subject 컬럼·3-튜플 UNIQUE 복귀.
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            assert _subject_column_exists(), "subject 컬럼 재적용 후 미복귀"
        finally:
            # 항상 head로 복원(다른 통합테스트가 head 전제) 후 잔여 행 정리.
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            _cleanup()
