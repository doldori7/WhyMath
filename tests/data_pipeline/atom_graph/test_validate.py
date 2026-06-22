"""atom_graph 그래프 검증 단위테스트 — invariant별 위반 탐지(인위적 픽스처).

정본: docs/data/atom_graph_v1.md + 마이그레이션 플랜 Phase 1.
"""

from __future__ import annotations

from data_pipeline.atom_graph.models import (
    AtomConcept,
    AtomEdge,
    NodeLevel,
    SchoolLevel,
)
from data_pipeline.atom_graph.transform import transform_dataset
from data_pipeline.atom_graph.validate import validate_dataset, validate_graph


def _atom(code: str, **over: object) -> AtomConcept:
    data: dict[str, object] = {
        "code": code,
        "name": f"원자 {code}",
        "level": NodeLevel.ATOM.value,
        "school_level": SchoolLevel.ELEMENTARY.value,
    }
    data.update(over)
    return AtomConcept(**data)  # type: ignore[arg-type]


def _node(code: str, level: str, **over: object) -> AtomConcept:
    data: dict[str, object] = {
        "code": code,
        "name": f"노드 {code}",
        "level": level,
        "school_level": SchoolLevel.ELEMENTARY.value,
    }
    data.update(over)
    return AtomConcept(**data)  # type: ignore[arg-type]


def _edge(frm: str, to: str, **over: object) -> AtomEdge:
    data: dict[str, object] = {"from_code": frm, "to_code": to}
    data.update(over)
    return AtomEdge(**data)  # type: ignore[arg-type]


def _rules(report: object) -> set[str]:
    return {i.rule for i in report.issues}  # type: ignore[attr-defined]


_A, _B, _C = "A-1", "A-2", "A-3"


class TestCycle:
    def test_detects_prerequisite_cycle(self) -> None:
        """선수관계 순환 → error(하드에러)·success=False."""
        atoms = [_atom(_A), _atom(_B)]
        edges = [_edge(_A, _B), _edge(_B, _A)]
        report = validate_graph(atoms, edges)
        assert "prerequisite_cycle" in _rules(report)
        assert report.success is False

    def test_detects_longer_cycle(self) -> None:
        atoms = [_atom(_A), _atom(_B), _atom(_C)]
        edges = [_edge(_A, _B), _edge(_B, _C), _edge(_C, _A)]
        report = validate_graph(atoms, edges)
        assert "prerequisite_cycle" in _rules(report)

    def test_acyclic_passes(self) -> None:
        atoms = [_atom(_A), _atom(_B), _atom(_C)]
        edges = [_edge(_A, _B), _edge(_B, _C)]
        report = validate_graph(atoms, edges)
        assert "prerequisite_cycle" not in _rules(report)
        assert report.success is True


class TestAtomIdUnique:
    def test_detects_duplicate_atom_id(self) -> None:
        report = validate_graph([_atom(_A), _atom(_A)], [])
        assert "atom_id_unique" in _rules(report)
        assert report.success is False

    def test_unique_passes(self) -> None:
        report = validate_graph([_atom(_A), _atom(_B)], [])
        assert "atom_id_unique" not in _rules(report)


class TestDanglingEdge:
    def test_detects_dangling_endpoint(self) -> None:
        """엣지가 원자 노드에 없는 끝점을 가리키면 error."""
        report = validate_graph([_atom(_A)], [_edge(_A, _B)])  # _B 없음
        assert "dangling_edge_endpoint" in _rules(report)
        assert report.success is False

    def test_clean_endpoints_pass(self) -> None:
        report = validate_graph([_atom(_A), _atom(_B)], [_edge(_A, _B)])
        assert "dangling_edge_endpoint" not in _rules(report)


class TestParentExists:
    def test_detects_missing_parent(self) -> None:
        report = validate_graph([_atom(_A, parent_code="초수연-U1-S9")], [])
        assert "parent_exists" in _rules(report)
        assert report.success is False

    def test_parent_present_passes(self) -> None:
        sub = _node("초수연-U1-S1", NodeLevel.SUBUNIT.value)
        atom = _atom(_A, parent_code="초수연-U1-S1")
        report = validate_graph([atom, sub], [])
        assert "parent_exists" not in _rules(report)


class TestSubunitNameConsistency:
    def test_detects_inconsistent_name(self) -> None:
        """같은 소단원코드에 다른 소단원명 → error."""
        a1 = _atom(_A, subunit_code="초수연-U1-S1", subunit="세기")
        a2 = _atom(_B, subunit_code="초수연-U1-S1", subunit="다른이름")
        report = validate_graph([a1, a2], [])
        assert "subunit_name_consistency" in _rules(report)
        assert report.success is False

    def test_consistent_name_passes(self) -> None:
        a1 = _atom(_A, subunit_code="초수연-U1-S1", subunit="세기")
        a2 = _atom(_B, subunit_code="초수연-U1-S1", subunit="세기")
        report = validate_graph([a1, a2], [])
        assert "subunit_name_consistency" not in _rules(report)


class TestStandardExists:
    def test_warns_missing_standard(self) -> None:
        """standard_codes가 known 집합에 없으면 warning(에러 아님)."""
        atom = _atom(_A, standard_codes=["[99수99-99]"])
        report = validate_graph([atom], [], known_standard_codes={"[2수01-01]"})
        assert "standard_exists" in _rules(report)
        assert report.success is True  # warning이라 통과

    def test_present_standard_passes(self) -> None:
        atom = _atom(_A, standard_codes=["[2수01-01]"])
        report = validate_graph([atom], [], known_standard_codes={"[2수01-01]"})
        assert "standard_exists" not in _rules(report)

    def test_skips_when_no_catalog(self) -> None:
        atom = _atom(_A, standard_codes=["[99수99-99]"])
        report = validate_graph([atom], [])  # known 미지정 → skip
        assert "standard_exists" not in _rules(report)


class TestReport:
    def test_summary_pass(self) -> None:
        report = validate_graph([_atom(_A), _atom(_B)], [_edge(_A, _B)])
        assert "PASS" in report.summary()
        assert "노드 2개" in report.summary()

    def test_summary_fail_on_cycle(self) -> None:
        report = validate_graph([_atom(_A), _atom(_B)], [_edge(_A, _B), _edge(_B, _A)])
        assert "FAIL" in report.summary()

    def test_report_text_lists_rules(self) -> None:
        report = validate_graph([_atom(_A)], [_edge(_A, _B)])
        text = report.report_text()
        assert "dangling_edge_endpoint" in text
        assert "rule별 집계" in text

    def test_counts_by_rule(self) -> None:
        report = validate_graph([_atom(_A), _atom(_A)], [])
        assert report.counts_by_rule().get("atom_id_unique") == 1


class TestValidateDataset:
    def test_wraps_transform_result(self, make_atom_row) -> None:  # type: ignore[no-untyped-def]
        atoms = [
            make_atom_row(원자ID="2수01-01-1"),
            make_atom_row(원자ID="2수01-01-2", 원자명="기수 원리"),
        ]
        edge = {
            "from(선수)": "2수01-01-1",
            "to(후행)": "2수01-01-2",
            "from_유형": "원자ID",
            "관계유형": "소단원내",
        }
        result = transform_dataset(atom_rows=atoms, edge_rows=[edge])
        report = validate_dataset(result, known_standard_codes={"[2수01-01]"})
        assert report.success is True
        assert report.edge_count == 1
