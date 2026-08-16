"""VariableEngine 테스트 — 결정론적 생성·제약 검증."""

import pytest

from whymath_backend.l3.dsl.models import (
    ConstraintSpec,
    ProblemTemplate,
    VariableSpec,
)
from whymath_backend.l3.dsl.variable_engine import VariableEngine


def test_variable_engine_deterministic_with_seed() -> None:
    template = ProblemTemplate(
        template="{a}x + {b} = {c}",
        variables={
            "a": VariableSpec(type="integer", range=(2, 9)),
            "b": VariableSpec(type="integer", range=(-20, 20)),
            "c": VariableSpec(type="integer", range=(-20, 40)),
        },
    )
    engine = VariableEngine(template)
    b1 = engine.generate(seed=42)
    b2 = engine.generate(seed=42)
    assert b1.values == b2.values


def test_variable_engine_constraint_satisfaction() -> None:
    template = ProblemTemplate(
        template="{a}x + {b} = {c}",
        variables={
            "a": VariableSpec(type="integer", range=(2, 9)),
            "b": VariableSpec(type="integer", range=(-20, 20)),
            "c": VariableSpec(type="integer", range=(-20, 40)),
        },
        constraints=(ConstraintSpec(expression="(c - b) % a == 0"),),
    )
    engine = VariableEngine(template)
    binding = engine.generate(seed=42)
    a = int(binding.values["a"])
    b = int(binding.values["b"])
    c = int(binding.values["c"])
    assert (c - b) % a == 0


def test_variable_engine_raises_when_no_solution() -> None:
    template = ProblemTemplate(
        template="{a}",
        variables={"a": VariableSpec(type="integer", range=(2, 2))},
        constraints=(ConstraintSpec(expression="a == 3"),),
    )
    engine = VariableEngine(template)
    with pytest.raises(ValueError, match="제약을 만족하는 변수 조합"):
        engine.generate(seed=0)


def test_variable_engine_instantiate_applies_binding() -> None:
    template = ProblemTemplate(
        template="{a}x + {b} = {c}",
        variables={
            "a": VariableSpec(type="integer", range=(2, 2)),
            "b": VariableSpec(type="integer", range=(4, 4)),
            "c": VariableSpec(type="integer", range=(12, 12)),
        },
    )
    engine = VariableEngine(template)
    binding = engine.generate(seed=0)
    assert binding.values == {"a": "2", "b": "4", "c": "12"}
    text = engine.instantiate(binding)
    assert text == "2x + 4 = 12"


def test_variable_engine_fixed_statement() -> None:
    template = ProblemTemplate(statement="x + 2 = 5 일 때 x를 구하여라.")
    engine = VariableEngine(template)
    binding = engine.generate(seed=0)
    assert binding.values == {}
    text = engine.instantiate(binding)
    assert text == "x + 2 = 5 일 때 x를 구하여라."
