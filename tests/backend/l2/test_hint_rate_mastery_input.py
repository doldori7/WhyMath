"""EOS-45 acceptance ② — hint_usage 파생 hint_rate가 L2 입력 경로에 공급 *가능*함의 증명.

**L2 알고리즘 무변경**(7계층): 이 테스트는 L2 코드를 한 줄도 바꾸지 않는다. L2 입력 계약을
실측한 결과는 다음과 같고, 이 테스트는 그 *기존 계약* 위에서 hint_usage 파생값이 공급됨을
hermetic으로 보인다:

  - `l2.learning_metrics_rollup.AttemptFact.used_hint: bool | None` →
    `aggregate_user_behavior_metrics`(순수) → `daily_hint_reliance_rate`
    (`BEHAVIOR_METRIC_HINT_RELIANCE`) — 힌트가 현재 L2 추정·지표 파이프에 들어가는 유일 경로.
  - `l2.bkt.BktModel.update(prior, correct: bool)` — BKT 숙달 추정의 관측 입력은 불리언
    correct뿐이다(힌트 직접 입력 없음). 힌트-가중 관측(예: 힌트 정답을 약한 증거로 취급)은
    **L2 알고리즘 변경이라 이 태스크 범위 밖** — hint_usage가 그 확장에 필요한 원천(횟수·
    레벨·시각)을 이미 제공함을 파생 테스트로 보이는 데서 멈춘다(배선 확장은 후속 태스크 몫).

**used_hint 병행(대체 아님)**: `problem_attempt.used_hint` 컬럼과 `AttemptFact.used_hint`
필드는 불변이고, hint_usage에서 파생한 불리언은 기존 기록과 *일치 검증 가능한 병행 신호*다.

파생 함수는 이 테스트 모듈의 순수 헬퍼로 둔다 — 프로덕션 배선(파생 모듈 신설·rollup의
hint_usage 읽기)은 범위 밖이므로 l2/에 코드를 추가하지 않는다(좌석 존재를 수집·배선 작동으로
위장하지 않는다 — "작동 신호 없는 알고리즘 부착 금지").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.l2.learning_metrics_rollup import (
    BEHAVIOR_METRIC_HINT_RELIANCE,
    AttemptFact,
    aggregate_user_behavior_metrics,
)
from whymath_backend.schema.hint_usage import HintUsage

_UID = uuid.uuid4()
_T0 = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _usage(attempt_id: uuid.UUID, level: int) -> HintUsage:
    return HintUsage(attempt_id=attempt_id, user_id=_UID, hint_level=level, requested_at=_T0)


# ── 순수 파생 헬퍼(테스트 전용 — 프로덕션 배선은 범위 밖·모듈 docstring) ──────────


def derive_used_hint(usages: list[HintUsage], attempt_id: uuid.UUID) -> bool:
    """attempt의 힌트 사용 여부 — hint_usage 행 존재 = used_hint True(불리언 병행 파생)."""
    return any(u.attempt_id == attempt_id for u in usages)


def derive_hint_request_count(usages: list[HintUsage], attempt_id: uuid.UUID) -> int:
    """attempt의 힌트 요청 횟수 — used_hint 불리언이 잃는 첫 번째 축."""
    return sum(1 for u in usages if u.attempt_id == attempt_id)


def derive_max_hint_level(usages: list[HintUsage], attempt_id: uuid.UUID) -> int | None:
    """attempt의 최대 hint_level — used_hint 불리언이 잃는 두 번째 축(None=무힌트)."""
    levels = [u.hint_level for u in usages if u.attempt_id == attempt_id]
    return max(levels) if levels else None


def derive_hint_rate(usages: list[HintUsage], attempt_ids: list[uuid.UUID]) -> float:
    """시도 대비 힌트 사용 시도 비율 — `daily_hint_reliance_rate`와 동일 의미의 파생."""
    if not attempt_ids:
        return 0.0
    hinted = sum(1 for aid in attempt_ids if derive_used_hint(usages, aid))
    return hinted / len(attempt_ids)


# ── 증명 1: 기존 L2 입력 경로(AttemptFact.used_hint)에 파생값 공급 ────────────────


class TestFeedsExistingL2InputPath:
    def test_derived_used_hint_feeds_behavior_metric_pipeline(self) -> None:
        """hint_usage → used_hint 파생 → AttemptFact → daily_hint_reliance_rate 산출.

        L2의 `aggregate_user_behavior_metrics`(무변경)가 hint_usage 파생 입력만으로 기존
        지표를 낸다 — 신규 엔티티가 기존 입력 계약과 호환됨의 실측.
        """
        aid_hinted, aid_clean = uuid.uuid4(), uuid.uuid4()
        usages = [_usage(aid_hinted, 2), _usage(aid_hinted, 3)]

        attempts = [
            AttemptFact(
                user_id=_UID,
                started_at=_T0,
                is_correct=True,
                used_hint=derive_used_hint(usages, aid),  # ← hint_usage 파생 공급
            )
            for aid in (aid_hinted, aid_clean)
        ]
        rows = aggregate_user_behavior_metrics([], attempts)
        reliance = {r.metric_name: r.metric_value for r in rows}[BEHAVIOR_METRIC_HINT_RELIANCE]
        assert reliance == 0.5  # 2 시도 중 1 시도 힌트 — 파생 hint_rate와 일치

    def test_derived_rate_matches_pipeline_output(self) -> None:
        """파생 hint_rate(순수)와 L2 파이프 산출이 같은 값 — 의미 동치(이중 회계)."""
        aid_a, aid_b, aid_c = (uuid.uuid4() for _ in range(3))
        usages = [_usage(aid_a, 1)]
        attempt_ids = [aid_a, aid_b, aid_c]
        attempts = [
            AttemptFact(user_id=_UID, started_at=_T0, used_hint=derive_used_hint(usages, aid))
            for aid in attempt_ids
        ]
        rows = aggregate_user_behavior_metrics([], attempts)
        reliance = {r.metric_name: r.metric_value for r in rows}[BEHAVIOR_METRIC_HINT_RELIANCE]
        assert reliance == round(derive_hint_rate(usages, attempt_ids), 4) == round(1 / 3, 4)


# ── 증명 2: used_hint 병행 유지(대체 아님) ───────────────────────────────────────


class TestUsedHintCoexistence:
    def test_problem_attempt_used_hint_column_unchanged(self) -> None:
        """`problem_attempt.used_hint` 컬럼 잔존(불리언 병행 — 기존 소비자 불변)."""
        column = ProblemAttempt.__table__.columns["used_hint"]
        assert column.nullable is True  # 기존 계약 그대로(미기록=NULL)

    def test_attempt_fact_contract_unchanged(self) -> None:
        """`AttemptFact.used_hint` 필드 잔존 — rollup 입력 계약 무변경(L2 무수정 증거)."""
        fact = AttemptFact(user_id=_UID, started_at=_T0, used_hint=True)
        assert fact.used_hint is True

    def test_derived_boolean_agrees_with_recorded_boolean(self) -> None:
        """이중 기록 시나리오 — hint_usage 파생 불리언과 기록된 used_hint가 일치 검증 가능."""
        aid = uuid.uuid4()
        usages = [_usage(aid, 1)]
        recorded_used_hint = True  # writer가 problem_attempt.used_hint에 병행 기록한 값
        assert derive_used_hint(usages, aid) == recorded_used_hint


# ── 증명 3: 불리언이 잃는 정밀 축 — 횟수·최대 레벨 구분 ─────────────────────────


class TestFinerSignalThanBoolean:
    def test_distinguishes_attempts_boolean_cannot(self) -> None:
        """힌트 1회(레벨1) 정답 vs 힌트 3회(최대 레벨4) 정답 — used_hint는 둘 다 True로
        뭉개지만 hint_usage 파생은 구분한다(태스크 목적: 숙련도 해석 구분의 원천 데이터)."""
        aid_light, aid_heavy = uuid.uuid4(), uuid.uuid4()
        usages = [
            _usage(aid_light, 1),
            _usage(aid_heavy, 2),
            _usage(aid_heavy, 3),
            _usage(aid_heavy, 4),
        ]
        # 불리언 축: 구분 불가(둘 다 True).
        assert derive_used_hint(usages, aid_light) is derive_used_hint(usages, aid_heavy) is True
        # hint_usage 파생 축: 횟수·최대 레벨로 구분.
        assert derive_hint_request_count(usages, aid_light) == 1
        assert derive_hint_request_count(usages, aid_heavy) == 3
        assert derive_max_hint_level(usages, aid_light) == 1
        assert derive_max_hint_level(usages, aid_heavy) == 4

    def test_no_hint_attempt_yields_none_not_zero_level(self) -> None:
        """무힌트 attempt의 최대 레벨은 None(0 날조 금지) — 횟수는 0(셈이므로 사실)."""
        aid = uuid.uuid4()
        assert derive_max_hint_level([], aid) is None
        assert derive_hint_request_count([], aid) == 0
