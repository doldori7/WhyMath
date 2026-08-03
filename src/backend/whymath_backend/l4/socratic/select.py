"""Polya 단계 × 전이 → 소크라테스 카테고리 선택 — 결정론적 규칙(LLM 0회).

스펙 §"PRD Socratic 풀이 흐름과의 정렬"(L72-90)이 두 축의 직교성을 정의한다:
*Polya 단계*는 콘텐츠 전개 마디, *소크라테스 6카테고리*는 매 발화의 질문 종류.
이 모듈은 단계·전이·학생 발화 신호로 **다음 발화의 질문 종류**를 고른다.

규칙 핵심(보수적):
- next 전이 → 새 단계 *진입 발화*의 카테고리(단계별 기본·오버라이드 없음)
- stay/previous 전이 → ① 학생 발화 신호 ② 고신뢰 활성 오개념 가설 ③ 단조 발문 회전 ④ 단계 기본 순
- 단계 기본 매핑(스펙 L82-87 표 + L4 6카테고리 본문 정합):
    UNDERSTAND → CLARIFICATION ("어디까지 이해됐어?" — 명료화)
    PLAN       → PERSPECTIVE   (스펙 L84 "관점 선택" 마디 = PERSPECTIVE)
    EXECUTE    → IMPLICATION   ("그러면 다음은?" — 단계별 진전)
    REVIEW     → META          ("어떻게 도달했어?" — 메타인지)

학생 발화 신호 오버라이드(stay/previous 한정·키워드 화이트리스트, 단계와 무관):
- "왜·이유·근거·증명" 등 → EVIDENCE (근거 질문 신호 우선)
- "가정·라고 치"·"라고 하" 등 → ASSUMPTION

활성 오개념 가설 오버라이드(stay/previous 한정·학생 명시 신호가 *없을 때만*·pedagogy-designer 설계):
학생이 머무르며 막혀 있고 *고신뢰 + 최근* 활성 오개념 가설이 있으면 → **ASSUMPTION**으로 그 (잘못된)
*가정을 표면화*해 학생이 스스로 점검하게 한다(LTHC 최소도움·메타인지·자기 발견). 오개념은
본질적으로 "틀린 전제를 참으로 *가정*"한 상태라 ASSUMPTION("왜 그렇게 가정했어?")이 정확히 그
전제를 겨눈다(EVIDENCE는 *결론의 근거*를 물어 한 겹 어긋남). **금기 안전**: 반환은 *카테고리
enum*뿐(정답·"틀렸다"·발화 본문 생성 0·misconception_id 미노출). 가설이 없거나 저신뢰/오래된
증거면 *현 동작 완전 불변*(맞은 학생 영향 0·하위호환). 임계값은 KPI 튜닝 대상(아래 상수·정직).
"""

from __future__ import annotations

from collections.abc import Sequence

from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.models import PolyaStage, StageTransition, next_polya_stage
from whymath_backend.l4.socratic.categories import SocraticCategory

# 단계 기본 카테고리 — 스펙 L82-87 PRD 정렬표 + L4 본문(L65-70) 정합.
# PED-04: `l4/turn_meta.derive_recent_categories`가 적재된 `targeted_step`을 카테고리로 사영할 때
# *이 표*를 쓴다(사영 규칙 이중 정의 방지) — 그래서 공개 상수다.
STAGE_DEFAULT: dict[PolyaStage, SocraticCategory] = {
    PolyaStage.UNDERSTAND: SocraticCategory.CLARIFICATION,
    PolyaStage.PLAN: SocraticCategory.PERSPECTIVE,
    PolyaStage.EXECUTE: SocraticCategory.IMPLICATION,
    PolyaStage.REVIEW: SocraticCategory.META,
}


# 발화 신호 오버라이드(stay 한정). 단계 기본보다 *학생 발화 내용*이 더 강한 신호.
# 매핑 순서 의미 있음 — 가장 구체적인 신호(가정 탐색)를 먼저 검사.
# PED-04: `l4/turn_meta.classify_student_intent`가 *같은* 화이트리스트로 `질문` 의도를 분류하므로
# 공개 상수(`INPUT_SIGNAL_TOKENS`)로 승격했다 — 토큰셋 이중 정의(진실원천 2개) 방지. 값·순서 불변.
INPUT_SIGNAL_TOKENS: tuple[tuple[frozenset[str], SocraticCategory], ...] = (
    (
        frozenset({"가정", "라고 치", "라고 하면", "라고 두"}),
        SocraticCategory.ASSUMPTION,
    ),
    (
        frozenset({"왜", "이유", "근거", "증명", "보장"}),
        SocraticCategory.EVIDENCE,
    ),
)

# 활성 오개념 가설 오버라이드 임계(pedagogy-designer 설계·KPI 튜닝 대상·측정 최적값 아님).
# floor 0.65: 가지치기 생존선(_PRUNE_THRESHOLD=0.1)보다 *훨씬* 높아 "표면화할 만큼 확신"을 보수적
# 으로 요구(약한 가설 과조향 방지·오진단 비용 억제). recency≤2(=_HALF_LIFE_TURNS//2): confidence가
# 아직 높아도 *최근 증거가 끊긴* 가설은 거부 — "지금 작동 중인 가정"만 겨냥(낙인 방지 승계).
_HYPOTHESIS_CONFIDENCE_FLOOR: float = 0.65
_HYPOTHESIS_RECENCY_LIMIT: int = 2


# 단조 발문 회전(PED-04 D1 reader ①) — 같은 카테고리가 이만큼 연속되면 *차선* 카테고리로 돈다.
# 3인 이유: 같은 질문 종류 2회는 아직 "다시 묻기"(정상 코칭)지만, 3회부터는 학생이 같은 벽을 보고
# 있는데 튜터가 각도를 바꾸지 못한 상태다. KPI 튜닝 대상(측정 최적값 아님·정직).
_ROTATION_STREAK: int = 3

# 단계별 *차선* 카테고리 — 기본 카테고리가 막혔을 때 바꿔 볼 각도(결정론·6카테고리 내).
# 선정 근거(기본 발문이 통하지 않았다는 것 자체가 정보):
#   UNDERSTAND: 명료화가 안 통함 → 학생이 *무엇을 근거로* 그렇게 읽었는지(EVIDENCE)
#   PLAN:       관점 제시가 안 통함 → 깔고 있는 *전제*를 표면화(ASSUMPTION)
#   EXECUTE:    "그러면 다음은?"이 안 통함 → 어디까지 됐는지로 되돌림(CLARIFICATION)
#   REVIEW:     메타 회고가 안 통함 → *다른 관점*의 풀이로 되돌아보게(PERSPECTIVE)
# 정답·"틀렸다"는 여전히 생성 0(반환은 카테고리 enum뿐).
_STAGE_ALTERNATE: dict[PolyaStage, SocraticCategory] = {
    PolyaStage.UNDERSTAND: SocraticCategory.EVIDENCE,
    PolyaStage.PLAN: SocraticCategory.ASSUMPTION,
    PolyaStage.EXECUTE: SocraticCategory.CLARIFICATION,
    PolyaStage.REVIEW: SocraticCategory.PERSPECTIVE,
}


def _has_high_confidence_active_hypothesis(
    hypotheses: Sequence[MisconceptionHypothesis],
) -> bool:
    """고신뢰 + 최근 활성 가설이 하나라도 있는가(confidence≥floor AND recency≤limit·순수).

    `hypotheses`는 confidence 내림차순 정렬 가정(저장소 `curate` 계약). 선두부터 검사하되,
    confidence가 floor 미달이면 *이후 전부 미달*이라 조기 종료(`break`). recency만 미달인 가설은
    *건너뛰고*(`continue`) 차순위를 본다 — 선두가 stale해도 고신뢰·최근 차순위를 놓치지 않게
    (정렬 단조성은 confidence에만 적용·recency는 비단조). 입력 비변형(읽기만).
    """
    for hyp in hypotheses:
        if hyp.confidence < _HYPOTHESIS_CONFIDENCE_FLOOR:
            break  # 내림차순 — 이후 confidence는 모두 미달.
        if hyp.turns_since_evidence <= _HYPOTHESIS_RECENCY_LIMIT:
            return True
        # confidence는 충분하나 증거가 오래됨(stale) → 차순위 검사.
    return False


def select_category(
    stage: PolyaStage,
    transition: StageTransition,
    student_input: str,
    hypotheses: Sequence[MisconceptionHypothesis] | None = None,
    recent_categories: Sequence[SocraticCategory] = (),
) -> SocraticCategory:
    """현재 단계·전이·학생 발화·활성 오개념 가설에서 다음 발화의 소크라테스 카테고리를 고른다.

    - `next` → 다음 단계의 기본 카테고리(단계 진입 발화·오버라이드 없음).
    - `stay`/`previous` → ① 학생 발화 신호(가정·근거) ② *고신뢰+최근* 활성 오개념 가설
      (→ASSUMPTION) ③ **단조 발문 회전**(기본 카테고리 3연속 → 차선) ④ 현 단계 기본 순.
      `hypotheses` None/빈/전부 저신뢰·stale → ②를 건너뛰어 현 동작 불변(하위호환).

    `recent_categories`(PED-04 D1 reader ①·기본 `()`=잠듦)는 **직전 AI 턴들의 카테고리 꼬리
    연속열**(시간순)이다. 세션 경로가 `DialogueTurn.targeted_step` 이력에서 서버 파생해 넘긴다
    (`l4/turn_meta.derive_recent_categories` — 원문 복호 0). 회전은 규칙 ①②보다 **아래**라
    학생이 직접 물었거나 고신뢰 가설이 살아 있으면 그쪽이 이긴다.

    **회전 발동 조건을 좁게 잡은 이유**: 꼬리 `_ROTATION_STREAK`개가 *이번에 반환하려는 바로 그
    기본값*과 전부 같을 때만 회전한다. "직전 3개가 무언가로 같다"만 보면, 이력이 다른 값으로
    채워진 상황에서 엉뚱한 회전이 발동해 단계 골격을 흔든다.
    """
    target_stage = next_polya_stage(stage) if transition == "next" else stage

    # 규칙 0: next 진입 발화는 오버라이드 없음(가설·신호 둘 다 무시·단계 골격 보존).
    if transition == "next":
        return STAGE_DEFAULT[target_stage]

    # 규칙 1(최우선): 학생 명시 발화 신호 — 학생이 *직접 물은* 질문을 존중(기존 동작 보존).
    for tokens, category in INPUT_SIGNAL_TOKENS:
        if any(t in student_input for t in tokens):
            return category

    # 규칙 2: 고신뢰+최근 활성 오개념 가설 → 가정 표면화(ASSUMPTION).
    if hypotheses and _has_high_confidence_active_hypothesis(hypotheses):
        return SocraticCategory.ASSUMPTION

    default = STAGE_DEFAULT[target_stage]

    # 규칙 2.5(PED-04): 단조 발문 회전 — 꼬리 3턴이 *이 기본값 그대로*였다면 각도를 튼다.
    tail = tuple(recent_categories)[-_ROTATION_STREAK:]
    if len(tail) == _ROTATION_STREAK and all(c == default for c in tail):
        return _STAGE_ALTERNATE[target_stage]

    # 규칙 3: 단계 기본(현 동작).
    return default
