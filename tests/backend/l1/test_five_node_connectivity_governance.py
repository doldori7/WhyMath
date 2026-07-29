"""거버넌스 동결 — 플레이북 Part 2 §2 "우선 5노드, Formula는 마지막".

법칙: *노드 = 학생 사고가 바뀌는 최소 단위*. 우선 5노드(Concept → Misconception → Skill →
ProblemType → Visualization)를 연결하고 **Formula를 마지막에** 만든다(canonical-only·위험문서 개정
전제로만·실패 경로 회피).

WhyMath는 anti-explosion(CLAUDE.md "수학 전체 완벽 모델링 금지·핵심만 노드")에 따라 노드 승격을
*canonical·mastery 독립추정 가치*가 있을 때만 허용한다(설계 결정: docs/architecture/
concept_node_layering_decision.md §2). **Skill은 2026-07-03 Phase 2a**로, **ProblemType은
2026-07-07 Phase 3**으로, **Formula는 2026-07-08 Phase 5a**(canonical-only·위험문서 개정 전제)로
1급 노드 승격됐다(ADR·위험문서 갱신 완료). Skill은 CognitiveType enum 속성에서 `SkillNode`+
`BehaviorArea`(6종)로, ProblemType은 Problem 스키마 표현에서 `ProblemTypeNode`(cognitive-action
canonical·≠surface SignaturePattern)로, Formula는 부재에서 `FormulaNode`(canonical-only·
ID≠Signature·동치는 SymPy 위임)로 격상했다. 이 테스트는 그 결정을 코드로 동결한다:

  ① **노드 대체 표현/승격 존재**: Concept(모델)·Misconception(카탈로그)·**Skill(=SkillNode 1급
     노드·Phase 2a)**·**ProblemType(=ProblemTypeNode 1급 노드·Phase 3)**·Visualization(스키마)이
     전부 로드·비어있지 않다.
  ② **연결(다리) 존재**: identity 노드가 Misconception·Visualization로 *참조 키*를 노출한다
     (`misconception_codes`·`visualization_card_keys`) — 5노드가 배선돼 있다(Phase 1 값 미충전이어도
     연결 *능력*은 존재).
  ③ **Formula 1급 노드 승격**: `FormulaNode`(pipeline 모델·`formula_node` ORM)가 실재한다(Phase 5a).
     canonical-only 경계·SymPy 재구현 금지의 상세 동결은 `test_formula_governance.py` 몫이다.
     **SkillNode·ProblemTypeNode·FormulaNode는 각 Phase 2a·3·5a로 승격돼 금지집합이 비었다**
     (마지막 Formula 승격으로 "우선 5노드" 단계 완료).

hermetic: DB 불요(모델·enum import만).
"""

from __future__ import annotations

from data_pipeline.concept_graph.models import Concept
from data_pipeline.formula_graph.models import FormulaNode as PipelineFormulaNode
from data_pipeline.problem_type_graph.models import ProblemTypeNode as PipelineProblemTypeNode
from data_pipeline.skill_graph.models import BehaviorArea
from data_pipeline.skill_graph.models import SkillNode as PipelineSkillNode
from whymath_backend.db.models.formula_node import FormulaNode as OrmFormulaNode
from whymath_backend.db.models.problem_type_node import ProblemTypeNode as OrmProblemTypeNode
from whymath_backend.db.models.skill_node import SkillNode as OrmSkillNode
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.schema.visualization import Visualization


# ──────────────────────────────────────────────────────────────────────────
# ① 5노드 대체 표현 존재
# ──────────────────────────────────────────────────────────────────────────
def test_concept_node_exists() -> None:
    """Concept — identity 노드 모델이 존재하고 식별 필드를 갖는다.

    name_ko는 재-ID(P2d)로 노드에서 분리돼 `locales/ko.json`이 단일 진실이다(Concept Purity —
    표시이름은 개념이 아니라 투영). identity 노드는 concept_id·source_id로 식별된다.
    """
    assert "concept_id" in Concept.model_fields
    assert "source_id" in Concept.model_fields
    # 표시이름(name_ko/en/ja)은 노드에 없다 — locale 분리(P2d·Concept Purity).
    assert "name_ko" not in Concept.model_fields


def test_misconception_nodes_exist() -> None:
    """Misconception — 검증된 런타임 오개념 카탈로그가 비어있지 않다(별도 DB·독립 노드)."""
    assert len(CATALOG) > 0


def test_skill_is_first_class_node() -> None:
    """Skill — Phase 2a로 1급 노드 승격(SkillNode 모델·ORM + BehaviorArea 6종 축).

    CognitiveType enum 속성에서 격상됐다: data-pipeline `SkillNode`(빌드타임 노드)·backend
    `skill_node`(PG 프로젝션 ORM)이 실재하고, 폐쇄 행동영역 `BehaviorArea`가 정확히 6종이다.
    """
    assert "skill_id" in PipelineSkillNode.model_fields
    assert "behavior_area" in PipelineSkillNode.model_fields
    assert OrmSkillNode.__tablename__ == "skill_node"
    assert len(BehaviorArea) == 6


def test_problem_type_is_first_class_node() -> None:
    """ProblemType — Phase 3로 1급 노드 승격(ProblemTypeNode 모델·ORM).

    Problem 스키마 표현에서 격상됐다: data-pipeline `ProblemTypeNode`(빌드타임 노드·cognitive-action
    canonical)·backend `problem_type_node`(PG 프로젝션 ORM)이 실재한다. cognitive-action 축은
    `behavior_skills`(skill 참조)로 표현하고 표면 SignaturePattern과 구별된다(≠surface).
    """
    assert "problem_type_id" in PipelineProblemTypeNode.model_fields
    assert "behavior_skills" in PipelineProblemTypeNode.model_fields
    assert OrmProblemTypeNode.__tablename__ == "problem_type_node"


def test_visualization_node_exists() -> None:
    """Visualization — 선언적 시각화 명세 스키마가 존재한다."""
    assert Visualization.model_fields, "Visualization 스키마가 로드돼야 한다"


# ──────────────────────────────────────────────────────────────────────────
# ② 연결(다리) — identity 노드가 Misconception·Visualization로 참조 키를 노출
# ──────────────────────────────────────────────────────────────────────────
def test_concept_bridges_to_misconception_and_visualization() -> None:
    """5노드 배선: Concept가 Misconception·Visualization로 *참조 키*를 노출(내장 아님·다리)."""
    fields = set(Concept.model_fields)
    assert "misconception_codes" in fields  # Concept → Misconception 다리(카탈로그 코드 참조)
    assert "visualization_card_keys" in fields  # Concept → Visualization 다리(자산 키 참조)


# ──────────────────────────────────────────────────────────────────────────
# ③ Formula 1급 노드 승격(Phase 5a·canonical-only·위험문서 개정 전제)
# ──────────────────────────────────────────────────────────────────────────
def test_formula_is_first_class_node() -> None:
    """Formula — Phase 5a로 1급 노드 승격(FormulaNode 모델·ORM·canonical-only).

    부재에서 격상됐다: data-pipeline `FormulaNode`(빌드타임 노드·`formula_id` 사람 관리
    code)·backend `formula_node`(PG 프로젝션 ORM)이 실재한다. canonical 표현만 노드화하고 동치는
    런타임 SymPy에 위임한다 — 상세 경계(canonical-only·SymPy 재구현 금지·dsl parseable)는
    `test_formula_governance.py`가 동결한다. "우선 5노드, Formula는 마지막" 단계가 완료됐다.
    """
    assert "formula_id" in PipelineFormulaNode.model_fields
    assert "dsl" in PipelineFormulaNode.model_fields  # SymPy-parseable canonical 식
    assert OrmFormulaNode.__tablename__ == "formula_node"
