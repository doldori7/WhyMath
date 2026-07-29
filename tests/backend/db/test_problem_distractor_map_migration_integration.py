"""problem.distractor_map 마이그레이션 *왕복 통합테스트* — 실 PG (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에서 P3b 리비전(d9e0f1a2b3c4)을 *revision-local
왕복*(downgrade -1 → upgrade head)으로 검증한다. CI `backend — 마이그레이션·통합 (실 PG)` 잡이
이미 전구간 왕복을 돌리므로, 이 테스트는 그 위에서 *P3b 리비전이 distractor_map 컬럼을 정확히
더하고/되돌리며 UUID PK·기존 행을 보존*함을 못 박는다. PG 미도달 시 graceful skip
(`test_problem_p3a_migration_integration.py` 미러).

검증(P3b 핵심 — 가산적·UUID PK 보존):
  ① head에서 problem.distractor_map 존재.
  ② sentinel problem 행(자체생성·UUID 확보) → downgrade -1 → distractor_map 사라지되
     **sentinel 행·UUID PK는 그대로**(PK churn 0) → upgrade head → 컬럼 복귀·UUID 동일.

alembic은 `Config`(절대 script_location·주입 URL)로 프로그램 구동한다 — pytest rootdir·cwd와
무관(자격증명 0 하드코딩 — Settings에서).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_P3B_REVISION = "d9e0f1a2b3c4"  # 이 슬라이스가 추가한 리비전(head)
_PREV_REVISION = "c8d9e0f1a2b3"  # 직전 리비전(P3a head·downgrade -1 도착점)

_NEW_COLUMN = "distractor_map"

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
    """실 PG 도달 + `problem` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM problem"))
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


def _column_exists(column: str) -> bool:
    """problem 테이블에 주어진 컬럼이 존재하는지(information_schema)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            found = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'problem' AND column_name = :col"
                ),
                {"col": column},
            ).first()
        return found is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _seed_sentinel() -> uuid.UUID:
    """sentinel problem 행을 넣고 UUID PK를 돌려준다(왕복 중 PK 보존 관찰 대상)."""
    from sqlalchemy import text

    engine = _sync_engine()
    suffix = uuid.uuid4().hex[:8]
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                text(
                    "INSERT INTO problem "
                    "(source_type, curriculum_version, valid_from_year, subject, unit_codes) "
                    "VALUES ('자체생성', '2022_REVISION', 2022, '공통', :units) "
                    "RETURNING problem_id"
                ),
                {"units": [f"U-{suffix}"]},
            ).one()
        result: uuid.UUID = row.problem_id
        return result
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _sentinel_uuid(pid: uuid.UUID) -> uuid.UUID | None:
    """주어진 sentinel 행의 현재 UUID(없으면 None)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                text("SELECT problem_id FROM problem WHERE problem_id = :pid"),
                {"pid": str(pid)},
            ).first()
        return None if row is None else row.problem_id
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup_sentinel(pid: uuid.UUID) -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(text("DELETE FROM problem WHERE problem_id = :pid"), {"pid": str(pid)})
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestProblemDistractorMapMigrationRoundtrip:
    """P3b 리비전 revision-local 왕복 — distractor_map 추가/제거·UUID PK 보존."""

    def test_head_has_column(self) -> None:
        _skip_if_unreachable()
        # ① head 상태(CI가 upgrade head 완료): distractor_map 컬럼 존재.
        assert _column_exists(_NEW_COLUMN), f"{_NEW_COLUMN} 미존재"

    def test_downgrade_then_upgrade_preserves_uuid_pk(self) -> None:
        _skip_if_unreachable()
        from alembic import command

        cfg = _alembic_config()
        seeded_uuid = _seed_sentinel()
        try:
            assert _sentinel_uuid(seeded_uuid) == seeded_uuid

            # ② downgrade -1(P3b 역적용) — distractor_map 사라지되 행·UUID 보존.
            command.downgrade(cfg, _PREV_REVISION)  # type: ignore[arg-type]
            assert not _column_exists(_NEW_COLUMN), f"{_NEW_COLUMN} downgrade 후 잔존"
            # **핵심**: sentinel 행·UUID PK는 그대로(PK churn 0).
            assert _sentinel_uuid(seeded_uuid) == seeded_uuid

            # ③ upgrade head(재적용) — distractor_map 복귀·UUID 여전히 동일.
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            assert _column_exists(_NEW_COLUMN), f"{_NEW_COLUMN} 재적용 후 미복귀"
            assert _sentinel_uuid(seeded_uuid) == seeded_uuid  # 재적용 후에도 동일 UUID
        finally:
            # 항상 head로 복원(다른 통합테스트가 head 전제) + sentinel 정리.
            try:
                command.upgrade(cfg, "head")  # type: ignore[arg-type]
            finally:
                _cleanup_sentinel(seeded_uuid)
