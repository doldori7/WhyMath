"""Dialogue ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem/user ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(JSONB·enum·FK·UNIQUE) /
enum values_callable / schema↔ORM 변환 roundtrip.

설계 정본: schemas/v1.0/schema_v1.0.md §7.1.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from whymath_backend.db.base import Base
from whymath_backend.db.models.dialogue import (
    Dialogue as OrmDialogue,
)
from whymath_backend.db.models.dialogue import (
    DialogueTurn as OrmDialogueTurn,
)
from whymath_backend.schema.dialogue import (
    Dialogue as SchemaDialogue,
)
from whymath_backend.schema.dialogue import (
    DialogueTurn as SchemaDialogueTurn,
)
from whymath_backend.schema.enums import (
    ContentType,
    Resolution,
    SocraticStrategy,
    StudentIntent,
    TurnRole,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_dialogue_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인5 두 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"dialogue", "dialogue_turn"} <= tables


def test_dialogue_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §7.1 DDL 테이블명과 일치한다."""
    assert OrmDialogue.__tablename__ == "dialogue"
    assert OrmDialogueTurn.__tablename__ == "dialogue_turn"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일
# ──────────────────────────────────────────────────────────────────────────
def test_dialogue_ddl_fks_and_enum() -> None:
    """dialogue: FK 3개(user_profile·problem_attempt·problem)·resolution_enum·gen_random_uuid."""
    ddl = _pg_ddl(OrmDialogue.__table__)
    assert "REFERENCES user_profile" in ddl
    assert "REFERENCES problem_attempt" in ddl
    assert "REFERENCES problem" in ddl
    assert "resolution_enum" in ddl
    assert "gen_random_uuid()" in ddl
    assert "NUMERIC" in ddl  # estimated_cost_usd DECIMAL(8,4)
    # FK는 정확히 3개.
    assert len(OrmDialogue.__table__.foreign_keys) == 3


def test_dialogue_flagged_for_review_default_false() -> None:
    """flagged_for_review는 NOT NULL DEFAULT FALSE다."""
    col = OrmDialogue.__table__.c.flagged_for_review
    assert col.nullable is False
    assert col.server_default is not None


def test_dialogue_turn_ddl_fk_unique_and_loose_ref() -> None:
    """dialogue_turn: dialogue FK·UNIQUE(dialogue_id, turn_order)·targeted_concept_id는 FK 아님."""
    ddl = _pg_ddl(OrmDialogueTurn.__table__)
    assert "REFERENCES dialogue" in ddl
    assert "UNIQUE" in ddl  # UNIQUE(dialogue_id, turn_order)
    assert "JSONB" in ddl  # image_analysis
    # targeted_concept_id는 REFERENCES 없음 → FK 아님(FK는 dialogue_id 하나뿐).
    assert "REFERENCES concept" not in ddl
    assert len(OrmDialogueTurn.__table__.foreign_keys) == 1


def test_dialogue_turn_turn_order_not_null() -> None:
    """turn_order는 INTEGER NOT NULL(UNIQUE 구성요소)이다."""
    col = OrmDialogueTurn.__table__.c.turn_order
    assert col.nullable is False


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable
# ──────────────────────────────────────────────────────────────────────────
def test_resolution_enum_values() -> None:
    """resolution 컬럼 enum이 한글 값('학생자력해결' 등)을 갖는다."""
    enums = OrmDialogue.__table__.c.resolution.type.enums  # type: ignore[attr-defined]
    assert "학생자력해결" in enums
    assert "풀이공개로종결" in enums


def test_turn_role_enum_values() -> None:
    """role 컬럼 enum이 영어 값(student/assistant/system)을 갖는다."""
    enums = OrmDialogueTurn.__table__.c.role.type.enums  # type: ignore[attr-defined]
    assert "student" in enums
    assert "assistant" in enums
    assert "system" in enums


def test_dialogue_turn_other_enum_values() -> None:
    """content_type·socratic_strategy·student_intent enum 값이 정합."""
    ct = OrmDialogueTurn.__table__.c.content_type.type.enums  # type: ignore[attr-defined]
    assert "수식" in ct
    ss = OrmDialogueTurn.__table__.c.socratic_strategy.type.enums  # type: ignore[attr-defined]
    assert "조건확인" in ss
    assert "그래프그리기제안" in ss
    si = OrmDialogueTurn.__table__.c.student_intent.type.enums  # type: ignore[attr-defined]
    assert "막힘표현" in si


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_dialogue_roundtrip() -> None:
    """Dialogue schema↔ORM 변환이 핵심 필드(id·결과·비용·플래그)를 보존한다."""
    did = uuid.uuid4()
    uid = uuid.uuid4()
    s = SchemaDialogue(
        dialogue_id=did,
        user_id=uid,
        resolution=Resolution.Socratic유도성공,
        total_turns=6,
        model_used="qwen3-32b-local",
        estimated_cost_usd=0.0123,
        student_rating=5,
        flagged_for_review=True,
    )
    orm = OrmDialogue.from_schema(s)
    assert orm.dialogue_id == did
    assert orm.user_id == uid
    assert orm.resolution == "Socratic유도성공"
    assert orm.model_used == "qwen3-32b-local"
    assert orm.estimated_cost_usd == 0.0123
    assert orm.flagged_for_review is True

    back = orm.to_schema()
    assert back.dialogue_id == did
    assert back.resolution == s.resolution
    assert back.estimated_cost_usd == 0.0123
    assert back.student_rating == 5
    assert back.flagged_for_review is True


def test_dialogue_default_flagged_for_review() -> None:
    """flagged_for_review 미지정 시 False로 보존된다(schema 기본값 False)."""
    s = SchemaDialogue()
    orm = OrmDialogue.from_schema(s)
    assert orm.flagged_for_review is False
    back = orm.to_schema()
    assert back.flagged_for_review is False


def test_dialogue_turn_roundtrip_jsonb_and_loose_ref() -> None:
    """DialogueTurn 변환이 image_analysis JSONB·느슨참조(targeted_concept_id)를 보존한다."""
    tid = uuid.uuid4()
    did = uuid.uuid4()
    concept = uuid.uuid4()
    s = SchemaDialogueTurn(
        turn_id=tid,
        dialogue_id=did,
        turn_order=1,
        role=TurnRole.assistant,
        content="조건 (가)를 수식으로 표현해보세요",
        content_type=ContentType.텍스트,
        socratic_strategy=SocraticStrategy.조건확인,
        student_intent=StudentIntent.질문,
        targeted_concept_id=concept,
        image_analysis={"detected": "f(x)=x^2", "conf": 0.88},
    )
    orm = OrmDialogueTurn.from_schema(s)
    assert orm.turn_id == tid
    assert orm.dialogue_id == did
    assert orm.turn_order == 1
    assert orm.role == "assistant"
    assert orm.socratic_strategy == "조건확인"
    assert orm.targeted_concept_id == concept
    assert orm.image_analysis == {"detected": "f(x)=x^2", "conf": 0.88}

    back = orm.to_schema()
    assert back.turn_id == tid
    assert back.turn_order == 1
    assert back.role == s.role
    assert back.socratic_strategy == s.socratic_strategy
    assert back.targeted_concept_id == concept
    assert back.image_analysis == s.image_analysis
