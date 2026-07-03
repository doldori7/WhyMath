"""437↔원자 크로스워크(Concept↔Atom Crosswalk) — L1 자체 유도 다리 코퍼스.

원자 백본 인계(§5.4 Phase 4-ⓐ). Phase 5에서 구 437 개념그래프를 폐기하려면 437-키 자산
(behavior_skills·concept_content K-12)을 원자 축으로 옮길 다리가 필요하다 — 이 모듈이 그 다리를
**프로그램적으로 유도**한다(1차 성취기준 교집합 + 2차 이름 자카드·외부 lib 0·결정론).

**rekey 금지**: 기존 테이블 키를 바꾸지 않는다. 크로스워크는 독립 코퍼스
(`data/corpus/concept_atom_crosswalk_v1/`)이며, 1:N 시 귀속은 `primary_atom_code` 기준(S0-2 소비).

정본: docs/data/concept_atom_crosswalk_v1.md · docs/handoff/atom_backbone_next_session.md §5.4.
"""

from __future__ import annotations

from data_pipeline.concept_atom_crosswalk.derive import (
    AtomRecord,
    ConceptRecord,
    derive_crosswalk,
    load_atoms,
    load_concepts,
)
from data_pipeline.concept_atom_crosswalk.models import (
    MATCH_METHODS,
    REVIEW_STATUS_AI_ESTIMATED,
    SOURCE_CITATION,
    CrosswalkEntry,
    MatchMethod,
)
from data_pipeline.concept_atom_crosswalk.validate import (
    CrosswalkValidationReport,
    ValidationIssue,
    validate_crosswalk,
)

__all__ = [
    "MATCH_METHODS",
    "REVIEW_STATUS_AI_ESTIMATED",
    "SOURCE_CITATION",
    "AtomRecord",
    "ConceptRecord",
    "CrosswalkEntry",
    "CrosswalkValidationReport",
    "MatchMethod",
    "ValidationIssue",
    "derive_crosswalk",
    "load_atoms",
    "load_concepts",
    "validate_crosswalk",
]
