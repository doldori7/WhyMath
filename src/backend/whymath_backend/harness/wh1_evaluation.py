"""WH-1 튜터링 하네스 0단계 — 대리 지표 7종 베이스라인 좌석.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4. WH-1(소크라테스 튜터링
하네스) 도입의 **0단계**는 "측정 없는 도입 없음"(설계안 제1원칙)에 따라 *대리 지표 7종*을
계측하는 것이다. 산출물은 **"커버리지 맵 + 베이스라인 수치"** — 무엇을 *지금* 잴 수 있고,
무엇이 *아직* 못 재는지를 한 번에 보여 주는 골격이다.

정직성 원칙(CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지"·설계안 "측정 없는 도입 없음"):
  현재 코드/데이터로 *계측 가능한* 지표만 실값으로 내고, *미계측* 지표는 **가짜 0/stub을
  내지 않는다**. 각 지표는 `value(float|None)` + `status(MetricStatus)` + `note(한국어)`로
  구성해, 미계측 지표는 `value=None` + 상태 enum + "무엇이 필요한지"로 갭을 가시화한다. 이
  좌석 자체가 *측정 인프라의 골격*이며, 아직 무엇이 계측 불가인지를 정직하게 드러내는 게
  목적이다(0/stub은 날조다).

7종 대리 지표 커버리지(설계안 §8.4):
  ① verify 통과율          — 🟢 MEASURED/NO_DATA: attempt_event(event_type=검산결과)의
                             passed=거짓 수치관계 *미적발* 비율(binary 검산·3-state 아님).
  ② 진단-실제 오개념 일치율 — 🔴 REQUIRES_DATA: ground-truth 오개념 라벨 부재.
  ③ 세션 완주율            — 🟢 MEASURED: LearningSession.ended_at NOT NULL 비율.
  ④ 턴당 토큰              — 🟡 MEASURED/NO_DATA: Dialogue.total_tokens/total_turns 평균.
  ⑤ 도움 감소 곡선         — 🟡 MEASURED/NO_DATA: attempt_event(event_type=힌트제공)의
                             hint_level 시계열 OLS 기울기(음수=도움 감소). raw ⑤는 R15 미반영
                             이나, *파생 결합 판정* `help_reduction_validated`(R15)가 정답률
                             추세(ProblemAttempt.is_correct OLS)와 교차해 진짜 개선 vs 교정기
                             함정(힌트 회피)을 가린다(새 적재 0·기존 신호 결합만).
  ⑥ 보정 점수(Brier)      — 🔴 REQUIRES_TOOL: elicit_prediction 도구 미구현.
  ⑦ 전이 점수             — 🔴 REQUIRES_TOOL: 시그니처 패턴 태깅·전이 출제 미구현.

계층 메모(CLAUDE.md 7계층·설계안 §1): WH-1 하네스는 *새 계층이 아니라 횡단 인프라*다. 본
모듈은 L1(활동 로그 `LearningSession`)·L2/L5(대화 `Dialogue`) 데이터를 *조회만* 하고(역방향
의존 없음·ORM/쿼리빌더만·원시 SQL 문자열 회피), 노출은 L5(`api/me`)가 담당한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import (
    AttemptEvent,
    LearningSession,
    ProblemAttempt,
)
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.schema.enums import EventType

__all__ = [
    "HelpReductionValidation",
    "Metric",
    "MetricStatus",
    "R15Verdict",
    "SurrogateMetrics",
    "compute_wh1_surrogate_metrics",
]


# ⑤ 도움 감소 곡선 OLS 기울기의 *최소 종단 표본*. 이보다 적으면 NO_DATA(날조 회피).
# 종단 지표는 점이 2개뿐이면 기울기가 의미를 갖지 못하므로(과적합·노이즈) 최소 3점을 요구한다.
_MIN_SLOPE_POINTS = 3


def _ols_slope(ys: list[float]) -> float | None:
    """순서 인덱스 x(0..n-1) 대 ys의 OLS 단순선형회귀 기울기(순수·날조 0).

    x는 0,1,2,…,n-1(등차 적재/측정 순서), y는 `ys`다. 기울기 = Σ(x-x̄)(y-ȳ)/Σ(x-x̄)².
    종단 표본 가드: 유효 포인트가 `_MIN_SLOPE_POINTS` 미만이거나 x 분산이 0이면 **None**을
    반환한다(가짜 0/날조 기울기 금지). x는 0..n-1 등차라 n>=2면 분산은 항상 양수지만,
    방어적으로 0 분산도 None으로 막는다(이론적 경계).

    ⑤ 도움 감소 곡선(hint_level 시계열)·R15 정답률 추세(is_correct 1/0 시계열)가 공유하는
    OLS 코어 — 음수=하락 추세·양수=상승 추세·0=평탄(실측된 평탄이지 날조 0이 아니다).
    """
    n = len(ys)
    if n < _MIN_SLOPE_POINTS:
        return None
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    x_var = sum((x - x_mean) ** 2 for x in xs)
    if x_var == 0:  # 방어적 — n>=2 등차 인덱스면 도달 불가하나 분산 0이면 None(날조 회피).
        return None
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    return covariance / x_var


class MetricStatus(str, Enum):
    """대리 지표 1종의 계측 상태 — 실값/미계측 사유를 정직하게 구분(0/stub 금지).

    `MEASURED`만 `value`가 실수이고, 나머지 4종은 모두 `value=None`(날조 회피). 미계측 사유를
    상태로 분리해 *무엇을 만들면 잴 수 있는지*(이벤트 적재·라벨·도구)를 커버리지 맵으로 드러낸다.
    """

    MEASURED = "measured"
    """🟢 실측 — 현재 데이터로 계측 완료. `value`에 실수 베이스라인."""

    NO_DATA = "no_data"
    """🟡 좌석은 있으나 데이터 0 — 계측 *경로*는 살아 있고 표본이 없을 뿐(graceful None).

    표본이 쌓이면 그대로 `MEASURED`가 된다(③ 세션 0건·④ 토큰 미적재 행 0건). 미계측(코드
    부재)과 *구분*되는 정직 상태 — 0으로 채우지 않는다.
    """

    NOT_INSTRUMENTED = "not_instrumented"
    """🔴 이벤트 미적재 — 신호 자체가 어디에도 기록되지 않음(verify_result·힌트 시계열).

    계측하려면 *적재 좌석*(이벤트/시계열 컬럼)을 먼저 만들어야 한다 — 다른 슬라이스 책임.
    """

    REQUIRES_DATA = "requires_data"
    """🔴 ground-truth 라벨 부재 — 신호는 있으나 *정답(실제)* 라벨이 없어 일치율을 못 냄.

    문항-오개념 태깅·정답 라벨 코퍼스가 채워져야 계측 가능(② 진단-실제 오개념 일치율).
    """

    REQUIRES_TOOL = "requires_tool"
    """🔴 미구현 도구 — 측정에 필요한 *도구/출제*가 아직 없음(elicit_prediction·전이 출제).

    도구가 구현돼 신호를 생산해야 계측 가능(⑥ 보정 점수·⑦ 전이 점수).
    """


class Metric(BaseModel):
    """대리 지표 1종 — 실값 또는 미계측 사유. 미계측은 `value=None`(날조 금지·0/stub 금지).

    `MEASURED`/`NO_DATA`만 계측 경로가 살아 있고, 미계측 3종(NOT_INSTRUMENTED·REQUIRES_DATA·
    REQUIRES_TOOL)은 `value=None` + `note`로 "무엇이 필요한지"를 한국어로 밝힌다.
    """

    value: float | None = Field(
        default=None,
        description="실측값(MEASURED). 미계측·표본 0이면 None(가짜 0 금지).",
    )
    status: MetricStatus = Field(description="계측 상태 — 실값/미계측 사유 구분.")
    note: str = Field(description="한국어 설명 — 무엇이 필요/근거(미계측이면 적재·라벨·도구).")


class R15Verdict(str, Enum):
    """R15 결합 판정 — ⑤ 도움 감소를 *정답률 추세와 교차*해 "진짜 개선"인지 가린다.

    설계안 §11.2 R15: "도움 감소를 *정답률 유지와 결합 판정* — 힌트 회피만으로는 개선 인정
    안 함". 즉 도움(hint_level)이 줄어도 정답률이 *같이* 떨어지면 그건 *힌트 회피/방치*(교정기
    함정)이지 실력 향상이 아니다. 이 enum은 ⑤ 기울기 부호와 정답률 기울기 부호의 *교차*로
    내는 판정이다(경계 0 기준·tolerance 없음). 종단·표본 의존·이탈/무작위 신호 미반영은
    한계로 note에 정직 표기한다(R15 완전판정이 아니다).
    """

    GENUINE_IMPROVEMENT = "genuine_improvement"
    """진짜 개선 — 도움↓·정답률 유지/↑(힌트 회피가 아니라 실력으로 도움이 줄었다)."""

    GAMING_SUSPECT = "gaming_suspect"
    """교정기 함정 경보 — 도움↓이나 정답률↓(힌트 회피/방치 의심·실력 향상 아님)."""

    NO_HELP_REDUCTION = "no_help_reduction"
    """도움이 줄지 않음(기울기 >= 0) — 애초에 개선 신호가 아니다(판정 대상 밖)."""

    INSUFFICIENT_DATA = "insufficient_data"
    """도움/정답률 한쪽이라도 종단 표본 부족 — 교차검증 불가(날조 판정 금지)."""


class HelpReductionValidation(BaseModel):
    """R15 결합 판정 결과 — ⑤ 도움 감소(help_slope)와 정답률 추세(accuracy_slope)의 교차.

    ⑤ raw 도움 감소 기울기만으로는 *힌트 회피*(틀려도 레벨이 낮아짐)와 *실력 향상*을 구분
    못 한다(⑤ note의 R15 미반영 한계). 이 모델은 정답률 추세(`ProblemAttempt.is_correct`의
    OLS 기울기)를 교차해 verdict를 낸다 — 도움↓·정답률 유지/↑면 GENUINE_IMPROVEMENT,
    도움↓·정답률↓면 GAMING_SUSPECT. 정답률 신호로 ①(검산 미적발 proxy)이 아니라 *실제
    정답률*인 `is_correct`를 쓰는 이유: R15의 "정답률"에 직접 대응하고 ① 대비 더 직접적이다
    (①은 풀이 제출 턴의 수치 검산 통과 proxy일 뿐).

    한계(정직 표기): 종단·표본 의존(한쪽이라도 _MIN_SLOPE_POINTS 미만이면 INSUFFICIENT_DATA)·
    경계는 slope 0(tolerance 없음)·이탈/무작위/난이도 변화 신호 미반영. R15 완전판정이 아니다.
    """

    verdict: R15Verdict = Field(description="R15 결합 판정 — 도움↓·정답률 교차 결과.")
    help_slope: float | None = Field(
        default=None,
        description="⑤ 도움 감소 OLS 기울기(raw·음수=도움 감소). 표본 부족이면 None(날조 0 금지).",
    )
    accuracy_slope: float | None = Field(
        default=None,
        description="정답률(is_correct 1/0) OLS 기울기(양수=상승). 표본 부족이면 None(날조 0).",
    )
    note: str = Field(description="한국어 판정 근거 — 임계(slope 0)·교차 결과·한계.")


class SurrogateMetrics(BaseModel):
    """WH-1 0단계 대리 지표 7종 + 표본 메타 — 커버리지 맵 한 장.

    계측 가능분(① verify 통과율·③ 세션 완주율·④ 턴당 토큰)은 실값(또는 표본 0이면 NO_DATA),
    미계측 4종(②⑤⑥⑦)은 고정 상태 + note로 갭을 표면화한다. 메타(표본 수·시간창·user 스코핑)로
    이 베이스라인이 *어느 모집단/기간*을 잰 것인지 함께 기록한다.
    """

    # ── 7종 대리 지표 ──
    verify_pass_rate: Metric = Field(
        description="① verify 통과율 — 검산결과 이벤트 중 passed=거짓관계 미적발 비율(binary)."
    )
    diagnosis_agreement_rate: Metric = Field(
        description="② 진단-실제 오개념 일치율 — 진단 오개념 vs ground-truth 라벨."
    )
    session_completion_rate: Metric = Field(
        description="③ 세션 완주율 — LearningSession 중 ended_at 채워진 비율(실측)."
    )
    tokens_per_turn: Metric = Field(
        description="④ 턴당 토큰 — Dialogue.total_tokens/total_turns 평균(실측·비용 대리)."
    )
    help_reduction_slope: Metric = Field(
        description="⑤ 도움 감소 곡선 — 시간에 따른 힌트 의존 감소 기울기."
    )
    calibration_brier: Metric = Field(
        description="⑥ 보정 점수(Brier) — 자기 예측 확신도 vs 실제 정오답."
    )
    transfer_score: Metric = Field(
        description="⑦ 전이 점수 — 학습 직후 미학습 시그니처 패턴 전이 출제 정답률."
    )

    # ── R15 파생 결합 판정(⑤ 도움 감소 × 정답률 추세) ──
    help_reduction_validated: HelpReductionValidation = Field(
        description=(
            "R15 결합 판정 — ⑤ 도움 감소를 정답률(is_correct) 추세와 교차해 진짜 개선 vs "
            "교정기 함정(힌트 회피) 가림. ⑤ raw 기울기를 *검증*한 파생 신호(새 적재 0)."
        )
    )

    # ── 표본·범위 메타 ──
    sample_sessions: int = Field(
        default=0, description="③ 집계 대상 LearningSession 수(시간창·user 필터 적용)."
    )
    sample_dialogues: int = Field(
        default=0, description="④ 집계 대상 Dialogue 수(토큰·턴 채워진 행만)."
    )
    sample_verify_events: int = Field(
        default=0,
        description="① 집계 대상 검산결과 attempt_event 수(passed 채워진 행).",
    )
    sample_hint_events: int = Field(
        default=0,
        description="⑤ 집계 대상 힌트제공 attempt_event 수(hint_level 채워진 행·OLS 포인트 수).",
    )
    sample_accuracy_attempts: int = Field(
        default=0,
        description=(
            "R15 정답률 추세 집계 대상 ProblemAttempt 수(is_correct NOT NULL·OLS 포인트 수)."
        ),
    )
    window_start: datetime | None = Field(
        default=None, description="집계 시간창 시작(since·생략 시 None=무한 과거)."
    )
    window_end: datetime | None = Field(
        default=None, description="집계 시간창 끝(until·생략 시 None=무한 미래)."
    )
    user_scoped: bool = Field(
        default=False, description="True면 특정 user 본인 집계, False면 코호트 전체."
    )


# ── 미계측 5종 고정 Metric(value None·상태 enum·한국어 note) ──────────────────────
# 날조 금지: 신호가 적재/라벨/도구로 생산되기 전까지 value=None을 유지한다(0/stub 금지).
def _diagnosis_agreement_unmeasured() -> Metric:
    return Metric(
        value=None,
        status=MetricStatus.REQUIRES_DATA,
        note=(
            "문항-오개념 ground-truth 태깅 부재(카탈로그 30종·정답 라벨 없음) — 진단 오개념과 "
            "대조할 실제 라벨이 있어야 일치율 산출(L2 agreement는 BKT↔IRT 신호일 뿐)."
        ),
    )


def _help_reduction_from_levels(hint_levels: list[int]) -> Metric:
    """⑤ 도움 감소 곡선 — 힌트제공 hint_level 시계열의 OLS 단순선형회귀 기울기를 Metric으로.

    입력 `hint_levels`는 *event_at 오름차순*으로 정렬된 hint_level(1~4·supply) 시계열이다.
    x는 순서 인덱스(0,1,2,…), y는 hint_level. OLS 기울기 = Σ(x-x̄)(y-ȳ)/Σ(x-x̄)² —
    **음수면 시간이 갈수록 AI가 더 은근한(낮은) 힌트로 충분 = 도움 감소 = 개선**이다.

    종단 표본 가드(날조 0): 유효 포인트가 `_MIN_SLOPE_POINTS` 미만이거나 x 분산이 0이면
    기울기를 산출하지 않고 **NO_DATA**(value None)로 둔다 — 가짜 0/날조 기울기 금지. x는
    0..n-1 등차라 n>=2면 분산은 항상 양수지만, 방어적으로 0 분산도 NO_DATA로 막는다.

    정직 note: 이 기울기는 *raw* 힌트 노출량 추세일 뿐, **R15(정확률 교차검증) 미반영**이다 —
    학생이 힌트를 *회피*해서(틀려도) 레벨이 낮아진 것과 *실력으로* 낮아진 것을 구분하지 못한다.
    힌트 회피만으로 개선 판정하지 않는 교차검증은 후속 슬라이스 책임. 종단 지표라 표본이 적으면
    NO_DATA이고, hint_level은 graded 노출량(1~4·1=가장 은근/4=전체 풀이)이다.

    OLS 코어는 `_ols_slope`(공유 헬퍼)에 위임한다 — None(표본 부족/분산 0)이면 NO_DATA로
    분기(가드·note 비트동일 유지). n<_MIN_SLOPE_POINTS면 표본 부족 note, 그 외 None이면(이론적
    x 분산 0) 분산 0 note로 *기존과 동일하게* 갈라낸다.
    """
    n = len(hint_levels)
    slope = _ols_slope([float(level) for level in hint_levels])
    if slope is None:
        if n < _MIN_SLOPE_POINTS:
            return Metric(
                value=None,
                status=MetricStatus.NO_DATA,
                note=(
                    f"힌트제공 이벤트 {n}건 — 종단 표본 부족(최소 {_MIN_SLOPE_POINTS}점) 으로 OLS "
                    "기울기 산출 불가. 힌트제공이 쌓이면 도움 감소 곡선 계측(가짜 0/기울기 아님). "
                    "R15 정확률 교차검증 미반영(후속)·종단 지표."
                ),
            )
        return Metric(
            value=None,
            status=MetricStatus.NO_DATA,
            note=(
                "힌트제공 시계열의 시간축 분산 0 — OLS 기울기 산출 불가(가짜 0 아님). "
                "R15 정확률 교차검증 미반영(후속)·종단 지표."
            ),
        )

    return Metric(
        value=slope,
        status=MetricStatus.MEASURED,
        note=(
            f"힌트제공 {n}건 hint_level OLS 기울기 {slope:+.4f}(event_at 순서·음수=도움 감소). "
            "R15 정확률 교차검증 미반영(힌트 회피만으로 개선 판정 안 함은 후속)·종단 지표라 "
            "표본 적으면 NO_DATA·hint_level은 graded 노출량(1~4)."
        ),
    )


def _judge_r15(help_slope: float | None, accuracy_slope: float | None) -> HelpReductionValidation:
    """R15 결합 판정(순수) — ⑤ 도움 감소 기울기와 정답률 기울기를 교차해 verdict를 낸다.

    설계안 §11.2 R15: 도움 감소를 *정답률 유지와 결합 판정* — 힌트 회피만으로 개선 인정 안 함.
    경계는 slope 0(tolerance 없이 명확)·날조 0 금지(한쪽이라도 None이면 INSUFFICIENT_DATA):

    - help_slope None **또는** accuracy_slope None → INSUFFICIENT_DATA(종단 표본 부족·교차 불가).
    - help_slope >= 0(도움 안 줄어듦) → NO_HELP_REDUCTION(개선 신호 자체가 아님).
    - help_slope < 0 **and** accuracy_slope >= 0(정답률 유지/상승) → GENUINE_IMPROVEMENT.
    - help_slope < 0 **and** accuracy_slope < 0(정답률 하락) → GAMING_SUSPECT(힌트 회피/방치 의심).

    정답률 신호는 `ProblemAttempt.is_correct`의 OLS 기울기(실제 정답률 추세)다 — ①(검산
    미적발 proxy)이 아니라 is_correct를 쓰는 이유는 R15의 "정답률"에 직접 대응하고 더
    직접적이기 때문. 한계(종단·표본 의존·경계 0·이탈/난이도 미반영)는 note에 정직 표기한다.
    """
    if help_slope is None or accuracy_slope is None:
        return HelpReductionValidation(
            verdict=R15Verdict.INSUFFICIENT_DATA,
            help_slope=help_slope,
            accuracy_slope=accuracy_slope,
            note=(
                "도움/정답률 한쪽이라도 종단 표본 부족(최소 "
                f"{_MIN_SLOPE_POINTS}점)으로 R15 교차검증 불가 — verdict 미산출(날조 판정 금지). "
                "정답률 신호는 ProblemAttempt.is_correct 추세(① 검산 proxy 아님)."
            ),
        )

    if help_slope >= 0:
        return HelpReductionValidation(
            verdict=R15Verdict.NO_HELP_REDUCTION,
            help_slope=help_slope,
            accuracy_slope=accuracy_slope,
            note=(
                f"도움 기울기 {help_slope:+.4f} >= 0 — 도움이 줄지 않아 개선 신호 자체가 아님"
                "(임계 slope 0). 정답률 추세와 교차 불필요."
            ),
        )

    if accuracy_slope >= 0:
        return HelpReductionValidation(
            verdict=R15Verdict.GENUINE_IMPROVEMENT,
            help_slope=help_slope,
            accuracy_slope=accuracy_slope,
            note=(
                f"진짜 개선 — 도움 기울기 {help_slope:+.4f} < 0(도움↓)·정답률 기울기 "
                f"{accuracy_slope:+.4f} >= 0(유지/상승). 힌트 회피가 아니라 실력으로 도움 감소"
                "(임계 slope 0·정답률=is_correct 추세). 종단·표본 의존·이탈 미반영(완전판정 아님)."
            ),
        )

    return HelpReductionValidation(
        verdict=R15Verdict.GAMING_SUSPECT,
        help_slope=help_slope,
        accuracy_slope=accuracy_slope,
        note=(
            f"교정기 함정 경보 — 도움 기울기 {help_slope:+.4f} < 0(도움↓)이나 정답률 기울기 "
            f"{accuracy_slope:+.4f} < 0(하락). 힌트 회피/방치 의심(실력 향상 아님·임계 slope 0·"
            "정답률=is_correct 추세). 종단·표본 의존·이탈/난이도 신호 미반영(R15 완전판정 아님)."
        ),
    )


def _calibration_unmeasured() -> Metric:
    return Metric(
        value=None,
        status=MetricStatus.REQUIRES_TOOL,
        note=(
            "elicit_prediction 도구 미구현 — confidence_self_reported 필드는 있으나 풀이 전 "
            "예측을 verify 결과와 대조하는 출제 흐름이 없어 Brier 산출 불가."
        ),
    )


def _transfer_unmeasured() -> Metric:
    return Metric(
        value=None,
        status=MetricStatus.REQUIRES_TOOL,
        note=(
            "시그니처 패턴(55+108) 문항 태깅·전이 출제(assign_transfer_probe) 미구현 — 학습 직후 "
            "미학습 동형 문항을 내는 흐름이 있어야 전이 정답률 산출."
        ),
    )


async def compute_wh1_surrogate_metrics(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> SurrogateMetrics:
    """WH-1 0단계 대리 지표 7종을 계산 — 계측 가능분 실측 + 미계측 3종 정직 표시.

    설계안 §8.4 0단계 베이스라인. **계측 가능(①③④⑤)만 실값**으로 내고, **미계측(②⑥⑦)은
    value=None + status + note**로 갭을 가시화한다(CLAUDE.md "모르면 모른다"·설계안 "측정 없는
    도입 없음" — 0/stub 날조 금지). ⑤(도움 감소 곡선)는 힌트제공 이벤트 적재 슬라이스로
    NOT_INSTRUMENTED→MEASURED가 됐다(표본 부족이면 NO_DATA·R15 교차검증 미반영).

    Args:
        session: 조회 전용 AsyncSession(쓰기 없음·ORM/쿼리빌더만·원시 SQL 회피).
        user_id: 지정 시 그 user 본인 집계, None이면 코호트 전체(ops/스크립트).
        since/until: 집계 시간창(started_at 기준·inclusive·생략 시 무한). TZ 검증은 노출
            계층(api/me·time_window_conditions)이 수행 — 여기선 받은 경계를 그대로 비교.

    Returns:
        SurrogateMetrics — 7 지표(각 Metric) + 표본 수·시간창·user 스코핑 메타.

    계측 가능(MEASURED 가능):
        ① verify_pass_rate: attempt_event(event_type=검산결과) 중 event_data->>'passed'=true
           비율(passed=거짓 수치관계 *미적발*·binary 검산·3-state 아님). total==0이면 NO_DATA
           (값 None·날조 회피)·아니면 MEASURED(passed/total). event_at 기준 시간창·user 필터.
        ③ session_completion_rate: LearningSession 중 ended_at IS NOT NULL 비율. total==0이면
           NO_DATA(value None·날조 회피)·아니면 MEASURED(completed/total).
        ④ tokens_per_turn: total_tokens IS NOT NULL AND total_turns > 0인 Dialogue에서
           AVG(total_tokens/total_turns). 해당 행 0이면 NO_DATA(현재 토큰 미적재면 정직하게
           NO_DATA·0 아님)·있으면 MEASURED.
        ⑤ help_reduction_slope: attempt_event(event_type=힌트제공)의 hint_level을 event_at
           오름차순으로 뽑아 OLS 단순선형회귀 기울기(음수=도움 감소=개선). 유효 포인트가
           `_MIN_SLOPE_POINTS` 미만이거나 x 분산 0이면 NO_DATA(날조 회피)·아니면 MEASURED.
           raw 기울기일 뿐 R15 정확률 교차검증은 미반영(후속).

    미계측(고정 status·value None):
        ② REQUIRES_DATA · ⑥ REQUIRES_TOOL · ⑦ REQUIRES_TOOL.
        각 사유는 note 한국어로 명시(무엇을 만들면 계측되는지).
    """
    # ── ③ 세션 완주율 (LearningSession.ended_at NOT NULL 비율) ──
    session_conds = []
    if user_id is not None:
        session_conds.append(LearningSession.user_id == user_id)
    if since is not None:
        session_conds.append(LearningSession.started_at >= since)
    if until is not None:
        session_conds.append(LearningSession.started_at <= until)

    total_sessions = (
        await session.execute(
            select(func.count()).select_from(LearningSession).where(*session_conds)
        )
    ).scalar() or 0
    completed_sessions = (
        await session.execute(
            select(func.count())
            .select_from(LearningSession)
            .where(*session_conds, LearningSession.ended_at.isnot(None))
        )
    ).scalar() or 0

    if total_sessions == 0:
        session_completion = Metric(
            value=None,
            status=MetricStatus.NO_DATA,
            note="집계 시간창·범위에 LearningSession 0건 — 표본이 쌓이면 완주율 계측(가짜 0 아님).",
        )
    else:
        session_completion = Metric(
            value=completed_sessions / total_sessions,
            status=MetricStatus.MEASURED,
            note=(
                f"완주(ended_at NOT NULL) {completed_sessions}/{total_sessions}건 — "
                "LearningSession.ended_at 채워진 비율(실측 베이스라인)."
            ),
        )

    # ── ④ 턴당 토큰 (Dialogue.total_tokens/total_turns 평균) ──
    dialogue_conds = [
        Dialogue.total_tokens.isnot(None),
        Dialogue.total_turns.isnot(None),
        Dialogue.total_turns > 0,
    ]
    if user_id is not None:
        dialogue_conds.append(Dialogue.user_id == user_id)
    if since is not None:
        dialogue_conds.append(Dialogue.started_at >= since)
    if until is not None:
        dialogue_conds.append(Dialogue.started_at <= until)

    # 토큰·턴이 채워진 행만 집계 — AVG(total_tokens::float / total_turns)와 표본 수를 한 행으로.
    token_row = (
        await session.execute(
            select(
                func.avg(cast(Dialogue.total_tokens, Float) / Dialogue.total_turns),
                func.count(),
            )
            .select_from(Dialogue)
            .where(*dialogue_conds)
        )
    ).one()
    avg_tokens_per_turn, sample_dialogues_raw = token_row
    sample_dialogues = int(sample_dialogues_raw or 0)

    if sample_dialogues == 0 or avg_tokens_per_turn is None:
        tokens_metric = Metric(
            value=None,
            status=MetricStatus.NO_DATA,
            note=(
                "total_tokens·total_turns 채워진 Dialogue 0건 — 현재 토큰 미적재 가능성. 적재되면 "
                "턴당 토큰 계측(가짜 0 아님)."
            ),
        )
    else:
        tokens_metric = Metric(
            value=float(avg_tokens_per_turn),
            status=MetricStatus.MEASURED,
            note=(
                f"{sample_dialogues}개 대화 AVG(total_tokens/total_turns) — 비용 대리 지표"
                "(실측 베이스라인)."
            ),
        )

    # ── ① verify 통과율 (attempt_event event_type=검산결과 중 passed=true 비율) ──
    # 한 행으로 (passed_count, total_count)를 뽑는다 — passed는 event_data->>'passed'를 boolean으로
    # 캐스팅(JSONB 접근도 쿼리빌더로·원시 SQL 문자열 회피). FILTER로 passed=true만 센다.
    verify_conds = [AttemptEvent.event_type == EventType.검산결과]
    if user_id is not None:
        verify_conds.append(AttemptEvent.user_id == user_id)
    if since is not None:
        verify_conds.append(AttemptEvent.event_at >= since)
    if until is not None:
        verify_conds.append(AttemptEvent.event_at <= until)

    verify_row = (
        await session.execute(
            select(
                func.count().filter(AttemptEvent.event_data["passed"].as_boolean().is_(True)),
                func.count(),
            )
            .select_from(AttemptEvent)
            .where(*verify_conds)
        )
    ).one()
    passed_count_raw, verify_total_raw = verify_row
    passed_count = int(passed_count_raw or 0)
    verify_total = int(verify_total_raw or 0)

    if verify_total == 0:
        verify_metric = Metric(
            value=None,
            status=MetricStatus.NO_DATA,
            note=("검산결과 이벤트 0건 — coach 풀이 제출이 쌓이면 통과율 계측(가짜 0 아님)."),
        )
    else:
        verify_metric = Metric(
            value=passed_count / verify_total,
            status=MetricStatus.MEASURED,
            note=(
                f"검산결과 이벤트 기반 — passed(거짓 수치관계 *미적발*) {passed_count}/"
                f"{verify_total}건. binary 검산(3-state verify 아님·unverifiable 미구분·"
                "풀이 제출 턴 한정)."
            ),
        )

    # ── ⑤ 도움 감소 곡선 (attempt_event event_type=힌트제공의 hint_level OLS 기울기) ──
    # event_at 오름차순으로 hint_level(event_data->>'hint_level'을 integer 캐스팅·쿼리빌더로 접근·
    # 원시 SQL 문자열 회피) 시계열을 뽑아 Python에서 순수 OLS 기울기를 계산한다. 기울기 산출은
    # _help_reduction_from_levels(종단 표본 가드·날조 0)에 위임.
    hint_conds = [AttemptEvent.event_type == EventType.힌트제공]
    if user_id is not None:
        hint_conds.append(AttemptEvent.user_id == user_id)
    if since is not None:
        hint_conds.append(AttemptEvent.event_at >= since)
    if until is not None:
        hint_conds.append(AttemptEvent.event_at <= until)

    hint_rows = (
        await session.execute(
            select(AttemptEvent.event_data["hint_level"].as_integer())
            .select_from(AttemptEvent)
            .where(*hint_conds)
            .order_by(AttemptEvent.event_at.asc())
        )
    ).all()
    # JSONB 파싱 실패(키 부재 등)로 None이 섞일 수 있으니 정수만 채택(날조 회피·결손 행 제외).
    hint_levels = [int(row[0]) for row in hint_rows if row[0] is not None]
    help_reduction = _help_reduction_from_levels(hint_levels)

    # ── R15 결합 판정 (⑤ 도움 감소 × 정답률 추세) ──
    # 정답률 신호 = ProblemAttempt.is_correct(실제 정답률·① 검산 proxy보다 직접적·R15의
    # "정답률"에 정확히 대응). is_correct IS NOT NULL(미응답=NULL 제외)·started_at 오름차순으로
    # 뽑아 1.0/0.0 시퀀스 → _ols_slope로 정답률 기울기. user_id/since/until은 started_at 기준
    # (ProblemAttempt.started_at). ⑤ help_slope는 _ols_slope(hint_levels) raw 기울기(_help_
    # reduction_from_levels의 Metric.value와 동일한 코어·NO_DATA면 None). 둘을 _judge_r15로 교차.
    accuracy_conds: list[ColumnElement[bool]] = [ProblemAttempt.is_correct.isnot(None)]
    if user_id is not None:
        accuracy_conds.append(ProblemAttempt.user_id == user_id)
    if since is not None:
        accuracy_conds.append(ProblemAttempt.started_at >= since)
    if until is not None:
        accuracy_conds.append(ProblemAttempt.started_at <= until)

    accuracy_rows = (
        await session.execute(
            select(ProblemAttempt.is_correct)
            .select_from(ProblemAttempt)
            .where(*accuracy_conds)
            .order_by(ProblemAttempt.started_at.asc())
        )
    ).all()
    # is_correct(bool)를 1.0/0.0 시퀀스로(None은 IS NOT NULL 필터로 이미 제외·방어적 재확인).
    accuracy_series = [1.0 if row[0] else 0.0 for row in accuracy_rows if row[0] is not None]
    help_slope = _ols_slope([float(level) for level in hint_levels])
    accuracy_slope = _ols_slope(accuracy_series)
    help_reduction_validated = _judge_r15(help_slope, accuracy_slope)

    return SurrogateMetrics(
        verify_pass_rate=verify_metric,
        diagnosis_agreement_rate=_diagnosis_agreement_unmeasured(),
        session_completion_rate=session_completion,
        tokens_per_turn=tokens_metric,
        help_reduction_slope=help_reduction,
        calibration_brier=_calibration_unmeasured(),
        transfer_score=_transfer_unmeasured(),
        help_reduction_validated=help_reduction_validated,
        sample_sessions=int(total_sessions),
        sample_dialogues=sample_dialogues,
        sample_verify_events=verify_total,
        sample_hint_events=len(hint_levels),
        sample_accuracy_attempts=len(accuracy_series),
        window_start=since,
        window_end=until,
        user_scoped=user_id is not None,
    )
