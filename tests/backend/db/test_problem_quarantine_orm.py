"""EOS-71 — `problem.quarantine_reason`·`quarantined_at` 영속 계약 (DB 연결 없이).

기존 테이블 ALTER형 태스크라 검증 축은 EOS-57(`test_attempt_skill_ids_orm.py`)·EOS-48
(`test_event_time_active_time_orm.py`)과 동형이다: **비파괴**(nullable·server_default 없음 — 기존
행/writer 무영향·백필 날조 방지)와 **round-trip 정합**(신규 ORM 컬럼이 Pydantic schema에 대응 필드를
가져 `to_schema`가 `extra='forbid'`에서 깨지지 않음)을 못박는다.

여기에 이 태스크 고유의 축이 둘 더 붙는다:

① **미격리(None) ≠ 격리 시각**. `quarantined_at`에 `server_default=now()`를 달면 기존 행 전체가
   "마이그레이션 시각에 격리됨"으로 채워져 격리 이력이 통째로 날조된다. 그 순간 "이 문항은 회수된 적
   없다"와 "이 시각에 회수됐다"가 같은 글자가 되고, 계약 §2 비파괴 원칙의 근거 데이터가 사라진다.

② **격리는 삭제가 아니다**(계약 §2). 상태값이 `quarantined`여도 `Problem` 레코드는 그대로 존재하고
   round-trip에서 어떤 필드도 유실되지 않는다 — 이 파일이 그 "보존"을 스키마 층에서 확인한다
   (서빙 층 보존은 `tests/backend/api/test_problem_quarantine_serving.py`).

계약 정본: `docs/standards/problem_quarantine_contract.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from whymath_backend.db.models.problem import Problem
from whymath_backend.schema.enums import Curriculum, ReviewStatus, SourceType, Subject
from whymath_backend.schema.problem import Problem as ProblemSchema

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS_DIR = _REPO_ROOT / "src" / "backend" / "alembic" / "versions"
_MIGRATION_GLOB = "*problem_quarantine_status.py"

_QUARANTINED_AT = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
_REASON = "복수 정답 — 조건 (나)에서 x<0도 해가 된다(2026-08-31 판정)"


def _schema(**over: object) -> ProblemSchema:
    """자체생성 최소 문항(본문 보유 허용 출처 — 저작권 불변식을 건드리지 않는다)."""
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
        "question_text": "적분값을 구하시오",
    }
    kwargs.update(over)
    return ProblemSchema(**kwargs)  # type: ignore[arg-type]


class TestNonDestructiveColumns:
    def test_both_columns_nullable_without_server_default(self) -> None:
        """nullable + server_default 없음 — 기존 행 백필 0(격리 이력 날조 방지).

        `quarantined_at`에 `DEFAULT now()`를 달면 기존 행 전체가 마이그레이션 시각으로 채워져
        "격리된 적 없음"과 "이 시각에 격리됨"이 구분 불가가 된다(EOS-48이 시각 컬럼에서 막은 것과
        같은 날조 유형).
        """
        for name in ("quarantine_reason", "quarantined_at"):
            column = Problem.__table__.columns[name]
            assert column.nullable is True, name
            assert column.server_default is None, name

    def test_existing_review_columns_untouched(self) -> None:
        """기존 검수 컬럼 불변 — `review_status`·`review_score`는 그대로(회귀 0의 근거)."""
        assert Problem.__table__.columns["review_status"].nullable is True
        assert Problem.__table__.columns["review_score"].nullable is True


class TestUnquarantinedIsNotQuarantinedAtZero:
    """미격리(None)와 격리(값)는 round-trip 전 구간에서 다른 값으로 남는다."""

    def test_unquarantined_stays_none(self) -> None:
        restored = Problem.from_schema(_schema()).to_schema()
        assert restored.quarantine_reason is None
        assert restored.quarantined_at is None

    def test_quarantine_fields_round_trip(self) -> None:
        """격리 3필드(상태·사유·시각)가 schema→ORM→schema에서 보존된다."""
        restored = Problem.from_schema(
            _schema(
                review_status=ReviewStatus.quarantined,
                quarantine_reason=_REASON,
                quarantined_at=_QUARANTINED_AT,
            )
        ).to_schema()
        assert restored.review_status == ReviewStatus.quarantined
        assert restored.quarantine_reason == _REASON
        assert restored.quarantined_at == _QUARANTINED_AT

    def test_quarantine_preserves_the_record_body(self) -> None:
        """격리는 삭제가 아니다(계약 §2) — 본문·정답류가 함께 지워지지 않는다."""
        restored = Problem.from_schema(
            _schema(
                answer="3",
                review_status=ReviewStatus.quarantined,
                quarantine_reason=_REASON,
                quarantined_at=_QUARANTINED_AT,
            )
        ).to_schema()
        assert restored.question_text == "적분값을 구하시오"
        assert restored.answer == "3"


class TestMigrationFile:
    def test_migration_adds_enum_value_and_two_columns_symmetrically(self) -> None:
        """EOS-71 마이그레이션 존재·add/drop 대칭·upgrade 구간 server_default 0건."""
        matches = list(_VERSIONS_DIR.glob(_MIGRATION_GLOB))
        assert len(matches) == 1, "EOS-71 마이그레이션 파일이 정확히 1개여야 한다"
        source = matches[0].read_text(encoding="utf-8")
        assert "ALTER TYPE review_status_enum ADD VALUE IF NOT EXISTS 'quarantined'" in source
        assert '"quarantine_reason"' in source
        assert '"quarantined_at"' in source
        assert 'op.drop_column("problem", "quarantine_reason")' in source
        assert 'op.drop_column("problem", "quarantined_at")' in source
        upgrade_src = source.split("def upgrade()")[1].split("def downgrade()")[0]
        # 백필 날조 방지(핵심 비파괴 계약) — 키워드 인자 형태로 검사한다. 맨 substring은 이 규약을
        # *설명하는 주석*에도 걸려 변별력이 없다(정상 상태에서도 실패한다 — EOS-57 선례).
        assert "server_default=" not in upgrade_src

    def test_no_table_or_constraint_mutation(self) -> None:
        """컬럼 add/drop + enum add만 — 테이블·제약 변경 0건(기존 데이터 무손상의 근거)."""
        source = next(_VERSIONS_DIR.glob(_MIGRATION_GLOB)).read_text(encoding="utf-8")
        assert "op.create_table(" not in source
        assert "op.drop_table(" not in source
        assert "op.create_check_constraint(" not in source
        assert "op.drop_constraint(" not in source

    def test_chain_is_linear_on_the_single_head(self) -> None:
        """체인 — EOS-57(`d4a71c0f9b32`) 위에 선형으로 쌓인다(단일 head 관례).

        EOS-57은 `attempt_event`를, 본 리비전은 `problem`을 건드려 객체가 겹치지 않으므로 순서
        의존이 0이다. down_revision을 이름으로 동결해 다음 갈라짐이 드러나게 한다
        (`test_solution_path_orm.py::test_single_head_chain`이 head 유일성을 함께 강제).
        """
        source = next(_VERSIONS_DIR.glob(_MIGRATION_GLOB)).read_text(encoding="utf-8")
        assert 'revision: str = "e7c3b9a15f24"' in source
        assert 'down_revision: str | None = "d4a71c0f9b32"' in source
