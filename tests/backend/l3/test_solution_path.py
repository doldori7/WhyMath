"""SolutionPath/SolutionStep/Justification invariant 테스트 — S4-09 (hermetic).

`schemas/v1.1/solution_path.schema.yaml`의 `validation_invariants`를 1:1로 검증한다 —
각 invariant에 대해 **성공 케이스와 실패 케이스 양쪽**을 둔다("실패 상태에서 실제로 실패
신호를 내는지" 변별력 — CLAUDE.md 변별력 없는 검증 스텝 금지).

Pydantic 소관 invariant(이 파일):
  - steps order 1부터 연속(중복·건너뜀·역순 거부)
  - justification.prior_step_orders 각 값 < 현재 order(전방·자기참조 금지·비순환)
  - reasoning_type 폐쇄 7종 밖 거부(기존 좌석 `schema/enums.py::ReasoningType` 소비 — 신설 0)
  - approach_type 6종 밖 거부(Literal — Enum 클래스 신설 0·S4-10에서 좌석 승격)
  - reasoning_type·justification 미지정 스텝도 유효(하위호환·strict superset)

적재 시점 소관(여기서 검증 *안 함* — 경계 명시): problem_id/concept ID 실재(cross-dataset)는
`whs/path_promotion.py`(존재 확인)·DB FK가 강제한다 — `tests/backend/whs/test_path_promotion.py`
가 그 분기를 검증한다. `equivalence_cluster_id`의 "확정 동치 아님" invariant는 판정 로직이
아니라 소비 측 정책(S4-12·D4)이라 여기서는 필드 수용만 본다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from whymath_backend.l3.solution_path import (
    APPROACH_TYPES,
    Justification,
    SolutionPath,
    SolutionStep,
)
from whymath_backend.schema.enums import ReasoningType

_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _step(order: int, **overrides: Any) -> dict[str, Any]:
    """유효 스텝 dict 빌더 — content는 렌더러-중립 표현식 문자열."""
    data: dict[str, Any] = {"order": order, "content": f"x**2 - {order} = 0"}
    data.update(overrides)
    return data


def _path(**overrides: Any) -> SolutionPath:
    """유효 SolutionPath 빌더(3스텝) — 테스트가 일부 필드만 바꿔 쓴다."""
    data: dict[str, Any] = {
        "solution_path_id": "sp-test-1",
        "problem_id": "11111111-1111-1111-1111-111111111111",
        "approach_type": "algebraic",
        "concept_sequence": [],
        "steps": [_step(1), _step(2), _step(3)],
        "created_at": _NOW,
    }
    data.update(overrides)
    return SolutionPath.model_validate(data)


# ==========================================================================
# invariant: steps order 1부터 연속
# ==========================================================================
class TestStepsOrderConsecutive:
    def test_valid_consecutive_orders_pass(self) -> None:
        """성공: 1..n 연속 order는 통과한다."""
        path = _path()
        assert [s.order for s in path.steps] == [1, 2, 3]

    def test_empty_steps_pass(self) -> None:
        """성공: 빈 steps는 자명 통과(비어있음 금지 invariant는 yaml에 없음 — 어댑터가 스킵)."""
        assert _path(steps=[]).steps == []

    def test_orders_not_starting_at_one_rejected(self) -> None:
        """실패: 2부터 시작(1 누락)은 거부."""
        with pytest.raises(ValidationError, match="1부터 연속"):
            _path(steps=[_step(2), _step(3)])

    def test_gap_in_orders_rejected(self) -> None:
        """실패: 건너뜀(1, 3)은 거부."""
        with pytest.raises(ValidationError, match="1부터 연속"):
            _path(steps=[_step(1), _step(3)])

    def test_duplicate_orders_rejected(self) -> None:
        """실패: 중복 order(1, 1)는 거부."""
        with pytest.raises(ValidationError, match="1부터 연속"):
            _path(steps=[_step(1), _step(1)])

    def test_descending_orders_rejected(self) -> None:
        """실패: 역순(2, 1)은 거부 — 리스트 순서 = order 순서(정규형)."""
        with pytest.raises(ValidationError, match="1부터 연속"):
            _path(steps=[_step(2), _step(1)])

    def test_zero_order_rejected(self) -> None:
        """실패: order=0은 스텝 자체 제약(ge=1)이 거부(1부터 정의)."""
        with pytest.raises(ValidationError):
            SolutionStep.model_validate(_step(0))


# ==========================================================================
# invariant: justification.prior_step_orders 각 값 < 현재 order (전방·자기참조 금지)
# ==========================================================================
class TestJustificationPriorStepOrders:
    def test_prior_reference_passes(self) -> None:
        """성공: 이전 스텝(1, 2)을 참조하는 3번 스텝은 통과."""
        step = SolutionStep.model_validate(_step(3, justification={"prior_step_orders": [1, 2]}))
        assert step.justification is not None
        assert step.justification.prior_step_orders == [1, 2]

    def test_self_reference_rejected(self) -> None:
        """실패: 자기참조(order=2가 2를 참조)는 거부."""
        with pytest.raises(ValidationError, match="전방참조·자기참조"):
            SolutionStep.model_validate(_step(2, justification={"prior_step_orders": [2]}))

    def test_forward_reference_rejected(self) -> None:
        """실패: 전방참조(order=1이 2를 참조)는 거부(비순환)."""
        with pytest.raises(ValidationError, match="전방참조·자기참조"):
            SolutionStep.model_validate(_step(1, justification={"prior_step_orders": [2]}))

    def test_nonpositive_reference_rejected(self) -> None:
        """실패: 0 이하 참조는 어떤 스텝도 가리키지 않는 무의미 참조 — 거부."""
        with pytest.raises(ValidationError, match="전방참조·자기참조"):
            SolutionStep.model_validate(_step(3, justification={"prior_step_orders": [0]}))

    def test_within_path_forward_reference_rejected(self) -> None:
        """실패: 경로 조립 시에도 스텝 검증기가 전방참조를 거부한다(경로 차원 회귀)."""
        with pytest.raises(ValidationError, match="전방참조·자기참조"):
            _path(
                steps=[
                    _step(1, justification={"prior_step_orders": [3]}),
                    _step(2),
                    _step(3),
                ]
            )

    def test_reference_lists_default_empty(self) -> None:
        """성공: Justification 3필드는 기본 빈 리스트(얇은 참조 묶음)."""
        justification = Justification()
        assert justification.theorem_concept_ids == []
        assert justification.concept_node_ids == []
        assert justification.prior_step_orders == []


# ==========================================================================
# invariant: reasoning_type 폐쇄 7종 밖 거부 (기존 enum 좌석 소비·신설 금지)
# ==========================================================================
class TestReasoningTypeClosedEnum:
    def test_all_seven_members_pass(self) -> None:
        """성공: 폐쇄 7종 전원이 수용된다(기존 좌석 `ReasoningType` 소비)."""
        assert len(ReasoningType) == 7
        for member in ReasoningType:
            step = SolutionStep.model_validate(_step(1, reasoning_type=member.value))
            assert step.reasoning_type == member.value

    def test_outside_value_rejected(self) -> None:
        """실패: 폐쇄집합 밖 값은 거부(무한 온톨로지 금지)."""
        with pytest.raises(ValidationError):
            SolutionStep.model_validate(_step(1, reasoning_type="GUESSING"))

    def test_lowercase_value_rejected(self) -> None:
        """실패: 소문자 표기(yaml 키)는 구현 정본 값(대문자·enum 단일 좌석)이 아니다 — 거부."""
        with pytest.raises(ValidationError):
            SolutionStep.model_validate(_step(1, reasoning_type="deduction"))

    def test_untagged_step_valid(self) -> None:
        """성공: reasoning_type·justification 미지정 스텝도 유효(하위호환·strict superset)."""
        step = SolutionStep.model_validate(_step(1))
        assert step.reasoning_type is None
        assert step.justification is None


# ==========================================================================
# invariant: approach_type 6종 밖 거부 (Literal — Enum 클래스 신설 0)
# ==========================================================================
class TestApproachTypeClosedSet:
    def test_all_six_values_pass(self) -> None:
        """성공: 폐쇄 6종 전원이 수용된다(거버넌스 테스트 리터럴과 동일 집합)."""
        assert set(APPROACH_TYPES) == {
            "algebraic",
            "geometric",
            "combinatorial",
            "inductive",
            "visual",
            "backward",
        }
        for value in APPROACH_TYPES:
            assert _path(approach_type=value).approach_type == value

    def test_outside_value_rejected(self) -> None:
        """실패: 6종 밖 값("비유적" — 프롬프트 불일치 실측값)은 거부."""
        with pytest.raises(ValidationError):
            _path(approach_type="비유적")

    def test_no_enum_class_created(self) -> None:
        """approach_type용 Enum 클래스를 *신설하지 않았다* — schema/enums.py 단일 좌석 규약.

        좌석 승격(ApproachType Enum)은 S4-10 몫이다. 여기서는 schema.enums에 ApproachType이
        아직 없음을 동결한다(S4-10이 들어오면 이 테스트를 좌석 참조 검증으로 교체).
        """
        import whymath_backend.schema.enums as enums

        assert not hasattr(enums, "ApproachType")


# ==========================================================================
# 필드 계약 — yaml 1:1(embedding 부재·기본값·동치 후보 필드 수용)
# ==========================================================================
class TestFieldContract:
    def test_embedding_field_absent(self) -> None:
        """`embedding` 필드는 없다 — S4-12에서 판정(acceptance 명시·extra=forbid가 거부)."""
        assert "embedding" not in SolutionPath.model_fields
        with pytest.raises(ValidationError):
            _path(embedding=[0.1, 0.2])

    def test_verified_by_human_defaults_false(self) -> None:
        """`verified_by_human` 기본 false — 승격 직후는 항상 미검수(AI 자기승인 금지)."""
        assert _path().verified_by_human is False

    def test_equivalence_cluster_id_accepts_value_and_none(self) -> None:
        """`equivalence_cluster_id`는 값/None 수용 — 값이 있어도 '후보 군집'일 뿐(정직 경계)."""
        assert _path().equivalence_cluster_id is None
        assert _path(equivalence_cluster_id="eqc-1").equivalence_cluster_id == "eqc-1"

    def test_content_preserved_byte_exact(self) -> None:
        """content는 문자열 그대로 보존(표현≠의미 — strip·정규화 없음)."""
        raw = "  \\frac{1}{2}x^2 + C  "
        step = SolutionStep.model_validate(_step(1, content=raw))
        assert step.content == raw

    def test_sympy_verified_defaults_false(self) -> None:
        """`sympy_verified` 기본 false — 검증 통과를 기본값으로 위장하지 않는다."""
        assert SolutionStep.model_validate(_step(1)).sympy_verified is False
        assert SolutionStep.model_validate(_step(1)).lean_verified is None

    def test_unknown_field_rejected(self) -> None:
        """extra=forbid — 미지 필드 밀반입 거부(renderer/curriculum 혼입 등 구조 붕괴 방지)."""
        with pytest.raises(ValidationError):
            SolutionStep.model_validate(_step(1, renderer="mathjax"))
