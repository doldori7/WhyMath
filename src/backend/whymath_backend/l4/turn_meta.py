"""교수 결정 로그 — 턴 메타 파생·역산 (PED-04 D1·D2, 순수·LLM 0회).

`docs/architecture/ai_tutor_module_gap_review.md` §3 D1·D2 정본.

**왜 이 모듈이 있나**: 튜터는 매 턴 옳은 교수 결정을 *계산*하지만 그것을 *기록*하지 않았다.
`DialogueTurn`의 메타 4컬럼(`socratic_strategy`·`targeted_step`·`student_intent`·
`student_understanding_signal`)은 스키마·마이그레이션에 실재하는데 writer가 0이라, 튜터는
"지금 무엇을 할지"는 알아도 "지난번에 무엇을 했는지"를 기억하지 못했다.

**설계 원칙**:
- **재계산 0** — 여기 있는 함수는 전부 핸들러가 *이미 손에 든 값*을 컬럼 값 공간으로 옮기는
  사영(projection)이다. 새 추정기·새 결정을 만들지 않는다.
- **날조 0** — 생산자가 없는 축은 `None`(NULL)을 반환한다. 가짜 0·억지 매핑을 만들지 않는다.
- **복호 0** — 역산 함수는 평문 메타 컬럼만 입력으로 받는다. 학생 원문(봉투 암호화)을 열지 않는다.
- **L4 순수** — DB·HTTP를 모른다. 조회는 L5(`api/coach.py`)가 하고 여기엔 값만 들어온다
  (`_prerequisite_coaching_for`의 "L2 fetch + L4 decide" 선례 동형).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from whymath_backend.l4.hint_deferral import (
    DEMAND_ANSWER_TOKENS,
    FRUSTRATION_TOKENS,
    STUCK_TURN_THRESHOLD,
    has_any_token,
)
from whymath_backend.l4.misconception.models import InterventionDecision, InterventionPattern
from whymath_backend.l4.models import (
    PolyaStage,
    PolyaState,
    polya_stage_from_index,
    polya_stage_index,
)
from whymath_backend.l4.socratic import SocraticCategory
from whymath_backend.l4.socratic.select import INPUT_SIGNAL_TOKENS, STAGE_DEFAULT
from whymath_backend.schema.enums import SocraticStrategy, StudentIntent, TurnRole

__all__ = [
    "TurnMeta",
    "TurnMetaRow",
    "classify_student_intent",
    "compose_understanding_signal",
    "derive_polya_state",
    "derive_recent_categories",
    "detect_state_mismatch",
    "resolve_socratic_strategy",
]


class TurnMeta(NamedTuple):
    """한 턴에 적재할 메타 4축 봉투 — `_build_dialogue_turn`으로 넘기는 값.

    학생 턴과 AI 턴은 채우는 축이 다르다(컬럼 주석의 구획 그대로):
    - 학생 턴 → `student_intent`·`student_understanding_signal` (+`targeted_step`: 이 발화가
      어느 단계 맥락에서 나왔는지)
    - AI 턴   → `socratic_strategy`·`targeted_step`
    반대편 축이 NULL인 것은 결손이 아니라 *정의상 비어 있음*이다.
    """

    socratic_strategy: SocraticStrategy | None = None
    targeted_step: int | None = None
    student_intent: StudentIntent | None = None
    student_understanding_signal: float | None = None


class TurnMetaRow(NamedTuple):
    """역산 입력 — 이미 적재된 턴의 평문 메타 한 행(본문 컬럼 없음).

    L5가 `SELECT turn_order, role, targeted_step, student_intent`로 *컬럼 투영*해 만든다.
    ORM 엔티티를 통째로 로드하지 않는 것이 계약이다 — ciphertext를 메모리에 올리지 않기 위함
    (복호하지 않더라도 데이터 최소화).
    """

    turn_order: int
    role: TurnRole | None
    targeted_step: int | None
    student_intent: StudentIntent | None


# ──────────────────────────────────────────────────────────────────────────
# D1 writer — 이미 계산된 값 → 컬럼 값 공간
# ──────────────────────────────────────────────────────────────────────────

# 개입 패턴 → 발문 전략. 두 축은 각각 "무엇으로 흔들 것인가"(개입)와 "어떤 발문 형식으로
# 말할 것인가"(전략)라서 대응이 자연스럽다. 근거는 개입 문안 자체(`intervene.py`):
#   COUNTEREXAMPLE     — "반례 케이스일 때는 어떻게 돼?"        → 반례제시
#   REVERSE_REASONING  — "*원래 조건*에 부합하는지 거꾸로 확인"  → 조건확인
#   CONCRETE_CASE      — 패턴 2 구체 사례                        → 예시제시
#   VISUALIZATION      — 패턴 3 시각화 유도                      → 그래프그리기제안
_PATTERN_TO_STRATEGY: dict[InterventionPattern, SocraticStrategy] = {
    InterventionPattern.COUNTEREXAMPLE: SocraticStrategy.반례제시,
    InterventionPattern.REVERSE_REASONING: SocraticStrategy.조건확인,
    InterventionPattern.CONCRETE_CASE: SocraticStrategy.예시제시,
    InterventionPattern.VISUALIZATION: SocraticStrategy.그래프그리기제안,
}

# 개입이 없을 때의 단계 기본 전략 — 각 단계 발문의 *첫 요구*(`polya/prompts.py`)에서 읽었다.
#   UNDERSTAND "주어진 정보가 뭐야?(조건들)"  → 조건확인
#   PLAN       "비슷한 문제 본 적 있어?"       → 유사문제
#   EXECUTE    "천천히 단계별로 적어줘"        → 단계분해
#   REVIEW     "답이 합리적이야?(검산)"        → **대응 없음 → None**
# REVIEW를 억지로 채우지 않는 이유: 6종 중 검산·회고에 해당하는 값이 없다. 없는 대응을 만드는
# 것이 이 프로젝트가 금지한 "억지 매핑"이라, 정직하게 NULL로 둔다.
_STAGE_DEFAULT_STRATEGY: dict[PolyaStage, SocraticStrategy | None] = {
    PolyaStage.UNDERSTAND: SocraticStrategy.조건확인,
    PolyaStage.PLAN: SocraticStrategy.유사문제,
    PolyaStage.EXECUTE: SocraticStrategy.단계분해,
    PolyaStage.REVIEW: None,
}

# 답 미루기 2단계 이상의 노출 라벨 — 문자 그대로 "단계 흐름 노출"·"일부 단계 시연"이라
# 발문 전략이 `단계분해`로 수렴한다(`hint_deferral.REVEALS`).
_STEP_DECOMPOSITION_REVEALS: frozenset[str] = frozenset(
    {"step_flow", "partial_steps_demo", "full_solution"}
)

# 이 프로젝트의 현재 생산 경로에서 **실제로 도달 가능한** 전략 값. `select_intervention`이
# COUNTEREXAMPLE·REVERSE_REASONING 2종만 반환하므로(`l4/misconception/intervene.py`), 개입 경로
# 2종 + 단계 기본 3종에서 중복을 뺀 4종이 상한이다. 다양성 지표가 이 상한을 모르면 "6종 중 4종만
# 쓴다"를 품질 저하로 오독한다 — 측정 note에 이 집합을 싣는다(가짜 다양성·거짓 경보 방지).
REACHABLE_STRATEGIES: frozenset[SocraticStrategy] = frozenset(
    {
        SocraticStrategy.반례제시,
        SocraticStrategy.조건확인,
        SocraticStrategy.유사문제,
        SocraticStrategy.단계분해,
    }
)


def resolve_socratic_strategy(
    *,
    intervention: InterventionDecision | None,
    reveals: str,
    target_stage: PolyaStage,
) -> SocraticStrategy | None:
    """AI 턴이 *실제로 사용한* 발문 전략 — 이미 계산된 3값의 우선순위 사다리(재계산 0).

    **`SocraticCategory`(질문 유형)를 매핑하지 않는다.** 컬럼 타입 `SocraticStrategy`는 발문
    *전략*이고 `SocraticCategory`는 질문 *종류*로 서로 직교하는 enum 공간이다(gap_review §3 D1
    정정). 억지 매핑 대신 전략 축에 실제 생산자가 있는 값만 채운다.

    사다리:
      1. 개입 패턴이 있으면 그 패턴의 전략(개입이 이번 발화의 형식을 결정한다)
      2. 답 미루기 2단계 이상(`reveals`가 단계 노출 계열) → 단계분해
      3. 목표 Polya 단계의 기본 전략 — REVIEW는 대응 없어 None

    반환 None은 결손이 아니라 "이 턴에 대응하는 전략 값이 없음"이다(날조 금지).
    """
    if intervention is not None:
        mapped = _PATTERN_TO_STRATEGY.get(intervention.pattern)
        if mapped is not None:
            return mapped
    if reveals in _STEP_DECOMPOSITION_REVEALS:
        return SocraticStrategy.단계분해
    return _STAGE_DEFAULT_STRATEGY[target_stage]


# 이해도 신호 합성 가중(KPI 튜닝 대상·**미보정**). 가용한 축만 정규화 가중 평균한다.
_SIGNAL_WEIGHT_MASTERY = 0.5
_SIGNAL_WEIGHT_VERIFY = 0.3
_SIGNAL_WEIGHT_STUCK = 0.2


def compose_understanding_signal(
    *,
    mastery: float | None,
    verify_passed: bool | None,
    stuck_turns: int,
) -> float | None:
    """이해도 신호(0~1) — **기존 3신호의 결정론 합성**이지 새 추정기가 아니다.

    축(가용한 것만 가중 평균 → [0,1] 클램프 → 소수 2자리 반올림):
      · mastery(0.5) — BKT posterior 또는 클라 제출 숙달도. 없으면 축 제외.
      · verify(0.3)  — 이번 턴 검산 통과 1.0 / 실패 0.0. 풀이 미제출이면 축 제외.
      · stuck(0.2)   — `1 - stuck_turns/STUCK_TURN_THRESHOLD`(5회+ 막힘이면 0). 항상 가용.

    **보정되지 않았다**: 가중치·축 구성은 파일럿 이전 설계값이고 실학생 데이터로 검증된 바 없다.
    `Numeric(3,2)` 반올림이 여기서 일어나야 한다 — `DialogueTurnSchema`가 `ge=0 le=1`을 강제하므로
    클램프를 빠뜨리면 세션 생성이 ValidationError로 죽는다.

    가용 축이 하나도 없으면 `None`(NULL) — 가짜 0을 만들지 않는다. `stuck` 축은 항상 가용하므로
    실제로 None이 나오는 경로는 없지만, 축 구성이 바뀔 미래를 위해 계약으로 남긴다.
    """
    parts: list[tuple[float, float]] = []
    if mastery is not None:
        parts.append((_SIGNAL_WEIGHT_MASTERY, max(0.0, min(1.0, mastery))))
    if verify_passed is not None:
        parts.append((_SIGNAL_WEIGHT_VERIFY, 1.0 if verify_passed else 0.0))
    stuck_ratio = max(0.0, 1.0 - (max(0, stuck_turns) / STUCK_TURN_THRESHOLD))
    parts.append((_SIGNAL_WEIGHT_STUCK, stuck_ratio))

    total_weight = sum(w for w, _ in parts)
    if total_weight <= 0:
        return None
    weighted = sum(w * v for w, v in parts) / total_weight
    return round(max(0.0, min(1.0, weighted)), 2)


def classify_student_intent(
    *,
    student_input: str,
    has_solution: bool,
) -> StudentIntent | None:
    """학생 발화 → `StudentIntent` 5종(결정론·LLM 0회·기존 토큰셋 재사용).

    우선순위(보수적 — 강한 신호부터):
      1. 답 요구 토큰("그냥 답 알려줘") → **포기** — 자력 풀이를 그만두겠다는 의사 표시다.
         답 미루기가 발동하는 바로 그 지점이라 `hint_deferral`과 같은 토큰셋을 쓴다.
      2. 좌절 토큰("모르겠어요") → **막힘표현**
      3. 발화 신호 토큰(왜·근거·가정) → **질문** — `select_category` 규칙 1과 *같은*
         화이트리스트(`INPUT_SIGNAL_TOKENS`)를 쓴다. 진실원천 이중화 방지.
      4. 풀이 제출 있음 → **답시도**
      5. 그 외 비어있지 않은 발화 → **이해확인**(중립적 수긍·확인 발화의 잔여 범주)
      6. 빈 문자열 → **None** — 첫 진입 턴은 의도가 없다. 날조하지 않는다.

    5번이 잔여 범주라 분포가 이해확인 쪽으로 치우칠 수 있다. 이는 분류 실패가 아니라 정의이며,
    치우침 자체가 "의도 신호가 더 필요하다"는 측정 신호다(파일럿에서 분포로 확인).
    """
    text = student_input.strip()
    if not text:
        return StudentIntent.답시도 if has_solution else None
    if has_any_token(text, DEMAND_ANSWER_TOKENS):
        return StudentIntent.포기
    if has_any_token(text, FRUSTRATION_TOKENS):
        return StudentIntent.막힘표현
    for tokens, _category in INPUT_SIGNAL_TOKENS:
        if any(t in text for t in tokens):
            return StudentIntent.질문
    if has_solution:
        return StudentIntent.답시도
    return StudentIntent.이해확인


# 의도가 이 집합에 들면 그 턴의 카테고리는 단계 기본이 *아니었을 수* 있다(발화 신호 오버라이드).
# 회전 판정에서 이런 턴을 만나면 연속열을 끊는다 — 추정을 사실처럼 쓰지 않기 위한 보수적 절단.
_OVERRIDE_SUSPECT_INTENTS: frozenset[StudentIntent] = frozenset(
    {StudentIntent.질문, StudentIntent.막힘표현, StudentIntent.포기}
)


# ──────────────────────────────────────────────────────────────────────────
# D1 reader ① / D2 — 평문 메타에서 역산 (복호 0)
# ──────────────────────────────────────────────────────────────────────────


def derive_recent_categories(
    rows: Sequence[TurnMetaRow],
    *,
    window: int = 3,
) -> tuple[SocraticCategory, ...]:
    """적재된 메타에서 **직전 AI 턴들의 기본 카테고리 꼬리 연속열**을 복원한다(시간순).

    복원 방법: `targeted_step` → Polya 단계 → `STAGE_DEFAULT` 사영. 학생 원문을 보지 않으므로
    **복호 0**이고, 딕셔너리 조회일 뿐이라 결정 재실행도 아니다.

    **보수적 절단** — 꼬리에서 역방향으로 걷다가 다음을 만나면 즉시 멈춘다:
      · `targeted_step`이 NULL인 AI 턴(구 데이터·미기록 턴)
      · 직전 학생 턴의 의도가 오버라이드 의심(`질문`/`막힘표현`/`포기`) — 그 턴의 카테고리는
        발화 신호 오버라이드였을 수 있어 기본값 사영이 틀릴 수 있다

    **남는 오차와 그 영향**: 고신뢰 가설 오버라이드(→ASSUMPTION)가 걸렸던 턴은 의도로 표식되지
    않아 기본값이었던 것처럼 복원될 수 있다. 그러나 회전은 규칙 ①②보다 아래라, 지금도 가설이
    살아 있으면 규칙 ②가 먼저 반환한다. 거짓 회전이 실제로 발동하려면 "과거엔 고신뢰 가설이
    있었고 지금은 없다"가 성립해야 하고, 그때의 결과는 같은 단계의 *차선* 카테고리를 쓰는 것뿐
    이다 — 단계 골격·전이·정답 노출 불변이라 교수학적 손해가 없다.
    """
    intent_by_order = {
        row.turn_order: row.student_intent for row in rows if row.role == TurnRole.student
    }
    assistant_rows = sorted(
        (row for row in rows if row.role == TurnRole.assistant), key=lambda r: r.turn_order
    )

    collected: list[SocraticCategory] = []
    for row in reversed(assistant_rows):
        stage = polya_stage_from_index(row.targeted_step)
        if stage is None:
            break
        # 세션 경로는 학생 턴 → AI 턴 순으로 쌍을 적재한다(turn_order n, n+1).
        paired_intent = intent_by_order.get(row.turn_order - 1)
        if paired_intent in _OVERRIDE_SUSPECT_INTENTS:
            break
        collected.append(STAGE_DEFAULT[stage])
        if len(collected) >= window:
            break
    return tuple(reversed(collected))


def derive_polya_state(
    rows: Sequence[TurnMetaRow],
    *,
    prev_hint_level: int | None,
) -> PolyaState:
    """적재된 메타에서 **서버 소유** Polya 상태를 파생한다(D2·신규 컬럼 0).

    - `current_stage` — 마지막 AI 턴의 `targeted_step`. 이력이 없으면 UNDERSTAND(새 세션 기본).
    - `history` — 단계가 바뀔 때마다 *전이 직전* 단계를 append(`PolyaState` 계약 그대로).
    - `turn_count` — 현재 단계의 꼬리 연속 AI 턴 수(전이 시 0 리셋 의미 충족).
    - `prev_hint_level` — 인자 주입(`attempt_event(힌트제공)` 조회는 L5 책임).

    왜 서버가 소유하나: 이 세 값은 S3 파일럿 KPI(전환 지표·도달 깊이·막힘 턴)의 입력인데,
    지금까지 **클라이언트가 매 턴 실어 보냈다**. 측정이 클라 버그·조작에 열려 있었다는 뜻이다.
    """
    stages = [
        stage
        for row in sorted(rows, key=lambda r: r.turn_order)
        if row.role == TurnRole.assistant
        and (stage := polya_stage_from_index(row.targeted_step)) is not None
    ]
    if not stages:
        return PolyaState(prev_hint_level=prev_hint_level)

    history: list[PolyaStage] = []
    for previous, current in zip(stages, stages[1:], strict=False):
        if previous != current:
            history.append(previous)

    current_stage = stages[-1]
    turn_count = 0
    for stage in reversed(stages):
        if stage != current_stage:
            break
        turn_count += 1

    return PolyaState(
        current_stage=current_stage,
        history=history,
        turn_count=turn_count,
        prev_hint_level=prev_hint_level,
    )


# 클라↔서버 비교 축. `history`는 제외한다 — 클라가 안 보내는 것이 정상이라 노이즈만 만든다.
_MISMATCH_FIELDS: tuple[str, ...] = ("current_stage", "turn_count", "prev_hint_level")


def detect_state_mismatch(client: PolyaState, server: PolyaState) -> tuple[str, ...]:
    """클라 제출 상태와 서버 파생 상태가 어긋난 **필드명**들(빈 tuple = 일치).

    값이 아니라 필드명을 반환하는 이유: 호출자가 로그·플래그를 만들 때 "무엇이 어긋났는가"만
    있으면 충분하고, 값까지 흘리면 로그 표면이 넓어진다(값은 호출자가 필요할 때 직접 싣는다).
    """
    return tuple(
        name
        for name in _MISMATCH_FIELDS
        if getattr(client, name, None) != getattr(server, name, None)
    )


def stage_to_targeted_step(stage: PolyaStage) -> int:
    """Polya 단계 → `targeted_step` 값(1~4). 스키마가 `ge=1`이라 1-기반이 계약이다."""
    return polya_stage_index(stage)
