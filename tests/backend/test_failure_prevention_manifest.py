"""Part 12(실패 방지 체크리스트) manifest 동결 — 정의·근거 앵커 드리프트 차단.

`docs/architecture/failure_prevention_part12_review.md`가 "Part 12 3개 검문이 이미 준수된다"고
판정할 때 근거로 든 것이 *실재*함을 동결한다:
  (1) 정본 정의(`CLAUDE.md:167-212`)의 온전성 — 8대 구조 원칙 제목·7대 붕괴 연쇄 문자열·3개 하드
      게이트 블록이 그대로 있는가(검문 ①②③의 정의).
  (2) 8대 원칙·하드 게이트를 떠받치는 거버넌스 테스트·스키마·검증기가 저장소에 *실재*하는가
      (감사 결과표 §1의 근거 무결성).
  (3) 본 검토 문서가 실재하고, *재정의가 아니라* 정본(`CLAUDE.md`)을 가리키며(단일 진실원),
      메타 질문(7대 붕괴 · 인지행동) 규칙을 스스로 따르는가.

이 테스트는 Part 11 manifest(`test_ai_collaboration_protocol_manifest.py`)의 단언을 **중복하지
않는다** — Part 11이 프로토콜 문자열·근거 실재를 동결한다면, Part 12는 *8대 원칙·7대 붕괴·하드
게이트*라는 다른 정본 구획과 그 근거 매핑만 동결한다. 8대 원칙/하드게이트가 붙은 정본 블록을
지우거나 근거 테스트를 삭제하면(체크리스트가 근거를 잃는 침묵 실패) 이 테스트가 red가 되어
문서·정본·근거가 함께 움직이도록 강제한다.

hermetic: 외부 의존·DB·`whymath_backend` import 불요(파일 존재·텍스트 부분일치만).
"""

from __future__ import annotations

from pathlib import Path

# 저장소 루트 — 이 파일: tests/backend/…  →  parents[2] = repo root(CLAUDE.md·docs·tests 보유).
_REPO_ROOT = Path(__file__).resolve().parents[2]

_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_REVIEW_DOC = _REPO_ROOT / "docs/architecture/failure_prevention_part12_review.md"
_CHECKLIST = _REPO_ROOT / "docs/standards/playbook_part_review_questions.md"


def _claude_md_text() -> str:
    return _CLAUDE_MD.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
# (1) 정본 정의 온전성 — CLAUDE.md §8대 원칙·§7대 붕괴·§하드 게이트가 담아야 할 문자열.
#     (하나라도 사라지면 Part 12 검문 ①②③의 정의가 증발한다.)
# ──────────────────────────────────────────────────────────────────────────
# 8대 구조 원칙(12-2) — 제목 8개 그대로(검문 ①의 정의).
_MARKERS_EIGHT_PRINCIPLES = (
    "Concept Purity",
    "Layer Separation",
    "Relation Typing 최소화",
    "Renderer는 Plugin",
    "Curriculum은 Overlay",
    "오개념은 독립 DB",
    "AI Context Slimming",
    "AST 중심",
)

# 7대 붕괴 연쇄(12-1) — 연쇄 문자열 + 각 마디(검문 ②의 정의).
_MARKERS_SEVEN_COLLAPSE = (
    # 전체 연쇄를 겹치는 두 반절로 동결(유지보수 지옥에서 overlap → 순서 그대로 보존·줄길이 준수).
    "노드 폭발 → 관계 폭발 → 순환참조 → 유지보수 지옥",
    "유지보수 지옥 → 성능 병목 → AI 추론 실패 → 교육 일관성 붕괴",
    "attention dilution",
    "Minimal Reasoning Subgraph",
)

# 작업 전/후 하드 게이트(12-3) — 3개 블록 헤더 + 핵심 강제 문자열(검문 ③의 정의).
_MARKERS_HARD_GATES = (
    "**노드 추가 시**",
    "**관계 추가 시**",
    "**AI 연동 시**",
    "depth ≤ 2, max_nodes ≤ 12~20",
    "reactive",
)

# ──────────────────────────────────────────────────────────────────────────
# (2) 검문 ①③ 근거 — 8대 원칙·하드 게이트를 물화한 거버넌스 아티팩트가 실재(repo 상대경로).
#     감사 결과표(§1)가 인용한 방어들. 소실 시 판정이 근거를 잃는다.
# ──────────────────────────────────────────────────────────────────────────
_REFERENCED_GOVERNANCE = (
    # 원칙 1 Concept Purity / 노드 추가 게이트
    "tests/data_pipeline/concept_graph/test_concept_node_purity.py",
    # 원칙 2 Layer Separation
    "tests/backend/l1/test_no_import_cycle.py",
    "tests/backend/schema/test_visualization_state_separation.py",
    # 원칙 3 Relation Typing / 관계 추가 게이트
    "tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py",
    "tests/backend/l1/test_edge_relation_governance.py",
    # 원칙 4 Renderer Plugin
    "tests/backend/schema/test_render_contract.py",
    # 원칙 6 오개념 독립 DB(reactive)
    "docs/architecture/04c_misconception_seven_stage_separation.md",
    # 노드폭발 방어 / 다중노드 taxonomy 동결
    "tests/backend/l1/test_five_node_connectivity_governance.py",
    # AI 연동 게이트 — embedding 경계 · depth budget
    "tests/backend/l1/test_embedding_namespace_governance.py",
    "tests/backend/l2/test_prerequisite_depth_budget.py",
    # 순환참조 방어 — DAG 검증기
    "src/data-pipeline/data_pipeline/concept_graph/validate.py",
    # ID/Curriculum/Relation 스키마
    "schemas/v1.1/concept.schema.yaml",
    "schemas/v1.1/edge.schema.yaml",
    "schemas/v1.1/curriculum_entry.schema.yaml",
)


# ──────────────────────────────────────────────────────────────────────────
# 단계 (1) — 정본 정의 온전성
# ──────────────────────────────────────────────────────────────────────────
def test_eight_structure_principles_present_in_claude_md() -> None:
    """8대 구조 원칙 제목 8개가 정본에 온전하다(검문 ①의 정의)."""
    text = _claude_md_text()
    for marker in _MARKERS_EIGHT_PRINCIPLES:
        assert marker in text, f"8대 구조 원칙 문자열 소실: {marker!r}"


def test_seven_collapse_chain_present_in_claude_md() -> None:
    """7대 붕괴 연쇄(순서 그대로) + 핵심 원인/방어가 정본에 온전하다(검문 ②의 정의)."""
    text = _claude_md_text()
    for marker in _MARKERS_SEVEN_COLLAPSE:
        assert marker in text, f"7대 붕괴 연쇄 문자열 소실: {marker!r}"


def test_hard_gates_present_in_claude_md() -> None:
    """작업 전/후 하드 게이트 3블록 + 핵심 강제 문자열이 정본에 온전하다(검문 ③의 정의)."""
    text = _claude_md_text()
    for marker in _MARKERS_HARD_GATES:
        assert marker in text, f"하드 게이트 문자열 소실: {marker!r}"


# ──────────────────────────────────────────────────────────────────────────
# 단계 (2) — 8대 원칙·하드 게이트 근거 거버넌스 실재
# ──────────────────────────────────────────────────────────────────────────
def test_governance_artifacts_exist() -> None:
    """8대 원칙·하드 게이트 근거 거버넌스 테스트·스키마·검증기가 실재한다(근거 무결성)."""
    for rel in _REFERENCED_GOVERNANCE:
        assert (_REPO_ROOT / rel).is_file(), f"Part 12 근거 방어 부재: {rel}"


# ──────────────────────────────────────────────────────────────────────────
# 단계 (3) — 검토 문서: 실재 + 정본 참조(재정의 아님) + 메타 질문 자기 준수
# ──────────────────────────────────────────────────────────────────────────
def test_review_doc_exists_and_points_to_canonical() -> None:
    """Part 12 검토 문서가 실재하고, 재정의가 아니라 정본(CLAUDE.md)을 가리킨다(단일 진실원)."""
    assert _REVIEW_DOC.is_file(), f"Part 12 검토 문서 부재: {_REVIEW_DOC}"
    text = _REVIEW_DOC.read_text(encoding="utf-8")
    assert "CLAUDE.md:167-212" in text, "검토 문서가 정본(CLAUDE.md) 위치를 안 가리킴"
    assert "재정의" in text, "검토 문서에 '재정의하지 않음'(감사만) 방침이 명시돼야 함"


def test_review_doc_carries_meta_question() -> None:
    """Part 12 검토 문서가 '각 파트 끝 필수' 메타 질문(7대 붕괴·인지행동) 규칙을 따른다."""
    text = _REVIEW_DOC.read_text(encoding="utf-8")
    assert "메타 질문" in text
    assert "붕괴 연쇄" in text
    assert "인지 행동(cognitive action)" in text


def test_checklist_part12_section_exists() -> None:
    """질문지에 Part 12 섹션이 실재한다(본 검토의 검토 대상)."""
    text = _CHECKLIST.read_text(encoding="utf-8")
    assert "## Part 12. 실패 방지 체크리스트" in text
