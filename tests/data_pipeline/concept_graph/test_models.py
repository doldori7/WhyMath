"""concept_graph 모델 단위테스트 — Concept · ConceptEdge invariant.

정본 검증 invariant: docs/data/concept_graph.md §5 + schemas/v1.1/{concept,edge}.schema.yaml.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.concept_graph.models import (
    CONCEPT_ID_PATTERN,
    EVIDENCE_SOURCES,
    LEGACY_UC_PATTERN,
    RELATION_TYPES,
    REVIEW_STATUSES,
    SOURCE_CITATION,
    Concept,
    ConceptEdge,
    EvidenceSource,
    Relation,
    ReviewStatus,
)


def _concept(**overrides: object) -> Concept:
    # 표시이름(name_*)은 노드 비내장(P2d Concept Purity) — 인자에 없다. concept_id는 canonical
    # (math.<area>.<slug>). aliases는 [교육과정축 코드, 옛 UC, src_id](비공백만 강제).
    data: dict[str, object] = {
        "concept_id": "math.calculus.epsilon-delta-geukhan",
        "source_id": "H:12미적Ⅰ01-01",
        "aliases": ["HIGH-CALC-001", "UC.calc1.a01.h-12-01-01", "H:12미적Ⅰ01-01"],
        "domain": "미적분",
    }
    data.update(overrides)
    return Concept(**data)  # type: ignore[arg-type]


def _edge(**overrides: object) -> ConceptEdge:
    data: dict[str, object] = {
        "src_concept_id": "math.calculus.geukhanui-jeongui",
        "dst_concept_id": "math.calculus.misibun",
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
        assert c.concept_id == "math.calculus.epsilon-delta-geukhan"
        assert c.source_id == "H:12미적Ⅰ01-01"
        assert c.aliases == [
            "HIGH-CALC-001",
            "UC.calc1.a01.h-12-01-01",
            "H:12미적Ⅰ01-01",
        ]
        assert c.prerequisite_concept_ids == []
        assert c.standard_codes == []

    @pytest.mark.parametrize(
        "good_id",
        [
            "math.geometry.samgakhyeong",
            "math.calculus.geukhan",
            "math.place-value.su-gaenyeom",  # 하이픈 포함 영역어
            "math.equation.ilchabangjeongsik-2",  # 충돌 접미
            "math.arithmetic.a01",  # slug에 숫자 허용
        ],
    )
    def test_accepts_valid_concept_id(self, good_id: str) -> None:
        """canonical 규약(`math.<area>.<slug>`)을 지키는 ID는 통과(하이픈 영역어·충돌 접미 포함)."""
        assert _concept(concept_id=good_id).concept_id == good_id

    @pytest.mark.parametrize(
        "bad_id",
        [
            "UC.calc.limit.epsilon-delta",  # 옛 UC 형식 거부
            "ELEM-GEO-001",  # 옛 교육과정축 코드(P2a) 거부 — 이제 별칭일 뿐
            "MATH.geometry.x",  # subject 대문자
            "math.Geometry.x",  # AREA 대문자
            "math.geometry.삼각형",  # slug 비-ASCII
            "math.geometry",  # slug 세그먼트 누락
            "math.geometry.",  # slug 비어있음
            "math..x",  # AREA 비어있음
            "geometry.x",  # math 접두 누락
        ],
    )
    def test_rejects_malformed_concept_id(self, bad_id: str) -> None:
        """canonical 규약 위반 ID는 ValidationError."""
        with pytest.raises(ValidationError):
            _concept(concept_id=bad_id)

    def test_concept_id_pattern_matches_examples(self) -> None:
        """CONCEPT_ID_PATTERN이 canonical만·LEGACY_UC_PATTERN이 옛 UC만 매칭(분리 확인)."""
        assert CONCEPT_ID_PATTERN.match("math.geometry.samgakhyeong")
        assert not CONCEPT_ID_PATTERN.match("UC.calc.limit.def")
        assert not CONCEPT_ID_PATTERN.match("ELEM-GEO-001")  # 옛 축코드는 canonical 아님
        assert LEGACY_UC_PATTERN.match("UC.calc.limit.def")
        assert not LEGACY_UC_PATTERN.match("math.geometry.samgakhyeong")

    def test_display_names_not_model_fields(self) -> None:
        """표시이름(name_ko/en/ja)은 노드 필드가 아니다(P2d Concept Purity·locale 분리)."""
        assert "name_ko" not in Concept.model_fields
        assert "name_en" not in Concept.model_fields
        assert "name_ja" not in Concept.model_fields

    def test_rejects_name_field_as_extra(self) -> None:
        """name_* 인자는 extra='forbid'로 거부(노드에 표시이름 슬롯 없음)."""
        with pytest.raises(ValidationError):
            _concept(name_ko="극한")

    def test_source_id_required_and_nonempty(self) -> None:
        """source_id는 필수·비공백(원천 추적 키)."""
        with pytest.raises(ValidationError):
            _concept(source_id="")
        with pytest.raises(ValidationError):
            _concept(source_id="   ")

    def test_aliases_default_empty(self) -> None:
        """aliases는 선택(기본 빈 목록)."""
        c = Concept(
            concept_id="math.calculus.geukhan",  # type: ignore[call-arg]
            source_id="H:12미적Ⅰ01-01",
            domain="미적분",
        )
        assert c.aliases == []

    def test_aliases_reject_empty_string(self) -> None:
        """별칭에 빈 문자열 금지(추적성 키 누락 차단)."""
        with pytest.raises(ValidationError):
            _concept(aliases=["UC.calc1.a01.x", ""])

    def test_rejects_extra_field(self) -> None:
        """extra='forbid' — 미정의 필드 거부."""
        with pytest.raises(ValidationError):
            _concept(unknown_field="x")

    def test_standard_codes_holds_only_codes(self) -> None:
        """standard_codes는 NCIC 코드 참조만(본문 복제 아님)."""
        c = _concept(standard_codes=["[10공수1-05-02]"])
        assert c.standard_codes == ["[10공수1-05-02]"]


class TestConceptEnrichedFields:
    """데이터셋 v1 풍부 필드 — ccss_code·difficulty_tier·review_status + 리치 9계층 semantic
    (intuition·representations·core_meaning).

    ※ 2026-07-03 Part 2 전면 채택 Phase 1: 은유·허용표현은 리치 기준 semantic이라 노드로 *복원*
    (intuition·representations·self-authored). 단 자유텍스트 오개념 `misconception_text`(독립 DB)·
    성취기준 본문(description·formal_definition)은 여전히 노드 비내장. 순수성 동결은
    test_concept_node_purity.py가 담당."""

    def test_enriched_fields_roundtrip(self) -> None:
        """풍부 필드가 그대로 보존된다."""
        c = _concept(ccss_code="HSF-IF.A.1", difficulty_tier=12)
        assert c.ccss_code == "HSF-IF.A.1"
        assert c.difficulty_tier == 12

    def test_enriched_fields_default_none(self) -> None:
        """풍부 필드는 모두 선택(기본 None)."""
        c = _concept()
        assert c.ccss_code is None
        assert c.difficulty_tier is None

    def test_semantic_layer_present_and_pedagogy_freetext_absent(self) -> None:
        """semantic(intuition·representations)은 노드 슬롯 — 자유텍스트 오개념·본문은 노드 밖."""
        c = _concept(intuition="가까이 다가감", representations="ε-δ로 설명")
        assert c.intuition == "가까이 다가감"  # Phase 1 복원(=metaphor)
        assert c.representations == "ε-δ로 설명"  # Phase 1 복원(=accepted_expressions)
        assert c.misconception_codes == []  # 오개념은 참조 키로만
        assert not hasattr(c, "misconception_text")  # 자유텍스트 오개념 — 독립 DB(비내장)
        assert not hasattr(c, "metaphor")  # 옛 필드명은 없다(intuition으로 대체)
        assert not hasattr(c, "accepted_expressions")  # 옛 필드명은 없다(representations로 대체)

    @pytest.mark.parametrize("ok", [0, 12, 24])
    def test_difficulty_tier_in_range(self, ok: int) -> None:
        """difficulty_tier ∈ [0, 24] 허용."""
        assert _concept(difficulty_tier=ok).difficulty_tier == ok

    @pytest.mark.parametrize("bad", [-1, 25, 100])
    def test_difficulty_tier_out_of_range_rejected(self, bad: int) -> None:
        """difficulty_tier ∉ [0, 24] 거부."""
        with pytest.raises(ValidationError):
            _concept(difficulty_tier=bad)

    def test_review_status_default_pending(self) -> None:
        """review_status 기본값은 pending(적재 보류 — 명시 검수 전)."""
        assert _concept().review_status == ReviewStatus.PENDING

    @pytest.mark.parametrize("status", ["reviewed", "pending"])
    def test_review_status_accepts_both(self, status: str) -> None:
        assert _concept(review_status=status).review_status == status

    def test_review_status_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            _concept(review_status="approved")

    @pytest.mark.parametrize("redacted", ["description", "formal_definition"])
    def test_redacted_fields_have_no_slot(self, redacted: str) -> None:
        """redaction 구조적 차단: description/formal_definition 슬롯 부재 → extra='forbid' 거부."""
        with pytest.raises(ValidationError):
            _concept(**{redacted: "성취기준 본문 근접 복제"})


class TestConceptPurity:
    """Concept Purity(Part 3 항목 ③·8대 원칙 ①) — 노드에 renderer·animation·layout·UI·embedding·
    prompt 혼입 금지. AI Graph(개념) ↔ Runtime Graph(렌더·애니·레이아웃·UI) 분리를 모델 필드
    수준에서 동결한다. 시각화·오개념은 *참조 키*(visualization_card_keys·misconception_codes)만
    허용 — 실체(렌더 명세·오개념 목록)는 노드 밖(render_contract·오개념 카탈로그)에 산다."""

    # 노드가 보유할 수 있는 필드 화이트리스트(동결). 새 필드 추가 시 이 테스트가 red →
    # "개념 자체인가, 해석/투영/실행 정보인가?"를 의식적으로 판정하도록 강제(하드 게이트).
    _ALLOWED_FIELDS = frozenset(
        {
            "concept_id",
            "source_id",
            "aliases",
            "domain",
            "grade_band_hint",
            "prerequisite_concept_ids",
            "misconception_codes",
            "visualization_card_keys",
            "standard_codes",
            "ccss_code",
            "difficulty_tier",
            "review_status",
            "notes",
            # 리치 9계층(2026-07-03 전면 채택 Phase 1)
            # — semantic(self-authored)·cognition 스칼라·참조 키
            "intuition",  # semantic(=metaphor 복원·self-authored)
            "representations",  # semantic(=accepted_expressions 복원·self-authored)
            "core_meaning",  # semantic(자체 1줄)
            "formal_definition_ref",  # 참조(본문 미내장)
            "behavior_skills",  # 참조(SkillNode·Phase 2)
            "cognitive_load",  # cognition 스칼라
            "abstraction_required",  # cognition 스칼라
            "assessment_ids",  # 참조(AssessmentNode)
            "formula_refs",  # 참조(FormulaNode·Phase 5·AST 참조만)
        }
    )  # name_ko/en/ja는 P2d·Part 9로 제거(표시이름=locale 레이어). metaphor·accepted는 §3 Stage B.
    # Runtime Graph(투영/실행) 관심사 토큰 — 노드 필드명에 등장 금지(참조 키 예외는 화이트리스트).
    _FORBIDDEN_TOKENS = (
        "renderer",
        "animation",
        "layout",
        "embedding",
        "prompt",
        "widget",
    )

    def test_field_set_frozen(self) -> None:
        """Concept 필드 집합이 화이트리스트와 정확히 일치(순수 개념만)."""
        assert set(Concept.model_fields) == self._ALLOWED_FIELDS

    def test_no_runtime_graph_field_leaks_in(self) -> None:
        """어떤 필드명도 renderer/animation/layout/embedding/prompt 토큰을 담지 않는다."""
        for name in Concept.model_fields:
            low = name.lower()
            for token in self._FORBIDDEN_TOKENS:
                assert token not in low, f"Runtime Graph 관심사 누수 의심 필드: {name}"

    def test_visualization_is_reference_key_only(self) -> None:
        """시각화는 *참조 키*만(L5 자산 참조) — 렌더 명세 실체는 노드에 없다."""
        assert "visualization_card_keys" in Concept.model_fields
        # 렌더 실체 슬롯(예: figure_spec·render_spec)은 부재 → extra='forbid'가 거부.
        with pytest.raises(ValidationError):
            _concept(figure_spec={"type": "plot"})


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

    def test_review_statuses_match_enum(self) -> None:
        """REVIEW_STATUSES는 ReviewStatus enum 값과 1:1(단일 진실)."""
        assert REVIEW_STATUSES == tuple(s.value for s in ReviewStatus)
        assert set(REVIEW_STATUSES) == {"reviewed", "pending"}

    def test_source_citation_mentions_ncic(self) -> None:
        """승계 출처 문구에 NCIC·교육부 고시 명시(공공누리 1유형)."""
        assert "NCIC" in SOURCE_CITATION
        assert "2022-33" in SOURCE_CITATION
