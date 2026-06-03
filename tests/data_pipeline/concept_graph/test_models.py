"""concept_graph 모델 단위테스트 — Concept · ConceptEdge invariant.

정본 검증 invariant: docs/data/concept_graph.md §5 + schemas/v1.1/{concept,edge}.schema.yaml.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.concept_graph.models import (
    EVIDENCE_SOURCES,
    RELATION_TYPES,
    SOURCE_CITATION,
    Concept,
    ConceptEdge,
    EvidenceSource,
    Relation,
)


def _concept(**overrides: object) -> Concept:
    data: dict[str, object] = {
        "concept_id": "UC.calc.limit.epsilon-delta",
        "name_ko": "엡실론-델타 극한 정의",
        "name_en": "epsilon-delta definition of limit",
        "name_ja": "イプシロン・デルタ論法",
        "domain": "미적분",
    }
    data.update(overrides)
    return Concept(**data)  # type: ignore[arg-type]


def _edge(**overrides: object) -> ConceptEdge:
    data: dict[str, object] = {
        "src_concept_id": "UC.calc.limit.definition",
        "dst_concept_id": "UC.calc.deriv.definition",
        "relation": "prerequisite",
        "strength": 0.9,
        "evidence": "NCIC 성취기준 학년 인접 + 수학교육 문헌",
        "evidence_source": "ncic",
    }
    data.update(overrides)
    return ConceptEdge(**data)  # type: ignore[arg-type]


class TestConcept:
    def test_valid_instance(self) -> None:
        """유효 인스턴스 생성 + 기본값(빈 리스트)."""
        c = _concept()
        assert c.concept_id == "UC.calc.limit.epsilon-delta"
        assert c.prerequisite_concept_ids == []
        assert c.standard_codes == []

    @pytest.mark.parametrize(
        "good_id",
        [
            "UC.calc.limit.epsilon-delta",
            "UC.calc.deriv.definition",
            "UC.alg.poly.factor-theorem",
        ],
    )
    def test_accepts_valid_concept_id(self, good_id: str) -> None:
        """UC 규약(§2.4)을 지키는 ID는 통과."""
        assert _concept(concept_id=good_id).concept_id == good_id

    @pytest.mark.parametrize(
        "bad_id",
        [
            "calc.limit.def",  # UC 접두사 없음
            "UC.calc.limit",  # 파트 부족(3 only)
            "UC.calc.limit.def.extra",  # 파트 초과
            "UC.CALC.limit.def",  # 대문자
            "UC.calc.limit.엡실론",  # 비ASCII slug
            "UC..limit.def",  # 빈 domain
        ],
    )
    def test_rejects_malformed_concept_id(self, bad_id: str) -> None:
        """UC 규약 위반 ID는 ValidationError."""
        with pytest.raises(ValidationError):
            _concept(concept_id=bad_id)

    @pytest.mark.parametrize("field", ["name_ko", "name_en", "name_ja"])
    def test_rejects_empty_multilingual_name(self, field: str) -> None:
        """name_ko/en/ja 중 하나라도 비면 거부(다국 정합성 키)."""
        with pytest.raises(ValidationError):
            _concept(**{field: ""})

    @pytest.mark.parametrize("field", ["name_ko", "name_en", "name_ja"])
    def test_rejects_whitespace_only_name(self, field: str) -> None:
        """공백만 있는 이름은 strip 후 빈 문자열 → 거부."""
        with pytest.raises(ValidationError):
            _concept(**{field: "   "})

    def test_rejects_extra_field(self) -> None:
        """extra='forbid' — 미정의 필드 거부."""
        with pytest.raises(ValidationError):
            _concept(unknown_field="x")

    def test_standard_codes_holds_only_codes(self) -> None:
        """standard_codes는 NCIC 코드 참조만(본문 복제 아님)."""
        c = _concept(standard_codes=["[10공수1-05-02]"])
        assert c.standard_codes == ["[10공수1-05-02]"]


class TestConceptEdge:
    def test_valid_instance(self) -> None:
        e = _edge()
        assert e.relation == Relation.PREREQUISITE
        assert e.evidence_source == EvidenceSource.NCIC

    @pytest.mark.parametrize("rel", list(RELATION_TYPES))
    def test_accepts_all_relation_types(self, rel: str) -> None:
        """7종 관계 enum 모두 허용."""
        assert _edge(relation=rel).relation == rel

    def test_rejects_unknown_relation(self) -> None:
        """6/7종 밖 관계는 ValidationError."""
        with pytest.raises(ValidationError):
            _edge(relation="nonsense")

    @pytest.mark.parametrize("src", EVIDENCE_SOURCES)
    def test_accepts_all_evidence_sources(self, src: str) -> None:
        assert _edge(evidence_source=src).evidence_source == src

    def test_rejects_unknown_evidence_source(self) -> None:
        with pytest.raises(ValidationError):
            _edge(evidence_source="hearsay")

    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
    def test_rejects_strength_out_of_range(self, bad: float) -> None:
        """strength ∉ [0.0, 1.0] 거부."""
        with pytest.raises(ValidationError):
            _edge(strength=bad)

    @pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
    def test_accepts_strength_bounds(self, ok: float) -> None:
        assert _edge(strength=ok).strength == ok

    def test_rejects_empty_evidence(self) -> None:
        """evidence 빈 문자열 거부(근거 없는 엣지 차단)."""
        with pytest.raises(ValidationError):
            _edge(evidence="")

    def test_rejects_whitespace_only_evidence(self) -> None:
        """공백만 있는 evidence는 strip 후 빈 문자열 → 거부."""
        with pytest.raises(ValidationError):
            _edge(evidence="   ")

    def test_rejects_malformed_endpoint_id(self) -> None:
        """src/dst도 UC 규약 강제(노드와 동일 키 공간)."""
        with pytest.raises(ValidationError):
            _edge(src_concept_id="not-a-uc-id")


class TestConstants:
    def test_relation_types_match_enum(self) -> None:
        """RELATION_TYPES는 Relation enum 값과 1:1(단일 진실)."""
        assert RELATION_TYPES == tuple(r.value for r in Relation)
        assert "notation_variant" in RELATION_TYPES
        assert len(RELATION_TYPES) == 7

    def test_evidence_sources_match_enum(self) -> None:
        assert EVIDENCE_SOURCES == tuple(e.value for e in EvidenceSource)

    def test_source_citation_mentions_ncic(self) -> None:
        """승계 출처 문구에 NCIC·교육부 고시 명시(공공누리 1유형)."""
        assert "NCIC" in SOURCE_CITATION
        assert "2022-33" in SOURCE_CITATION
