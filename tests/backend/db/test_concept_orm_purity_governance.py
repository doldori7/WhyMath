"""정적 거버넌스 — **런타임** `Concept` ORM의 Concept Purity 스냅샷 동결.

배경(2026-07-21 전면 정합성 검토): 저작 노드는 `tests/data_pipeline/concept_graph/
test_concept_node_purity.py`가 금칙·스냅샷으로 동결했으나, 런타임 투영인
`db/models/concept.py`의 `Concept` ORM에는 동형 게이트가 없어 순수성 방어가
*비대칭*이었다 — 저작 단계에서 막은 혼입(renderer·prompt·본문·오개념)이 런타임
테이블로는 무단 재유입될 수 있는 공백. 이 테스트가 그 공백을 닫는다.

정책:
- **금칙 컬럼**(저작 게이트와 동일 축)은 런타임에도 0이어야 한다.
- **알려진 부채 1건**(`recommended_visual_styles`)은 현 스냅샷에 *존재*한다 — 저작
  게이트가 금지한 축이지만 런타임에는 역사적으로 남아 있다. Overlay/투영 계층 이관은
  ARCH-14-review-residual-hardening가 추적한다. (`embedding_id`는 ARCH-14로 *제거·청산
  완료* — `_FORBIDDEN_COLUMNS`로 재유입 차단.) 이관 착륙 시 이 파일의 부채 집합·스냅샷을
  함께 갱신한다(무단 확대는 스냅샷이 차단).

hermetic: DB 불요 — `__table__.columns` introspection만(엔진·세션 0).
"""

from __future__ import annotations

from whymath_backend.db.models.concept import Concept

# ──────────────────────────────────────────────────────────────────────────
# 스냅샷 — 현재 런타임 concept 테이블 컬럼 전체(추가/삭제 시 의식적 리뷰 강제).
# ──────────────────────────────────────────────────────────────────────────
_IDENTITY_COLUMNS = frozenset({"concept_id", "code", "name_ko", "name_en", "source_id", "aliases"})
_HIERARCHY_COLUMNS = frozenset({"level", "parent_concept_id"})
_SEMANTIC_COLUMNS = frozenset(
    {
        "is_signature_korean",
        "cognitive_type",
        "intrinsic_difficulty",
        "exam_frequency",
        "weight_in_curriculum",
        "behavior_skills",  # 참조 키 배열(→ SkillNode) — 내장 아님
    }
)
_OPS_COLUMNS = frozenset({"created_at"})

# 알려진 순수성 부채 — 저작 게이트 기준 금칙 축이나 런타임에 잔존. 이관은 ARCH-14가
# 추적한다(visual styles는 concept_visualization Overlay로). `embedding_id`는 ARCH-14로
# *제거 완료*(죽은 컬럼 청산·소비처 0·전량 NULL) — 아래 _FORBIDDEN_COLUMNS로 재유입 차단.
# 이 집합에 *새 항목을 추가하는 것*은 부채 확대이므로 금지 — 리뷰에서 반려하라.
_KNOWN_PURITY_DEBT = frozenset({"recommended_visual_styles"})

_EXPECTED_COLUMNS = (
    _IDENTITY_COLUMNS | _HIERARCHY_COLUMNS | _SEMANTIC_COLUMNS | _OPS_COLUMNS | _KNOWN_PURITY_DEBT
)

# 절대 금칙 — 재유입 시 즉시 red(저작 게이트 `_FORBIDDEN_NODE_FIELDS`와 동일 축 + 런타임
# 청산 이력 컬럼). Phase 1b redaction·Overlay 분리로 *제거된* 컬럼들의 부활을 막는다.
_FORBIDDEN_COLUMNS = frozenset(
    {
        # 자유텍스트 오개념(독립 오개념 DB·CLAUDE.md 구조원칙 #6)
        "misconception_text",
        "misconception",
        "common_misconceptions",
        # 본문 근접 자유 서술(redaction — 성취기준·교과서 본문 복제 위험)
        "description",
        "formal_definition",
        "intuitive_explanation",
        # 렌더러·프롬프트·시각화 실체(Concept → Intent → Adapter)
        "renderer",
        "visualization_spec",
        "prompt",
        # 벡터 실체·참조(별도 pgvector 테이블이 code 키로 소유 — 노드는 참조조차 금지)
        "embedding",
        "embedding_id",  # ARCH-14로 죽은 참조 컬럼 청산 — 재유입 금지
        # 교육과정 Overlay(CurriculumEntry 단일 진실 — rev f3a4b5c6d7e8 제거 이력)
        "curriculum",
        "subject",
        "curriculum_version",
        "grade_introduced",
        "semester_introduced",
    }
)


def _runtime_columns() -> set[str]:
    """런타임 concept 테이블 컬럼명 집합 — DB 없이 매핑 introspection."""
    return set(Concept.__table__.columns.keys())


def test_forbidden_columns_absent() -> None:
    """청산·금칙 컬럼(본문·오개념·렌더러·프롬프트·교육과정·벡터 실체)의 재유입은 즉시 red."""
    leaked = _runtime_columns() & _FORBIDDEN_COLUMNS
    assert not leaked, (
        f"런타임 Concept ORM에 금칙 컬럼이 재유입됐다: {sorted(leaked)}. "
        "본문·오개념·렌더러·프롬프트·교육과정은 노드에 넣지 말 것(Concept Purity) — "
        "ConceptContent·오개념 독립 DB·Overlay(CurriculumEntry 등)로 외부화하라."
    )


def test_columns_snapshot_frozen() -> None:
    """컬럼 전체 스냅샷 동결 — 추가/삭제 시 이 파일의 계층 집합 갱신(의식적 리뷰)을 강제."""
    assert _runtime_columns() == set(_EXPECTED_COLUMNS), (
        "런타임 Concept ORM 컬럼 구성이 바뀌었다. 새 컬럼이 순수성(참조만·내장 금지)을 "
        "깨지 않는지 검토하고 이 테스트의 계층 집합을 갱신하라. 부채 축소(embedding_id·"
        "recommended_visual_styles 이관)면 _KNOWN_PURITY_DEBT에서도 제거할 것."
    )


def test_purity_debt_is_tracked_not_grown() -> None:
    """부채 1건은 실제 존재(추적 정합)하며, 부채 집합은 딱 그 1건이다(확대 금지).

    embedding_id는 ARCH-14로 제거·청산됨(_FORBIDDEN_COLUMNS로 재유입 차단).
    """
    assert _KNOWN_PURITY_DEBT <= _runtime_columns(), (
        "부채로 선언된 컬럼이 이미 제거됐다 — 이관이 착륙했다면 _KNOWN_PURITY_DEBT와 "
        "_EXPECTED_COLUMNS에서 함께 제거해 이 파일을 현행화하라."
    )
    assert _KNOWN_PURITY_DEBT == {"recommended_visual_styles"}
