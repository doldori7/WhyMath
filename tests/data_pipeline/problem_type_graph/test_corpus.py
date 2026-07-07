"""problem_type_graph 실 코퍼스 검증 — 커밋된 `problem_types.jsonl`·`graph.json` 무결성.

hermetic: 커밋된 코퍼스 파일만 읽는다(DB·네트워크 불요). CI가 코퍼스 회귀를 잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.problem_type_graph.models import ProblemTypeNode
from data_pipeline.problem_type_graph.transform import transform_problem_types
from data_pipeline.problem_type_graph.validate import validate_problem_types

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "data" / "corpus" / "problem_type_graph_v1"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_problem_types_jsonl_transforms_clean() -> None:
    """실 problem_types.jsonl → 정형화 skip 0(전 행 유효)."""
    records = _read_jsonl(_CORPUS / "problem_types.jsonl")
    result = transform_problem_types(records)
    assert result.skipped == []
    assert len(result.problem_types) == len(records)


def test_corpus_validates_pass() -> None:
    """실 코퍼스 그래프 검증 PASS(유일·≥1 skill·error 0)."""
    result = transform_problem_types(_read_jsonl(_CORPUS / "problem_types.jsonl"))
    report = validate_problem_types(result.problem_types)
    assert report.success, report.report_text()
    assert report.errors == []


def test_graph_json_matches_source() -> None:
    """커밋된 graph.json이 problem_types.jsonl 재정형화 산출과 일치(결정성·정합)."""
    result = transform_problem_types(_read_jsonl(_CORPUS / "problem_types.jsonl"))
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    committed = [ProblemTypeNode(**r) for r in graph["problem_types"]]
    assert [p.model_dump() for p in committed] == [p.model_dump() for p in result.problem_types]


def test_graph_json_has_no_surface_body_or_edge_keys() -> None:
    """graph.json 유형 노드에 표면·본문 키·엣지 배열 없음(참조 키만·신규 엣지 타입 0)."""
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    assert "edges" not in graph  # 연결은 노드 내장 참조 키(별도 엣지 배열 없음)
    for node in graph["problem_types"]:
        assert node["behavior_skills"]  # ≥1 스킬 참조
        for forbidden in ("signature_pattern", "signature_patterns", "formal_definition", "prompt"):
            assert forbidden not in node
