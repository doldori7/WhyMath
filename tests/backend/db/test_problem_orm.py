"""Problem ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

이 테스트는 살아있는 PostgreSQL을 요구하지 않는다(메타데이터→PG DDL 컴파일·enum 값·
schema↔ORM 변환·lazy import만 본다). 실제 PG 적용(테이블 생성·CRUD)·get_session/
dispose 같은 *런타임 연결 경로*는 메인의 실 PG 통합검증에서 확인한다.

검증 핵심:
  - 메타데이터 등록: Base.metadata에 problem·problem_step·problem_relation 존재.
  - PG DDL 컴파일: CreateTable→PG dialect 문자열에 JSONB·source_type_enum·
    gen_random_uuid()·uuid 포함(메타데이터→PG DDL 생성이 맞는지 연결 없이 검증).
  - enum values_callable: source_type이 값 '평가원'을, curriculum이 '2015_REVISION'을
    PG enum 라벨로 갖는지(멤버명 'REVISION_2015'이 아니라 값 — DDL §14.3 정합).
  - 변환 roundtrip: schema.Problem → ORM.from_schema → .to_schema()가 핵심 필드 보존.
  - lazy import: db.session import가 연결 없이 성공(엔진은 첫 사용에만 생성).

설계 정본: schemas/v1.0/schema_v1.0.md §3.1·§3.2·§14.3.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.problem import (
    Problem as OrmProblem,
)
from whymath_backend.db.models.problem import (
    ProblemRelation as OrmProblemRelation,
)
from whymath_backend.db.models.problem import (
    ProblemStep as OrmProblemStep,
)
from whymath_backend.schema.enums import (
    Curriculum,
    Persona,
    RelationType,
    SignaturePattern,
    SourceType,
    StepType,
    Subject,
)
from whymath_backend.schema.problem import (
    Condition,
    Problem as SchemaProblem,
    ProblemRelation as SchemaProblemRelation,
    ProblemStep as SchemaProblemStep,
)


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼: PG dialect로 컴파일한 CREATE TABLE 문자열
# ──────────────────────────────────────────────────────────────────────────
def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인1 세 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"problem", "problem_step", "problem_relation"} <= tables


def test_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §3.1/§3.2 DDL 테이블명과 일치한다."""
    assert OrmProblem.__tablename__ == "problem"
    assert OrmProblemStep.__tablename__ == "problem_step"
    assert OrmProblemRelation.__tablename__ == "problem_relation"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일 — 메타데이터→PG DDL 생성이 맞는지 연결 없이 검증
# ──────────────────────────────────────────────────────────────────────────
def test_problem_ddl_compiles_to_postgres() -> None:
    """Problem 테이블의 PG DDL에 JSONB·source_type_enum·gen_random_uuid()·UUID 포함."""
    ddl = _pg_ddl(OrmProblem.__table__)
    assert "JSONB" in ddl
    assert "source_type_enum" in ddl
    assert "gen_random_uuid()" in ddl
    # PG UUID 타입(컬럼 타입). 대문자 UUID로 방출된다.
    assert "UUID" in ddl


def test_problem_ddl_has_array_and_numeric() -> None:
    """TEXT[](unit_codes)·NUMERIC(DECIMAL 매핑)·enum 배열이 PG DDL에 반영된다."""
    ddl = _pg_ddl(OrmProblem.__table__)
    # unit_codes TEXT[] → 'TEXT[]'
    assert "TEXT[]" in ddl
    # DECIMAL → NUMERIC(p,s)
    assert "NUMERIC" in ddl
    # signature_patterns signature_pattern_enum[] — enum 배열 타입명
    assert "signature_pattern_enum" in ddl


def test_step_and_relation_ddl_compile() -> None:
    """problem_step·problem_relation도 PG DDL로 컴파일된다(FK·복합 PK·enum 포함)."""
    step_ddl = _pg_ddl(OrmProblemStep.__table__)
    assert "step_type_enum" in step_ddl
    assert "gen_random_uuid()" in step_ddl
    # UNIQUE(problem_id, step_order) 제약이 DDL에 들어간다.
    assert "UNIQUE" in step_ddl

    rel_ddl = _pg_ddl(OrmProblemRelation.__table__)
    assert "relation_type_enum" in rel_ddl
    # 복합 PK(parent·related·relation_type) → PRIMARY KEY 절
    assert "PRIMARY KEY" in rel_ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable — 멤버명이 아니라 *값*이 PG enum 라벨인지
# ──────────────────────────────────────────────────────────────────────────
def test_source_type_enum_uses_values_not_member_names() -> None:
    """source_type 컬럼의 PG enum이 값 '평가원'을 갖는다(멤버명이 아닌 DDL 값)."""
    enums = OrmProblem.__table__.c.source_type.type.enums  # type: ignore[attr-defined]
    assert "평가원" in enums
    assert "자체생성" in enums


def test_curriculum_enum_uses_value_with_distinct_member_name() -> None:
    """curriculum 컬럼이 값 '2015_REVISION'을 갖는다(멤버명 'REVISION_2015' 아님).

    values_callable이 빠지면 SQLAlchemy가 멤버명('REVISION_2015')으로 PG enum을 만들어
    §14.3 DDL 값('2015_REVISION')과 어긋난다 — 이 테스트가 그 회귀를 막는다.
    """
    enums = OrmProblem.__table__.c.curriculum_version.type.enums  # type: ignore[attr-defined]
    assert "2015_REVISION" in enums
    assert "REVISION_2015" not in enums  # 멤버명이 라벨로 새지 않았는지


def test_persona_enum_values_in_ddl() -> None:
    """persona 등 다른 enum도 값 기반인지 — Persona 값이 enum 정의에 정합."""
    # persona_fit은 JSONB라 enum 컬럼이 아니다. 대신 enum 매핑 헬퍼의 정합을 직접 확인:
    # signature_patterns 배열 원소 타입이 값 'COMPOSITE_DIFFERENTIABILITY'를 갖는다.
    item_type = OrmProblem.__table__.c.signature_patterns.type.item_type  # type: ignore[attr-defined]
    assert "COMPOSITE_DIFFERENTIABILITY" in item_type.enums
    # Persona 값 자체는 schema enum에서 확인(ORM JSONB라 라벨 없음).
    assert Persona.A_일반고고3.value == "A_일반고고3"


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip — schema → ORM.from_schema → .to_schema() 핵심 필드 보존
# ──────────────────────────────────────────────────────────────────────────
def _valid_schema_problem() -> SchemaProblem:
    """유효한 schema.Problem 인스턴스(자체생성 — 본문 보유 허용)."""
    return SchemaProblem(
        problem_id=uuid.uuid4(),
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2015,
        valid_from_year=2014,
        subject=Subject.미적분,
        unit_codes=["CAL-INT-DEF", "FUN-COMPOSITE"],
        question_text="f(x)를 구하시오",
        answer="16",
        signature_patterns=[SignaturePattern.COMPOSITE_DIFFERENTIABILITY],
        conditions_parsed=[Condition(label="가", text="미분가능", formal="diff(f,R)")],
        persona_fit={Persona.A_일반고고3: 0.9},
        tags=["킬러"],
        keywords=["합성함수"],
    )


def test_problem_roundtrip_preserves_core_fields() -> None:
    """schema.Problem → ORM → schema가 핵심 필드(id·출처·발문·과목 등)를 보존한다."""
    s = _valid_schema_problem()
    orm = OrmProblem.from_schema(s)

    # ORM 단계에서 핵심 필드 보존(use_enum_values=True → enum은 문자열 값).
    assert orm.problem_id == s.problem_id
    assert orm.source_type == "자체생성"
    assert orm.question_text == "f(x)를 구하시오"
    assert orm.subject == "미적분"
    assert orm.unit_codes == ["CAL-INT-DEF", "FUN-COMPOSITE"]
    # JSONB 대상: list[Condition] → list[dict]
    assert orm.conditions_parsed == [
        {"label": "가", "text": "미분가능", "formal": "diff(f,R)"}
    ]
    assert orm.persona_fit == {"A_일반고고3": 0.9}

    # 역변환(검증 포함) 후에도 핵심 필드 보존.
    back = orm.to_schema()
    assert back.problem_id == s.problem_id
    assert back.source_type == s.source_type
    assert back.question_text == s.question_text
    assert back.subject == s.subject
    assert back.unit_codes == s.unit_codes
    # list[dict] → list[Condition] 재검증
    assert back.conditions_parsed == s.conditions_parsed
    assert back.tags == s.tags
    assert back.keywords == s.keywords


def test_problem_step_roundtrip() -> None:
    """ProblemStep schema↔ORM 변환이 핵심 필드를 보존한다."""
    pid = uuid.uuid4()
    s = SchemaProblemStep(
        problem_id=pid,
        step_order=1,
        step_type=StepType.조건해석,
        step_title="조건 해석",
        socratic_prompt="조건 (가)를 수식으로 표현해보세요",
        common_mistakes=[{"error": "부호 실수", "hint": "양변 확인"}],
    )
    orm = OrmProblemStep.from_schema(s)
    assert orm.problem_id == pid
    assert orm.step_order == 1
    assert orm.step_type == "조건해석"
    assert orm.common_mistakes == [{"error": "부호 실수", "hint": "양변 확인"}]

    back = orm.to_schema()
    assert back.problem_id == pid
    assert back.step_order == 1
    assert back.step_type == s.step_type
    assert back.socratic_prompt == s.socratic_prompt


def test_problem_relation_roundtrip() -> None:
    """ProblemRelation schema↔ORM 변환이 복합키·관계유형을 보존한다."""
    parent = uuid.uuid4()
    related = uuid.uuid4()
    s = SchemaProblemRelation(
        parent_problem_id=parent,
        related_problem_id=related,
        relation_type=RelationType.변형,
        similarity_score=0.87,
    )
    orm = OrmProblemRelation.from_schema(s)
    assert orm.parent_problem_id == parent
    assert orm.related_problem_id == related
    assert orm.relation_type == "변형"
    assert orm.similarity_score == 0.87

    back = orm.to_schema()
    assert back.parent_problem_id == parent
    assert back.related_problem_id == related
    assert back.relation_type == s.relation_type


def test_to_schema_revalidates_copyright_invariant() -> None:
    """to_schema는 schema.Problem 검증을 재차 통과시킨다(본문 미보유 불변식 안전망).

    메타 전용 출처(평가원)에 본문이 없는 ORM은 to_schema가 정상 복원된다 — 본문 미보유
    불변식이 schema 레이어에서 시행됨을 확인(ORM에는 가짜 CHECK가 없다).
    """
    pid = uuid.uuid4()
    meta_only = SchemaProblem(
        problem_id=pid,
        source_type=SourceType.평가원,  # 본문 미보유 출처
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2022,
        subject=Subject.공통,
        unit_codes=["FUN-LIMIT"],
        # 본문 필드(question_text/answer_explanation/choices)는 비움 — 불변식 충족.
    )
    orm = OrmProblem.from_schema(meta_only)
    assert orm.source_type == "평가원"
    assert orm.question_text is None

    back = orm.to_schema()  # schema 검증을 다시 통과(예외 없이 복원)
    assert back.source_type == meta_only.source_type
    assert back.question_text is None


# ──────────────────────────────────────────────────────────────────────────
# 5) lazy import — db.session import가 연결 없이 성공
# ──────────────────────────────────────────────────────────────────────────
def test_session_module_imports_without_connection() -> None:
    """db.session import가 살아있는 DB 없이 성공한다(엔진은 첫 사용에만 lazy 생성).

    import 시점에 create_async_engine을 부르지 않으므로(모듈 전역 캐시는 None) import
    자체는 PostgreSQL을 요구하지 않는다 — 공개 심볼만 존재 확인(연결은 메인 통합검증).
    """
    from whymath_backend.db import session as session_mod

    # lazy: 아직 엔진이 만들어지지 않았다(전역 캐시 None).
    assert session_mod._engine is None
    assert session_mod._sessionmaker is None
    # 공개 심볼이 노출된다(호출은 하지 않음 — 호출하면 연결 경로로 진입).
    assert callable(session_mod.get_engine)
    assert callable(session_mod.get_sessionmaker)
    assert callable(session_mod.get_session)
    assert callable(session_mod.dispose_engine)


def test_db_package_public_symbols() -> None:
    """db 패키지가 Base·모델·세션 심볼을 공개 export한다."""
    from whymath_backend import db

    for name in (
        "Base",
        "Problem",
        "ProblemStep",
        "ProblemRelation",
        "get_engine",
        "get_sessionmaker",
        "get_session",
        "dispose_engine",
    ):
        assert hasattr(db, name), f"db.{name} 미노출"
