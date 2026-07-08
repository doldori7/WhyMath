"""formula_graph 실 코퍼스 검증 — 커밋된 `formulas.jsonl`·`graph.json` 무결성.

hermetic: 커밋된 코퍼스 파일만 읽는다(DB·네트워크 불요). CI가 코퍼스 회귀를 잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.formula_graph.models import FormulaNode
from data_pipeline.formula_graph.transform import transform_formulas
from data_pipeline.formula_graph.validate import validate_formulas

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "data" / "corpus" / "formula_graph_v1"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_formulas_jsonl_transforms_clean() -> None:
    """실 formulas.jsonl → 정형화 skip 0(전 행 유효)."""
    records = _read_jsonl(_CORPUS / "formulas.jsonl")
    result = transform_formulas(records)
    assert result.skipped == []
    assert len(result.formulas) == len(records)


def test_corpus_validates_pass() -> None:
    """실 코퍼스 그래프 검증 PASS(유일·error 0)."""
    result = transform_formulas(_read_jsonl(_CORPUS / "formulas.jsonl"))
    report = validate_formulas(result.formulas)
    assert report.success, report.report_text()
    assert report.errors == []


def test_graph_json_matches_source() -> None:
    """커밋된 graph.json이 formulas.jsonl 재정형화 산출과 일치(결정성·정합)."""
    result = transform_formulas(_read_jsonl(_CORPUS / "formulas.jsonl"))
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    committed = [FormulaNode(**r) for r in graph["formulas"]]
    assert [f.model_dump() for f in committed] == [f.model_dump() for f in result.formulas]


def test_graph_json_has_no_variant_or_edge_keys() -> None:
    """graph.json 수식 노드에 변형/동치 열거 키·엣지 배열 없음(canonical-only·참조 키만)."""
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    assert "edges" not in graph  # 연결은 참조 키(formula_refs·Phase 5b)·별도 엣지 배열 없음
    for node in graph["formulas"]:
        assert node["latex"] and node["dsl"]  # 필수 표현 존재
        for forbidden in ("equivalence_class", "sympy_repr", "variants", "prompt"):
            assert forbidden not in node
