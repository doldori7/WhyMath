"""검수 타이머 이벤트 계약 검증 — 3종 폐쇄·교차 필드 강제·F1~F8 소비 (EOS-54 acceptance ①·④).

정본: `schema/review_timer.py`. 핵심 계약 — started/finished/aborted 폐쇄 3종, finished는
판정 필수, rejected는 failure_code(F1~F8 — EOS-51 동결 enum) 필수, elapsed_ms None=미측정
(0 날조 금지). 변별력: 각 규칙마다 **통과/실패 양쪽**을 실측한다(변별력 없는 검증 스텝 금지).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import GenerationFailureCode
from whymath_backend.schema.review_timer import ReviewTimerEvent, ReviewTimerEventType


def _base(**overrides: Any) -> dict[str, Any]:
    """유효 이벤트 재료 — overrides로 케이스 변형."""
    data: dict[str, Any] = {
        "review_session_id": uuid.uuid4(),
        "cu_slug": "quadratic-roots-001",
        "reviewer_id": "kiki",
        "event_type": "started",
    }
    data.update(overrides)
    return data


class TestEventTypeClosure:
    def test_three_types_frozen(self) -> None:
        """설계서 §6 "시작·종료·중단" — 폐쇄 3종 값집합 동결."""
        assert {m.value for m in ReviewTimerEventType} == {"started", "finished", "aborted"}

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(event_type="paused"))

    def test_extra_field_rejected(self) -> None:
        """extra=forbid — 계약 밖 필드 유입 차단."""
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(student_id=str(uuid.uuid4())))


class TestStartedShape:
    def test_valid_started(self) -> None:
        event = ReviewTimerEvent.model_validate(_base())
        assert event.event_type == "started"  # use_enum_values — 값 문자열 저장
        assert event.verdict is None and event.elapsed_ms is None

    def test_started_rejects_verdict(self) -> None:
        with pytest.raises(ValidationError, match="started"):
            ReviewTimerEvent.model_validate(_base(verdict="approved"))

    def test_started_rejects_elapsed(self) -> None:
        """착수 시점엔 잰 것이 없다 — elapsed 동반 started는 계약 위반."""
        with pytest.raises(ValidationError, match="elapsed_ms"):
            ReviewTimerEvent.model_validate(_base(elapsed_ms=1000))


class TestFinishedShape:
    def test_valid_approved(self) -> None:
        event = ReviewTimerEvent.model_validate(
            _base(event_type="finished", verdict="approved", elapsed_ms=95_000)
        )
        assert event.verdict == "approved"
        assert event.elapsed_ms == 95_000

    def test_finished_requires_verdict(self) -> None:
        """판정 없는 종결 없음 — 그런 상태는 aborted다."""
        with pytest.raises(ValidationError, match="verdict"):
            ReviewTimerEvent.model_validate(_base(event_type="finished"))

    def test_finished_verdict_pending_rejected(self) -> None:
        """pending은 판정이 아니다 — Literal 폐쇄 2종(approved|rejected)."""
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(event_type="finished", verdict="pending"))

    def test_finished_elapsed_none_is_unmeasured_not_zero(self) -> None:
        """acceptance ④ — 계측 실패한 종결은 elapsed=None으로 유효(판정은 남기되 미계측)."""
        event = ReviewTimerEvent.model_validate(
            _base(event_type="finished", verdict="approved", elapsed_ms=None)
        )
        assert event.elapsed_ms is None  # 0이 아니라 None — 집계가 분리 카운트

    def test_negative_elapsed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="approved", elapsed_ms=-1)
            )


class TestRejectedRequiresFailureCode:
    """설계서 §4 강제 분류 — 반려코드 없는 반려는 생성 자체가 불가(함수 레벨 집행)."""

    def test_rejected_without_code_fails(self) -> None:
        with pytest.raises(ValidationError, match="failure_code"):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="rejected", elapsed_ms=10_000)
            )

    def test_rejected_with_each_frozen_code_passes(self) -> None:
        """F1~F8 동결 8코드 전건 수용 — 이 계약이 GenerationFailureCode의 소비 지점."""
        for code in GenerationFailureCode:
            event = ReviewTimerEvent.model_validate(
                _base(
                    event_type="finished",
                    verdict="rejected",
                    failure_code=code.value,
                    elapsed_ms=10_000,
                )
            )
            assert event.failure_code == code.value

    def test_unknown_code_rejected(self) -> None:
        """계약 밖 코드(F9) 차단 — 폐쇄 8종은 G0 동결(추가는 설계서 개정 전제)."""
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="rejected", failure_code="F9")
            )

    def test_approved_with_code_fails(self) -> None:
        """승인에 반려코드 금지 — 판정과 코드의 모순 조합 차단."""
        with pytest.raises(ValidationError, match="rejected"):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="approved", failure_code="F1")
            )

    def test_note_without_code_fails(self) -> None:
        """자유 텍스트 단독 금지(§4) — note는 코드의 부기로만."""
        with pytest.raises(ValidationError, match="failure_note"):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="approved", failure_note="애매함")
            )

    def test_note_with_code_passes(self) -> None:
        event = ReviewTimerEvent.model_validate(
            _base(
                event_type="finished",
                verdict="rejected",
                failure_code="F3",
                failure_note="2→3단계 비약",
                elapsed_ms=10_000,
            )
        )
        assert event.failure_note == "2→3단계 비약"


class TestAbortedShape:
    def test_valid_aborted_with_partial_elapsed(self) -> None:
        event = ReviewTimerEvent.model_validate(_base(event_type="aborted", elapsed_ms=30_000))
        assert event.elapsed_ms == 30_000

    def test_aborted_rejects_verdict(self) -> None:
        """판정이 있으면 finished다 — aborted+verdict 모순 차단."""
        with pytest.raises(ValidationError, match="aborted"):
            ReviewTimerEvent.model_validate(_base(event_type="aborted", verdict="approved"))

    def test_aborted_rejects_failure_code(self) -> None:
        with pytest.raises(ValidationError, match="aborted"):
            ReviewTimerEvent.model_validate(_base(event_type="aborted", failure_code="F1"))


class TestTimeSeparation:
    """EOS-48 발생/수신 분리 — occurred_at(발생)·recorded_at(수신) 독립 좌석."""

    def test_both_default_none(self) -> None:
        event = ReviewTimerEvent.model_validate(_base())
        assert event.occurred_at is None  # 미신고
        assert event.recorded_at is None  # 적재 계층(DB now()/JSONL append)이 채움

    def test_both_settable_independently(self) -> None:
        occurred = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
        received = datetime(2026, 8, 31, 2, 5, tzinfo=UTC)
        event = ReviewTimerEvent.model_validate(_base(occurred_at=occurred, recorded_at=received))
        assert event.occurred_at == occurred
        assert event.recorded_at == received


class TestIdentityFields:
    def test_cu_slug_width_matches_problem_slug(self) -> None:
        """폭 128 = problem.slug String(128) — 경계 통과/초과 양쪽 실측."""
        ok = ReviewTimerEvent.model_validate(_base(cu_slug="s" * 128))
        assert len(ok.cu_slug) == 128
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(cu_slug="s" * 129))

    def test_reviewer_id_required_nonempty(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(reviewer_id=""))

    def test_no_student_axis_fields(self) -> None:
        """학생 소유 축 필드 부재 — 검수자 텔레메트리(모듈 docstring 개인정보 판정)."""
        fields = set(ReviewTimerEvent.model_fields)
        assert fields & {"user_id", "student_id", "target_user_id"} == set()
