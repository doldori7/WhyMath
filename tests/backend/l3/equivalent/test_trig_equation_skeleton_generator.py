"""삼각방정식 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

sin/cos x = v (0°≤x<360°) 방정식 생성기가 ① 전건 S2-a 4종 게이트 통과 ② answer가
derive_selected_root(selection)와 정확 일치(교차 검증) ③ 결정론·slug 유일 ④ **초월함수라
signature=None**(exp/log형·구조 dedup 우회) ⑤ **빌드 필터가 정수 2근 [0,360)만 채택**(sin 음수값·
tan 배제) ⑥ 개념 태깅·근 선택(smallest/largest)을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.trig_equation_skeleton_generator import (
    TrigonometricEquationSkeletonGenerator,
    _build_trig_eq_pool,
)
from whymath_backend.l3.verify_answer import derive_selected_root

_STANDARD = "[12대수02-02]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.2,
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


class TestTrigEquationGenerator:
    def test_pool_roots_are_integer_degrees_in_domain(self) -> None:
        pool = _build_trig_eq_pool()
        assert len(pool) >= 12
        for s in pool:
            assert 0 <= s.answer < 360  # 정수각·구간 내(빌드 필터 실증)
            assert s.func in {"sin", "cos"}
        # sin 음수값(작은근 음수)은 배제됐다 — sin -1/2 등은 풀에 없다.
        assert not any(s.func == "sin" and s.value_expr.startswith("-") for s in pool)
        # cos·sin 둘 다 대표된다(전부 cos로 쏠리지 않음).
        assert {s.func for s in pool} == {"sin", "cos"}

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(TrigonometricEquationSkeletonGenerator(), 100)
        assert len(candidates) >= 12
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

    def test_answer_matches_selected_root(self) -> None:
        # 교차 검증 — answer가 조건의 derive_selected_root(선택)와 정수 일치.
        for candidate in _drain(TrigonometricEquationSkeletonGenerator(), 100):
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signature_is_none_transcendental(self) -> None:
        # 초월함수 조건 → canonical_signature None(exp/log형). 구조 dedup 우회·slug에 위임.
        for candidate in _drain(TrigonometricEquationSkeletonGenerator(), 100):
            assert canonical_signature(candidate.conditions, candidate.answer_selection) is None

    def test_slugs_unique(self) -> None:
        cands = _drain(TrigonometricEquationSkeletonGenerator(), 100)
        slugs = [c.problem.slug for c in cands]
        assert len(slugs) == len(set(slugs))

    def test_selection_and_concept_tag(self) -> None:
        candidate = TrigonometricEquationSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.answer_selection in {"smallest", "largest"}
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수02-02"]
        assert candidate.problem.question_format == "단답형"
        assert candidate.problem.answer_format == "자연수"

    def test_deterministic_sequence(self) -> None:
        a = _drain(TrigonometricEquationSkeletonGenerator(), 6)
        b = _drain(TrigonometricEquationSkeletonGenerator(), 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]


def test_difficulty_below_quad_factoring() -> None:
    # 계통 관찰 2 회귀 차단(S2-08): 삼각방정식은 값 조회보단 무겁지만 QUAD-EQ(2.0) 언저리 —
    # 대표 최소 < 2.0·상한 ≤ 2.1.
    from whymath_backend.l3.equivalent.difficulty import estimate_difficulty

    quad = estimate_difficulty(root_kind="integer", lead_coefficient=1, max_abs_coefficient=10)
    assert quad == 2.0
    diffs = [
        c.problem.difficulty_overall for c in _drain(TrigonometricEquationSkeletonGenerator(), 100)
    ]
    assert diffs
    assert min(diffs) < quad  # type: ignore[type-var]
    assert max(diffs) <= 2.1  # type: ignore[type-var]
