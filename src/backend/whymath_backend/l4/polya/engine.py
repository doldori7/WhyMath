"""Polya 코칭 엔진 — 결정·조립 + L3 호출 좌석.

`PolyaCoach.decide()`는 *순수*(LLM 0회) — 학생 발화·상태 → `PedagogyDecision`.
`PolyaCoach.coach()`는 `LLMSeam`을 주입받아 결정 → 생성 → 톤필터까지 한 번에. L4→L3
호출은 *Protocol* 좌석으로 격리(L3 import 0 — 계층 분리 유지).

설계: 단계 전이 후 *다음 단계*의 프롬프트를 채워 반환(즉, "다음에 할 말"이 결정 결과).
`stay`면 현 단계 프롬프트(같은 질문을 다른 표현으로 재제시는 후속 — 슬라이스 1은 동일 본문).
"""

from __future__ import annotations

from whymath_backend.l4.hint_deferral import REVEALS, decide_hint_level
from whymath_backend.l4.models import (
    LLMSeam,
    PedagogyDecision,
    PolyaStage,
    PolyaState,
    ToneReport,
)
from whymath_backend.l4.polya.prompts import STAGE_PROMPTS
from whymath_backend.l4.polya.transitions import should_advance
from whymath_backend.l4.socratic import select_category
from whymath_backend.l4.tone_filter import filter_tone

_STAGE_ORDER: tuple[PolyaStage, ...] = (
    PolyaStage.UNDERSTAND,
    PolyaStage.PLAN,
    PolyaStage.EXECUTE,
    PolyaStage.REVIEW,
)


# 단계별 보조 행동 라벨 — UI/내부 후속 트리거 후보(스펙 §"인터페이스" L173).
# 슬라이스 1은 정적 매핑(학습자별 동적 조정은 L2 통합 후속).
_STAGE_ACTIONS: dict[PolyaStage, tuple[str, ...]] = {
    PolyaStage.UNDERSTAND: ("조건 나열", "목표 식별", "미지수 표시"),
    PolyaStage.PLAN: ("관점 선택", "전략 후보 나열", "유사 문제 회상"),
    PolyaStage.EXECUTE: ("단계별 적기", "막힘 보고", "중간 점검"),
    PolyaStage.REVIEW: ("검산", "다른 풀이 탐색", "메타인지 회상", "전이 시도"),
}


def _next_stage(current: PolyaStage) -> PolyaStage:
    """현 단계의 다음 단계. REVIEW면 자기 자신(종착)."""
    idx = _STAGE_ORDER.index(current)
    if idx == len(_STAGE_ORDER) - 1:
        return current
    return _STAGE_ORDER[idx + 1]


class PolyaCoach:
    """Polya 4단계 코칭 엔진.

    상태 비저장(stateless) — 모든 입력을 인자로 받는다. 세션 상태(`PolyaState`) 영속화는
    호출자(또는 후속 슬라이스의 세션 저장소) 책임.
    """

    def decide(self, student_input: str, state: PolyaState) -> PedagogyDecision:
        """LLM 없이 *결정*만. 다음 단계·프롬프트·system·권장 티어·보조 행동을 채운다.

        - 전이 판정 → next면 `_next_stage()`의 프롬프트, stay면 현 단계 프롬프트.
        - `socratic_category`: 단계·전이·발화 신호로 6카테고리 중 하나(슬라이스 2).
        - `hint_level`: 답 미루기 4단계 — 좌절·답요구·5회+ 막힘 신호로 점진 상승(슬라이스 3).
        - `reveals`: hint_level에서 파생된 노출량 라벨(KPI 입력).
        - `recommended_cost_tier=LOCAL`(기본 — Polya 코칭은 로컬 충분, CLAUDE.md "로컬 LLM 우선").
        """
        transition = should_advance(state, student_input)
        target_stage = (
            _next_stage(state.current_stage) if transition == "next" else state.current_stage
        )
        sp = STAGE_PROMPTS[target_stage]
        category = select_category(state.current_stage, transition, student_input)
        hint_level = decide_hint_level(
            student_input=student_input,
            turn_count=state.turn_count,
            prev_hint_level=state.prev_hint_level,
        )
        return PedagogyDecision(
            polya_stage_to_advance=transition,
            hint_level=hint_level,
            socratic_category=category.value,
            prompt=sp.prompt,
            system=sp.system,
            suggested_actions=list(_STAGE_ACTIONS[target_stage]),
            reveals=REVEALS[hint_level],
        )

    async def coach(
        self,
        student_input: str,
        state: PolyaState,
        *,
        llm: LLMSeam,
    ) -> tuple[PedagogyDecision, str, ToneReport]:
        """decide → LLM 생성 → 톤필터까지. 반환 = (결정, 필터된 응답, 톤보고).

        LLM 출력에 금지 패턴이 섞여 와도 `filter_tone`이 *마지막 방어선*으로 치환한다.
        `ToneReport.violations`가 비어있지 않으면 *프롬프트 회귀*(시스템 프롬프트 조정·
        provider 교체 신호 — KPI 추적).
        """
        decision = self.decide(student_input, state)
        raw = await llm.generate(decision.prompt, decision.system)
        filtered, report = filter_tone(raw)
        return decision, filtered, report
