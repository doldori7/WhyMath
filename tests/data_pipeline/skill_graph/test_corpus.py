"""skill_graph 실 코퍼스 검증 — 커밋된 `skills.jsonl`·`graph.json` 무결성.

hermetic: 커밋된 코퍼스 파일만 읽는다(DB·네트워크 불요). CI가 코퍼스 회귀를 잡는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.skill_graph.models import BEHAVIOR_AREAS, SkillNode
from data_pipeline.skill_graph.transform import transform_skills
from data_pipeline.skill_graph.validate import validate_skills

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "data" / "corpus" / "skill_graph_v1"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_skills_jsonl_transforms_clean() -> None:
    """실 skills.jsonl → 정형화 skip 0(전 행 유효)."""
    records = _read_jsonl(_CORPUS / "skills.jsonl")
    result = transform_skills(records)
    assert result.skipped == []
    assert len(result.skills) == len(records)


def test_corpus_validates_pass() -> None:
    """실 코퍼스 그래프 검증 PASS(유일·비순환 선수·error 0)."""
    result = transform_skills(_read_jsonl(_CORPUS / "skills.jsonl"))
    report = validate_skills(result.skills)
    assert report.success, report.report_text()
    assert report.errors == []


def test_corpus_covers_all_six_behavior_areas() -> None:
    """v1 코퍼스가 6종 행동영역을 모두 커버(coverage warning 0)."""
    result = transform_skills(_read_jsonl(_CORPUS / "skills.jsonl"))
    present = {s.behavior_area for s in result.skills}
    assert present == set(BEHAVIOR_AREAS)


def test_graph_json_matches_source() -> None:
    """커밋된 graph.json이 skills.jsonl 재정형화 산출과 일치(결정성·정합)."""
    result = transform_skills(_read_jsonl(_CORPUS / "skills.jsonl"))
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    committed = [SkillNode(**r) for r in graph["skills"]]
    assert [s.model_dump() for s in committed] == [s.model_dump() for s in result.skills]


def test_graph_json_has_no_body_or_edge_keys() -> None:
    """graph.json 스킬 노드에 본문 키·엣지 배열 없음(참조 키만·신규 엣지 타입 0)."""
    graph = json.loads((_CORPUS / "graph.json").read_text(encoding="utf-8"))
    assert "edges" not in graph  # 선수는 노드 내장 참조 키(별도 엣지 배열 없음)
    for skill in graph["skills"]:
        for forbidden in ("misconception_text", "formal_definition", "prompt"):
            assert forbidden not in skill
