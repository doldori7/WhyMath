"""atom_graph 모델 단위테스트 — AtomConcept · AtomEdge invariant.

정본: docs/data/atom_graph_v1.md(스키마·§3 redaction).
"""

from __future__ import annotations

import pytest
from data_pipeline.atom_graph.models import (
    ATOM_RELATIONS,
    COGNITIVE_TYPES,
    NODE_LEVELS,
    NODE_TYPES,
    SCHOOL_LEVELS,
    SOURCE_CITATION,
    AtomConcept,
    AtomEdge,
    AtomRelation,
    NodeLevel,
    SchoolLevel,
)
from pydantic import ValidationError


def _atom(**over: object) -> AtomConcept:
    data: dict[str, object] = {
        "code": "2수01-01-1",
        "name": "일대일 대응으로 세기",
        "name_display": "일대일 대응으로 세기",
        "level": "세부개념",
        "parent_code": "초수연-U1-S1",
        "school_level": "초등",
        "intrinsic_difficulty": 1,
        "standard_codes": ["[2수01-01]"],
    }
    data.update(over)
    return AtomConcept(**data)  # type: ignore[arg-type]


def _edge(**over: object) -> AtomEdge:
    data: dict[str, object] = {
        "from_code": "2수01-01-1",
        "to_code": "2수01-01-2",
        "relation": "prerequisite",
    }
    data.update(over)
    return AtomEdge(**data)  # type: ignore[arg-type]


class TestAtomConcept:
    def test_valid_instance(self) -> None:
        c = _atom()
        assert c.code == "2수01-01-1"
        assert c.level == NodeLevel.ATOM.value
        assert c.school_level == SchoolLevel.ELEMENTARY.value
        assert c.standard_codes == ["[2수01-01]"]
        assert c.atomicity == {}

    def test_rejects_empty_code(self) -> None:
        with pytest.raises(ValidationError):
            _atom(code="")

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            _atom(name="")

    def test_rejects_extra_field(self) -> None:
        """extra='forbid' — 미정의 필드 거부."""
        with pytest.raises(ValidationError):
            _atom(unknown="x")

    @pytest.mark.parametrize("redacted", ["description", "formal_definition"])
    def test_no_body_slot(self, redacted: str) -> None:
        """본문 슬롯 부재(구조 차단) — description/formal_definition는 extra='forbid' 거부."""
        with pytest.raises(ValidationError):
            _atom(**{redacted: "성취기준 본문 근접 복제"})

    @pytest.mark.parametrize("ok", [1, 3, 5])
    def test_difficulty_in_range(self, ok: int) -> None:
        assert _atom(intrinsic_difficulty=ok).intrinsic_difficulty == ok

    @pytest.mark.parametrize("bad", [0, 6, -1, 100])
    def test_difficulty_out_of_range_rejected(self, bad: int) -> None:
        with pytest.raises(ValidationError):
            _atom(intrinsic_difficulty=bad)

    @pytest.mark.parametrize("level", NODE_LEVELS)
    def test_accepts_all_levels(self, level: str) -> None:
        assert _atom(level=level).level == level

    def test_rejects_unknown_level(self) -> None:
        with pytest.raises(ValidationError):
            _atom(level="중간개념")

    @pytest.mark.parametrize("school", SCHOOL_LEVELS)
    def test_accepts_all_school_levels(self, school: str) -> None:
        """4축 — 대학 포함."""
        assert _atom(school_level=school).school_level == school

    def test_rejects_unknown_school_level(self) -> None:
        with pytest.raises(ValidationError):
            _atom(school_level="초등학교")  # 정규화 전 원본은 거부(transform이 정규화)

    @pytest.mark.parametrize("cog", COGNITIVE_TYPES)
    def test_accepts_cognitive_types(self, cog: str) -> None:
        assert _atom(cognitive_type=cog).cognitive_type == cog

    @pytest.mark.parametrize("nt", NODE_TYPES)
    def test_accepts_node_types(self, nt: str) -> None:
        assert _atom(node_type=nt).node_type == nt

    def test_standard_codes_reject_empty_item(self) -> None:
        with pytest.raises(ValidationError):
            _atom(standard_codes=["[2수01-01]", ""])

    def test_redacted_fields_reject_empty_item(self) -> None:
        with pytest.raises(ValidationError):
            _atom(redacted_fields=[""])

    def test_core_proposition_optional(self) -> None:
        """핵심명제 슬롯은 대학 자체작성 보존용 — 기본 None."""
        assert _atom().core_proposition is None
        c = _atom(school_level="대학", core_proposition="자체작성 명제")
        assert c.core_proposition == "자체작성 명제"

    def test_hierarchy_node_minimal(self) -> None:
        """단원/소단원 노드는 4요소·난이도 None·atomicity 빈 dict로 표현."""
        unit = AtomConcept(
            code="초수연-U1",
            name="수와 연산",
            level=NodeLevel.UNIT,  # type: ignore[arg-type]
            school_level=SchoolLevel.ELEMENTARY,  # type: ignore[arg-type]
        )
        assert unit.parent_code is None
        assert unit.intrinsic_difficulty is None
        assert unit.cognitive_type is None
        assert unit.atomicity == {}


class TestAtomEdge:
    def test_valid_instance(self) -> None:
        e = _edge()
        assert e.relation == AtomRelation.PREREQUISITE.value
        assert e.evidence  # 합성 기본값 비공백
        assert 0.0 <= e.strength <= 1.0

    def test_rejects_empty_endpoints(self) -> None:
        with pytest.raises(ValidationError):
            _edge(from_code="")
        with pytest.raises(ValidationError):
            _edge(to_code="")

    def test_rejects_unknown_relation(self) -> None:
        with pytest.raises(ValidationError):
            _edge(relation="일반화")

    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0])
    def test_rejects_strength_out_of_range(self, bad: float) -> None:
        with pytest.raises(ValidationError):
            _edge(strength=bad)

    def test_rejects_empty_evidence(self) -> None:
        with pytest.raises(ValidationError):
            _edge(evidence="")

    def test_relation_subtype_and_school_link(self) -> None:
        e = _edge(relation_subtype="소단원내", school_link=True)
        assert e.relation_subtype == "소단원내"
        assert e.school_link is True

    def test_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            _edge(unknown="x")


class TestConstants:
    def test_atom_relations_match_enum(self) -> None:
        assert ATOM_RELATIONS == tuple(r.value for r in AtomRelation)

    def test_levels_school_cognitive_nodetypes(self) -> None:
        assert set(NODE_LEVELS) == {"단원", "소단원", "세부개념"}
        assert set(SCHOOL_LEVELS) == {"초등", "중학", "고등", "대학"}
        assert set(COGNITIVE_TYPES) == {"개념", "절차", "표상"}
        assert set(NODE_TYPES) == {"선행", "구성", "결과"}

    def test_source_citation_mentions_ncic(self) -> None:
        assert "NCIC" in SOURCE_CITATION
        assert "2022-33" in SOURCE_CITATION
