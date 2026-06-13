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
  ⑤ 도움 감소 곡선         — 🔴 NOT_INSTRUMENTED: 힌트 시계열 부재(used_hint bool flag만).
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
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import AttemptEvent, LearningSession
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.schema.enums import EventType

__all__ = [
    "Metric",
    "MetricStatus",
    "SurrogateMetrics",
    "compute_wh1_surrogate_metrics",
]


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

    # ── 표본·범위 메타 ──
    sample_sessions: int = Field(
        default=0, description="③ 집계 대상 LearningSession 수(시간창·user 필터 적용)."
    )
    sample_dialogues: int = Field(
        default=0, description="④ 집계 대상 Dialogue 수(토큰·턴 채워진 행만)."
    )
    sample_verify_events: int = Field(
        default=0, description="① 집계 대상 검산결과 attempt_event 수(passed 채워진 행)."
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


def _help_reduction_unmeasured() -> Metric:
    return Metric(
        value=None,
        status=MetricStatus.NOT_INSTRUMENTED,
        note=(
            "힌트 이벤트 시계열 부재 — ProblemAttempt.used_hint는 bool flag만이라 횟수·시간축이 "
            "없어 감소 기울기 산출 불가(힌트 이벤트 적재 필요)."
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
    """WH-1 0단계 대리 지표 7종을 계산 — 계측 가능분 실측 + 미계측 4종 정직 표시.

    설계안 §8.4 0단계 베이스라인. **계측 가능(①③④)만 실값**으로 내고, **미계측(②⑤⑥⑦)은
    value=None + status + note**로 갭을 가시화한다(CLAUDE.md "모르면 모른다"·설계안 "측정 없는
    도입 없음" — 0/stub 날조 금지).

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

    미계측(고정 status·value None):
        ② REQUIRES_DATA · ⑤ NOT_INSTRUMENTED · ⑥ REQUIRES_TOOL · ⑦ REQUIRES_TOOL.
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

    return SurrogateMetrics(
        verify_pass_rate=verify_metric,
        diagnosis_agreement_rate=_diagnosis_agreement_unmeasured(),
        session_completion_rate=session_completion,
        tokens_per_turn=tokens_metric,
        help_reduction_slope=_help_reduction_unmeasured(),
        calibration_brier=_calibration_unmeasured(),
        transfer_score=_transfer_unmeasured(),
        sample_sessions=int(total_sessions),
        sample_dialogues=sample_dialogues,
        sample_verify_events=verify_total,
        window_start=since,
        window_end=until,
        user_scoped=user_id is not None,
    )
