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
# semantic(의미) — 개념의 의미 속성. "핵심만 노드, 나머지는 속성"(CLAUDE.md)에 따라 노드 적합.
_SEMANTIC_FIELDS = frozenset(
    {
        "difficulty_tier",  # 난이도(의미 속성) — 노드 OK
        "standard_codes",  # 성취기준 코드 *참조*(truth source 연결)
        "grade_band_hint",  # 도입 학년군 힌트(의미)
        "prerequisite_concept_ids",  # 선수 관계 조회 캐시(엣지가 정본)
        "ccss_code",  # 매칭 CCSS 코드 참조
        "review_status",  # 적재 보류 표식(운영 메타)
        "notes",  # 검수 메모(운영 메타)
    }
)
# 참조 키(다리) — 실체는 노드 *밖*(pedagogy/visualization 계층)에 있고 노드는 키만 보유.
# 이는 Concept Purity 위반이 *아니다*(내장이 아니라 참조).
_REFERENCE_KEY_FIELDS = frozenset({"misconception_codes", "visualization_card_keys"})

# pedagogy(교수학) 잔류 부채 — **Stage B(2026-07-02)로 청산됨(빈 집합)**. metaphor·accepted_
# expressions를 노드에서 제거하고 pedagogy 계층(ConceptContent)으로 이관했다. 이 집합이 다시
# 비어있지 않게 되면(새 pedagogy 필드를 노드에 추가) 아래 테스트가 red — 부채 재발 방지 경계다.
_STAGE_B_PEDAGOGY_DEBT: frozenset[str] = frozenset()

# 노드에 **절대 있어서는 안 되는** 필드(즉시 금칙). 오개념 자유텍스트·은유·허용표현·본문·설명·
# 렌더러·프롬프트·임베딩 벡터·교육과정 오버레이. 누가 다시 넣으면 이 테스트가 즉시 잡는다.
_FORBIDDEN_NODE_FIELDS = frozenset(
    {
        "misconception_text",  # 자유텍스트 오개념(Stage A 제거 — 삼중 중복·오염 위험)
        "metaphor",  # 은유(pedagogy·Stage B 제거 — ConceptContent 단일 진실)
        "accepted_expressions",  # 허용표현(pedagogy·Stage B 제거 — ConceptContent 단일 진실)
        "description",  # 성취기준 본문 근접 복제 위험(redaction)
        "formal_definition",  # 동
        "intuitive_explanation",  # pedagogy 설명(콘텐츠 계층 소관)
        "misconception",  # 자유텍스트 오개념(별칭)
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
# Stage B 이후 pedagogy 부채는 0이므로 identity·semantic·참조 키 3계층만 남는다.
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


def test_stage_b_pedagogy_debt_is_cleared() -> None:
    """노드의 pedagogy 잔류 부채는 *0*이어야 한다(Stage B 완료·부채 재발 차단).

    metaphor·accepted_expressions를 노드에서 제거하고 ConceptContent로 이관했다(Stage B). 노드에
    pedagogy 필드가 다시 생기면(부채 재발) red — `_STAGE_B_PEDAGOGY_DEBT`는 빈 집합으로 동결한다.
    """
    present = set(Concept.model_fields)
    pedagogy_in_node = present & (_STAGE_B_PEDAGOGY_DEBT | _FORBIDDEN_NODE_FIELDS)
    assert pedagogy_in_node == set(_STAGE_B_PEDAGOGY_DEBT), (
        f"노드에 pedagogy/금칙 필드가 잔류한다: {sorted(pedagogy_in_node)}(기대: 빈 집합). "
        "Stage B로 청산됐어야 하며, 새 pedagogy 필드를 추가했다면 pedagogy 계층으로 외부화하라."
    )


def test_model_fields_snapshot_frozen() -> None:
    """`Concept.model_fields` 전체 스냅샷 동결 — 필드 추가/삭제 시 의식적 리뷰 강제."""
    assert set(Concept.model_fields) == set(_EXPECTED_MODEL_FIELDS), (
        "Concept 노드 필드 구성이 바뀌었다. 4계층 분류(identity/semantic/pedagogy/visualization)에 "
        "맞춰 이 테스트의 계층 집합을 갱신하고, 새 필드가 순수성을 깨지 않는지 검토하라."
    )
