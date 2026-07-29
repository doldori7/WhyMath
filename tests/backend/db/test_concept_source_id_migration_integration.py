"""concept.source_id/aliases 마이그레이션 *왕복 통합테스트* — P2b (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에서 P2b 리비전(b7c8d9e0f1a2)을 *revision-local 왕복*
(downgrade -1 → upgrade head)으로 검증한다. CI `backend — 마이그레이션·통합 (실 PG)` 잡이 이미
`alembic downgrade base → upgrade head` 전구간 왕복을 돌리므로(ci.yml backend-migrations), 이
테스트는 그 위에서 *P2b 리비전이 컬럼을 정확히 더하고/되돌리며
UUID PK·기존 행을 보존*함을 못 박는다.
PG 미도달 시 graceful skip(`test_concept_backend_load_integration.py` 미러).

검증(P2b 핵심 — UUID PK 보존 결정):
  ① head에서 concept.source_id·aliases 컬럼·idx_concept_source_id 인덱스 존재.
  ② sentinel concept 행(알려진 code)을 넣고 UUID 확보 → downgrade -1 → source_id 컬럼 사라지되
     **sentinel 행·UUID PK는 그대로**(PK churn 0·라이브 mastery/edge FK 안정성) → upgrade head →
     source_id 컬럼 복귀·UUID 여전히 동일·aliases NOT NULL.
  ③ downgrade가 aliases NULL 행을 만들지 않는다(왕복 후에도 빈 배열로 정합).

alembic은 `Config`(절대 script_location·주입 URL)로 프로그램 구동한다 — pytest rootdir·cwd와
무관하게 동작(자격증명 0 하드코딩 — Settings.database_url의 sync 형태 사용).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from whymath_backend.config import Settings

pytestmark = pytest.mark.integration

# 왕복 검증용 sentinel concept code(실 데이터와 충돌 않도록 9xx slug·재ID 새 형식).
_SENTINEL_CODE = "HIGH-MIGIT-901"
_P2B_REVISION = "b7c8d9e0f1a2"  # 이 슬라이스가 추가한 리비전(head)
_PREV_REVISION = "a6b7c8d9e0f1"  # 직전 리비전(downgrade -1 도착점)

# alembic 디렉토리 절대 경로(src/backend/alembic) — 이 테스트 파일 기준 ../../../src/backend.
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "src" / "backend"
_ALEMBIC_DIR = _BACKEND_DIR / "alembic"


def _sync_url() -> str:
    """Settings의 sync(psycopg) DB URL
    — alembic env가 async지만 여기선 조회용 sync 엔진에도 쓴다."""
    return Settings().sync_database_url


def _sync_engine() -> object:
    """조회·시드·정리용 sync(psycopg) 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    if settings.db_disable_pool:
        return create_engine(settings.sync_database_url, poolclass=NullPool)
    return create_engine(settings.sync_database_url)


def _reachable() -> bool:
    """실 PG 도달 + `concept` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
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


def _alembic_config() -> object:
    """절대 script_location·주입 URL로 구성한 alembic Config(cwd·rootdir 무관)."""
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    # env.py는 Settings().database_url(async)을 직접 읽으므로 sqlalchemy.url 주입은 불필요하나,
    # 안전하게 비워둔 ini 대신 명시적으로 둔다(자격증명은 Settings·env에서·하드코딩 0).
    cfg.set_main_option("sqlalchemy.url", "")
    return cfg


def _column_exists(column: str) -> bool:
    """concept 테이블에 주어진 컬럼이 존재하는지(information_schema)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            found = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'concept' AND column_name = :col"
                ),
                {"col": column},
            ).first()
        return found is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _index_exists(index_name: str) -> bool:
    """주어진 인덱스가 존재하는지(pg_indexes)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            found = conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = :ix"),
                {"ix": index_name},
            ).first()
        return found is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _seed_sentinel() -> uuid.UUID:
    """sentinel concept 행을 넣고 UUID PK를 돌려준다(왕복 중 PK 보존 관찰 대상)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            # level은 NOT NULL enum — '세부개념'(한글 값). aliases는 NOT NULL이라 명시.
            row = conn.execute(
                text(
                    "INSERT INTO concept (code, name_ko, level, aliases) "
                    "VALUES (:code, :name, '세부개념', '{}'::text[]) "
                    "RETURNING concept_id"
                ),
                {"code": _SENTINEL_CODE, "name": "마이그레이션 왕복 sentinel"},
            ).one()
        result: uuid.UUID = row.concept_id
        return result
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _sentinel_uuid() -> uuid.UUID | None:
    """sentinel 행의 현재 UUID(없으면 None)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                text("SELECT concept_id FROM concept WHERE code = :code"),
                {"code": _SENTINEL_CODE},
            ).first()
        return None if row is None else row.concept_id
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup_sentinel() -> None:
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(text("DELETE FROM concept WHERE code = :code"), {"code": _SENTINEL_CODE})
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestSourceIdMigrationRoundtrip:
    """P2b 리비전 revision-local 왕복 — 컬럼 추가/제거·UUID PK 보존(라이브 FK 안정성)."""

    def test_head_has_source_id_aliases_and_index(self) -> None:
        _skip_if_unreachable()
        # ① head 상태(CI가 upgrade head 완료): source_id·aliases 컬럼·인덱스 존재.
        assert _column_exists("source_id")
        assert _column_exists("aliases")
        assert _index_exists("idx_concept_source_id")

    def test_downgrade_then_upgrade_preserves_uuid_pk(self) -> None:
        _skip_if_unreachable()
        from alembic import command

        cfg = _alembic_config()
        try:
            # 시드 → UUID 확보(왕복 동안 보존돼야 하는 PK).
            seeded_uuid = _seed_sentinel()
            assert _sentinel_uuid() == seeded_uuid

            # ② downgrade -1(P2b 역적용) — source_id 컬럼·인덱스 사라지되 행·UUID 보존.
            command.downgrade(cfg, _PREV_REVISION)  # type: ignore[arg-type]
            assert not _column_exists("source_id")  # 컬럼 제거
            assert not _index_exists("idx_concept_source_id")  # 인덱스 제거
            # **핵심**: sentinel 행·UUID PK는 그대로(PK churn 0 — 라이브 mastery/edge FK 안정성).
            assert _sentinel_uuid() == seeded_uuid

            # ③ upgrade head(재적용) — source_id 컬럼 복귀·UUID 여전히 동일.
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            assert _column_exists("source_id")
            assert _index_exists("idx_concept_source_id")
            assert _sentinel_uuid() == seeded_uuid  # 재적용 후에도 동일 UUID
        finally:
            # 항상 head로 복원(다른 통합테스트가 head 전제) + sentinel 정리.
            try:
                command.upgrade(cfg, "head")  # type: ignore[arg-type]
            finally:
                _cleanup_sentinel()

    def test_roundtrip_keeps_aliases_not_null(self) -> None:
        _skip_if_unreachable()
        from alembic import command
        from sqlalchemy import text

        cfg = _alembic_config()
        try:
            seeded_uuid = _seed_sentinel()
            # 왕복: downgrade -1(aliases nullable로) → upgrade head(다시 NOT NULL·backfill).
            command.downgrade(cfg, _PREV_REVISION)  # type: ignore[arg-type]
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            # 왕복 후 sentinel의 aliases는 NULL이 아니라 빈 배열(backfill·정합).
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    row = conn.execute(
                        text("SELECT aliases FROM concept WHERE code = :code"),
                        {"code": _SENTINEL_CODE},
                    ).one()
                assert row.aliases is not None  # NOT NULL 유지(왕복이 NULL을 남기지 않음)
                assert row.aliases == []
            finally:
                engine.dispose()  # type: ignore[attr-defined]
            assert _sentinel_uuid() == seeded_uuid  # PK 보존
        finally:
            try:
                command.upgrade(cfg, "head")  # type: ignore[arg-type]
            finally:
                _cleanup_sentinel()
