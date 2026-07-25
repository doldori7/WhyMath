"""렌더 → SymPy 검증 green — 완전예제/문제형이 검증 통과 콘텐츠만 clean 노출(03c §2·§3).

핵심 계약: WORKED_EXAMPLE·PROBLEM_BASED는 렌더한 assessment 정답을 `verify_answer`로 SymPy
검산하고, `state=='pass'`일 때만 `validation_signal=None`(clean)로 내보낸다. 틀린 정답을 담은
DSL은 검증에서 걸려 노출이 차단된다(미검증 노출 금지).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.l3.render.models import RenderContext
from whymath_backend.l3.render.registry import get_adapter
from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.schema.concept_dsl import (
    AssessmentSeed,
    ConceptDSL,
    ExampleSpec,
    build_example_concept_dsl,
)
from whymath_backend.schema.enums import PedagogyStrategy

_CTX = RenderContext()


def _quadratic_selection_dsl() -> ConceptDSL:
    """이차 조건 + 근 선택(largest) DSL — x²-5x+6=0의 큰 근은 3(derive-and-verify)."""
    return ConceptDSL(
        name="math.algebra.quadratic-larger-root",
        definition="$x^2 - 5x + 6 = 0$의 큰 근을 구하는 개념.",
        examples=[ExampleSpec(statement="$x^2 - 5x + 6 = 0$", slots={"context": "포물선"})],
        assessment=[
            AssessmentSeed(
                conditions=["x**2 - 5*x + 6 = 0"],
                answer={"x": "3"},
                selection="largest",
                prompt="$x^2 - 5x + 6 = 0$의 큰 근을 구하시오.",
            ),
        ],
    )


class TestRenderThenVerifyGreen:
    """렌더한 시드 정답을 SymPy로 재검증 — pass(green)."""

    def test_linear_worked_example_verifies_pass(self) -> None:
        """일차(2x+3=7→x=2) 완전예제 — 렌더 clean + verify_answer pass."""
        dsl = build_example_concept_dsl(coef=2, const=3, rhs=7)  # x = 2
        adapter = get_adapter(PedagogyStrategy.WORKED_EXAMPLE)
        assert adapter is not None
        unit = adapter.render(dsl, _CTX)
        assert unit.validation_signal is None  # 검증 통과분만 clean

        seed = dsl.assessment[0]
        assert verify_answer(seed.conditions, seed.answer).state == "pass"

    def test_quadratic_selection_worked_example_verifies_pass(self) -> None:
        """이차+근 선택(큰 근=3) 완전예제 — derive-and-verify로 clean + verify pass."""
        dsl = _quadratic_selection_dsl()
        adapter = get_adapter(PedagogyStrategy.WORKED_EXAMPLE)
        assert adapter is not None
        unit = adapter.render(dsl, _CTX)
        assert unit.validation_signal is None
        # 결론 블록에 유도된 큰 근(3)이 담긴다.
        assert any("x = 3" in b.text for b in unit.blocks)

        seed = dsl.assessment[0]
        assert verify_answer(seed.conditions, seed.answer).state == "pass"

    def test_problem_based_verifies_before_presenting(self) -> None:
        """문제형 — 내부 검증 통과 시 clean(문제 제시), 정답 값은 노출하지 않는다."""
        dsl = build_example_concept_dsl(coef=3, const=1, rhs=10)  # x = 3
        adapter = get_adapter(PedagogyStrategy.PROBLEM_BASED)
        assert adapter is not None
        unit = adapter.render(dsl, _CTX)
        assert unit.validation_signal is None
        # 정답 값('3')은 학생에게 노출되지 않는다(문제부터 제시·정답 미노출).
        assert all("= 3" not in b.text for b in unit.blocks)

        seed = dsl.assessment[0]
        assert verify_answer(seed.conditions, seed.answer).state == "pass"


class TestRenderVerifyBlocksBadContent:
    """틀린 정답을 담은 DSL은 검증에서 걸려 노출 차단(validation_signal 실림)."""

    def test_wrong_answer_worked_example_flags_signal(self) -> None:
        """정답이 틀린 시드(2x+3=7인데 x=99) — 완전예제가 검증 실패 신호를 실어 노출 차단."""
        dsl = ConceptDSL(
            name="math.algebra.bad-answer",
            definition="정의",
            examples=[ExampleSpec(statement="$2x + 3 = 7$")],
            assessment=[AssessmentSeed(conditions=["2*x + 3 = 7"], answer={"x": "99"})],
        )
        adapter = get_adapter(PedagogyStrategy.WORKED_EXAMPLE)
        assert adapter is not None
        unit = adapter.render(dsl, _CTX)
        assert unit.validation_signal is not None  # 미검증 → 노출 차단
        assert unit.validation_signal.kind == "solution"

    def test_wrong_answer_problem_based_flags_signal(self) -> None:
        """문제형도 malformed(틀린 정답) 시드를 검증 실패로 걸러 노출 차단."""
        dsl = ConceptDSL(
            name="math.algebra.bad-answer",
            definition="정의",
            assessment=[AssessmentSeed(conditions=["2*x + 3 = 7"], answer={"x": "99"})],
        )
        adapter = get_adapter(PedagogyStrategy.PROBLEM_BASED)
        assert adapter is not None
        unit = adapter.render(dsl, _CTX)
        assert unit.validation_signal is not None


class TestConditionDslViolationGate:
    """condition_dsl_violation — pseudo-DSL 조건 거부(정상 조건은 통과)."""

    def test_pseudo_dsl_rejected(self) -> None:
        assert condition_dsl_violation("largest_root(2, 8) == 8") is not None

    def test_valid_condition_accepted(self) -> None:
        assert condition_dsl_violation("2*x + 3 = 7") is None
