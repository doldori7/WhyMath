"""정적 거버넌스 — 개념그래프 identity 노드(`Concept`)의 **Concept Purity 동결**.

플레이북 Part 2 §3 + CLAUDE.md 8대 구조원칙 #1(Concept Purity)·#6(오개념 독립 DB):
identity 노드에는 renderer·prompt·curriculum·misconception·embedding을 *내장하지 않는다*.
오개념·설명·은유 같은 pedagogy 정보는 별도 계층(ConceptContent·MisconceptionCatalog)이 단일
진실이며, 노드는 *참조 키*(`misconception_codes`·`visualization_card_keys`)로만 이어진다.

이 테스트는 `Concept.model_fields`를 스냅샷으로 동결해, 누군가 pedagogy/오개념/렌더러 필드를
노드에 (재)추가하면 즉시 red가 되게 한다("표현 통합의 기준은 참조, 내장이 아니다"를 코드로 성문화).

hermetic: 외부 의존·DB 불요(모델 필드 introspection만).
"""

from __future__ import annotations

from data_pipeline.concept_graph.models import Concept

# ──────────────────────────────────────────────────────────────────────────
# 4계층 분류(플레이북 Part 2 §3 — identity/semantic/pedagogy/visualization)
# ──────────────────────────────────────────────────────────────────────────
# identity(식별) — 개념을 유일 식별하는 순수 정체성. 표시이름(name_ko/en/ja)은 P2d·Part 9로
# 노드에서 제거하고 locale 레이어로 분리했다(언어-무관 식별자만 노드에 남긴다).
_IDENTITY_FIELDS = frozenset({"concept_id", "source_id", "aliases", "domain"})
# semantic(의미·리치 9계층 "가장 중요"·self-authored) + cognition 스칼라. 노드 내장.
_SEMANTIC_FIELDS = frozenset(
    {
        # semantic 텍스트(self-authored — Phase 1 복원·리치 semantic 계층)
        "intuition",  # 직관/은유(= Stage B metaphor 복원·self-authored)
        "representations",  # 허용 표현형(= Stage B accepted_expressions 복원·self-authored)
        "core_meaning",  # 핵심 의미 1줄(자체 작성·신규)
        # semantic 속성(스칼라/코드 참조)
        "difficulty_tier",  # 난이도(의미 속성) — 노드 OK
        "standard_codes",  # 성취기준 코드 *참조*(truth source 연결)
        "grade_band_hint",  # 도입 학년군 힌트(의미)
        "prerequisite_concept_ids",  # 선수 관계 조회 캐시(엣지가 정본)
        "ccss_code",  # 매칭 CCSS 코드 참조
        "review_status",  # 적재 보류 표식(운영 메타)
        "notes",  # 검수 메모(운영 메타)
        # cognition 스칼라(리치 cognition 계층 — 자유텍스트 아님)
        "cognitive_load",  # 인지 부하 [1,5]
        "abstraction_required",  # 요구 추상화 수준 [1,5]
    }
)
# 참조 키(다리) — 실체는 노드 *밖*(pedagogy/visualization/skill/formula 계층)에 있고 노드는 키만
# 보유. 이는 Concept Purity 위반이 *아니다*(내장이 아니라 참조).
_REFERENCE_KEY_FIELDS = frozenset(
    {
        "misconception_codes",  # → MisconceptionCatalog(독립 DB)
        "visualization_card_keys",  # → L5 시각화 자산
        # → ConceptContent.formal_definition_internal (본문 미내장·redaction)
        "formal_definition_ref",
        "behavior_skills",  # → SkillNode(Phase 2·초기 dangling)
        "assessment_ids",  # → AssessmentNode(초기 dangling)
        "formula_refs",  # → FormulaNode(Phase 5·AST 참조만·초기 dangling)
    }
)

# pedagogy 잔류 부채 — 여전히 0. Phase 1은 리치 기준 semantic(intuition·representations)을 복원했을
# 뿐이며, **금칙 pedagogy(자유텍스트 오개념·본문·설명)는 노드에 없다**. 재발 시 아래 테스트 red.
_STAGE_B_PEDAGOGY_DEBT: frozenset[str] = frozenset()

# 노드에 **절대 있어서는 안 되는** 필드(즉시 금칙). 자유텍스트 오개념·성취기준/교과서 본문·설명·
# 렌더러·프롬프트·임베딩 벡터·교육과정 오버레이. (metaphor·accepted는 Phase 1에서 semantic
# intuition·representations로 복원됐으므로 더는 금칙이 아니다 — self-authored·본문 아님.)
_FORBIDDEN_NODE_FIELDS = frozenset(
    {
        "misconception_text",  # 자유텍스트 오개념(독립 DB·CLAUDE.md #6)
        "misconception",  # 자유텍스트 오개념(별칭)
        "description",  # 성취기준 본문 근접 복제 위험(redaction)
        "formal_definition",  # 본문 근접(참조는 formal_definition_ref로만)
        "intuitive_explanation",  # pedagogy 설명(콘텐츠 계층 소관)
        "embedding",  # 벡터 내장 금지(별도 pgvector 테이블)
        "embedding_id",  # 벡터 참조도 identity 노드엔 두지 않는다(투영 계층)
        "renderer",  # 렌더러 구현체 이름 금지(Concept → Intent → Adapter)
        "visualization_spec",  # 시각화 명세 실체 금지(참조 키만)
        "prompt",  # LLM 프롬프트 금지
        "curriculum",  # 교육과정은 Overlay(CurriculumEntry) 단일 진실
        "subject",  # Overlay 이관 완료(rev f3a4b5c6d7e8)
        "curriculum_version",  # 동
        "grade_introduced",  # 동
    }
)

# 현재 노드가 가져야 할 필드의 *정확한* 스냅샷. 추가/삭제 시 의식적 리뷰를 강제한다(무단 변경 차단).
# Phase 1(9계층) 이후: identity + semantic(복원 포함) + 참조 키. 자유텍스트 pedagogy는 여전히 0.
_EXPECTED_MODEL_FIELDS = _IDENTITY_FIELDS | _SEMANTIC_FIELDS | _REFERENCE_KEY_FIELDS


def test_forbidden_pedagogy_and_renderer_fields_absent() -> None:
    """오개념 자유텍스트·본문·렌더러·프롬프트·임베딩·교육과정 필드는 노드에 없어야 한다."""
    present = set(Concept.model_fields)
    leaked = present & _FORBIDDEN_NODE_FIELDS
    assert not leaked, (
        f"Concept 노드에 금칙 필드가 내장됐다: {sorted(leaked)}. "
        "pedagogy/오개념/렌더러/임베딩/교육과정은 노드에 넣지 말 것(Concept Purity·Part 2 §3) — "
        "참조 키(misconception_codes 등)나 별도 계층으로 외부화하라."
    )


def test_misconception_link_is_reference_only() -> None:
    """오개념 연결은 카탈로그 *참조 키*(misconception_codes)로만 — 자유텍스트 슬롯은 없다."""
    assert "misconception_codes" in Concept.model_fields  # 참조(다리) — 허용
    assert "misconception_text" not in Concept.model_fields  # 자유텍스트 내장 — 금지


def test_no_forbidden_pedagogy_in_node() -> None:
    """금칙 pedagogy(자유텍스트 오개념·본문·설명)는 노드에 *0*이어야 한다(재발 차단).

    Phase 1은 리치 기준 semantic(intuition·representations)을 노드로 복원했을 뿐이고, 자유텍스트
    오개념·성취기준 본문·설명은 여전히 노드 비내장이다(독립 DB·redaction·pedagogy 계층). 금칙
    필드가 노드에 생기면 red.
    """
    present = set(Concept.model_fields)
    pedagogy_in_node = present & (_STAGE_B_PEDAGOGY_DEBT | _FORBIDDEN_NODE_FIELDS)
    assert pedagogy_in_node == set(_STAGE_B_PEDAGOGY_DEBT), (
        f"노드에 금칙 필드가 잔류한다: {sorted(pedagogy_in_node)}(기대: 빈 집합). "
        "자유텍스트 오개념·본문·설명은 pedagogy 계층/독립 DB로 외부화하라(참조 키만 허용)."
    )


def test_semantic_layer_restored() -> None:
    """리치 semantic 계층(intuition·representations)이 노드에 존재한다(Phase 1 복원)."""
    fields = set(Concept.model_fields)
    assert "intuition" in fields  # = metaphor 복원(self-authored)
    assert "representations" in fields  # = accepted_expressions 복원(self-authored)


def test_model_fields_snapshot_frozen() -> None:
    """`Concept.model_fields` 전체 스냅샷 동결 — 필드 추가/삭제 시 의식적 리뷰 강제."""
    assert set(Concept.model_fields) == set(_EXPECTED_MODEL_FIELDS), (
        "Concept 노드 필드 구성이 바뀌었다. 리치 9계층 분류(identity/semantic/pedagogy/"
        "visualization/assessment/misconception/cognition/graph_links/ast_binding)에 맞춰 "
        "이 테스트의 계층 집합을 "
        "갱신하고, 새 필드가 순수성(self-authored·참조만)을 깨지 않는지 검토하라."
    )
