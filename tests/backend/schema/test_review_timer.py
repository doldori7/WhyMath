"""검수 타이머 이벤트 계약 검증 — 3종 폐쇄·교차 필드 강제·F1~F8 소비 (EOS-54 acceptance ①·④).

정본: `schema/review_timer.py`. 핵심 계약 — started/finished/aborted 폐쇄 3종, finished는
판정 필수, rejected는 failure_code(F1~F8 — EOS-51 동결 enum) 필수, elapsed_ms None=미측정
(0 날조 금지). 변별력: 각 규칙마다 **통과/실패 양쪽**을 실측한다(변별력 없는 검증 스텝 금지).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import (
    GenerationFailureCode,
    ReviewStatus,
    is_review_status_cleared,
)
from whymath_backend.schema.review_timer import (
    VERDICT_APPROVED_WITH_EDIT,
    ReviewTimerEvent,
    ReviewTimerEventType,
    ReviewVerdict,
    review_status_for_verdict,
)


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


class TestEditAwareVerdictVocabulary:
    """EOS-62 — 판정 3종화. '손질해서 통과시킨 CU'가 무손질 통과와 구분되는가.

    이 해상도가 없으면 "HIT 중앙값 4분 + 승인율 93%"가 성공으로 읽히는데 승인분의 상당수가
    사람 손질일 수 있고, 그 손질분이 정확히 AI-first 전략의 실패 신호다 — 성공 지표가 실패를
    가리는 구조다(N4 갭 ③).
    """

    def test_verdict_vocabulary_is_exactly_three(self) -> None:
        """폐쇄 3종 동결 — 문서 §17의 5종 중 REGENERATE·ESCALATE는 의도적 미채택."""
        assert set(get_args(ReviewVerdict)) == {"approved", "approved_with_edit", "rejected"}

    def test_edit_approval_accepts_optional_failure_code(self) -> None:
        """부기 규약 — 권장하되 강제하지 않는다(코드 없이도 유효)."""
        with_code = ReviewTimerEvent.model_validate(
            _base(
                event_type="finished",
                verdict="approved_with_edit",
                failure_code=GenerationFailureCode.F7,
                elapsed_ms=90_000,
            )
        )
        assert with_code.failure_code == GenerationFailureCode.F7

        without_code = ReviewTimerEvent.model_validate(
            _base(event_type="finished", verdict="approved_with_edit", elapsed_ms=90_000)
        )
        assert without_code.failure_code is None

    def test_edit_approval_allows_note_with_code(self) -> None:
        event = ReviewTimerEvent.model_validate(
            _base(
                event_type="finished",
                verdict="approved_with_edit",
                failure_code=GenerationFailureCode.F3,
                failure_note="3단계 근거 문장을 보강",
            )
        )
        assert event.failure_note is not None

    def test_edit_approval_note_still_requires_a_code(self) -> None:
        """§4 자유 텍스트 단독 금지 — 손질 승인에서도 유지."""
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(
                _base(event_type="finished", verdict="approved_with_edit", failure_note="고침")
            )

    def test_plain_approval_still_forbids_failure_code(self) -> None:
        """무손질 승인에 결함코드를 붙이는 경로를 막는다 — 고쳤다면 값이 틀린 것이다.

        이걸 허용하면 `approved` + code가 사실상 '손질 승인'이 되어 해상도 갭이 되살아난다.
        """
        with pytest.raises(ValidationError, match="무손질 승인"):
            ReviewTimerEvent.model_validate(
                _base(
                    event_type="finished",
                    verdict="approved",
                    failure_code=GenerationFailureCode.F1,
                )
            )

    def test_rejection_still_requires_a_code(self) -> None:
        """반려의 강제 분류(§4)는 불변 — 어휘 확장이 기존 계약을 느슨하게 만들지 않았다."""
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(_base(event_type="finished", verdict="rejected"))

    def test_aborted_still_forbids_the_new_verdict(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTimerEvent.model_validate(
                _base(event_type="aborted", verdict="approved_with_edit")
            )

    def test_unknown_verdict_rejected(self) -> None:
        """문서 §17의 미채택 2종은 어휘에 들어오지 않는다(폐쇄 유지)."""
        for outsider in ("escalate", "regenerate", "pending"):
            with pytest.raises(ValidationError):
                ReviewTimerEvent.model_validate(_base(event_type="finished", verdict=outsider))


class TestBackwardCompatibility:
    """acceptance ④ — 기존 `approved` 행의 의미를 바꾸지 않는다(값 추가만·소급 재분류 금지)."""

    def test_existing_approved_rows_still_validate_unchanged(self) -> None:
        """EOS-62 이전에 기록된 무손질 승인 행이 그대로 통과한다."""
        event = ReviewTimerEvent.model_validate(
            _base(event_type="finished", verdict="approved", elapsed_ms=120_000)
        )
        assert event.verdict == "approved"
        assert event.failure_code is None

    def test_approved_is_not_silently_reinterpreted(self) -> None:
        """`approved`는 여전히 '무손질 승인'이지 '손질 여부 미상'으로 바뀌지 않는다.

        어휘가 늘었다고 과거 값의 의미를 재정의하면 12월 판정이 소급 재분류 위에 서게 된다 —
        골든 승격의 `edit_aware_since` 경계도 같은 원칙의 시각 축 표현이다.
        """
        assert review_status_for_verdict("approved") is ReviewStatus.approved


class TestVerdictToReviewStatusBridge:
    """두 축(판정 ↔ 노출 상태)이 갈라진 뒤의 유일한 정본 변환."""

    def test_both_approvals_map_to_approved_status(self) -> None:
        """손질 여부는 생산성 축이지 노출 축이 아니다 — 둘 다 노출 통과."""
        assert review_status_for_verdict("approved") is ReviewStatus.approved
        assert review_status_for_verdict(VERDICT_APPROVED_WITH_EDIT) is ReviewStatus.approved

    def test_mapped_status_passes_the_exposure_predicate(self) -> None:
        """★ 이 변환이 없으면 손질 승인 CU가 **무증상으로 노출에서 빠진다**.

        `is_review_status_cleared`는 `approved`만 True인 fail-closed 술어다. verdict를 그대로
        review_status에 복사하면 `approved_with_edit`가 False로 떨어져 에러 없이 목록에서
        사라진다 — 그 경로가 실제로 침묵 실패임을 여기서 실측 고정한다.
        """
        assert is_review_status_cleared(review_status_for_verdict(VERDICT_APPROVED_WITH_EDIT))
        assert not is_review_status_cleared(VERDICT_APPROVED_WITH_EDIT)  # 직접 복사 = 조용한 탈락

    def test_rejected_maps_to_rejected(self) -> None:
        assert review_status_for_verdict("rejected") is ReviewStatus.rejected

    def test_none_is_undecided_not_a_status(self) -> None:
        assert review_status_for_verdict(None) is None

    def test_unknown_verdict_raises_instead_of_guessing(self) -> None:
        """상류가 확장됐는데 변환이 따라가지 않은 상태를 조용히 통과시키지 않는다."""
        with pytest.raises(ValueError, match="어휘 밖"):
            review_status_for_verdict("escalate")

    def test_review_status_vocabulary_did_not_absorb_the_verdict(self) -> None:
        """`approved_with_edit`는 ReviewStatus에 넣지 않는다 — §13.3 노출 정책 보호."""
        assert VERDICT_APPROVED_WITH_EDIT not in {m.value for m in ReviewStatus}
