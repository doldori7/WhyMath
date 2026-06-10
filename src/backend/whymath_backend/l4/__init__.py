"""L4 교수학 엔진 — Polya 4단계·소크라테스·LTHC·오개념 진단.

L3(생성)와 L5(상호작용) 사이의 *결정 계층*. 학생 발화·상태에서 **교수학적 결정**을
내리고(`PedagogyDecision`) 단계별 프롬프트를 조립한다. 실제 LLM 생성은 L3 책임 — L4는
프롬프트 조립·단계 판정·톤필터까지만(`docs/architecture/04_pedagogy_engine.md` L13:
"L3 LLM은 *생성*, L4는 *결정*").

첫 슬라이스 범위: Polya 4단계 코칭 엔진(`polya/`) + 정서 안전 톤필터(`tone_filter`).
범위 밖(후속): Socratic 50+ 카탈로그·답 미루기 4단계 graded hint·오개념 30·LTHC·
개념 점화 지도·HTTP 노출·L2 학습자 모델 통합.
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
    InterventionDecision,
    InterventionPattern,
    Misconception,
    MisconceptionMatch,
    diagnose,
    select_intervention,
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
    "HintLevel",
    "InterventionDecision",
    "InterventionPattern",
    "LLMSeam",
    "LthcAdaptation",
    "MISCONCEPTION_CATALOG",
    "MasteryLevel",
    "Misconception",
    "MisconceptionMatch",
    "PedagogyDecision",
    "PolyaCoach",
    "PolyaStage",
    "PolyaState",
    "REVEALS",
    "SlipKind",
    "SocraticCategory",
    "SolutionCoaching",
    "StageTransition",
    "ToneReport",
    "adapt_lthc",
    "decide_hint_level",
    "diagnose",
    "filter_tone",
    "focus_to_socratic_category",
    "mastery_to_level",
    "recommend_coaching",
    "recommend_coaching_for_solution",
    "select_category",
    "select_intervention",
    "visualize_misconception",
]
