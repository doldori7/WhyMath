"""concept_graph 그래프 검증 단위테스트 — §5 invariant 1:1 대응.

정본: docs/data/concept_graph.md §5 표.
"""

from __future__ import annotations

from data_pipeline.concept_graph.models import Concept, ConceptEdge
from data_pipeline.concept_graph.validate import validate_graph


def _concept(
    concept_id: str, *, standard_codes: list[str] | None = None, **over: object
) -> Concept:
    data: dict[str, object] = {
        "concept_id": concept_id,
        "name_ko": "개념",
        "name_en": "concept",
        "name_ja": "概念",
        "domain": "미적분",
        "standard_codes": standard_codes or [],
    }
    data.update(over)
    return Concept(**data)  # type: ignore[arg-type]


def _edge(src: str, dst: str, relation: str = "prerequisite", **over: object) -> ConceptEdge:
    data: dict[str, object] = {
        "src_concept_id": src,
        "dst_concept_id": dst,
        "relation": relation,
        "strength": 0.8,
        "evidence": "근거",
        "evidence_source": "ncic",
    }
    data.update(over)
    return ConceptEdge(**data)  # type: ignore[arg-type]


_A = "UC.calc.a01.g10n01"
_B = "UC.calc.a01.g10n02"
_C = "UC.calc.a01.g11n01"


def _rules(report: object) -> set[str]:
    return {i.rule for i in report.issues}  # type: ignore[attr-defined]


class TestCycle:
    def test_detects_prerequisite_cycle(self) -> None:
        """선수관계 순환 → error, success=False."""
        concepts = [_concept(_A), _concept(_B)]
        edges = [_edge(_A, _B), _edge(_B, _A)]
        report = validate_graph(concepts, edges)
        assert "prerequisite_cycle" in _rules(report)
        assert report.success is False
        assert len(report.errors) == 1

    def test_acyclic_graph_has_no_cycle_error(self) -> None:
        concepts = [_concept(_A), _concept(_B)]
        edges = [_edge(_A, _B)]
        report = validate_graph(concepts, edges)
        assert "prerequisite_cycle" not in _rules(report)
        assert report.success is True


class TestInversePair:
    def test_warns_generalization_specialization_inverse(self) -> None:
        """(A→B generalization) + (B→A specialization) → warning."""
        concepts = [_concept(_A), _concept(_B)]
        edges = [
            _edge(_A, _B, relation="generalization"),
            _edge(_B, _A, relation="specialization"),
        ]
        report = validate_graph(concepts, edges)
        assert "inverse_pair" in _rules(report)
        assert report.success is True  # warning이라 통과

    def test_no_inverse_when_only_one_direction(self) -> None:
        report = validate_graph(
            [_concept(_A), _concept(_B)], [_edge(_A, _B, relation="generalization")]
        )
        assert "inverse_pair" not in _rules(report)


class TestIsolatedNode:
    def test_warns_isolated_node(self) -> None:
        """엣지에 안 닿는 노드 → warning."""
        concepts = [_concept(_A), _concept(_B), _concept(_C)]
        edges = [_edge(_A, _B)]  # _C 고립
        report = validate_graph(concepts, edges)
        isolated = [i for i in report.issues if i.rule == "isolated_node"]
        assert len(isolated) == 1
        assert isolated[0].ref == _C


class TestDangling:
    def test_warns_dangling_edge_endpoint(self) -> None:
        """엣지가 노드 집합에 없는 끝점을 가리키면 warning."""
        report = validate_graph([_concept(_A)], [_edge(_A, _B)])  # _B 노드 없음
        assert "dangling_edge_endpoint" in _rules(report)
        assert report.success is True

    def test_warns_dangling_prerequisite_cache(self) -> None:
        report = validate_graph([_concept(_A, prerequisite_concept_ids=[_B])], [])
        assert "dangling_prerequisite_ref" in _rules(report)

    def test_warns_dangling_misconception_when_catalog_given(self) -> None:
        """known 카탈로그 주어지면 미수록 오개념 키 → warning."""
        concepts = [_concept(_A, misconception_codes=["unknown-mc"])]
        report = validate_graph(concepts, [], known_misconception_codes={"known-mc"})
        assert "dangling_misconception" in _rules(report)

    def test_skips_dangling_misconception_without_catalog(self) -> None:
        """known 미지정이면 검증 불가 → 건너뜀(경고 없음)."""
        concepts = [_concept(_A, misconception_codes=["whatever"])]
        report = validate_graph(concepts, [])
        assert "dangling_misconception" not in _rules(report)


class TestGradeMonotonic:
    def test_warns_when_prerequisite_grade_inverted(self) -> None:
        """선수개념(11학년)이 후행(10학년)보다 높은 학년 → warning."""
        senior = _concept(_C, standard_codes=["[11미적Ⅰ01-01]"])  # g11
        junior = _concept(_A, standard_codes=["[10공수1-01-01]"])  # g10
        edges = [_edge(_C, _A)]  # 11학년이 10학년의 선수 — 역전
        report = validate_graph([senior, junior], edges)
        assert "grade_monotonic" in _rules(report)

    def test_no_warning_when_grade_monotonic(self) -> None:
        junior = _concept(_A, standard_codes=["[10공수1-01-01]"])  # g10
        senior = _concept(_C, standard_codes=["[11미적Ⅰ01-01]"])  # g11
        edges = [_edge(_A, _C)]  # 10학년이 11학년의 선수 — 정상
        report = validate_graph([junior, senior], edges)
        assert "grade_monotonic" not in _rules(report)

    def test_skips_when_no_standard_codes(self) -> None:
        """standard_codes 없으면 학년 비교 건너뜀."""
        report = validate_graph([_concept(_A), _concept(_B)], [_edge(_A, _B)])
        assert "grade_monotonic" not in _rules(report)


class TestReport:
    def test_summary_counts(self) -> None:
        report = validate_graph([_concept(_A), _concept(_B)], [_edge(_A, _B)])
        assert "노드 2개" in report.summary()
        assert "엣지 1개" in report.summary()
