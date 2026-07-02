"""거버넌스 동결 — 플레이북 Part 2 §2 "우선 5노드, Formula는 마지막".

법칙: *노드 = 학생 사고가 바뀌는 최소 단위*. 우선 5노드(Concept → Misconception → Skill →
ProblemType → Visualization)를 연결하고 **Formula를 먼저 만들지 않는다**(실패 경로 회피).

WhyMath는 anti-explosion(CLAUDE.md "수학 전체 완벽 모델링 금지·핵심만 노드")에 따라 Skill·
ProblemType·Formula를 *전용 노드 테이블로 승격하지 않고* 속성/스키마로 표현한다(설계 결정:
docs/architecture/concept_node_layering_decision.md). 이 테스트는 그 결정을 코드로 동결한다:

  ① **5노드 대체 표현 존재**: Concept(모델)·Misconception(카탈로그)·Skill(=CognitiveType enum)·
     ProblemType(=Problem 스키마)·Visualization(스키마)이 전부 로드 가능·비어있지 않다.
  ② **연결(다리) 존재**: identity 노드가 Misconception·Visualization로 *참조 키*를 노출한다
     (`misconception_codes`·`visualization_card_keys`) — 5노드가 배선돼 있다(Phase 1 값 미충전이어도
     연결 *능력*은 존재).
  ③ **Formula/Skill/ProblemType 전용 노드 부재 동결**: 소스 스캔으로 `FormulaNode`/`SkillNode`/
     `ProblemTypeNode` 클래스가 코드베이스에 없음을 단언 — 누가 승격하면 red가 되어 ADR 재검토를
     강제한다(노드 폭발·"Formula 먼저" 실패 경로 차단).

hermetic: DB 불요(모델·enum import·소스 텍스트 스캔만).
"""

from __future__ import annotations

import re
from pathlib import Path

import data_pipeline
import whymath_backend
from data_pipeline.concept_graph.models import Concept
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.schema.enums import CognitiveType
from whymath_backend.schema.problem import Problem
from whymath_backend.schema.visualization import Visualization

# 소스 스캔 루트(두 패키지 — 노드 승격은 어디서든 일어날 수 있다).
_PKG_ROOTS = (
    Path(whymath_backend.__file__).resolve().parent,
    Path(data_pipeline.__file__).resolve().parent,
)

# 승격 금지 노드 클래스명(anti-explosion — 속성/스키마로만 표현). *Node 접미사 정확 매칭.
_FORBIDDEN_NODE_CLASSES = ("FormulaNode", "SkillNode", "ProblemTypeNode")
_FORBIDDEN_CLASS_RE = re.compile(r"^\s*class\s+(FormulaNode|SkillNode|ProblemTypeNode)\b", re.M)


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
    """Concept — identity 노드 모델이 존재하고 식별 필드를 갖는다."""
    assert "concept_id" in Concept.model_fields
    assert "name_ko" in Concept.model_fields


def test_misconception_nodes_exist() -> None:
    """Misconception — 검증된 런타임 오개념 카탈로그가 비어있지 않다(별도 DB·독립 노드)."""
    assert len(CATALOG) > 0


def test_skill_is_cognitive_type_attribute() -> None:
    """Skill — 전용 노드 대신 CognitiveType enum 속성으로 표현(개념의 인지 유형)."""
    values = [c.value for c in CognitiveType]
    assert values, "CognitiveType(=Skill 축) enum이 비어있으면 안 된다"


def test_problem_type_is_problem_schema() -> None:
    """ProblemType — 전용 노드 대신 Problem 스키마로 표현(로드 가능·필드 보유)."""
    assert Problem.model_fields, "Problem 스키마(=ProblemType 표현)가 로드돼야 한다"


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
# ③ Formula/Skill/ProblemType 전용 노드 부재 동결(anti-explosion·"Formula 먼저" 차단)
# ──────────────────────────────────────────────────────────────────────────
def test_no_dedicated_formula_skill_problemtype_node_classes() -> None:
    """전용 노드 클래스 승격 금지 — 발견되면 ADR(concept_node_layering_decision.md) 재검토 강제."""
    hits = _scan_forbidden_node_classes()
    offending = {name: locs for name, locs in hits.items() if locs}
    assert not offending, (
        f"anti-explosion 위반 — 전용 노드 클래스가 추가됐다: {offending}. "
        "Skill/ProblemType/Formula는 속성/스키마로 표현한다(노드 폭발·'Formula 먼저' 실패 경로 방지). "
        "승격이 정말 정당하면 concept_node_layering_decision.md ADR을 갱신하고 이 동결을 수정하라."
    )
