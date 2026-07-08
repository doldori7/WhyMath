"""거버넌스 동결 — FormulaNode (리치 Part 2 Phase 5a·2026-07-08).

FormulaNode 1급 승격(위험문서 정식 개정)이 CLAUDE.md 금기·위험문서 canonical-only 경계 안에서 사는지
동결한다. FormulaNode는 두 위험문서(`math_dsl_evolution`·`risk_register`)가 유일하게 anti-goal로
판정했던 노드라, 경계가 코드로 강제돼야 한다:

  ① **신규 엣지 타입 0**: FormulaNode 도입이 EdgeType/Relation을 늘리지 않는다 — 수식 연결은
     참조 키(formula_refs·Phase 5b)만(anti-explosion).
  ② **canonical-only 불변식**: 노드에 변형/동치 열거 필드(`equivalence_class`·`sympy_repr`·
     `variant*`)가 없다 — canonical 1개만 노드화(조합폭발 방지). id 공간 `formula.<slug>`.
  ③ **SymPy 재구현 금지 경계**: FormulaNode 노드 모듈(pipeline 모델·backend 프로젝션·ORM)이 sympy를
     import하지 않는다 — 이 노드는 정체성·참조만 담고 동치 계산(CAS·재작성 규칙)은 l3 SymPy 단일
     권위가 한다(`math_dsl_evolution.md` §2.1 "SymPy 재구현 금지").
  ④ **dsl SymPy-parseable**: 정본 코퍼스의 전 수식 `dsl`이 `to_sympy_source`+`condition_dsl_
     violation`을 통과한다(검증가능·동치는 SymPy에 위임). data-pipeline은 sympy-free라 backend 몫.

hermetic: DB 불요(모델·enum import + 코퍼스 JSON 스캔·소스 AST 스캔 + l3 SymPy primitive).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from data_pipeline.concept_graph.models import RELATION_TYPES
from data_pipeline.formula_graph.models import FORMULA_ID_PATTERN
from data_pipeline.formula_graph.models import FormulaNode as PipelineFormulaNode

from whymath_backend.db.models.formula_node import FormulaNode as OrmFormulaNode
from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.l3.symbolic_equivalence import to_sympy_source
from whymath_backend.schema.enums import EdgeType

# 리포지토리 루트(tests/backend/l1/ 기준 3단 상위) → 코퍼스·소스 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORMULA_GRAPH = _REPO_ROOT / "data" / "corpus" / "formula_graph_v1" / "graph.json"

# FormulaNode 노드 모듈(③ sympy 미import 스캔 대상 — 정체성·참조 전용·동치는 l3).
_NODE_SOURCES = (
    _REPO_ROOT / "src" / "data-pipeline" / "data_pipeline" / "formula_graph" / "models.py",
    _REPO_ROOT / "src" / "backend" / "whymath_backend" / "db" / "models" / "formula_node.py",
    _REPO_ROOT
    / "src"
    / "backend"
    / "whymath_backend"
    / "l1"
    / "formula_graph"
    / "formula_node_projection.py",
)

# canonical-only 위반 — 변형/동치 열거 저장 필드(있으면 조합폭발·SymPy 위임 원칙 위반).
_FORBIDDEN_NODE_FIELDS = ("equivalence_class", "sympy_repr", "variant", "variants", "equivalents")


def _load_formulas() -> list[dict[str, object]]:
    return list(json.loads(_FORMULA_GRAPH.read_text(encoding="utf-8"))["formulas"])


# ── ① 신규 엣지 타입 0 ──────────────────────────────────────────────────────
def test_formula_adds_no_edge_type() -> None:
    """FormulaNode 도입이 EdgeType/Relation을 늘리지 않는다 — 수식 연결은 참조 키(5b)만.

    EdgeType(backend)·RELATION_TYPES(pipeline)는 Formula 승격과 무관하게 예산(5~8) 안에 머문다.
    """
    assert 5 <= len(EdgeType) <= 8
    assert 5 <= len(RELATION_TYPES) <= 8
    edge_tokens = {e.value.lower() for e in EdgeType} | {r.lower() for r in RELATION_TYPES}
    assert not any("formula" in tok for tok in edge_tokens)


def test_corpus_has_no_edge_array() -> None:
    """코퍼스에 별도 엣지 배열이 없다 — canonical 노드만(연결은 참조 키·Phase 5b)."""
    graph = json.loads(_FORMULA_GRAPH.read_text(encoding="utf-8"))
    assert "edges" not in graph


# ── ② canonical-only 불변식 ─────────────────────────────────────────────────
def test_node_has_no_variant_or_equivalence_field() -> None:
    """노드(파이프라인 모델·ORM)에 변형/동치 열거 필드가 없다 — canonical 1개만·동치는 SymPy."""
    pipeline_fields = set(PipelineFormulaNode.model_fields)
    orm_columns = {c.key for c in OrmFormulaNode.__table__.columns}
    for forbidden in _FORBIDDEN_NODE_FIELDS:
        assert forbidden not in pipeline_fields, forbidden
        assert forbidden not in orm_columns, forbidden


def test_formula_ids_follow_slug_space() -> None:
    """전 수식 formula_id가 `formula.<slug>` 공간(사람 관리 code·SymPy 계산값 아님)·유일."""
    formulas = _load_formulas()
    assert formulas, "formula 코퍼스가 비어있지 않아야 한다(스캔 무력화 방지)"
    ids = [str(f["formula_id"]) for f in formulas]
    assert len(ids) == len(set(ids)), "formula_id 중복(canonical 중복)"
    for fid in ids:
        assert FORMULA_ID_PATTERN.match(fid), fid


# ── ③ SymPy 재구현 금지 경계 (노드 모듈 sympy 미import) ─────────────────────
def _imports_sympy(tree: ast.Module) -> bool:
    """AST에서 `import sympy`/`from sympy ...`(하위 포함) 실제 import를 탐지."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "sympy" or a.name.startswith("sympy.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "sympy" or mod.startswith("sympy."):
                return True
    return False


def test_node_modules_do_not_import_sympy() -> None:
    """FormulaNode 노드 모듈이 sympy를 import하지 않는다 — 동치 권위는 l3 SymPy 단일(재구현 금지).

    노드는 수식의 정체성·참조만 담는다. CAS·재작성 규칙을 내장하면 위험문서 §2.1 "SymPy 재구현=즉사"
    경계를 넘는다. 이 스캔이 경계를 코드로 동결한다(동치 계산은 `l3/symbolic_equivalence`가 담당).
    """
    offenders: list[str] = []
    for path in _NODE_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_sympy(tree):
            offenders.append(path.name)
    assert (
        not offenders
    ), f"FormulaNode 노드 모듈이 sympy import(동치 권위 l3 단일 위반): {offenders}"


# ── ④ dsl SymPy-parseable (검증가능·동치는 SymPy 위임) ──────────────────────
def test_all_dsl_are_sympy_parseable() -> None:
    """전 수식 dsl이 `to_sympy_source`+`condition_dsl_violation`을 통과(닫힌 검증 DSL).

    dsl이 SymPy로 파싱돼야 런타임 동치 판정(변형↔canonical)이 가능하다 — canonical-only 실효성 보증.
    """
    bad: dict[str, str] = {}
    for node in _load_formulas():
        dsl = str(node["dsl"])
        violation = condition_dsl_violation(to_sympy_source(dsl))
        if violation is not None:
            bad[str(node["formula_id"])] = violation
    assert not bad, f"dsl SymPy-parseable 위반(동치 위임 불가): {bad}"
