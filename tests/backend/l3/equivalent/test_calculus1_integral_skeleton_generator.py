"""고등 미적분Ⅰ 적분(부정적분·정적분·넓이·속도와 거리) 스켈레톤 생성기 단위테스트(hermetic).

`Calculus1IntegralSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `Integral`
정적분 검증 신규 경로 실증) ② answer가 독립 재계산(반도함수 닫힌형)과 일치 ③ `kind`
필터로 밴드가 실제로 분리되고 성취기준 코드도 함께 결정됨(gcd_lcm·conic_section_focus·
measurement_unit_conversion 생성기의 "kind→코드" 패턴 재실증) ④ area/distance kind는
구간 전체에서 f(x)>0(부호분석 불요 v1 단순화 불변식) ⑤ concept_src_id가 legacy 437
공간에 실존 ⑥ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프 미사용을
못 박는다. `Integral` 심볼릭 평가 비용이 있어(스파이크 실측 ~0.4초/건) 게이트 소진
테스트는 표본(30~50건)으로 한다(형제 표본평균 생성기의 대형 풀 처방과 동형).
LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from fractions import Fraction

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus1_integral_skeleton_generator import (
    ANTIDERIVATIVE_STANDARD_CODE,
    AREA_STANDARD_CODE,
    DEFINITE_STANDARD_CODE,
    DISTANCE_STANDARD_CODE,
    Calculus1IntegralSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪")

_KIND_TO_CODE = {
    "antiderivative": ANTIDERIVATIVE_STANDARD_CODE,
    "definite": DEFINITE_STANDARD_CODE,
    "area": AREA_STANDARD_CODE,
    "distance": DISTANCE_STANDARD_CODE,
}
_KIND_TO_CONCEPT = {
    "antiderivative": "H:12미적Ⅰ03-02",
    "definite": "H:12미적Ⅰ03-04",
    "area": "H:12미적Ⅰ03-05",
    "distance": "H:12미적Ⅰ03-06",
}


def _spec(kind: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_KIND_TO_CODE[kind]}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.1,
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


def _assert_no_bad_glyphs(candidate: CandidateProblem) -> None:
    for field in (candidate.problem.question_text, candidate.problem.answer_explanation):
        for glyph in _BAD_GLYPHS:
            assert glyph not in field, f"{glyph!r} in {field!r}"


def _independent_answer(skeleton: object) -> Fraction:
    a, b, c = skeleton.a, skeleton.b, skeleton.c  # type: ignore[attr-defined]
    lower, upper = skeleton.lower, skeleton.upper  # type: ignore[attr-defined]

    def antideriv(x: int) -> Fraction:
        return Fraction(a, 3) * x**3 + Fraction(b, 2) * x**2 + Fraction(c) * x

    base = antideriv(upper) - antideriv(lower)
    return base + (skeleton.k if skeleton.kind == "antiderivative" else 0)  # type: ignore[attr-defined]


class TestPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) == 300 * 4
        keys = {(s.kind, s.a, s.b, s.c, s.lower, s.upper, s.k) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool()[:400]:
            assert skeleton.answer == _independent_answer(skeleton)

    def test_area_and_distance_kinds_are_always_positive_on_interval(self) -> None:
        """area/distance kind의 v1 불변식 — b=0·a,c>0이라 f(x)=a·x²+c는 구간 전체 양수."""
        for skeleton in _build_pool():
            if skeleton.kind in ("area", "distance"):
                assert skeleton.b == 0
                assert skeleton.a > 0
                assert skeleton.c > 0
                assert skeleton.lower < skeleton.upper


class TestKindFilterDeterminesCode:
    def test_kind_filter_restricts_output_and_sets_expected_code(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리하고 코드도 함께 결정한다 — kind→코드 패턴 재실증."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("antiderivative", "definite", "area", "distance"):
            candidates = _drain(
                Calculus1IntegralSkeletonGenerator(kind=kind), _spec(kind), 15  # type: ignore[arg-type]
            )
            assert len(candidates) == 15
            assert all(
                c.problem.achievement_standard_codes == [_KIND_TO_CODE[kind]] for c in candidates
            ), kind
            assert all(
                c.concept_tags[0].concept_src_id == _KIND_TO_CONCEPT[kind] for c in candidates
            ), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        all_ids = [i for ids in ids_by_kind.values() for i in ids]
        assert len(all_ids) == len(set(all_ids)), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("antiderivative", "definite", "area", "distance"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = Calculus1IntegralSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _spec(kind), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec(kind)) is None


class TestAcceptance:
    def test_sample_passes_acceptance_gate(self) -> None:
        for kind in ("antiderivative", "definite", "area", "distance"):
            candidates = _drain(
                Calculus1IntegralSkeletonGenerator(kind=kind), _spec(kind), 40  # type: ignore[arg-type]
            )
            assert len(candidates) == 40
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
        candidate = Calculus1IntegralSkeletonGenerator(kind="definite").generate(_spec("definite"))
        assert candidate is not None
        original = Fraction(candidate.problem.answer)  # type: ignore[arg-type]
        broken = str(original + 1)
        verdict = evaluate_equivalent_candidate(
            _spec("definite"),
            candidate.problem.model_copy(update={"answer": broken}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = Calculus1IntegralSkeletonGenerator(kind="area")
        for candidate in _drain(gen, _spec("area"), 15):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for kind in ("antiderivative", "definite", "area", "distance"):
            gen = Calculus1IntegralSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(kind), 40):
                _assert_no_bad_glyphs(candidate)

    def test_distance_kind_displays_t_not_x(self) -> None:
        """실측 발견 회귀 봉인 — distance는 서술상 변수가 t(시각)인데 x로 표시되던 버그
        ("v(t) = x^2 + 1" 형태로 산출됐었음)."""
        gen = Calculus1IntegralSkeletonGenerator(kind="distance")
        for candidate in _drain(gen, _spec("distance"), 30):
            text = candidate.problem.question_text
            assert "t^2" in text  # area/distance kind는 a>0로 강제되어 이차항이 항상 존재.
            assert "x^2" not in text
            assert "x)" not in text
