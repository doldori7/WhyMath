"""unit_spec/learning_objective 컴파일 산출물↔DB 정합 감사 (PED-16③) — reader 0(unit_spec) +
FK로 얽힌 live 테이블(learning_objective)의 조용한 드리프트를 상시 감시.

배경: `unit_spec` 테이블 자체는 애플리케이션 코드 어디서도 SELECT되지 않는다(전수 grep 확인 —
`UnitSpec` 참조는 `unit_compiler.py`의 insert 구문과 테스트뿐). `harness/objective_coverage.py`는
이 테이블을 우회해 `.unit.yaml`을 직접 glob한다(그 모듈 자신의 docstring이 "hermetic·DB 0"으로
명시하는 *의도적* 설계). 하지만 `unit_spec`은 **제거 불가**하다 — `learning_objective`가 복합 FK
`(unit_id, unit_version)`로 `unit_spec`을 참조하고(ON DELETE CASCADE), `learning_objective` 자체는
`api/study.py`(`session.get`)·`l4/pedagogy/k_type_resolver.py`(`select(...)`)가 실제로 읽는 **live**
테이블이다. 즉 `unit_spec`은 "아무도 안 읽는 고아 테이블"이 아니라 "아무도 안 읽지만 live 테이블의
FK 부모"라 제거하면 `learning_objective`의 스키마·시더(`UnitSpecStore.seed`)까지 재설계해야
한다(PED-16 태스크 범위 밖). 판정 근거 전문은 `l1/pedagogy/unit_compiler.py` 모듈 docstring.

이 테스트는 컴파일러가 실제로 만드는 행 dict(`CompiledUnit.unit_spec_row`/`objective_rows`)의 키
집합과 ORM 컬럼 집합을 *서로* 대조한다(하드코딩 스냅샷 없음). `compile_unit()`은 dict 키를 그대로
`pg_insert(...).values(**row)`에 바인딩하므로 이 등식이 깨지면 실제 배포에서도 즉시 SQLAlchemy
에러가 나지만(요란한 실패), 그 신호는 **실 PG가 있는 통합 잡에서만** 드러난다(`test_e2e_pedagogy_
pilot_integration.py`는 `pytest.mark.integration`·PG 미도달 시 skip). 이 테스트는 hermetic이라
매 CI 실행마다 훨씬 이르게, 훨씬 명확한 메시지로 같은 드리프트를 잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa

from whymath_backend.db.models.pedagogy_dsl import LearningObjective, UnitSpec
from whymath_backend.l1.pedagogy.unit_compiler import compile_unit
from whymath_backend.l1.pedagogy.unit_compiler import load_packs as load_packs_mem

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "data" / "corpus"
_UNIT_YAML = _CORPUS / "units_v1" / "quadratic_maxmin.unit.yaml"
_PACKS_DIR = _CORPUS / "pedagogy_packs_v1"
_GRAPH = _CORPUS / "atom_graph_v1" / "graph.json"
_STANDARDS = _CORPUS / "standards_v1" / "standards.json"

# unit_spec 컬럼 중 서버 디폴트라 컴파일러 행 dict에서 *의도적으로* 생략되는 것들
# (컴파일러 docstring "compiled_at은 server default라 생략" — 여기서만 예외로 인정).
_UNIT_SPEC_SERVER_DEFAULT_OMITTED = {"compiled_at"}


def _orm_column_keys(model: type) -> set[str]:
    """ORM 매핑 컬럼 키 집합(하드코딩 아님 — mapper 실시간 introspection)."""
    return {col.key for col in sa.inspect(model).mapper.column_attrs}


def _compile_pilot_unit():
    """실 파일럿 코퍼스(이차함수 최대최소 소단원)를 컴파일 — 실 컴파일러 출력을 대조 대상으로."""
    valid_atoms = {c["code"] for c in json.loads(_GRAPH.read_text(encoding="utf-8"))["concepts"]}
    statements = {
        s["code"]: s["statement"]
        for s in json.loads(_STANDARDS.read_text(encoding="utf-8"))["standards"]
    }
    return compile_unit(
        _UNIT_YAML.read_text(encoding="utf-8"),
        packs=load_packs_mem(_PACKS_DIR),
        valid_atom_codes=valid_atoms,
        statements_by_code=statements,
    )


class TestUnitSpecRowDbParity:
    def test_unit_spec_row_keys_equal_orm_columns_minus_server_defaults(self) -> None:
        """컴파일러가 만드는 `unit_spec_row`의 키 = ORM 컬럼 - server-default 생략분.

        어긋나면 두 방향의 실제 위험:
          - row에만 있는 키 → `pg_insert(UnitSpec).values(**row)`가 미지 컬럼으로 즉시 실패.
          - ORM에만 있는(생략 목록 밖) 컬럼 → NOT NULL이면 삽입이 즉시 실패, nullable이면
            **조용히 항상 NULL**로 깔림(침묵 실패 — 이쪽이 진짜 위험).
        """
        compiled = _compile_pilot_unit()
        row_keys = set(compiled.unit_spec_row)
        orm_keys = _orm_column_keys(UnitSpec)
        expected_orm_keys = orm_keys - _UNIT_SPEC_SERVER_DEFAULT_OMITTED
        assert row_keys == expected_orm_keys, (
            f"unit_spec_row 키 vs ORM 컬럼(server-default 제외) 불일치 — "
            f"row에만: {row_keys - expected_orm_keys}, ORM에만: {expected_orm_keys - row_keys}"
        )

    def test_objective_row_keys_equal_learning_objective_orm_columns(self) -> None:
        """컴파일러가 만드는 `objective_rows[*]`의 키 = `LearningObjective` ORM 컬럼(생략 0).

        `learning_objective`는 `api/study.py`·`k_type_resolver.py`가 실제로 읽는 live 테이블이라
        이 등식이 깨지면 unit_spec보다 훨씬 직접적인 서빙 영향(숨은 NULL 필드)이 난다.
        """
        compiled = _compile_pilot_unit()
        assert compiled.objective_rows, "파일럿 소단원은 목표 4개를 낸다 — 빈 리스트면 컴파일 이상"
        row_keys = set(compiled.objective_rows[0])
        orm_keys = _orm_column_keys(LearningObjective)
        assert row_keys == orm_keys, (
            f"objective_row 키 vs LearningObjective ORM 컬럼 불일치 — "
            f"row에만: {row_keys - orm_keys}, ORM에만: {orm_keys - row_keys}"
        )

    def test_unit_spec_pk_matches_composite_fk_source_columns(self) -> None:
        """`unit_spec` 복합 PK가 `learning_objective`의 FK 참조 컬럼과 여전히 일치한다.

        이 정합이 깨지면 `UnitSpecStore.seed`의 FK 순서 전제(unit 먼저→목표) 자체가 무너진다.
        """
        unit_pk = {c.key for c in sa.inspect(UnitSpec).mapper.primary_key}
        assert unit_pk == {"unit_id", "unit_version"}
        fk_targets = {
            fk.column.key
            for fk in LearningObjective.__table__.foreign_keys
            if fk.column.table.name == "unit_spec"
        }
        assert fk_targets == unit_pk
