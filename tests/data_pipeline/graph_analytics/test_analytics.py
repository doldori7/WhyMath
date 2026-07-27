"""그래프 분석 코어 단위테스트 — ARCH-17 (hermetic·합성 미니 그래프).

합성 그래프(다이아몬드 + 체인)로 지표 정의를 못 박는다:

    A → B → D → E     (A: 하류 4 [B,C,D,E] · E: 하류 0)
    A → C → D         (D: in 2 · 다이아몬드 중복 도달은 1회만 센다)

오개념 전파는 체인 조인(concept_src_id → concept_id → atom_codes → 하류 합집합)과
해석 실패 skip 보고(침묵 금지)를 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.graph_analytics.analytics import (
    build_report,
    compute_misconception_impacts,
    compute_node_metrics,
    find_prerequisite_cycle,
    load_atom_dag,
)

_EDGES = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "E")]
_NAMES = {c: f"원자{c}" for c in "ABCDE"}


def _write_corpus(tmp_path: Path) -> dict[str, Path]:
    """합성 코퍼스 4파일 — 실 코퍼스와 같은 파일 형태(키·구조)."""
    atom_graph = tmp_path / "atom_graph.json"
    atom_graph.write_text(
        json.dumps(
            {
                "concepts": [{"code": c, "level": "세부개념", "name": _NAMES[c]} for c in "ABCDE"]
                + [{"code": "U1", "level": "단원", "name": "단원노드"}],
                "edges": [
                    {"from_code": f, "to_code": t, "relation": "prerequisite"} for f, t in _EDGES
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    concept_graph = tmp_path / "concept_graph.json"
    concept_graph.write_text(
        json.dumps(
            {
                "concepts": [
                    {"concept_id": "math.test.gaenyeom-a", "source_id": "N1"},
                    {"concept_id": "math.test.gaenyeom-d", "source_id": "N2"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    misconceptions = tmp_path / "misconceptions.json"
    misconceptions.write_text(
        json.dumps(
            {
                "misconceptions": [
                    {
                        "mis_id": "M0001",
                        "severity": "blocking",
                        "concept_src_id": "N1",
                        "canonical_statement": "A를 오해한다",
                    },
                    {
                        "mis_id": "M0002",
                        "severity": "blocking",
                        "concept_src_id": "N9",  # 미해석 — skip 보고 대상
                        "canonical_statement": "존재하지 않는 개념",
                    },
                    {
                        "mis_id": "M0003",
                        "severity": "local",  # blocking 아님 — 집계 제외
                        "concept_src_id": "N1",
                        "canonical_statement": "경미한 오해",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    crosswalk = tmp_path / "crosswalk.jsonl"
    crosswalk.write_text(
        "\n".join(
            [
                json.dumps({"concept_id": "math.test.gaenyeom-a", "atom_codes": ["A"]}),
                json.dumps({"concept_id": "math.test.gaenyeom-d", "atom_codes": []}),
            ]
        ),
        encoding="utf-8",
    )
    return {
        "atom_graph": atom_graph,
        "concept_graph": concept_graph,
        "misconceptions": misconceptions,
        "crosswalk": crosswalk,
    }


class TestNodeMetrics:
    def test_degrees_and_downstream_diamond(self) -> None:
        """다이아몬드 중복 도달은 1회만 — A 하류 4·D in 2·E 하류 0."""
        metrics = {m.code: m for m in compute_node_metrics(_NAMES, _EDGES)}
        assert metrics["A"].downstream_count == 4  # B, C, D, E — D는 두 경로여도 1회
        assert metrics["A"].out_degree == 2
        assert metrics["A"].in_degree == 0
        assert metrics["D"].in_degree == 2
        assert metrics["D"].downstream_count == 1  # E
        assert metrics["E"].downstream_count == 0

    def test_hub_ranking_order(self) -> None:
        """downstream desc → out_degree desc → code 사전순 결정론 정렬."""
        ranked = compute_node_metrics(_NAMES, _EDGES)
        assert ranked[0].code == "A"
        assert [m.code for m in ranked][-1] == "E"


class TestCycleDetection:
    def test_dag_returns_none(self) -> None:
        assert find_prerequisite_cycle(_EDGES) is None

    def test_cycle_detected(self) -> None:
        cycle = find_prerequisite_cycle([("A", "B"), ("B", "C"), ("C", "A")])
        assert cycle is not None
        assert cycle[0] == cycle[-1]  # 닫힘 노드 반복


class TestMisconceptionImpacts:
    def test_chain_join_and_skip_report(self, tmp_path: Path) -> None:
        """N1→A 체인 성공(하류 4), N9 미해석·crosswalk 미매핑은 skip으로 보고."""
        paths = _write_corpus(tmp_path)
        report = build_report(
            atom_graph=paths["atom_graph"],
            concept_graph=paths["concept_graph"],
            misconceptions=paths["misconceptions"],
            crosswalk=paths["crosswalk"],
        )
        assert report.atom_count == 5  # 단원 노드 제외
        assert report.edge_count == 5
        assert report.blocking_total == 2  # local 제외
        assert report.cycle is None and report.success
        assert len(report.impacts) == 1
        impact = report.impacts[0]
        assert impact.mis_id == "M0001"
        assert impact.concept_id == "math.test.gaenyeom-a"
        assert impact.blocked_downstream_count == 4
        # 해석 실패 보고(침묵 금지): N9 미해석 1건.
        assert len(report.skipped) == 1
        assert "M0002" in report.skipped[0]

    def test_multi_atom_union(self) -> None:
        """여러 원자에 걸친 오개념은 하류 합집합(중복 1회)."""
        impacts, skipped = compute_misconception_impacts(
            blocking_rows=[
                {"mis_id": "M1", "concept_src_id": "N1", "statement": "s"},
            ],
            source_id_map={"N1": "cid"},
            crosswalk={"cid": ["B", "C"]},
            names=_NAMES,
            edges=_EDGES,
        )
        assert skipped == []
        assert impacts[0].atom_count == 2
        assert impacts[0].blocked_downstream_count == 2  # D, E — 합집합


class TestLoadAtomDag:
    def test_filters_non_atoms_and_non_prerequisite(self, tmp_path: Path) -> None:
        graph = tmp_path / "g.json"
        graph.write_text(
            json.dumps(
                {
                    "concepts": [
                        {"code": "A", "level": "세부개념", "name": "a"},
                        {"code": "U", "level": "단원", "name": "u"},
                    ],
                    "edges": [
                        {"from_code": "A", "to_code": "B", "relation": "prerequisite"},
                        {"from_code": "A", "to_code": "C", "relation": "related_to"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        names, edges = load_atom_dag(graph)
        assert list(names) == ["A"]
        assert edges == [("A", "B")]  # 비-prerequisite 무시(방어)
