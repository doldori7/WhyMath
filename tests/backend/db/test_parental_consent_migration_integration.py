"""parental_consent 마이그레이션 *왕복 통합테스트* — 실 PG (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**에서 PIPA 동의 GRANT 리비전(e0f1a2b3c4d5)을
*revision-local 왕복*(downgrade -1 → upgrade head)으로 검증한다. CI `backend — 마이그레이션·통합
(실 PG)` 잡이 이미 전구간 왕복을 돌리므로, 이 테스트는 그 위에서 *이 리비전이 parental_consent
테이블을 정확히 만들고/되돌리며, 동의 행을 적재·해시만 저장*함을 못 박는다. PG 미도달 시
graceful skip(`test_problem_distractor_map_migration_integration.py` 미러).

검증(PIPA GRANT 핵심 — 가산적·해시 저장·왕복):
  ① head에서 parental_consent 테이블 존재.
  ② 동의 행 1개를 sentinel user에 적재 → guardian_email_hash가 *평문 아닌 64 hex 해시*임을
     확인(평문 PII 부재) + verification_method='stub'.
  ③ downgrade -1 → 테이블 사라짐 → upgrade head → 테이블 복귀(왕복 안전).

alembic은 `Config`(절대 script_location·주입 URL)로 프로그램 구동한다 — pytest rootdir·cwd와
무관(자격증명 0 하드코딩 — Settings에서).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REVISION = "e0f1a2b3c4d5"  # 이 슬라이스가 추가한 리비전(head)
_PREV_REVISION = "d9e0f1a2b3c4"  # 직전 리비전(downgrade -1 도착점)

_TABLE = "parental_consent"

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
    """실 PG 도달 + `user_profile` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM user_profile"))
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


def _table_exists(table: str) -> bool:
    """주어진 테이블이 존재하는지(information_schema)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            found = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = :t AND table_schema = 'public'"
                ),
                {"t": table},
            ).first()
        return found is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _seed_user() -> uuid.UUID:
    """sentinel user_profile 행을 넣고 user_id를 돌려준다(동의 행 FK 대상)."""
    from sqlalchemy import text

    engine = _sync_engine()
    uid = uuid.uuid4()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text(
                    "INSERT INTO user_profile (user_id, persona_primary, is_minor) "
                    "VALUES (:uid, 'A_일반고고3', true)"
                ),
                {"uid": str(uid)},
            )
        return uid
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _insert_consent(uid: uuid.UUID, guardian_email: str) -> tuple[str, str]:
    """동의 행 1개 적재(해시 저장) → (저장된 guardian_email_hash, verification_method) 반환."""
    from sqlalchemy import text

    digest = hashlib.sha256(guardian_email.strip().lower().encode("utf-8")).hexdigest()
    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text(
                    "INSERT INTO parental_consent "
                    "(consent_id, user_id, guardian_email_hash, verification_method, "
                    " consent_scope, consent_signed_at) "
                    "VALUES (:cid, :uid, :h, 'stub', 'service_core', :ts)"
                ),
                {
                    "cid": str(uuid.uuid4()),
                    "uid": str(uid),
                    "h": digest,
                    "ts": datetime.now(tz=timezone.utc),
                },
            )
            row = conn.execute(
                text(
                    "SELECT guardian_email_hash, verification_method "
                    "FROM parental_consent WHERE user_id = :uid"
                ),
                {"uid": str(uid)},
            ).one()
        return str(row.guardian_email_hash), str(row.verification_method)
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(uid: uuid.UUID) -> None:
    """동의 행 → 사용자 순 삭제(FK parental_consent.user_id → user_profile)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            conn.execute(
                text("DELETE FROM parental_consent WHERE user_id = :uid"), {"uid": str(uid)}
            )
            conn.execute(text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(uid)})
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class TestParentalConsentMigrationRoundtrip:
    """PIPA GRANT 리비전 revision-local 왕복 — 테이블 추가/제거·해시 저장 검증."""

    def test_head_has_table(self) -> None:
        _skip_if_unreachable()
        # ① head 상태(CI가 upgrade head 완료): parental_consent 테이블 존재.
        assert _table_exists(_TABLE), f"{_TABLE} 미존재"

    def test_consent_row_stores_hash_only_not_plaintext(self) -> None:
        """동의 행 적재 → guardian_email_hash는 64 hex 해시(평문 PII 부재)·method='stub'."""
        _skip_if_unreachable()
        guardian_email = "parent@example.com"
        uid = _seed_user()
        try:
            stored_hash, method = _insert_consent(uid, guardian_email)
            # 핵심(미성년 PII): 저장된 값은 *해시*다 — 평문 이메일이 아니다.
            assert stored_hash != guardian_email
            assert len(stored_hash) == 64
            assert (
                stored_hash
                == hashlib.sha256(guardian_email.strip().lower().encode("utf-8")).hexdigest()
            )
            assert method == "stub"  # 실 본인확인 아님(법적 경계·변호사 자문 후속)
        finally:
            _cleanup(uid)

    def test_downgrade_then_upgrade_roundtrip(self) -> None:
        _skip_if_unreachable()
        from alembic import command

        cfg = _alembic_config()
        try:
            assert _table_exists(_TABLE)
            # ② downgrade -1(이 리비전 역적용) — 테이블 사라짐.
            command.downgrade(cfg, _PREV_REVISION)  # type: ignore[arg-type]
            assert not _table_exists(_TABLE), f"{_TABLE} downgrade 후 잔존"
            # ③ upgrade head(재적용) — 테이블 복귀.
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
            assert _table_exists(_TABLE), f"{_TABLE} 재적용 후 미복귀"
        finally:
            # 항상 head로 복원(다른 통합테스트가 head 전제).
            command.upgrade(cfg, "head")  # type: ignore[arg-type]
