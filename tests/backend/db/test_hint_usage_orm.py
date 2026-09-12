"""HintUsage ORM(`hint_usage`) — DB 연결 없이 검증 + 실 PG 소유 정합 통합 (EOS-45).

`test_answer_submission_orm.py`(EOS-32) 컨벤션 미러: 메타데이터 등록·PG DDL 컴파일·제약 선언·
schema↔ORM round-trip만 hermetic으로 검증하고, 실제 제약 강제(복합 FK 소유 불일치 거부)는
`@pytest.mark.integration`(실 PG·기본 skip)이 검증한다.

검증 핵심:
  - 복합 FK (attempt_id, user_id) → problem_attempt(attempt_id, user_id) CASCADE — EOS-32
    소유 정합 관례를 신설 시점부터 적용.
  - 참조 대상 UNIQUE(uq_problem_attempt_attempt_user)는 EOS-32 마이그레이션이 이미 생성 —
    **EOS-45 마이그레이션이 중복 생성하지 않음**을 소스 검사로 못박는다.
  - hint_id 느슨참조(FK 0건 — 힌트 정본 테이블 부재 실측·FK 날조 금지).
  - view_duration_ms nullable(미측정=NULL·0 날조 금지)·requested_at NOT NULL(보존 파기 축).
  - from_schema의 requested_at=None 제외(server_default 적용 경로·EOS-32 동형).
  - alembic 마이그레이션 파일 존재·up/down 대칭·체인(파일 시스템 검사 — DB 불요).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.hint_usage import HintUsage
from whymath_backend.schema.hint_usage import HintUsage as SchemaHintUsage

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS_DIR = _REPO_ROOT / "src" / "backend" / "alembic" / "versions"


def _full_schema() -> SchemaHintUsage:
    """모든 필드가 채워진 검증 schema 1건(round-trip 재료)."""
    return SchemaHintUsage(
        hint_usage_id=uuid.uuid4(),
        attempt_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        hint_id="genlog:0f3a",
        hint_level=3,
        requested_at=datetime(2026, 8, 30, 18, 0, tzinfo=UTC),
        view_duration_ms=4200,
    )


class TestHintUsageTable:
    def test_registered_in_metadata(self) -> None:
        """`hint_usage`가 Base.metadata에 등록(모델 패키지 import 경유)."""
        import whymath_backend.db.models  # noqa: F401  # 패키지 __init__ 등록 경로 검증

        assert "hint_usage" in Base.metadata.tables

    def test_pg_ddl_compiles_with_expected_shapes(self) -> None:
        """PG DDL 컴파일 — PK·복합 FK(CASCADE)·user FK·NOT NULL·server_default."""
        ddl = str(CreateTable(HintUsage.__table__).compile(dialect=postgresql.dialect()))
        assert "hint_usage" in ddl
        assert "PRIMARY KEY (hint_usage_id)" in ddl
        # EOS-32 소유 정합 관례 — 타인 attempt 조합 거부 + attempt 삭제 시 자식 동반 제거.
        assert (
            "FOREIGN KEY(attempt_id, user_id) "
            "REFERENCES problem_attempt (attempt_id, user_id) ON DELETE CASCADE" in ddl
        )
        assert "REFERENCES user_profile (user_id)" in ddl
        assert "now()" in ddl  # requested_at server_default(보존 파기 축)

    def test_composite_attempt_user_fk_declared(self) -> None:
        """(attempt_id, user_id) 복합 FK 정확히 1개 — problem_attempt 소유 정합(EOS-32 관례)."""
        composite = [
            constraint
            for constraint in HintUsage.__table__.constraints
            if constraint.__class__.__name__ == "ForeignKeyConstraint"
            and tuple(constraint.columns.keys()) == ("attempt_id", "user_id")
        ]
        assert len(composite) == 1
        targets = {fk.target_fullname for fk in composite[0].elements}
        assert targets == {"problem_attempt.attempt_id", "problem_attempt.user_id"}
        assert composite[0].ondelete == "CASCADE"

    def test_required_columns_not_null(self) -> None:
        """attempt_id·user_id·hint_level·requested_at은 NOT NULL(신규 수집 정합)."""
        columns = HintUsage.__table__.columns
        for name in ("attempt_id", "user_id", "hint_level", "requested_at"):
            assert columns[name].nullable is False, f"hint_usage.{name}은 NOT NULL이어야 한다"

    def test_hint_id_is_loose_reference(self) -> None:
        """hint_id는 nullable TEXT·FK 0건 — 힌트 정본 테이블 부재 실측(FK 날조 금지)."""
        column = HintUsage.__table__.columns["hint_id"]
        assert column.nullable is True
        assert len(column.foreign_keys) == 0

    def test_view_duration_nullable_for_unmeasured(self) -> None:
        """view_duration_ms nullable — 종료 신호 부재(이탈·강제 종료)는 NULL(0 날조 금지)."""
        assert HintUsage.__table__.columns["view_duration_ms"].nullable is True

    def test_indexes_exist(self) -> None:
        """(user_id, requested_at DESC) privacy 경로 + (attempt_id) 파생 조회 인덱스."""
        index_names = {index.name for index in HintUsage.__table__.indexes}
        assert "idx_hint_usage_user" in index_names
        assert "idx_hint_usage_attempt" in index_names

    def test_no_sequence_unique(self) -> None:
        """순번 UNIQUE 없음(의도) — 힌트 열람 순서는 requested_at·중복 열람도 각각 사실."""
        unique_sets = [
            tuple(constraint.columns.keys())
            for constraint in HintUsage.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert unique_sets == []


class TestSchemaOrmRoundTrip:
    def test_round_trip_preserves_all_fields(self) -> None:
        """schema → from_schema → to_schema 왕복이 전 필드를 보존한다(hint_level 재검증 포함)."""
        original = _full_schema()
        orm = HintUsage.from_schema(original)
        assert orm.hint_level == 3
        assert orm.view_duration_ms == 4200
        restored = orm.to_schema()
        assert restored == original

    def test_from_schema_omits_none_requested_at(self) -> None:
        """requested_at=None(기본)은 속성 미설정 — server_default 적용(EOS-32 동형)."""
        schema = SchemaHintUsage(attempt_id=uuid.uuid4(), user_id=uuid.uuid4(), hint_level=1)
        orm = HintUsage.from_schema(schema)
        assert "requested_at" not in orm.__dict__

    def test_to_schema_rejects_corrupted_hint_level(self) -> None:
        """DB에 오염된 hint_level(범위 밖)이 있으면 to_schema가 검증 실패(침묵 통과 없음)."""
        orm = HintUsage.from_schema(_full_schema())
        orm.hint_level = 9  # 폐쇄 1~4 밖(오염 시뮬레이션)
        with pytest.raises(Exception) as excinfo:
            orm.to_schema()
        assert "hint_level" in str(excinfo.value)


class TestMigrationFile:
    def test_migration_file_exists_with_symmetric_updown(self) -> None:
        """EOS-45 마이그레이션 파일 존재·up/down 대칭·복합 FK·인덱스 2종."""
        matches = list(_VERSIONS_DIR.glob("*hint_usage.py"))
        assert len(matches) == 1, "EOS-45 마이그레이션 파일이 정확히 1개여야 한다"
        source = matches[0].read_text(encoding="utf-8")
        assert 'op.create_table(\n        "hint_usage"' in source
        assert 'op.drop_table("hint_usage")' in source
        assert 'name="fk_hint_usage_attempt_owner"' in source
        assert 'ondelete="CASCADE"' in source
        assert '"idx_hint_usage_user"' in source
        assert '"idx_hint_usage_attempt"' in source
        assert 'op.drop_index("idx_hint_usage_user"' in source
        assert 'op.drop_index("idx_hint_usage_attempt"' in source
        # 체인: EOS-32 answer_submission(8f0b8e906362) 위에 쌓인다.
        assert 'down_revision: str | None = "8f0b8e906362"' in source

    def test_no_duplicate_unique_creation_on_problem_attempt(self) -> None:
        """복합 FK 참조 대상 UNIQUE는 EOS-32가 이미 생성 — EOS-45가 재생성하지 않는다.

        중복 create_unique_constraint는 실 PG upgrade에서 DuplicateObject로 터진다(체인 파손).
        """
        source = next(_VERSIONS_DIR.glob("*hint_usage.py")).read_text(encoding="utf-8")
        assert "op.create_unique_constraint(" not in source
        # downgrade도 EOS-32 소유물을 건드리지 않는다(대칭 경계).
        assert 'op.drop_constraint(\n        "uq_problem_attempt_attempt_user"' not in source
        assert 'op.drop_constraint("uq_problem_attempt_attempt_user"' not in source


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — 복합 FK 소유 정합 실제 강제 왕복(EOS-32 동형)
# ===========================================================================


@pytest.mark.integration
def test_owner_fk_enforced_on_live_pg() -> None:
    """A의 attempt + B의 user_id 힌트 사용 INSERT → 복합 FK IntegrityError(소유 불일치 거부)."""
    from pydantic import SecretStr
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from whymath_backend.config import Settings
    from whymath_backend.db.models.activity import ProblemAttempt
    from whymath_backend.db.models.user import UserProfile
    from whymath_backend.schema.activity import ProblemAttempt as ProblemAttemptSchema
    from whymath_backend.schema.enums import Persona
    from whymath_backend.schema.user import UserProfile as UserProfileSchema

    settings = Settings(jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"))

    async def _pg_reachable() -> bool:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid_a = uuid.uuid4()  # attempt 소유자 A
    uid_b = uuid.uuid4()  # 타인 B
    aid = uuid.uuid4()

    def _user(uid: uuid.UUID, nickname: str) -> UserProfile:
        return UserProfile.from_schema(
            UserProfileSchema(
                user_id=uid,
                persona_primary=Persona.A_일반고고3,
                nickname=nickname,
                email_hash=f"HASH-{uid.hex[:8]}",
                is_minor=True,
            )
        )

    def _usage(uid: uuid.UUID) -> HintUsage:
        return HintUsage.from_schema(SchemaHintUsage(attempt_id=aid, user_id=uid, hint_level=2))

    async def _run() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(_user(uid_a, "힌트학생A"))
                session.add(_user(uid_b, "타인B"))
                await session.flush()
                session.add(
                    ProblemAttempt.from_schema(ProblemAttemptSchema(attempt_id=aid, user_id=uid_a))
                )
                await session.commit()

            # 정상 소유(A) — 통과.
            async with sm() as session:
                session.add(_usage(uid_a))
                await session.flush()
                await session.rollback()

            # A의 attempt + B의 user_id — 복합 FK가 거부해야 한다(소유 정합).
            async with sm() as session:
                session.add(_usage(uid_b))
                with pytest.raises(IntegrityError) as excinfo:
                    await session.flush()
                assert "fk_hint_usage_attempt_owner" in str(excinfo.value)
                await session.rollback()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.begin() as conn:
                for tbl, col in (
                    ("hint_usage", "user_id"),
                    ("problem_attempt", "user_id"),
                    ("user_profile", "user_id"),
                ):
                    for uid in (uid_a, uid_b):
                        await conn.execute(
                            text(f"DELETE FROM {tbl} WHERE {col} = :k"), {"k": str(uid)}
                        )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup())
