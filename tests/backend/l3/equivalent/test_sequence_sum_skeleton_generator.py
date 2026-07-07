"""수열의 합(등차·등비) 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

등차합(Sₙ=n(2a+(n−1)d)/2)·등비합(Sₙ=a(rⁿ−1)/(r−1)) 두 형제 생성기가 ① 전건 S2-a 4종 게이트 통과
② answer가 derive_selected_root와 일치(교차 검증·독립 재계산) ③ 결정론·풀 유일 ④ **답 유일 →
signature 유일**(구조 dedup 오병합 방지) ⑤ 개념 태깅·유일해 선택·정수 합을 못 박는다. LLM·DB·PG 0.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.sequence_sum_skeleton_generator import (
    ArithmeticSumSkeletonGenerator,
    GeometricSumSkeletonGenerator,
    _build_arith_sum_pool,
    _build_geo_sum_pool,
)
from whymath_backend.l3.verify_answer import derive_selected_root

_ARITH_STANDARD = "[12대수03-02]"
_GEO_STANDARD = "[12대수03-03]"


def _spec(code: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({code}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.2,
        answer_format=None,
    )


def _drain(gen: object, code: str, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec(code))  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestArithmeticSumGenerator:
    def test_pool_answers_unique_and_positive(self) -> None:
        pool = _build_arith_sum_pool()
        assert len(pool) >= 30
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))  # 답 유일(signature 유일 보장)
        assert all(a > 0 for a in answers)

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 500)
        assert len(candidates) >= 30
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(_ARITH_STANDARD),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        # 교차 검증 — answer가 합 공식의 독립 SymPy 재계산과 정수 일치(계산 버그 차단).
        for candidate in _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 500):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signatures_unique(self) -> None:
        cands = _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 500)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = ArithmeticSumSkeletonGenerator().generate(_spec(_ARITH_STANDARD))
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수03-02"]
        assert candidate.problem.question_format == "단답형"
        assert "합" in candidate.problem.question_text

    def test_deterministic_sequence(self) -> None:
        a = _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 6)
        b = _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]


class TestGeometricSumGenerator:
    def test_pool_integer_answers_unique(self) -> None:
        pool = _build_geo_sum_pool()
        assert len(pool) >= 20
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))
        assert all(a > 0 for a in answers)
        assert all(s._is_integer for s in pool)  # 정수 합만 채택

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(GeometricSumSkeletonGenerator(), _GEO_STANDARD, 500)
        assert len(candidates) >= 20
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(_GEO_STANDARD),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        for candidate in _drain(GeometricSumSkeletonGenerator(), _GEO_STANDARD, 500):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signatures_unique(self) -> None:
        cands = _drain(GeometricSumSkeletonGenerator(), _GEO_STANDARD, 500)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = GeometricSumSkeletonGenerator().generate(_spec(_GEO_STANDARD))
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수03-03"]


class TestCrossFamily:
    def test_arith_sum_and_geo_sum_slugs_disjoint(self) -> None:
        arith = {
            c.problem.slug for c in _drain(ArithmeticSumSkeletonGenerator(), _ARITH_STANDARD, 500)
        }
        geo = {c.problem.slug for c in _drain(GeometricSumSkeletonGenerator(), _GEO_STANDARD, 500)}
        assert arith.isdisjoint(geo)
