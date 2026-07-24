"""소단원 DSL 컴파일러 v0.1 *단위테스트* — PED-01 후속 ② (hermetic·PG 불요).

CI hermetic 잡엔 PostgreSQL이 없으므로 `UnitSpecStore`의 *실 라운드트립*은 통합테스트로 미룬다.
여기서는 PG 없이 검증 가능한 것만 못 박는다(`test_pack_loader.py`의 가짜 엔진 패턴 재사용):

  (a) 실 예제 컴파일 — 1 unit_spec 행·4 목표 행·id·k_type·achievement_std·slot_manifest·
      exit_evidence·발주서·yaml_sha256(64 hex·결정론)
  (b) 참조 검증 — 미존재 개념 노드·성취기준·교수법 팩 → CompileError(전부 모아 실패)
  (c) `_merge_slots` — 기존 개수 교체 + 새 유형 append
  (d) `UnitSpecStore.seed` — unit_spec→learning_objective ON CONFLICT SQL(PK SET 제외·순서)
  (e) k_type_secondary==k_type → schema 거부

가짜 엔진(`_FakeEngine`)은 begin() 컨텍스트 + execute()를 흉내내 실행 statement를 수집한다 —
psycopg/PG 없이 배선·멱등 키·순서를 검증한다.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from whymath_backend.l1.pedagogy.unit_compiler import (
    CompiledUnit,
    CompileError,
    UnitSpecStore,
    _merge_slots,
    compile_unit,
    load_packs,
    load_statements_by_code,
    load_valid_atom_codes,
)
from whymath_backend.schema.pedagogy_pack import PedagogyPack, SlotSpec
from whymath_backend.schema.unit_dsl import ObjectiveDSL

# 예제 소단원의 확정 상수(파일럿 — data/corpus/units_v1/quadratic_maxmin.unit.yaml).
_UNIT_ID = "10공수1-이차함수-최대최소"
_STD_CODE = "[10공수1-02-06]"
_EXPECTED_IDS = [f"{_UNIT_ID}:OBJ-0{i}" for i in (1, 2, 3, 4)]
_EXPECTED_K_TYPES = ["CONCEPT", "PROCEDURE", "REPRESENT", "MODELING"]


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 로드 헬퍼 (실 corpus·실 예제)
# ──────────────────────────────────────────────────────────────────────────
def _repo_root() -> Path:
    """레포 루트 — 이 테스트는 tests/backend/l1/test_unit_compiler.py라 parents[3]가 루트."""
    return Path(__file__).resolve().parents[3]


def _corpus() -> tuple[dict[str, PedagogyPack], set[str], dict[str, str]]:
    root = _repo_root() / "data" / "corpus"
    packs = load_packs(root / "pedagogy_packs_v1")
    atoms = load_valid_atom_codes(root / "atom_graph_v1" / "graph.json")
    statements = load_statements_by_code(root / "standards_v1" / "standards.json")
    return packs, atoms, statements


def _example_yaml_text() -> str:
    return (_repo_root() / "data" / "corpus" / "units_v1" / "quadratic_maxmin.unit.yaml").read_text(
        encoding="utf-8"
    )


def _compile_example() -> CompiledUnit:
    packs, atoms, statements = _corpus()
    return compile_unit(
        _example_yaml_text(),
        packs=packs,
        valid_atom_codes=atoms,
        statements_by_code=statements,
    )


def _slots_as_dicts(pack: PedagogyPack) -> list[dict[str, Any]]:
    return [{"type": s.type, "count": s.count} for s in pack.required_slots]


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 (pack_loader 테스트 패턴 재사용)
# ──────────────────────────────────────────────────────────────────────────
class _FakeConnection:
    def __init__(self, engine: _FakeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, statement: object) -> None:
        self._engine.executed.append(statement)


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 수집."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _compile_sql(statement: object) -> str:
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# (a) 실 예제 컴파일
# ──────────────────────────────────────────────────────────────────────────
class TestCompileExample:
    def test_unit_spec_row_shape(self) -> None:
        compiled = _compile_example()
        row = compiled.unit_spec_row
        assert isinstance(row, dict)
        assert row["unit_id"] == _UNIT_ID
        assert row["unit_version"] == 1
        assert row["api_version"] == "unit/0.1"
        assert row["title"] == "이차함수의 최대·최소"
        assert row["curriculum_rev"] == "2022"
        assert row["standard_codes"] == [_STD_CODE]
        assert row["concept_nodes"] == ["10공수1-02-06-1", "10공수1-02-06-2", "10공수1-02-06-3"]
        assert row["compiler_ver"] == "soraw-dsl/0.1"
        assert row["status"] == "DRAFT"
        # compiled_at은 server default라 행 dict에서 생략한다.
        assert "compiled_at" not in row

    def test_four_objective_rows_ids_and_ktypes(self) -> None:
        compiled = _compile_example()
        assert len(compiled.objective_rows) == 4
        assert [r["id"] for r in compiled.objective_rows] == _EXPECTED_IDS
        assert [r["k_type"] for r in compiled.objective_rows] == _EXPECTED_K_TYPES
        # 미검증 정직 표기 — 기본 False.
        assert all(r["k_type_verified"] is False for r in compiled.objective_rows)
        # v0.1: 오개념 자동 채움 없음 — 미지정이라 None.
        assert all(r["misconception_ids"] is None for r in compiled.objective_rows)

    def test_achievement_std_resolved_from_standards(self) -> None:
        packs, atoms, statements = _corpus()
        compiled = compile_unit(
            _example_yaml_text(),
            packs=packs,
            valid_atom_codes=atoms,
            statements_by_code=statements,
        )
        expected = statements[_STD_CODE]
        assert expected  # 성취기준 원문이 실제로 존재
        assert all(r["achievement_std"] == expected for r in compiled.objective_rows)

    def test_concept_obj_slot_manifest_equals_pack(self) -> None:
        packs, _, _ = _corpus()
        compiled = _compile_example()
        obj01 = compiled.objective_rows[0]  # CONCEPT
        # CONCEPT 팩 required_slots 그대로(오버라이드 없음).
        assert obj01["slot_manifest"] == _slots_as_dicts(packs["CONCEPT"])
        types = {s["type"] for s in obj01["slot_manifest"]}
        assert types == {"example_pair", "contrast_case", "boundary_probe", "diag_item"}

    def test_modeling_obj_override_replaces_problem_variation_count(self) -> None:
        packs, _, _ = _corpus()
        compiled = _compile_example()
        obj04 = compiled.objective_rows[3]  # MODELING·slot_overrides problem_variation=3
        by_type = {s["type"]: s["count"] for s in obj04["slot_manifest"]}
        assert by_type["problem_variation"] == 3  # 팩 기본 2 → 3으로 교체
        # 팩의 다른 슬롯은 그대로.
        pack_by_type = {s.type: s.count for s in packs["MODELING"].required_slots}
        assert by_type["condition_extraction"] == pack_by_type["condition_extraction"]
        assert by_type["diag_item"] == pack_by_type["diag_item"]
        # 슬롯 유형 집합은 그대로(교체지 append 아님 — 새 유형 안 생김).
        assert set(by_type) == set(pack_by_type)

    def test_exit_evidence_equals_pack_default(self) -> None:
        packs, _, _ = _corpus()
        compiled = _compile_example()
        for row, k_type in zip(compiled.objective_rows, _EXPECTED_K_TYPES, strict=True):
            assert row["exit_evidence"] == packs[k_type].default_evidence

    def test_work_order_flat_list(self) -> None:
        compiled = _compile_example()
        # 발주서 = 각 목표 slot_manifest 평탄화(항목 수 = 총 슬롯 항목 수).
        total_entries = sum(len(r["slot_manifest"]) for r in compiled.objective_rows)
        assert len(compiled.work_order) == total_entries
        # 각 발주 항목의 count 합 = 모든 slot_manifest count 합(총 콘텐츠 수요).
        demand = sum(w["count"] for w in compiled.work_order)
        expected_demand = sum(
            s["count"] for r in compiled.objective_rows for s in r["slot_manifest"]
        )
        assert demand == expected_demand
        # 각 항목 구조 확인 + objective_id가 실제 목표에 속함.
        obj_ids = set(_EXPECTED_IDS)
        for w in compiled.work_order:
            assert set(w) == {"objective_id", "slot_type", "count"}
            assert w["objective_id"] in obj_ids

    def test_yaml_sha256_deterministic_64_hex(self) -> None:
        packs, atoms, statements = _corpus()
        text = _example_yaml_text()
        a = compile_unit(text, packs=packs, valid_atom_codes=atoms, statements_by_code=statements)
        b = compile_unit(text, packs=packs, valid_atom_codes=atoms, statements_by_code=statements)
        sha = a.unit_spec_row["yaml_sha256"]
        assert sha == b.unit_spec_row["yaml_sha256"]  # 결정론
        assert len(sha) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", sha)  # 64 hex


# ──────────────────────────────────────────────────────────────────────────
# (b) 참조 검증 (전부 모아 실패)
# ──────────────────────────────────────────────────────────────────────────
class TestRefValidation:
    def _yaml_with(self, mutate: Any) -> str:
        data = yaml.safe_load(_example_yaml_text())
        mutate(data)
        return yaml.safe_dump(data, allow_unicode=True)

    def test_unknown_concept_node_raises_listing_it(self) -> None:
        packs, atoms, statements = _corpus()

        def mutate(d: dict[str, Any]) -> None:
            d["objectives"][0]["concept_nodes"] = ["BOGUS-CODE-XYZ"]

        with pytest.raises(CompileError, match="BOGUS-CODE-XYZ"):
            compile_unit(
                self._yaml_with(mutate),
                packs=packs,
                valid_atom_codes=atoms,
                statements_by_code=statements,
            )

    def test_unknown_standard_code_raises(self) -> None:
        packs, atoms, statements = _corpus()

        def mutate(d: dict[str, Any]) -> None:
            d["objectives"][0]["standard_code"] = "[NOPE-00-00]"

        with pytest.raises(CompileError, match=r"\[NOPE-00-00\]"):
            compile_unit(
                self._yaml_with(mutate),
                packs=packs,
                valid_atom_codes=atoms,
                statements_by_code=statements,
            )

    def test_k_type_without_pack_raises(self) -> None:
        # 주입 팩 dict에서 MODELING을 잠시 뺀다 → OBJ-04(MODELING) 참조 실패.
        packs, atoms, statements = _corpus()
        packs_missing = {k: v for k, v in packs.items() if k != "MODELING"}
        with pytest.raises(CompileError, match="MODELING"):
            compile_unit(
                _example_yaml_text(),
                packs=packs_missing,
                valid_atom_codes=atoms,
                statements_by_code=statements,
            )

    def test_aggregates_all_missing_refs(self) -> None:
        # 여러 누락을 한 번에 → 메시지에 전부 담긴다(첫 오류에서 멈추지 않음).
        packs, atoms, statements = _corpus()

        def mutate(d: dict[str, Any]) -> None:
            d["objectives"][0]["concept_nodes"] = ["BAD-A"]
            d["objectives"][1]["standard_code"] = "[BAD-B]"

        with pytest.raises(CompileError) as excinfo:
            compile_unit(
                self._yaml_with(mutate),
                packs=packs,
                valid_atom_codes=atoms,
                statements_by_code=statements,
            )
        msg = str(excinfo.value)
        assert "BAD-A" in msg and "[BAD-B]" in msg


# ──────────────────────────────────────────────────────────────────────────
# (c) _merge_slots
# ──────────────────────────────────────────────────────────────────────────
class TestMergeSlots:
    def test_override_replaces_existing_and_appends_new(self) -> None:
        base = [SlotSpec(type="a", count=1), SlotSpec(type="b", count=2)]
        merged = _merge_slots(base, {"a": 5, "c": 3})
        # a 개수 교체(1→5)·b 보존·c append(뒤에).
        assert merged == [
            {"type": "a", "count": 5},
            {"type": "b", "count": 2},
            {"type": "c", "count": 3},
        ]

    def test_none_overrides_returns_base(self) -> None:
        base = [SlotSpec(type="a", count=1), SlotSpec(type="b", count=2)]
        assert _merge_slots(base, None) == [
            {"type": "a", "count": 1},
            {"type": "b", "count": 2},
        ]

    def test_does_not_mutate_pack_slotspecs(self) -> None:
        base = [SlotSpec(type="a", count=1)]
        _merge_slots(base, {"a": 99})
        assert base[0].count == 1  # 팩 원본 불변


# ──────────────────────────────────────────────────────────────────────────
# (d) UnitSpecStore.seed — ON CONFLICT SQL·PK SET 제외·순서
# ──────────────────────────────────────────────────────────────────────────
class TestSeedSql:
    def _seed_and_capture(self) -> list[object]:
        compiled = _compile_example()
        engine = _FakeEngine()
        store = UnitSpecStore(engine=engine)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
        unit_count, obj_count = store.seed(compiled)
        assert unit_count == 1
        assert obj_count == 4
        return engine.executed

    def test_unit_before_objectives_and_counts(self) -> None:
        executed = self._seed_and_capture()
        assert len(executed) == 5  # 1 unit + 4 목표
        first = _compile_sql(executed[0])
        assert "INSERT INTO unit_spec" in first
        for stmt in executed[1:]:
            assert "INSERT INTO learning_objective" in _compile_sql(stmt)

    def test_unit_spec_on_conflict_pk_absent_from_set(self) -> None:
        sql = _compile_sql(self._seed_and_capture()[0])
        assert "ON CONFLICT (unit_id, unit_version) DO UPDATE" in sql
        set_clause = sql.split("DO UPDATE SET", 1)[1]
        # 복합 PK는 SET에서 제외(멱등 보존).
        assert "unit_id" not in set_clause
        assert "unit_version" not in set_clause
        # 나머지 컬럼은 갱신.
        assert "api_version" in set_clause
        assert "yaml_sha256" in set_clause

    def test_learning_objective_on_conflict_id_absent_from_set(self) -> None:
        sql = _compile_sql(self._seed_and_capture()[1])
        assert "ON CONFLICT (id) DO UPDATE" in sql
        set_clause = sql.split("DO UPDATE SET", 1)[1]
        # PK id는 SET에서 제외 — \bid\b 경계로 검사(unit_id·misconception_ids 오탐 방지).
        assert re.search(r"\bid\b\s*=", set_clause) is None
        # 나머지 컬럼은 갱신.
        assert "statement" in set_clause
        assert "slot_manifest" in set_clause


# ──────────────────────────────────────────────────────────────────────────
# (e) k_type_secondary == k_type → schema 거부
# ──────────────────────────────────────────────────────────────────────────
class TestObjectiveDslSchema:
    def test_secondary_equals_primary_rejected(self) -> None:
        with pytest.raises(ValidationError, match="k_type_secondary"):
            ObjectiveDSL.model_validate(
                {
                    "suffix": "OBJ-01",
                    "statement": "x",
                    "standard_code": _STD_CODE,
                    "k_type": "CONCEPT",
                    "k_type_secondary": "CONCEPT",  # == 주 유형 → 거부
                    "concept_nodes": ["10공수1-02-06-1"],
                }
            )

    def test_distinct_secondary_allowed(self) -> None:
        obj = ObjectiveDSL.model_validate(
            {
                "suffix": "OBJ-01",
                "statement": "x",
                "standard_code": _STD_CODE,
                "k_type": "CONCEPT",
                "k_type_secondary": "REPRESENT",
                "concept_nodes": ["10공수1-02-06-1"],
            }
        )
        # use_enum_values=True라 값은 문자열.
        assert obj.k_type == "CONCEPT"
        assert obj.k_type_secondary == "REPRESENT"

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ObjectiveDSL.model_validate(
                {
                    "suffix": "OBJ-01",
                    "statement": "x",
                    "standard_code": _STD_CODE,
                    "k_type": "CONCEPT",
                    "concept_nodes": ["10공수1-02-06-1"],
                    "oops_typo": 1,
                }
            )
