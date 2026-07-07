"""거버넌스 동결 — 플레이북 Part 2 §2 "우선 5노드, Formula는 마지막".

법칙: *노드 = 학생 사고가 바뀌는 최소 단위*. 우선 5노드(Concept → Misconception → Skill →
ProblemType → Visualization)를 연결하고 **Formula를 먼저 만들지 않는다**(실패 경로 회피).

WhyMath는 anti-explosion(CLAUDE.md "수학 전체 완벽 모델링 금지·핵심만 노드")에 따라 노드 승격을
*canonical·mastery 독립추정 가치*가 있을 때만 허용한다(설계 결정: docs/architecture/
concept_node_layering_decision.md §2). **Skill은 2026-07-03 Phase 2a**로, **ProblemType은
2026-07-07 Phase 3**로 1급 노드 승격됐다(ADR 갱신 완료). Skill은 CognitiveType enum 속성에서
`SkillNode`+`BehaviorArea`(6종)로, ProblemType은 Problem 스키마 표현에서 `ProblemTypeNode`
(cognitive-action canonical·≠surface SignaturePattern)로 격상했다. Formula만 아직 스키마로 표현
(P5 승격 대기). 이 테스트는 그 결정을 코드로 동결한다:

  ① **노드 대체 표현/승격 존재**: Concept(모델)·Misconception(카탈로그)·**Skill(=SkillNode 1급
     노드·Phase 2a)**·**ProblemType(=ProblemTypeNode 1급 노드·Phase 3)**·Visualization(스키마)이
     전부 로드·비어있지 않다.
  ② **연결(다리) 존재**: identity 노드가 Misconception·Visualization로 *참조 키*를 노출한다
     (`misconception_codes`·`visualization_card_keys`) — 5노드가 배선돼 있다(Phase 1 값 미충전이어도
     연결 *능력*은 존재).
  ③ **Formula 전용 노드 부재 동결**: 소스 스캔으로 `FormulaNode` 클래스가 코드베이스에 없음을
     단언 — 누가 승격하면 red가 되어 ADR 재검토를 강제한다(노드 폭발·"Formula 먼저" 실패 경로 차단).
     **SkillNode·ProblemTypeNode는 각 Phase 2a·3으로 승격돼 이 금지집합에서 제외**된다.

hermetic: DB 불요(모델·enum import·소스 텍스트 스캔만).
"""

from __future__ import annotations

import re
from pathlib import Path

import data_pipeline
from data_pipeline.concept_graph.models import Concept
from data_pipeline.problem_type_graph.models import ProblemTypeNode as PipelineProblemTypeNode
from data_pipeline.skill_graph.models import BehaviorArea
from data_pipeline.skill_graph.models import SkillNode as PipelineSkillNode

import whymath_backend
from whymath_backend.db.models.problem_type_node import ProblemTypeNode as OrmProblemTypeNode
from whymath_backend.db.models.skill_node import SkillNode as OrmSkillNode
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.schema.visualization import Visualization

# 소스 스캔 루트(두 패키지 — 노드 승격은 어디서든 일어날 수 있다).
_PKG_ROOTS = (
    Path(whymath_backend.__file__).resolve().parent,
    Path(data_pipeline.__file__).resolve().parent,
)

# 승격 금지 노드 클래스명(anti-explosion — 스키마로만 표현). *Node 접미사 정확 매칭.
# SkillNode(Phase 2a·2026-07-03)·ProblemTypeNode(Phase 3·2026-07-07)는 1급 승격돼 이 집합에서
# 제외(ADR 갱신·각 mastery/cognitive-action canonical). Formula만 남는다(P5 승격 대기).
_FORBIDDEN_NODE_CLASSES = ("FormulaNode",)
_FORBIDDEN_CLASS_RE = re.compile(r"^\s*class\s+(FormulaNode)\b", re.M)


def _scan_forbidden_node_classes() -> dict[str, list[str]]:
    """두 패키지 소스에서 금지 노드 클래스 정의 위치를 수집(있으면 안 됨)."""
    hits: dict[str, list[str]] = {name: [] for name in _FORBIDDEN_NODE_CLASSES}
    for root in _PKG_ROOTS:
        for py in root.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for match in _FORBIDDEN_CLASS_RE.finditer(text):
                hits[match.group(1)].append(str(py))
    return hits


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
# ③ Formula 전용 노드 부재 동결(anti-explosion·"Formula 먼저" 차단)
# ──────────────────────────────────────────────────────────────────────────
def test_no_dedicated_formula_node_class() -> None:
    """Formula 전용 노드 승격 금지 — 발견되면 ADR(concept_node_layering_decision.md) 재검토 강제.

    Skill(Phase 2a)·ProblemType(Phase 3)은 이미 승격돼 제외. Formula만 남는다(P5 승격 대기 —
    위험문서 정식 개정 전제). FormulaNode 추가 시 red가 되어 "Formula 먼저" 실패 경로를 막는다.
    """
    hits = _scan_forbidden_node_classes()
    offending = {name: locs for name, locs in hits.items() if locs}
    assert not offending, (
        f"anti-explosion 위반 — Formula 전용 노드 클래스가 추가됐다: {offending}. "
        "Formula는 canonical-only 경계·위험문서 개정(P5)을 전제로만 승격한다"
        "(노드 폭발·'Formula 먼저' 실패 경로 방지). "
        "승격이 정말 정당하면 concept_node_layering_decision.md ADR을 갱신하고 이 동결을 수정하라."
    )
