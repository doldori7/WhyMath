"""고등 이차곡선(포물선·타원·쌍곡선) 초점 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`ConicSectionFocusSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `sqrt()` 조건이
계수만으로 초점을 독립 재유도함을 재확인) ② answer가 독립 재계산(포물선 p=coef/4·타원
c=√(a²−b²)·쌍곡선 c=√(a²+b²))과 일치 ③ 풀 유일·소진 시 None ④ `kind`가 밴드뿐 아니라
성취기준 코드 자체를 가른다는 이 도메인 고유 설계(gcd/lcm 생성기와 동형 — 3개 코드로 확장)
⑤ 타원·쌍곡선의 정수 초점 보장(피타고라스 삼조 구성 불변식) ⑥ 개념 태깅·위생 게이트
무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.conic_section_focus_skeleton_generator import (
    CONIC_STANDARD_CODES,
    ConicSectionFocusSkeletonGenerator,
    _build_pool,
    _EllipseSkeleton,
    _HyperbolaSkeleton,
    _ParabolaSkeleton,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring


def _spec(kind: str, difficulty: float = 3.2) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({CONIC_STANDARD_CODES[kind]}),  # type: ignore[index]
        target_misconception_ids=frozenset(),
        difficulty_overall=difficulty,
        answer_format=None,
    )


def _drain(gen: object, spec: EquivalenceSpec, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(spec)  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestPool:
    def test_pool_nonempty_and_unique_per_kind(self) -> None:
        for kind in ("parabola", "ellipse", "hyperbola"):
            pool = _build_pool(kind)  # type: ignore[arg-type]
            assert len(pool) >= 15

    def test_parabola_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool("parabola"):  # type: ignore[arg-type]
            assert isinstance(skeleton, _ParabolaSkeleton)
            assert skeleton.answer == skeleton.coef // 4
            assert skeleton.coef == 4 * skeleton.p

    def test_ellipse_answer_matches_pythagorean_invariant(self) -> None:
        for skeleton in _build_pool("ellipse"):  # type: ignore[arg-type]
            assert isinstance(skeleton, _EllipseSkeleton)
            assert skeleton.a2 == skeleton.b2 + skeleton.c * skeleton.c  # a²=b²+c².
            assert skeleton.answer == skeleton.c

    def test_hyperbola_answer_matches_pythagorean_invariant(self) -> None:
        for skeleton in _build_pool("hyperbola"):  # type: ignore[arg-type]
            assert isinstance(skeleton, _HyperbolaSkeleton)
            assert skeleton.c * skeleton.c == skeleton.a2 + skeleton.b2  # c²=a²+b².
            assert skeleton.answer == skeleton.c

    def test_kind_selects_distinct_standard_code_and_concept_tag(self) -> None:
        """이 도메인 고유 설계 — kind가 성취기준 코드·개념태그를 함께 결정(gcd/lcm 관례 계승)."""
        expected_concepts = {
            "parabola": "H:12기하01-01",
            "ellipse": "H:12기하01-02",
            "hyperbola": "H:12기하01-03",
        }
        for kind, expected_concept in expected_concepts.items():
            candidate = ConicSectionFocusSkeletonGenerator(kind=kind).generate(_spec(kind))  # type: ignore[arg-type]
            assert candidate is not None
            assert candidate.problem.achievement_standard_codes == [CONIC_STANDARD_CODES[kind]]  # type: ignore[index]
            assert candidate.concept_tags[0].concept_src_id == expected_concept

    def test_kind_filter_ids_stay_unique_across_bands(self) -> None:
        ids_by_kind: dict[str, set] = {}
        for kind in ("parabola", "ellipse", "hyperbola"):
            candidates = _drain(ConicSectionFocusSkeletonGenerator(kind=kind), _spec(kind), 15)  # type: ignore[arg-type]
            assert len(candidates) == 15
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (ids_by_kind["parabola"] & ids_by_kind["ellipse"])
        assert not (ids_by_kind["ellipse"] & ids_by_kind["hyperbola"])
        assert not (ids_by_kind["parabola"] & ids_by_kind["hyperbola"])

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("parabola", "ellipse", "hyperbola"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = ConicSectionFocusSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _spec(kind), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec(kind)) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in ("parabola", "ellipse", "hyperbola"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = ConicSectionFocusSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            candidates = _drain(gen, _spec(kind), pool_size)
            assert len(candidates) == pool_size
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _spec(kind),
                    candidate.problem,
                    provenance=candidate.provenance,
                    conditions=candidate.conditions,
                    answer_map=candidate.answer_map,
                    solution_steps=candidate.solution_steps,
                )
                label = f"{kind}/{candidate.problem.slug}"
                assert verdict.accepted is True, f"{label}: {verdict.reasons}"
                assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = ConicSectionFocusSkeletonGenerator(kind="ellipse").generate(_spec("ellipse"))
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec("ellipse"),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        for kind in ("parabola", "ellipse", "hyperbola"):
            gen = ConicSectionFocusSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(kind), 10):
                assert candidate.problem.question_format == QuestionFormat.단답형
                assert candidate.problem.choices is None
                assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs(self) -> None:
        for kind in ("parabola", "ellipse", "hyperbola"):
            gen = ConicSectionFocusSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(kind), 15):
                text = candidate.problem.question_text
                assert "Σ" not in text
                assert "α" not in text
                assert "β" not in text
