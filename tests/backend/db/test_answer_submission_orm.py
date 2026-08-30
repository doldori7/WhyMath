"""AnswerSubmission ORM(`answer_submission`) — DB 연결 없이 검증 + 실 PG 유니크 통합 (EOS-32).

`test_solution_path_orm.py` 컨벤션 미러: 살아있는 PostgreSQL을 요구하지 않는다(메타데이터 등록·
PG DDL 컴파일·컬럼 계약·schema↔ORM round-trip만). ★실제 PG 제약 강제(UNIQUE(attempt_id,
sequence_no) 중복 거부)는 아래 `@pytest.mark.integration`이 실 PG에서 검증한다(미도달 시 skip).

검증 핵심:
  - 메타데이터 등록: `answer_submission` 테이블이 Base.metadata에 존재.
  - PG DDL 컴파일: UUID PK·attempt FK(CASCADE)·user FK·UNIQUE·NOT NULL·server_default.
  - JSONB 3컬럼(canonical_ast·grading_result·error_analysis) `none_as_null=True`(SEC-06 —
    전수 스캔은 `test_jsonb_none_as_null_governance.py`가 자동 검출·여기서는 신규 컬럼을
    이름으로 못박아 회귀를 지역화).
  - from_schema/to_schema round-trip(서브모델 GradingResult/ErrorAnalysis JSONB 왕복 포함).
  - from_schema의 submitted_at=None 제외(명시 NULL INSERT 방지 — server_default 적용 경로).
  - alembic 마이그레이션 파일 존재·up/down 대칭·체인(파일 시스템 검사 — DB 불요).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.answer_submission import AnswerSubmission
from whymath_backend.schema.answer_submission import (
    AnswerSubmission as SchemaAnswerSubmission,
)
from whymath_backend.schema.answer_submission import (
    ErrorAnalysis,
    GradingResult,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS_DIR = _REPO_ROOT / "src" / "backend" / "alembic" / "versions"

# SEC-06 대상 JSONB 3컬럼(값 없음 = SQL NULL이어야 오계수·백필 굶주림이 없다).
_JSONB_COLUMNS = ("canonical_ast", "grading_result", "error_analysis")


def _full_schema() -> SchemaAnswerSubmission:
    """모든 필드가 채워진 검증 schema 1건(round-trip 재료)."""
    return SchemaAnswerSubmission(
        submission_id=uuid.uuid4(),
        attempt_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        sequence_no=2,
        response_type="latex",
        raw_response="x=2",
        latex="x = 2",
        canonical_ast={"op": "Eq", "args": ["x", {"int": 2}]},
        grading_result=GradingResult(
            is_correct=False, method="sympy_equivalence", detail={"expected": "x=3"}
        ),
        error_analysis=ErrorAnalysis(
            suspected_misconception_ids=["distribution-over-power"],
            detail={"step": 2},
        ),
        submitted_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    )


class TestAnswerSubmissionTable:
    def test_registered_in_metadata(self) -> None:
        """`answer_submission`이 Base.metadata에 등록(모델 패키지 import 경유)."""
        import whymath_backend.db.models  # noqa: F401  # 패키지 __init__ 등록 경로 검증

        assert "answer_submission" in Base.metadata.tables

    def test_pg_ddl_compiles_with_expected_shapes(self) -> None:
        """PG DDL 컴파일 — PK·FK(CASCADE)·UNIQUE·NOT NULL·server_default가 연결 없이 생성된다."""
        ddl = str(CreateTable(AnswerSubmission.__table__).compile(dialect=postgresql.dialect()))
        assert "answer_submission" in ddl
        assert "PRIMARY KEY (submission_id)" in ddl
        # PR #902 P1: 소유 일치 복합 FK + attempt 삭제(GDPR) 시 자식 제출 동반 제거(CASCADE).
        assert (
            "FOREIGN KEY(attempt_id, user_id) "
            "REFERENCES problem_attempt (attempt_id, user_id) ON DELETE CASCADE" in ddl
        )
        # pseudonymous user_id 직접 보유(privacy 3종 배선의 균일 경로) — NO ACTION.
        assert "REFERENCES user_profile (user_id)" in ddl
        assert "CONSTRAINT uq_answer_submission_attempt_seq UNIQUE (attempt_id, sequence_no)" in ddl
        assert "JSONB" in ddl
        assert "now()" in ddl  # submitted_at server_default(보존 파기 축)

    def test_required_columns_not_null(self) -> None:
        """attempt_id·user_id·sequence_no·response_type·submitted_at은 NOT NULL(신규 수집 정합)."""
        columns = AnswerSubmission.__table__.columns
        for name in ("attempt_id", "user_id", "sequence_no", "response_type", "submitted_at"):
            assert (
                columns[name].nullable is False
            ), f"answer_submission.{name}은 NOT NULL이어야 한다"

    def test_composite_attempt_user_fk_declared(self) -> None:
        """PR #902 P1 — (attempt_id, user_id) 복합 FK가 problem_attempt를 가리킨다(CASCADE).

        attempt FK와 user FK가 독립이면 "A의 attempt + B의 user_id" 조합 INSERT가 통과해,
        user_id만으로 선별하는 export/erasure에 타인 데이터가 섞인다(소유 불일치). 복합 FK가
        그 조합을 DB에서 거부한다(실제 강제는 아래 실 PG 통합테스트).
        """
        composite = [
            constraint
            for constraint in AnswerSubmission.__table__.constraints
            if constraint.__class__.__name__ == "ForeignKeyConstraint"
            and tuple(constraint.columns.keys()) == ("attempt_id", "user_id")
        ]
        assert len(composite) == 1, "(attempt_id, user_id) 복합 FK가 정확히 1개여야 한다"
        targets = {fk.target_fullname for fk in composite[0].elements}
        assert targets == {"problem_attempt.attempt_id", "problem_attempt.user_id"}
        assert composite[0].ondelete == "CASCADE"

    def test_problem_attempt_has_composite_unique_for_fk_target(self) -> None:
        """PR #902 P1 — 복합 FK 참조 대상 UNIQUE(attempt_id, user_id)가 problem_attempt에 선언.

        attempt_id가 PK라 논리적으로 중복이지만, PG는 복합 FK의 참조 대상 컬럼 조합에 유일성
        보장을 요구한다(표준 패턴).
        """
        from whymath_backend.db.models.activity import ProblemAttempt

        unique_sets = [
            tuple(constraint.columns.keys())
            for constraint in ProblemAttempt.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert ("attempt_id", "user_id") in unique_sets

    def test_sequence_unique_constraint_declared(self) -> None:
        """UNIQUE(attempt_id, sequence_no) — attempt 내 제출 순번 유일(정규 시퀀스 계약)."""
        unique_sets = [
            tuple(constraint.columns.keys())
            for constraint in AnswerSubmission.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ]
        assert ("attempt_id", "sequence_no") in unique_sets

    def test_user_recent_index_exists(self) -> None:
        """학생 단위 최근순 조회 인덱스(`idx_answer_submission_user`) — privacy 경로 접근 패턴."""
        index_names = {index.name for index in AnswerSubmission.__table__.indexes}
        assert "idx_answer_submission_user" in index_names

    def test_jsonb_columns_declare_none_as_null(self) -> None:
        """JSONB 3컬럼 전부 `none_as_null=True`(SEC-06) + nullable(값 없음 = SQL NULL)."""
        for name in _JSONB_COLUMNS:
            column = AnswerSubmission.__table__.columns[name]
            assert column.nullable is True, f"answer_submission.{name}은 nullable이어야 한다"
            assert isinstance(column.type, JSONB)
            assert column.type.none_as_null is True, f"answer_submission.{name}: none_as_null 필요"


class TestSchemaOrmRoundTrip:
    def test_round_trip_preserves_all_fields(self) -> None:
        """schema → from_schema → to_schema 왕복이 서브모델(JSONB) 포함 전 필드를 보존한다."""
        original = _full_schema()
        orm = AnswerSubmission.from_schema(original)
        # JSONB 좌석엔 dict로 풀려 담긴다(서브모델 → model_dump).
        assert orm.grading_result == {
            "is_correct": False,
            "method": "sympy_equivalence",
            "detail": {"expected": "x=3"},
        }
        assert orm.error_analysis is not None
        assert orm.error_analysis["suspected_misconception_ids"] == ["distribution-over-power"]
        restored = orm.to_schema()
        assert restored == original  # Pydantic 재검증 복원(response_type Literal 재검증 포함)

    def test_from_schema_omits_none_submitted_at(self) -> None:
        """submitted_at=None(기본)은 속성 미설정 — 명시 NULL INSERT가 아니라 server_default 적용."""
        schema = SchemaAnswerSubmission(
            attempt_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            sequence_no=1,
            response_type="text",
        )
        orm = AnswerSubmission.from_schema(schema)
        # 인스턴스 __dict__에 키 자체가 없어야 INSERT에서 컬럼이 생략된다(NOT NULL 위반 방지).
        assert "submitted_at" not in orm.__dict__

    def test_to_schema_rejects_corrupted_response_type(self) -> None:
        """DB에 오염된 response_type이 있으면 to_schema가 ValidationError(침묵 통과 없음)."""
        orm = AnswerSubmission.from_schema(_full_schema())
        orm.response_type = "essay"  # 폐쇄 4종 밖(오염 시뮬레이션)
        with pytest.raises(Exception) as excinfo:
            orm.to_schema()
        assert "response_type" in str(excinfo.value)


class TestMigrationFile:
    def test_migration_file_exists_with_symmetric_updown(self) -> None:
        """EOS-32 마이그레이션 파일이 존재하고 up/down이 대칭(테이블·인덱스 create/drop)이다."""
        matches = list(_VERSIONS_DIR.glob("*answer_submission.py"))
        assert len(matches) == 1, "EOS-32 마이그레이션 파일이 정확히 1개여야 한다"
        source = matches[0].read_text(encoding="utf-8")
        assert 'op.create_table(\n        "answer_submission"' in source
        assert 'op.drop_table("answer_submission")' in source
        assert 'name="uq_answer_submission_attempt_seq"' in source
        assert 'ondelete="CASCADE"' in source  # attempt 복합 FK
        # PR #902 P1: 소유 일치 복합 FK + 참조 대상 UNIQUE(problem_attempt) — up/down 대칭.
        assert '["attempt_id", "user_id"]' in source
        assert 'name="fk_answer_submission_attempt_owner"' in source
        assert '"uq_problem_attempt_attempt_user"' in source
        assert "op.create_unique_constraint(" in source
        assert "op.drop_constraint(" in source
        assert '"idx_answer_submission_user"' in source
        assert 'op.drop_index("idx_answer_submission_user"' in source
        # 체인: S4-10 gen_meta(d7e8f1a2b4c6) 위에 쌓인다(단일 head 불변의 짝 —
        # test_solution_path_orm.py::test_single_head_chain이 head 유일성을 강제).
        assert 'down_revision: str | None = "d7e8f1a2b4c6"' in source


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — UNIQUE(attempt_id, sequence_no) + 복합 FK 소유 일치 실제 강제 왕복
# ===========================================================================


@pytest.mark.integration
def test_sequence_unique_and_owner_fk_enforced_on_live_pg() -> None:
    """실 PG 제약 강제 2건 — ①같은 attempt·같은 sequence_no 중복 거부(UNIQUE) ②타인 attempt에
    제출을 다는 소유 불일치 조합("A의 attempt + B의 user_id") 거부(복합 FK·PR #902 P1)."""
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
    uid_b = uuid.uuid4()  # 타인 B(소유 불일치 조합 시도용)
    aid = uuid.uuid4()  # A 소유 attempt

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

    def _submission(uid: uuid.UUID, seq: int) -> AnswerSubmission:
        return AnswerSubmission.from_schema(
            SchemaAnswerSubmission(
                attempt_id=aid, user_id=uid, sequence_no=seq, response_type="text"
            )
        )

    async def _run() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            # 시드는 commit — 위반 2건을 각각 독립 세션에서 시도해도 남아 있게(정리는 _cleanup).
            async with sm() as session:
                session.add(_user(uid_a, "제출학생A"))
                session.add(_user(uid_b, "타인B"))
                await session.flush()
                session.add(
                    ProblemAttempt.from_schema(ProblemAttemptSchema(attempt_id=aid, user_id=uid_a))
                )
                await session.commit()

            # ① 같은 (attempt_id, sequence_no) — UNIQUE가 거부해야 한다.
            async with sm() as session:
                session.add(_submission(uid_a, 1))
                await session.flush()
                session.add(_submission(uid_a, 1))
                with pytest.raises(IntegrityError) as excinfo:
                    await session.flush()
                assert "uq_answer_submission_attempt_seq" in str(excinfo.value)
                await session.rollback()

            # ② A의 attempt + B의 user_id — 복합 FK가 거부해야 한다(PR #902 P1 소유 일치).
            async with sm() as session:
                session.add(_submission(uid_b, 1))
                with pytest.raises(IntegrityError) as excinfo:
                    await session.flush()
                assert "fk_answer_submission_attempt_owner" in str(excinfo.value)
                await session.rollback()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.begin() as conn:
                for tbl, col in (
                    ("answer_submission", "user_id"),
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
