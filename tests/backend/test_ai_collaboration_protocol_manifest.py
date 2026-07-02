"""Part 11(AI 협업 방법론) manifest 동결 — 프로토콜 정의·근거 앵커 드리프트 차단.

`docs/architecture/ai_collaboration_part11_review.md`가 "Part 11 3개 검문이 이미 준수된다"고
판정할 때 근거로 든 세 축이 *실재*함을 동결한다:
  (1) 정본 프로토콜 정의(`CLAUDE.md:156-193`)의 온전성 — 4종 질문 축·질문 골격·단계적 심화·7분할
      인지행동 출력 문자열이 그대로 있는가(검문 ②③의 정의).
  (2) 검문 ①을 떠받치는 거버넌스 테스트·검증기가 저장소에 *실재*하는가(감사 결과표 근거 무결성).
  (3) 검문 ③의 "메타 질문 각 파트 끝 필수" 강제(질문지)와 시연(Part 4 검토)이 실재하는가.

이 테스트는 기존 거버넌스 단언(namespace·purity·relation vocabulary…)을 **중복하지 않는다** — 그
방어들이 *실재*한다는 연결 무결성과, 정본 프로토콜 문자열이 *온전*하다는 것만 동결한다. 프로토콜을
지우거나 근거 테스트를 삭제하면(체크리스트가 근거를 잃는 침묵 실패) 이 테스트가 red가 되어
문서·정본·근거가 함께 움직이도록 강제한다.

hermetic: 외부 의존·DB·`whymath_backend` import 불요(파일 존재·텍스트 부분일치만).
"""

from __future__ import annotations

from pathlib import Path

# 저장소 루트 — 이 파일: tests/backend/…  →  parents[2] = repo root(CLAUDE.md·docs·tests 보유).
_REPO_ROOT = Path(__file__).resolve().parents[2]

_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_REVIEW_DOC = _REPO_ROOT / "docs/architecture/ai_collaboration_part11_review.md"
_CHECKLIST = _REPO_ROOT / "docs/standards/playbook_part_review_questions.md"
_PART4_REVIEW = _REPO_ROOT / "docs/architecture/math_dsl_part4_ast_review.md"


def _claude_md_text() -> str:
    return _CLAUDE_MD.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
# (1) 정본 프로토콜 정의 온전성 — CLAUDE.md §"AI 질문 프로토콜"이 담아야 할 문자열.
#     (하나라도 사라지면 검문 ②③의 정의가 증발한다.)
# ──────────────────────────────────────────────────────────────────────────
# "AI = 구조 붕괴 감지기" 핵심 대비(검문 ①의 정의).
_MARKERS_CORE = (
    "AI 질문 프로토콜",
    "구조 붕괴 감지기",
    "구조 비평가·boundary 검사기·explosion 탐지기·schema validator",
)

# 4종 질문 축(검문 ②) — 열거 그대로.
_MARKERS_FOUR_AXES = (
    "4종 질문 축",
    "①존재 이유",
    "②경계",
    "③붕괴",
    "④분리",
)

# 질문 골격 5부(검문 ②).
_MARKERS_SKELETON = ("[역할]", "[목표]", "[환경]", "[출력]", "[검증]")

# 단계적 심화 + 7분할 인지행동 출력(검문 ③).
_MARKERS_DEEPENING = ("생성 → 비판 → 반례 → 개선 → 테스트 → 자동화",)
_MARKERS_SEVEN_OUTPUT = (
    "1.구조적",
    "2.교육적",
    "3.AI retrieval",
    "4.scaling",
    "5.maintenance",
    "6.canonicalization",
    "7.mitigation",
    "인지 행동(cognitive action)",
)

# ──────────────────────────────────────────────────────────────────────────
# (2) 검문 ① 근거 — 거버넌스 테스트·검증기·budget guard가 실재(repo 상대경로).
#     감사 결과표(§1 검문①)가 인용한 방어들. 소실 시 판정이 근거를 잃는다.
# ──────────────────────────────────────────────────────────────────────────
_REFERENCED_GUARD_TESTS = (
    "tests/backend/l1/test_edge_relation_governance.py",
    "tests/backend/l1/test_five_node_connectivity_governance.py",
    "tests/backend/l1/test_embedding_namespace_governance.py",
    "tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py",
    "tests/data_pipeline/concept_graph/test_concept_node_purity.py",
    "tests/backend/l2/test_prerequisite_depth_budget.py",
    "src/data-pipeline/data_pipeline/concept_graph/validate.py",
    "src/data-pipeline/data_pipeline/atom_graph/validate.py",
)


# ──────────────────────────────────────────────────────────────────────────
# 단계 (1) — 정본 프로토콜 정의 온전성
# ──────────────────────────────────────────────────────────────────────────
def test_protocol_section_present_in_claude_md() -> None:
    """CLAUDE.md에 AI 질문 프로토콜 정본 섹션 + 핵심 대비가 온전하다(검문 ① 정의)."""
    text = _claude_md_text()
    for marker in _MARKERS_CORE:
        assert marker in text, f"CLAUDE.md 프로토콜 핵심 문자열 소실: {marker!r}"


def test_four_question_axes_enumerated() -> None:
    """4종 질문 축(존재이유·경계·붕괴·분리)이 정본에 열거돼 있다(검문 ②)."""
    text = _claude_md_text()
    for marker in _MARKERS_FOUR_AXES:
        assert marker in text, f"4종 질문 축 문자열 소실: {marker!r}"


def test_question_skeleton_five_parts() -> None:
    """질문 골격 5부 [역할][목표][환경][출력][검증]가 정본에 있다(검문 ②)."""
    text = _claude_md_text()
    for marker in _MARKERS_SKELETON:
        assert marker in text, f"질문 골격 5부 문자열 소실: {marker!r}"


def test_seven_part_cognitive_output_enforced() -> None:
    """단계적 심화 + 7분할 인지행동 출력 형식이 정본에 있다(검문 ③)."""
    text = _claude_md_text()
    for marker in (*_MARKERS_DEEPENING, *_MARKERS_SEVEN_OUTPUT):
        assert marker in text, f"7분할 인지행동 출력 문자열 소실: {marker!r}"


# ──────────────────────────────────────────────────────────────────────────
# 단계 (2) — 검문 ① 근거 거버넌스 방어 실재
# ──────────────────────────────────────────────────────────────────────────
def test_item1_governance_guards_exist() -> None:
    """검문 ①이 인용한 거버넌스 테스트·검증기가 저장소에 실재한다(근거 무결성)."""
    for rel in _REFERENCED_GUARD_TESTS:
        assert (_REPO_ROOT / rel).is_file(), f"검문 ① 근거 방어 부재: {rel}"


# ──────────────────────────────────────────────────────────────────────────
# 단계 (3) — 검문 ③ 메타 질문 강제(질문지) + 시연(Part 4 검토)
# ──────────────────────────────────────────────────────────────────────────
def test_item3_meta_question_mandated_in_checklist() -> None:
    """질문지가 메타 질문을 '각 파트 끝 필수'로 강제한다(검문 ③ 강제 축)."""
    text = _CHECKLIST.read_text(encoding="utf-8")
    assert "메타 질문 (각 파트 끝 필수)" in text
    assert "인지 행동(cognitive action)" in text


def test_item3_meta_question_demonstrated_in_part4_review() -> None:
    """Part 4 검토가 메타 질문을 7대 붕괴 연쇄·인지행동 기준으로 실제 시연한다(검문 ③ 시연 축)."""
    text = _PART4_REVIEW.read_text(encoding="utf-8")
    assert "메타 질문" in text
    assert "붕괴 연쇄" in text


# ──────────────────────────────────────────────────────────────────────────
# 대응 문서·본 검토의 메타 질문 자기 준수
# ──────────────────────────────────────────────────────────────────────────
def test_review_doc_exists_and_carries_meta_question() -> None:
    """Part 11 검토 문서가 실재하고, 스스로 '각 파트 끝 필수' 메타 질문 규칙을 따른다."""
    assert _REVIEW_DOC.is_file(), f"Part 11 검토 문서 부재: {_REVIEW_DOC}"
    text = _REVIEW_DOC.read_text(encoding="utf-8")
    assert "메타 질문" in text
    assert "붕괴 연쇄" in text


def test_checklist_part11_section_exists() -> None:
    """질문지에 Part 11 섹션이 실재한다(본 검토의 검토 대상)."""
    text = _CHECKLIST.read_text(encoding="utf-8")
    assert "## Part 11. AI 협업 방법론" in text
