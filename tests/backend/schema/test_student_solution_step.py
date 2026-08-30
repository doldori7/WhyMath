"""StudentSolutionStep Pydantic 계약(`schema/student_solution_step.py`) — 검증 경계 (EOS-46).

`test_answer_submission.py`(EOS-32)·`test_hint_usage.py`(EOS-45) 컨벤션 미러: DB 0·순수 모델
검증만. expression 원문 보존·필수 필드·StepValidation 경계(빈 method 금지 — 침묵 valid 위장
차단)·concept_ids 기본 빈 목록을 못박는다.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.schema.student_solution_step import StepValidation, StudentSolutionStep


def _minimal(**overrides: object) -> StudentSolutionStep:
    base: dict[str, object] = {
        "attempt_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "sequence_no": 1,
        "expression": "x = 2",
    }
    base.update(overrides)
    return StudentSolutionStep.model_validate(base)


class TestStudentSolutionStepContract:
    def test_minimal_valid_defaults(self) -> None:
        """필수 4필드만으로 유효 — 구조·검증·태그는 None/빈(미수행=정직 기본값)."""
        step = _minimal()
        assert step.canonical_ast is None  # 구조화 미수행(날조 금지)
        assert step.validation is None  # 미검증(미검증≠무효)
        assert step.concept_ids == []  # 미태깅(매칭 확정분만)
        assert step.submitted_at is None  # DB server_default now()가 채운다

    def test_expression_required_and_nonempty(self) -> None:
        """빈 step 없음 — expression은 required·min_length=1."""
        with pytest.raises(ValidationError):
            _minimal(expression="")
        with pytest.raises(ValidationError):
            StudentSolutionStep.model_validate(
                {"attempt_id": uuid.uuid4(), "user_id": uuid.uuid4(), "sequence_no": 1}
            )

    def test_expression_whitespace_preserved_verbatim(self) -> None:
        """EOS-32 P2 동형 — step 본문은 바이트 동일 보존(strip 정규화 금지·증거 보존)."""
        raw = "  x^2 = 4 \n"
        assert _minimal(expression=raw).expression == raw

    @pytest.mark.parametrize("value", [0, -1])
    def test_sequence_no_must_be_at_least_one(self, value: int) -> None:
        """순번은 1부터(ge=1)."""
        with pytest.raises(ValidationError):
            _minimal(sequence_no=value)

    def test_attempt_and_user_required(self) -> None:
        """attempt 없는 step·학생 없는 step은 없다(required)."""
        with pytest.raises(ValidationError):
            StudentSolutionStep.model_validate(
                {"user_id": uuid.uuid4(), "sequence_no": 1, "expression": "x=2"}
            )
        with pytest.raises(ValidationError):
            StudentSolutionStep.model_validate(
                {"attempt_id": uuid.uuid4(), "sequence_no": 1, "expression": "x=2"}
            )

    def test_extra_fields_forbidden(self) -> None:
        """extra='forbid' — 오타 필드가 조용히 버려지지 않는다."""
        with pytest.raises(ValidationError):
            _minimal(unknown_field="x")

    def test_concept_ids_nested(self) -> None:
        """UC 개념 id 목록 수용(느슨참조 — solution_paths.concept_sequence 동형)."""
        step = _minimal(concept_ids=["math.calculus.limit", "math.algebra.factorization"])
        assert step.concept_ids == ["math.calculus.limit", "math.algebra.factorization"]


class TestStepValidationContract:
    def test_method_must_be_nonempty(self) -> None:
        """빈 method 금지 — 검증 없는 판정을 판정으로 위장하지 않는다(SymPy 단일 권위)."""
        with pytest.raises(ValidationError):
            StepValidation(is_valid=True, method="")

    def test_valid_validation_nested_in_step(self) -> None:
        """서브모델이 step에 중첩 수용된다(JSONB 구조 계약)."""
        step = _minimal(validation={"is_valid": False, "method": "sympy_step_check"})
        assert step.validation is not None
        assert step.validation.is_valid is False
        assert step.validation.detail is None
