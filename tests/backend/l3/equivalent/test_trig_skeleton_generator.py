"""삼각함수 특수각 값 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

sin/cos/tan 특수각 값 생성기가 ① 전건 S2-a 4종 게이트 통과(게이트 인프라 무변경 재사용 실증)
② answer가 derive_selected_root와 **글자·수치 일치**(교차 검증·sstr 정합) ③ 결정론·값 유일
④ **값 유일 → signature 유일**(구조 dedup 오병합 방지) ⑤ 미정의 각(tan 90°) 자동 제외
⑥ 개념 태깅·유일해 선택을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import sympy

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.trig_skeleton_generator import (
    TrigonometricValueSkeletonGenerator,
    _build_trig_pool,
)
from whymath_backend.l3.verify_answer import derive_selected_root

_STANDARD = "[12대수02-02]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _drain(gen: object, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestTrigGenerator:
    def test_pool_values_unique_and_finite(self) -> None:
        pool = _build_trig_pool()
        assert len(pool) >= 10
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))  # 값 유일(signature 유일 보장)
        # tan 90°·270°(미정의)는 풀에 없다.
        assert all(s.value.is_finite is True for s in pool)
        assert not any(s.degree in (90, 270) and s.func == "tan" for s in pool)

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(TrigonometricValueSkeletonGenerator(), 100)
        assert len(candidates) >= 10
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        # 교차 검증 — answer가 조건식의 독립 SymPy 재계산과 **기호적으로** 일치(무리수 포함).
        for candidate in _drain(TrigonometricValueSkeletonGenerator(), 100):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            diff = sympy.simplify(sympy.sympify(derived) - sympy.sympify(candidate.answer_map["x"]))
            assert (
                diff == 0
            ), f"{candidate.conditions}: derive={derived} ans={candidate.answer_map['x']}"

    def test_signatures_unique(self) -> None:
        # 값 유일 → signature 유일(같은 값 다른 각의 구조 dedup 충돌 방지).
        cands = _drain(TrigonometricValueSkeletonGenerator(), 100)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_irrational_answer_format_is_real(self) -> None:
        # 무리수 값(sqrt 포함)은 실수 형식·반올림 소수 0(무리근 형제 규약 미러).
        for candidate in _drain(TrigonometricValueSkeletonGenerator(), 100):
            if "sqrt" in candidate.answer_map["x"]:
                assert candidate.problem.answer_format == "실수"
                assert "." not in (candidate.problem.answer or "")

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = TrigonometricValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수02-02"]
        assert candidate.problem.question_format == "단답형"

    def test_deterministic_sequence(self) -> None:
        a = _drain(TrigonometricValueSkeletonGenerator(), 6)
        b = _drain(TrigonometricValueSkeletonGenerator(), 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]
