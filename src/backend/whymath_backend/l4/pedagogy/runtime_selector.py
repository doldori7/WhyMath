"""실행용 교수법 선택기 — 학생 상태 → `PedagogyStrategy` + 교수학 게이트(2축).

설계 정본: `docs/architecture/04d_adaptive_pedagogy_engine.md` §2(Runtime Pedagogy Selector).

2단계 교수법 中 **②실행용**을 담당한다. ①설계용(DSL 생성 시 `pedagogy_pack`)과 달리, 이 모듈은
*학생이
공부하는 순간* 어떤 방식으로 보여줄지를 매번 다시 고른다 — 같은 개념이라도 계산 실수가 잦은 학생과
개념
이해가 부족한 학생에게 다른 방식이 가야 하기 때문이다. 고른 전략은 L3 렌더 어댑터(`l3/render/`)가
실행한다.

────────────────────────────────────────────────────────────────────────────
책임 분리 — 선택(효과) ≤ 게이트(허용)
────────────────────────────────────────────────────────────────────────────
`select()`는 "무엇이 이 학생에게 효과적인가"만 답한다. `gate()`는 "그것이 교수학적으로 허용되는가"를
판정해 위반 시 강등한다. **효과가 허용을 이길 수 없다** — 의사결정 우선순위상 비용·효율(#6)이
교수학적
정확성(#3)을 역전하지 못한다는 원칙의 기계적 실행이다(CLAUDE.md).

────────────────────────────────────────────────────────────────────────────
완전예제 2축 게이트 — 왜 두 축이 모두 필요한가
────────────────────────────────────────────────────────────────────────────
`WORKED_EXAMPLE`(완전예제)은 두 얼굴을 가진다. **초기 교수**로서의 완전예제는 Sweller의 worked
example
effect가 뒷받침하는 정당한 방식이고, 실제로 PROCEDURE 팩은 이를 *의도*한다(`fading_schedule`
`{worked:2, completion:2, solo:3}` — 완전예제 2회로 흐름을 보여준 뒤 점차 걷어낸다). 반면 **막힌
학생에게
던지는 완전예제**는 "막혔을 때 바로 정답 제공"이며 CLAUDE.md 절대 금기다.

두 상황을 가르는 것이 이 게이트의 핵심이다:

  축① **팩 금지(선행 차단)** — 팩이 `WORKED_EXAMPLE_FIRST`를 금지하면(실제 코퍼스에서는 CONCEPT
  하나)
       시도 전 단계의 완전예제를 막는다. 금지 모드 이름의 "FIRST"(선행)가 정확히 이 축이다.
       PROCEDURE는
       이를 금지하지 않으므로 페이딩 진입이 보존된다.
  축② **막힘 시 에스컬레이션** — 팩과 무관하게, 학생이 막힌 상황에서는 힌트 단계가 충분히 올라간
       뒤에만 완전예제를 허용한다. 기존 `hint_deferral.decide_hint_level`이 이미 "좌절·답요구·5회+
       막힘"을
       점진 상승으로 다루므로 새 카운터를 만들지 않고 그 산출(`hint_level`)을 그대로 읽는다.

**팩이 없어도 축②는 적용된다**(fail-safe) — 팩 조회 실패가 냉담 제공을 열어주면 안 된다.

────────────────────────────────────────────────────────────────────────────
계층 경계
────────────────────────────────────────────────────────────────────────────
L4 → L3(`l3/render/registry`) 하향 임포트는 합법이다(`api→l6→l5→l4→l3→l2→l1→schema`). 반대로 L3 렌더
어댑터는 이 모듈을 임포트하지 않는다 — 렌더는 "선택"을 모르고 "실행"만 한다(REND-01 인계 사항).

DB 세션에 의존하지 않는 순수 함수다(`pack_registry`가 DB-free인 것과 동형). 신호 조립(ORM 조회)은
호출자(API·하네스) 책임이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from whymath_backend.l3.render.registry import registered_strategies
from whymath_backend.l4.hint_deferral import HintLevel
from whymath_backend.l4.lthc.models import MasteryLevel
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.pedagogy.pack_registry import get_pack
from whymath_backend.schema.enums import PedagogyStrategy
from whymath_backend.schema.pedagogy_pack import PedagogyPack

# ──────────────────────────────────────────────────────────────────────────
# 튜닝 상수 — KPI 튜닝 대상이며 측정된 최적값이 아니다(socratic/select.py 관례).
# ──────────────────────────────────────────────────────────────────────────
# 시도 전 단계 — 여기서 완전예제를 주면 "선행"(WORKED_EXAMPLE_FIRST)이 된다.
# EXECUTE/REVIEW는 학생이 이미 손을 댄 뒤라 선행이 아니다.
_PRE_ATTEMPT_STAGES: frozenset[PolyaStage] = frozenset({PolyaStage.UNDERSTAND, PolyaStage.PLAN})

# 막힘 누적 임계 — `hint_deferral._STUCK_TURN_THRESHOLD`와 같은 축(스펙 "5회+ 막힘").
_STUCK_TURN_THRESHOLD = 5

# 완전예제가 "벌어진" 것으로 보는 최소 힌트 단계. 3 = 부분 단계 시연(`hint_deferral.REVEALS`).
# 즉 방향(1)·흐름(2)을 거친 뒤에만 완전예제가 열린다.
_EARNED_HINT_LEVEL = 3

# 강등 대상 — 말하기 대신 묻기. 어댑터가 항상 등록돼 있어 폴백이 실패하지 않는다.
_FALLBACK_STRATEGY = PedagogyStrategy.SOCRATIC

# 금지 모드 토큰 — `mode_guard`/`FORBIDDEN_MODE_VOCAB`와 같은 어휘를 쓴다(사후 가드의 사전 형제).
_MODE_WORKED_EXAMPLE_FIRST = "WORKED_EXAMPLE_FIRST"

# reason_code — 차단 사유(호출자 로깅·KPI 집계용).
REASON_PACK_FORBIDS_WORKED_FIRST = _MODE_WORKED_EXAMPLE_FIRST
"""팩이 완전예제 선행을 금지하는데 시도 전 단계에서 요청됨(축①)."""

REASON_HINT_NOT_ESCALATED = "HINT_NOT_ESCALATED"
"""막힌 학생에게 힌트 에스컬레이션 없이 완전예제가 요청됨(축② — 냉담 정답 제공)."""


@dataclass(frozen=True, slots=True)
class StudentSignals:
    """선택기 입력 — **실재하는(생산자가 있는) 신호만** 담는다.

    04d §2는 8개 입력(수준·오답유형·학습속도·집중도·학습시간·선호·성취도·직전결과)을 지정했으나,
    2026-07 실측 결과 그중 셋은 코드에 존재하지 않거나 생산자가 없다:

      - **집중도**(`LearningSession.focus_score`)·**학습시간**(세션 duration) — 컬럼은 있으나
      *쓰는 코드가
        없어 항상 NULL*이다.
      - **선호**(`MasteryState.preferred_solution_style`) — `MasteryState` 자체가 문서 스케치이며
      코드에
        존재하지 않는다.

    따라서 그 셋은 **필드로 만들지 않는다**. 항상 None인 필드를 두면 "읽고는 있다"는 착시를 주지만
    실제
    판단에는 아무 기여도 하지 못하기 때문이다(가짜 통과 금지). 해당 축이 필요해지면 *생산자를
    먼저* 만들고
    그때 필드를 연다.

    04d가 `StudentState` 값객체를 명시했으므로 dataclass로 묶는다. 형제 L4 결정 함수들
    (`recommend_coaching`·`PolyaCoach.decide`)은 flat kwargs 관례를 쓰지만, 여기서는 신호가 10개에
    달하고
    "무엇이 실재하고 무엇이 부재한가"를 한자리에 문서화하는 값이 더 커서 값객체를 택했다.
    """

    # ── 수준·성취도 (L2 BKT/IRT) ────────────────────────────────
    mastery_level: MasteryLevel | None = None
    """`lthc.adapt.mastery_to_level` 산출('초보'/'발전 중'/'숙달')."""
    bkt_mastery: float | None = None
    """BKT P(L) 0~1 — `l2.mastery_tracking.get_current_mastery`."""
    irt_theta: float | None = None
    """IRT θ — `l2.ability_tracking.get_current_theta`."""

    # ── 진행 상태 (세션 — 클라이언트가 왕복시키는 값) ──────────────
    polya_stage: PolyaStage = PolyaStage.UNDERSTAND
    """현재 Polya 단계. 시도 전/후를 가르는 축(게이트 축①)."""
    turn_count: int = 0
    """현재 단계 내 턴 수 — 막힘 누적 신호."""
    hint_level: HintLevel | None = None
    """`hint_deferral.decide_hint_level` 산출(1~4). 게이트 축②의 판정 재료."""

    # ── 직전 시도 결과 (L2 `problem_attempt`) ────────────────────
    last_attempt_correct: bool | None = None
    """직전 문제 정답 여부(`ProblemAttempt.is_correct`)."""
    time_vs_expected: float | None = None
    """소요시간/기대시간 비(1.0=평균·2.0=2배 느림). 학습 속도 대용."""
    used_hint: bool | None = None
    """직전 시도에서 힌트를 썼는지."""

    # ── 오개념 (L4 반응형 진단) ──────────────────────────────────
    misconception_ids: tuple[str, ...] = field(default=())
    """활성 오개념 가설 id(`l4.misconception.diagnose`/`hypothesis_store`). 비면 미검출."""

    @property
    def is_stuck(self) -> bool:
        """막힘 상태인지 — 힌트가 이미 올라갔거나 같은 단계에서 오래 맴돌면 막힌 것으로 본다.

        `hint_level`은 좌절·답요구·5회+ 막힘을 이미 종합한 값이라 2 이상이면 학생이 도움을
        구했다는 뜻이다
        (1=방향 제시는 기본값이므로 막힘 신호가 아니다).
        """
        if self.hint_level is not None and self.hint_level >= 2:
            return True
        return self.turn_count >= _STUCK_TURN_THRESHOLD

    @property
    def hint_escalated(self) -> bool:
        """완전예제를 열어도 되는 만큼 힌트가 올라갔는지(축② 판정)."""
        return self.hint_level is not None and self.hint_level >= _EARNED_HINT_LEVEL


@dataclass(frozen=True, slots=True)
class GateResult:
    """게이트 판정 — 예외가 아니라 *구조화 결과*로 돌려준다(`match_gate` 관례).

    `strategy`는 **최종 사용 가능한** 전략이다(차단 시 강등된 값). 호출자는 이 값을 그대로 렌더에
    넘기면
    되며, `allowed`/`reason_code`로 무슨 일이 있었는지 로깅·집계할 수 있다. 조용한 실패가 아니다.
    """

    strategy: PedagogyStrategy
    allowed: bool
    reason_code: str | None = None
    requested: PedagogyStrategy | None = None
    """게이트 이전에 요청됐던 전략(강등 시에만 채워짐 — 감사용)."""


def select(signals: StudentSignals) -> PedagogyStrategy:
    """학생 신호 → 교수법 전략(결정론 규칙표 v1). **허용 판정은 하지 않는다** — `gate()` 담당.

    우선순위(먼저 걸린 규칙이 이긴다):
      R1. 막힘 상태 → `WORKED_EXAMPLE` 제안. 실제 허용 여부는 게이트가 2축으로 판정한다(여기서 막지
          않는 이유: 선택은 *필요*를, 게이트는 *허용*을 담당하는 분리).
      R2. 오개념 가설 있음 → `ANALOGY`. 틀린 직관은 설명을 덧대기보다 다른 직관으로 재구성하는
      편이 낫다.
      R3. 직전 오답 + 초보 → `DIRECT`. 기반이 약한 학생에게 발문만 던지면 인지 부하만 커진다.
      R4. 숙달 → `PROBLEM_BASED`. 충분히 아는 학생에게는 문제를 먼저 줘 생산적 고투를 만든다.
      R5. 그 외 → `SOCRATIC`. "답이 아닌, 이유를 묻는" 기본값.

    **출력은 렌더 어댑터가 등록된 전략으로 제한된다.** 폐쇄 enum은 10종이지만 어댑터는 5종만 있어
    (REND-01), 미등록 전략을 고르면 호출자가 `LookupError`를 맞는다. 어댑터가 늘면 이 규칙표를 함께
    확장한다(거버넌스 테스트가 `select()` 출력 ⊆ 등록 전략을 동결한다).
    """
    # R1. 막힘 — 완전예제 제안(게이트가 최종 판정).
    if signals.is_stuck:
        return PedagogyStrategy.WORKED_EXAMPLE

    # R2. 오개념 가설 — 비유로 직관 재구성.
    if signals.misconception_ids:
        return PedagogyStrategy.ANALOGY

    # R3. 직전 오답 + 초보 — 설명 스캐폴딩.
    if signals.last_attempt_correct is False and signals.mastery_level == "초보":
        return PedagogyStrategy.DIRECT

    # R4. 숙달 — 문제 우선(생산적 고투).
    if signals.mastery_level == "숙달":
        return PedagogyStrategy.PROBLEM_BASED

    # R5. 기본 — 질문 중심.
    return PedagogyStrategy.SOCRATIC


def gate(
    strategy: PedagogyStrategy,
    signals: StudentSignals,
    *,
    pack: PedagogyPack | None = None,
) -> GateResult:
    """교수학 게이트 — 위반 전략을 강등한다(2축). 통과면 요청 전략 그대로.

    현재 판정 대상은 `WORKED_EXAMPLE` 한 축이다. 나머지 전략은 단일 응답 문면이 아니라 여러 턴의
    *시퀀스* 성질(페이딩·표현 전환 균형)이라 이 시점 판정이 불가능하다 — `mode_guard`가 같은 이유로
    6개 모드를 `DEFERRED_MODES`로 남긴 것과 동일한 정직한 공백이며, 조용히 통과시키는 것과 다르다.

    `pack=None`(팩 미적용·조회 실패)이어도 **축②는 적용된다** — 팩이 없다는 사실이 냉담 정답 제공을
    열어주면 안 된다(fail-safe).
    """
    if strategy is not PedagogyStrategy.WORKED_EXAMPLE:
        return GateResult(strategy=strategy, allowed=True)

    # 축① 팩 금지 — 시도 전 단계의 완전예제 "선행" 차단(실제 코퍼스에서는 CONCEPT 팩).
    forbids_worked_first = pack is not None and _MODE_WORKED_EXAMPLE_FIRST in pack.forbidden_modes
    if forbids_worked_first and signals.polya_stage in _PRE_ATTEMPT_STAGES:
        return GateResult(
            strategy=_FALLBACK_STRATEGY,
            allowed=False,
            reason_code=REASON_PACK_FORBIDS_WORKED_FIRST,
            requested=strategy,
        )

    # 축② 막힘 시 에스컬레이션 — 힌트가 부분 시연(3) 이상으로 올라간 뒤에만 허용.
    if signals.is_stuck and not signals.hint_escalated:
        return GateResult(
            strategy=_FALLBACK_STRATEGY,
            allowed=False,
            reason_code=REASON_HINT_NOT_ESCALATED,
            requested=strategy,
        )

    return GateResult(strategy=strategy, allowed=True)


def decide(signals: StudentSignals, *, k_type: str | None = None) -> GateResult:
    """선택 + 게이트 합성 — 호출자가 쓰는 단일 진입점.

    `k_type`(학습목표의 지식 유형)을 주면 해당 교수법 팩을 조회해 축①을 적용한다. 팩을 못 찾으면
    축①은 생략되고 축②만 적용된다(`gate()` fail-safe 참조).
    """
    pack = get_pack(k_type) if k_type is not None else None
    return gate(select(signals), signals, pack=pack)


def selectable_strategies() -> frozenset[PedagogyStrategy]:
    """이 선택기가 낼 수 있는 전략 집합 — 렌더 어댑터 등록분과 일치해야 한다.

    거버넌스 테스트가 `select()` 실제 출력이 이 집합에 속하는지, 그리고 이 집합이 L3 등록분과
    같은지를
    동결한다(선택기가 렌더 불가 전략을 내는 회귀 차단).
    """
    return registered_strategies()


__all__ = [
    "REASON_HINT_NOT_ESCALATED",
    "REASON_PACK_FORBIDS_WORKED_FIRST",
    "GateResult",
    "StudentSignals",
    "decide",
    "gate",
    "select",
    "selectable_strategies",
]
