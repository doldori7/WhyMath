"""AnswerSubmission Pydantic 계약(`schema/answer_submission.py`) — 검증 경계 (EOS-32).

`test_activity.py`류 hermetic 컨벤션: DB 0·순수 모델 검증만. 폐쇄 어휘(response_type Literal)·
순번 하한(sequence_no ≥ 1)·필수 필드·extra 금지·서브모델(GradingResult/ErrorAnalysis) 경계를
못박는다 — DB 컬럼은 값만 담으므로(String/JSONB 좌석) 이 Literal·검증이 유일한 강제 지점이다
(`misconception_relation.relation_type` 선례).
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.schema.answer_submission import (
    AnswerSubmission,
    ErrorAnalysis,
    GradingResult,
)


def _minimal(**overrides: object) -> AnswerSubmission:
    base: dict[str, object] = {
        "attempt_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "sequence_no": 1,
        "response_type": "text",
    }
    base.update(overrides)
    return AnswerSubmission.model_validate(base)


class TestAnswerSubmissionContract:
    def test_minimal_valid_defaults(self) -> None:
        """필수 4필드만으로 유효 — 나머지는 None/자동(submission_id 자동·submitted_at DB 몫)."""
        sub = _minimal()
        assert sub.sequence_no == 1
        assert sub.raw_response is None
        assert sub.canonical_ast is None
        assert sub.grading_result is None
        assert sub.error_analysis is None
        assert sub.submitted_at is None  # DB server_default now()가 채운다

    @pytest.mark.parametrize("value", ["latex", "text", "choice", "handwriting"])
    def test_response_type_closed_vocabulary_accepts(self, value: str) -> None:
        """폐쇄 4종은 전부 수용(subject-neutral 제출 양식)."""
        assert _minimal(response_type=value).response_type == value

    @pytest.mark.parametrize("value", ["essay", "LATEX", "수식", ""])
    def test_response_type_rejects_out_of_vocabulary(self, value: str) -> None:
        """폐쇄 4종 밖(오타·대소문자·한글·빈 문자열)은 ValidationError — DB는 값만 담으므로
        이 Literal이 유일한 강제 지점이다."""
        with pytest.raises(ValidationError):
            _minimal(response_type=value)

    @pytest.mark.parametrize("value", [0, -1])
    def test_sequence_no_must_be_at_least_one(self, value: int) -> None:
        """순번은 1부터(ge=1) — 0/음수는 거부."""
        with pytest.raises(ValidationError):
            _minimal(sequence_no=value)

    def test_attempt_and_user_required(self) -> None:
        """attempt 없는 제출·학생 없는 제출은 없다(required — 신규 수집 정합)."""
        with pytest.raises(ValidationError):
            AnswerSubmission.model_validate(
                {"user_id": uuid.uuid4(), "sequence_no": 1, "response_type": "text"}
            )
        with pytest.raises(ValidationError):
            AnswerSubmission.model_validate(
                {"attempt_id": uuid.uuid4(), "sequence_no": 1, "response_type": "text"}
            )

    def test_extra_fields_forbidden(self) -> None:
        """extra='forbid' — 오타 필드가 조용히 버려지지 않는다."""
        with pytest.raises(ValidationError):
            _minimal(unknown_field="x")


class TestGradingResultContract:
    def test_method_must_be_nonempty(self) -> None:
        """빈 method 금지 — 검증 없는 판정을 판정으로 위장하지 않는다(min_length=1)."""
        with pytest.raises(ValidationError):
            GradingResult(is_correct=True, method="")

    def test_valid_grading_nested_in_submission(self) -> None:
        """서브모델이 제출에 중첩 수용된다(JSONB 구조 계약)."""
        sub = _minimal(
            grading_result={"is_correct": True, "method": "sympy_equivalence"},
        )
        assert sub.grading_result is not None
        assert sub.grading_result.is_correct is True
        assert sub.grading_result.detail is None


class TestErrorAnalysisContract:
    def test_default_empty_misconception_list(self) -> None:
        """기본 빈 목록 = 의심 오개념 없음(None 아님 — 목록 계약 고정)."""
        assert ErrorAnalysis().suspected_misconception_ids == []

    def test_misconception_ids_nested_in_submission(self) -> None:
        """kebab-case 카탈로그 id 목록이 제출에 중첩 수용된다(evidence_links 1급 입력 좌석)."""
        sub = _minimal(
            error_analysis={"suspected_misconception_ids": ["distribution-over-power"]},
        )
        assert sub.error_analysis is not None
        assert sub.error_analysis.suspected_misconception_ids == ["distribution-over-power"]
