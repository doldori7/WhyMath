"""L4 오개념 진단·개입 — 카탈로그 + 진단 매처 + 개입 결정트리.

스펙 §"오개념 진단·개입"(L121-127) + `docs/prompts/misconception_diagnosis.md` 정본.
범위: 풀이 → 규칙 기반 매칭 → 결정 트리 → 자각 유도 프롬프트. PRM 단계 파싱·임베딩
매칭·LLM-judged는 후속.
"""

from __future__ import annotations

from whymath_backend.l4.misconception.catalog import CATALOG, CATALOG_BY_ID
from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.l4.misconception.intervene import select_intervention
from whymath_backend.l4.misconception.models import (
    InterventionDecision,
    InterventionPattern,
    Misconception,
    MisconceptionDomain,
    MisconceptionMatch,
)

__all__ = [
    "CATALOG",
    "CATALOG_BY_ID",
    "InterventionDecision",
    "InterventionPattern",
    "Misconception",
    "MisconceptionDomain",
    "MisconceptionMatch",
    "diagnose",
    "select_intervention",
]
