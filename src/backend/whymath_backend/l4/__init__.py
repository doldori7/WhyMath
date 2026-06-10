"""L4 교수학 엔진 — Polya 4단계·소크라테스·LTHC·오개념 진단.

L3(생성)와 L5(상호작용) 사이의 *결정 계층*. 학생 발화·상태에서 **교수학적 결정**을
내리고(`PedagogyDecision`) 단계별 프롬프트를 조립한다. 실제 LLM 생성은 L3 책임 — L4는
프롬프트 조립·단계 판정·톤필터까지만(`docs/architecture/04_pedagogy_engine.md` L13:
"L3 LLM은 *생성*, L4는 *결정*").

첫 슬라이스 범위: Polya 4단계 코칭 엔진(`polya/`) + 정서 안전 톤필터(`tone_filter`).
오개념 진단(카탈로그 30·substring+정규식 매칭)·LTHC·소크라테스·메타인지 트리거는 후속
슬라이스에서 채워졌다. slice 104: 오개념 의미(임베딩) 매칭 좌석(`misconception.semantic`)을
추가 — substring 거짓음성(패러프레이즈·동의어 recall) 보완. *정직 스코프*: 의미 매칭은
recall만 개선하고 방향·부정·등치는 못 가린다(임베딩 방향맹 — LLM-judged/NLI 후속).
범위 밖(후속): pgvector 영속화·LLM-judged 방향 판별·HTTP 노출.
"""

from __future__ import annotations

from whymath_backend.l4.hint_deferral import REVEALS, HintLevel, decide_hint_level
from whymath_backend.l4.lthc import (
    LthcAdaptation,
    MasteryLevel,
    adapt_lthc,
    mastery_to_level,
)
from whymath_backend.l4.metacognitive_trigger import (
    CoachingFocus,
    CoachingTrigger,
    focus_to_socratic_category,
    recommend_coaching,
)
from whymath_backend.l4.misconception import (
    CATALOG as MISCONCEPTION_CATALOG,
)
from whymath_backend.l4.misconception import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    InMemoryVectorIndex,
    InterventionDecision,
    InterventionPattern,
    LocalEmbeddingProvider,
    Misconception,
    MisconceptionMatch,
    OpenAIEmbeddingProvider,
    SemanticMatcher,
    VectorIndex,
    build_provider,
    diagnose,
    select_intervention,
    semantic_matches,
    visualize_misconception,
)
from whymath_backend.l4.models import (
    LLMSeam,
    PedagogyDecision,
    PolyaStage,
    PolyaState,
    StageTransition,
    ToneReport,
)
from whymath_backend.l4.polya.engine import PolyaCoach
from whymath_backend.l4.socratic import SocraticCategory, select_category
from whymath_backend.l4.solution_coaching import (
    SlipKind,
    SolutionCoaching,
    recommend_coaching_for_solution,
)
from whymath_backend.l4.tone_filter import filter_tone

__all__ = [
    "CoachingFocus",
    "CoachingTrigger",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "HintLevel",
    "InMemoryVectorIndex",
    "InterventionDecision",
    "InterventionPattern",
    "LLMSeam",
    "LocalEmbeddingProvider",
    "LthcAdaptation",
    "MISCONCEPTION_CATALOG",
    "MasteryLevel",
    "Misconception",
    "MisconceptionMatch",
    "OpenAIEmbeddingProvider",
    "PedagogyDecision",
    "PolyaCoach",
    "PolyaStage",
    "PolyaState",
    "REVEALS",
    "SemanticMatcher",
    "SlipKind",
    "SocraticCategory",
    "SolutionCoaching",
    "StageTransition",
    "ToneReport",
    "VectorIndex",
    "adapt_lthc",
    "build_provider",
    "decide_hint_level",
    "diagnose",
    "filter_tone",
    "focus_to_socratic_category",
    "mastery_to_level",
    "recommend_coaching",
    "recommend_coaching_for_solution",
    "select_category",
    "select_intervention",
    "semantic_matches",
    "visualize_misconception",
]
