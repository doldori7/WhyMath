"""ConceptDSL 계약 검증 — 방식-중립 동결 + 닫힌-DSL 게이트(03c §1).

`schema/concept_dsl.py`(순수 데이터 계약)와 `l3/render/dsl_gate.py`(SymPy 닫힌-DSL 게이트)를
함께 검증한다. 게이트가 l3에 있는 이유는 schema가 7계층 최하위라 SymPy 래퍼를 import할 수 없기
때문이다(import-linter 역방향 금지·모듈 docstring 참조).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from whymath_backend.l3.render.dsl_gate import assessment_dsl_violation, validate_concept_dsl
from whymath_backend.schema.concept_dsl import (
    AssessmentSeed,
    ConceptDSL,
    ExampleSpec,
    build_example_concept_dsl,
)


class TestNeutralityContract:
    """방식-중립 — 방식/전략 필드 주입·증식 양방향 차단."""

    def test_factory_builds_valid_dsl(self) -> None:
        """팩토리는 유효한 중립 DSL을 만든다(정의·예시·평가 시드 보유)."""
        dsl = build_example_concept_dsl()
        assert dsl.name == "math.algebra.linear-equation"
        assert dsl.assessment and dsl.assessment[0].answer == {"x": "2"}
        assert dsl.examples

    def test_extra_forbid_rejects_strategy_field(self) -> None:
        """extra=forbid — 외부에서 방식 필드(strategy)를 주입하면 거부(구성 시점 차단)."""
        with pytest.raises(ValidationError):
            ConceptDSL(  # type: ignore[call-arg]  # 의도적 미지 필드(거부 확인)
                name="math.x",
                definition="정의",
                strategy="SOCRATIC",
            )

    def test_extra_forbid_rejects_method_field(self) -> None:
        """extra=forbid — 'teaching_method' 같은 방식 필드도 거부."""
        with pytest.raises(ValidationError):
            ConceptDSL(  # type: ignore[call-arg]  # 의도적 미지 필드(거부 확인)
                name="math.x",
                definition="정의",
                teaching_method="direct",
            )

    def test_governance_freezes_field_name_against_method_token(self) -> None:
        """_governance — 계약 필드명에 방식 토큰이 새어들면 즉시 거부(내부 증식 동결).

        미래 세션이 `strategy` 필드를 심는 상황을 하위 클래스로 시뮬레이션한다 — model_fields에
        'strategy'가 들어오면 _governance가 방식 토큰을 잡아 ValueError를 던진다.
        """

        class LeakyDSL(ConceptDSL):
            strategy: str = "SOCRATIC"  # 방식 필드 유입(금지) — 거버넌스가 잡아야 한다.

        with pytest.raises(ValidationError) as exc:
            LeakyDSL(name="math.x", definition="정의")
        assert "방식 토큰" in str(exc.value)


class TestAssessmentSeed:
    """평가 시드 — 정답 비어있음·근 선택 허용값 검증."""

    def test_empty_answer_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentSeed(conditions=["x = 1"], answer={})

    def test_bad_selection_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentSeed(conditions=["x**2 = 4"], answer={"x": "2"}, selection="middle")

    def test_valid_selection_accepted(self) -> None:
        seed = AssessmentSeed(conditions=["x**2 = 4"], answer={"x": "2"}, selection="largest")
        assert seed.selection == "largest"


class TestClosedDslGate:
    """닫힌-DSL 게이트(l3/render) — pseudo-DSL 조건 거부(condition_dsl_violation 경유)."""

    def test_valid_dsl_passes_gate(self) -> None:
        """정상 (부)등식 조건은 게이트를 조용히 통과(부작용 없음)."""
        dsl = build_example_concept_dsl()
        assert assessment_dsl_violation(dsl) is None
        validate_concept_dsl(dsl)  # 예외 없음

    def test_pseudo_dsl_condition_rejected(self) -> None:
        """pseudo-DSL(미정의 함수 호출)은 게이트에서 위반으로 잡힌다."""
        dsl = ConceptDSL(
            name="math.x",
            definition="정의",
            assessment=[
                AssessmentSeed(conditions=["largest_root(2, 8) == 8"], answer={"x": "8"}),
            ],
        )
        violation = assessment_dsl_violation(dsl)
        assert violation is not None
        assert "assessment[0].conditions[0]" in violation
        with pytest.raises(ValueError, match="닫힌-DSL 위반"):
            validate_concept_dsl(dsl)

    def test_solve_pseudo_dsl_rejected(self) -> None:
        """solve()류 비수식 관계도 거부(닫힌 (부)등식만 허용)."""
        dsl = ConceptDSL(
            name="math.x",
            definition="정의",
            assessment=[
                AssessmentSeed(conditions=["solve(x**2 - 4, x) == [2, -2]"], answer={"x": "2"}),
            ],
        )
        assert assessment_dsl_violation(dsl) is not None


class TestSubmodelExtraForbid:
    """서브모델도 extra=forbid — 예시/시드에 방식 필드 주입 차단."""

    def test_example_spec_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            ExampleSpec(statement="$x=1$", render_as="socratic")  # type: ignore[call-arg]

    def test_example_spec_is_basemodel(self) -> None:
        assert issubclass(ExampleSpec, BaseModel)
