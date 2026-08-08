"""고등 일반각과 호도법(도-라디안 변환) 스켈레톤 생성기 단위테스트(hermetic).

`RadianConversionSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `pi` 상수 심볼
직접 평가 — `AnswerFormat.식` 세션 첫 사용 경로 실증) ② answer가 독립 재계산(gcd 소거
기약분수·역변환 공식)과 일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로 밴드가 실제로
분리되되 성취기준 코드는 **하나를 공유**함(measurement_unit_conversion류 "여러 kind가
한 코드 공유" 패턴 재실증) ⑤ concept_src_id가 legacy 437 개념그래프에 실존 ⑥
question_text·answer_explanation 양쪽 모두 유니코드 π 등 미검증 글리프 미사용을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.radian_conversion_skeleton_generator import (
    RADIAN_STANDARD_CODE,
    RadianConversionSkeletonGenerator,
    _build_pool,
    _reduced_radian,
)
from whymath_backend.schema.enums import AnswerFormat, QuestionFormat

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪", "π")
_CONCEPT_SRC_ID = "H:12대수02-01"
_ALL_KINDS = ("deg_to_rad", "rad_to_deg")

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({RADIAN_STANDARD_CODE}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.0,
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


class TestPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) == 72 * 2  # |k|<=36, k!=0 → 72개, 방향 2개.
        keys = {(s.kind, s.degree) for s in pool}
        assert len(keys) == len(pool)

    def test_degree_is_nonzero_multiple_of_15_within_bound(self) -> None:
        for skeleton in _build_pool():
            assert skeleton.degree != 0
            assert skeleton.degree % 15 == 0
            assert abs(skeleton.degree) <= 540

    def test_reduced_fraction_denominator_is_divisor_of_twelve(self) -> None:
        """v1 불변식 — d=15k라서 기약분수 분모가 항상 12의 약수(특수각 계열 보장)."""
        for skeleton in _build_pool():
            _numerator, denominator = _reduced_radian(skeleton.degree)
            assert 12 % denominator == 0

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool():
            numerator, denominator = _reduced_radian(skeleton.degree)
            if skeleton.kind == "deg_to_rad":
                # 기약분수 재구성이 실제 각도와 일치하는지 독립 검산(교차곱).
                assert numerator * 180 == skeleton.degree * denominator
            else:
                assert skeleton.answer_text == str(skeleton.degree)


class TestKindFilterSharesCode:
    def test_kind_filter_restricts_output_but_shares_single_code(self) -> None:
        """`kind` 필터가 밴드(변환 방향)를 분리하되 성취기준 코드는 하나를 공유한다
        (measurement_unit_conversion 패턴 재실증 — 이번엔 code가 아니라 kind만 갈림)."""
        ids_by_kind: dict[str, set] = {}
        for kind in _ALL_KINDS:
            candidates = _drain(
                RadianConversionSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _SPEC,
                15,
            )
            assert len(candidates) == 15
            assert all(
                c.problem.achievement_standard_codes == [RADIAN_STANDARD_CODE] for c in candidates
            ), kind
            assert all(
                c.concept_tags[0].concept_src_id == _CONCEPT_SRC_ID for c in candidates
            ), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        all_ids = [i for ids in ids_by_kind.values() for i in ids]
        assert len(all_ids) == len(set(all_ids)), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in _ALL_KINDS:
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = RadianConversionSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _SPEC, pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_SPEC) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in _ALL_KINDS:
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            candidates = _drain(
                RadianConversionSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _SPEC,
                pool_size,
            )
            assert len(candidates) == pool_size
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _SPEC,
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
        candidate = RadianConversionSkeletonGenerator(kind="rad_to_deg").generate(_SPEC)
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _SPEC,
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)

    def test_gate_rejects_wrong_pi_expression_answer(self) -> None:
        """식(π 분수) 답 경로 자체의 변별력 — 분자를 조작한 잘못된 식은 거부된다."""
        candidate = RadianConversionSkeletonGenerator(kind="deg_to_rad").generate(_SPEC)
        assert candidate is not None
        broken_answer = candidate.problem.answer.replace("pi", "2*pi", 1)
        verdict = evaluate_equivalent_candidate(
            _SPEC,
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = RadianConversionSkeletonGenerator(kind="deg_to_rad")
        for candidate in _drain(gen, _SPEC, 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_deg_to_rad_uses_expression_answer_format(self) -> None:
        gen = RadianConversionSkeletonGenerator(kind="deg_to_rad")
        for candidate in _drain(gen, _SPEC, 20):
            assert candidate.problem.answer_format == AnswerFormat.식
            assert "pi" in candidate.problem.answer

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for kind in _ALL_KINDS:
            gen = RadianConversionSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            for candidate in _drain(gen, _SPEC, pool_size):
                _assert_no_bad_glyphs(candidate)
