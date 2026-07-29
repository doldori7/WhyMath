"""거버넌스 동결 — ProblemTypeNode (리치 Part 2 Phase 3·2026-07-07).

ProblemType 1급 승격(ADR concept_node_layering_decision.md)이 CLAUDE.md 금기 안에서 사는지 동결한다:

  ① **신규 엣지 타입 0**: ProblemTypeNode 도입이 EdgeType/Relation을 늘리지 않는다 — 유형 연결은
     참조 키(`behavior_skills`)만(anti-explosion).
  ② **ProblemType ≠ SignaturePattern 구별 불변식**: cognitive-action 노드는 표면 패턴을
     재인코딩하지 않는다 — (a) 노드에 surface 필드 부재, (b) 파이프라인/프로젝션이 SignaturePattern
     미import, (c) `ptype.<slug>` id 공간이 SignaturePattern 값(UPPER_SNAKE)과 disjoint.
  ③ **cross-corpus 링크(dangling 0)**: 정본 코퍼스의 전 유형 `behavior_skills`가 skill_graph_v1
     skill_id에 실재하고(dangling 0), 유형당 ≥1 스킬을 참조(cognitive-action 표현 보장).

hermetic: DB 불요(enum·모델 import + 코퍼스 JSON 스캔·소스 텍스트 스캔만).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from data_pipeline.concept_graph.models import RELATION_TYPES
from data_pipeline.problem_type_graph.models import (
    PROBLEM_TYPE_ID_PATTERN,
)
from data_pipeline.problem_type_graph.models import (
    ProblemTypeNode as PipelineProblemTypeNode,
)
from whymath_backend.db.models.problem_type_node import ProblemTypeNode as OrmProblemTypeNode
from whymath_backend.schema.enums import EdgeType, SignaturePattern

# 리포지토리 루트(tests/backend/l1/ 기준 3단 상위) → 코퍼스 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_GRAPH = _REPO_ROOT / "data" / "corpus" / "skill_graph_v1" / "graph.json"
_PTYPE_GRAPH = _REPO_ROOT / "data" / "corpus" / "problem_type_graph_v1" / "graph.json"

# 파이프라인·프로젝션 소스(② SignaturePattern import 부재 스캔 대상).
_SCAN_SOURCES = (
    _REPO_ROOT / "src" / "data-pipeline" / "data_pipeline" / "problem_type_graph" / "models.py",
    _REPO_ROOT / "src" / "backend" / "whymath_backend" / "db" / "models" / "problem_type_node.py",
    _REPO_ROOT
    / "src"
    / "backend"
    / "whymath_backend"
    / "l1"
    / "problem_type_graph"
    / "problem_type_node_projection.py",
)


def _load_problem_types() -> list[dict[str, object]]:
    return list(json.loads(_PTYPE_GRAPH.read_text(encoding="utf-8"))["problem_types"])


# ── ① 신규 엣지 타입 0 ──────────────────────────────────────────────────────
def test_problemtype_adds_no_edge_type() -> None:
    """ProblemTypeNode 도입이 EdgeType/Relation을 늘리지 않는다 — 유형 연결은 참조 키만.

    EdgeType(backend)·RELATION_TYPES(pipeline)는 ProblemType 승격과 무관하게 예산(5~8) 안에 머문다.
    """
    assert 5 <= len(EdgeType) <= 8
    assert 5 <= len(RELATION_TYPES) <= 8
    # 문제유형 관련 엣지 타입 토큰이 EdgeType/Relation에 유입되지 않았다(참조 키로만 연결).
    edge_tokens = {e.value.lower() for e in EdgeType} | {r.lower() for r in RELATION_TYPES}
    assert not any("problemtype" in tok or "ptype" in tok for tok in edge_tokens)


# ── ② ProblemType ≠ SignaturePattern 구별 불변식 ────────────────────────────
def test_node_has_no_surface_field() -> None:
    """노드(파이프라인 모델·ORM)에 표면(SignaturePattern) 필드가 없다 — cognitive-action만."""
    pipeline_fields = set(PipelineProblemTypeNode.model_fields)
    orm_columns = {c.key for c in OrmProblemTypeNode.__table__.columns}
    for surface in ("signature_pattern", "signature_patterns", "surface", "surface_pattern"):
        assert surface not in pipeline_fields, surface
        assert surface not in orm_columns, surface


def _signature_pattern_references(tree: ast.Module) -> set[str]:
    """AST에서 `SignaturePattern`의 *실제* import/식별자 참조를 수집(docstring·주석·문자열 제외).

    docstring이 구별 불변식을 *설명*하며 "SignaturePattern"을 언급하는 것은 정당하다(표면 축 혼입
    아님) — Constant(문자열)는 잡지 않고, import·Name·Attribute만 잡는다(test_legacy_snapshot_
    governance 패턴).
    """
    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "SignaturePattern":
                    hits.add(f"import:{alias.name}")
        elif isinstance(node, ast.Name) and node.id == "SignaturePattern":
            hits.add(f"name:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr == "SignaturePattern":
            hits.add(f"attr:{node.attr}")
    return hits


def test_no_signature_pattern_import_in_node_sources() -> None:
    """파이프라인 모델·프로젝션이 `SignaturePattern`을 import·참조하지 않는다(표면 축과 분리).

    AST 기준(docstring prose의 언급은 허용) — 실제 import·식별자 참조만 red.
    """
    violations: dict[str, set[str]] = {}
    for path in _SCAN_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        refs = _signature_pattern_references(tree)
        if refs:
            violations[path.name] = refs
    assert not violations, f"SignaturePattern 실제 참조(표면 축 혼입): {violations}"


def test_ptype_ids_disjoint_from_signature_pattern_values() -> None:
    """`ptype.<slug>` id 공간이 SignaturePattern 값(UPPER_SNAKE)과 disjoint(분리 불변식)."""
    ptype_ids = {p["problem_type_id"] for p in _load_problem_types()}
    signature_values = {s.value for s in SignaturePattern}
    assert ptype_ids.isdisjoint(signature_values)
    # 형식도 구조적으로 분리(전부 ptype.<slug>·소문자 vs SignaturePattern UPPER_SNAKE).
    for pid in ptype_ids:
        assert PROBLEM_TYPE_ID_PATTERN.match(str(pid))
        assert pid not in signature_values


# ── ③ cross-corpus 링크(dangling 0) ────────────────────────────────────────
def test_behavior_skills_reference_existing_skills() -> None:
    """전 유형의 behavior_skills가 skill_graph_v1 skill_id에 실재(dangling 0)·유형당 ≥1개."""
    skill_ids = {
        s["skill_id"] for s in json.loads(_SKILL_GRAPH.read_text(encoding="utf-8"))["skills"]
    }
    problem_types = _load_problem_types()
    assert problem_types, "problem_type 코퍼스가 비어있지 않아야 한다(스캔 무력화 방지)"
    dangling: dict[str, list[str]] = {}
    for node in problem_types:
        refs = list(node["behavior_skills"])  # type: ignore[arg-type]
        assert refs, f"{node['problem_type_id']}: behavior_skills가 비어있음(≥1 계약 위반)"
        missing = [r for r in refs if r not in skill_ids]
        if missing:
            dangling[str(node["problem_type_id"])] = missing
    assert not dangling, f"cross-corpus dangling — skill_graph_v1에 없는 참조: {dangling}"
