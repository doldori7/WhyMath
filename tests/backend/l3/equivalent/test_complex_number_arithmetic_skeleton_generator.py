"""고등 복소수 사칙연산(덧셈·뺄셈·곱셈) 스켈레톤 생성기 단위테스트(hermetic).

`ComplexNumberArithmeticSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(순수 정수
산술 검증 — SymPy 전개 불요 설계, polynomial_arithmetic 생성기의 형제) ② answer가 독립
재계산(성분 합/차·곱셈 전개 실수부/허수부 공식)과 일치 ③ 풀 유일·소진 시 None ④ `kind`
필터로 밴드(연산 종류)가 실제로 분리되되 성취기준 코드는 **하나를 공유**함
(measurement_unit_conversion·radian_conversion류 "여러 kind가 한 코드 공유" 패턴
재실증 — 기수 대응코드 자체가 없는 첫 사례) ⑤ concept_src_id가 legacy 437 개념그래프에
실존 ⑥ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프·이중부호("+  -3i")
미사용을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.complex_number_arithmetic_skeleton_generator import (
    COMPLEX_ARITHMETIC_STANDARD_CODE,
    ComplexNumberArithmeticSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪", "π")
_CONCEPT_SRC_ID = "HK05"
_ALL_KINDS = ("add", "sub", "mul")

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({COMPLEX_ARITHMETIC_STANDARD_CODE}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.1,
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


def _independent_answer(s: object) -> int:
    a1, b1, a2, b2 = s.a1, s.b1, s.a2, s.b2  # type: ignore[attr-defined]
    if s.kind == "add":  # type: ignore[attr-defined]
        return a1 + a2 if s.target == "real" else b1 + b2  # type: ignore[attr-defined]
    if s.kind == "sub":  # type: ignore[attr-defined]
        return a1 - a2 if s.target == "real" else b1 - b2  # type: ignore[attr-defined]
    # mul: (a1+b1 i)(a2+b2 i) = (a1 a2 - b1 b2) + (a1 b2 + a2 b1) i
    if s.target == "real":  # type: ignore[attr-defined]
        return a1 * a2 - b1 * b2
    return a1 * b2 + a2 * b1


class TestPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) == 300 * 3
        keys = {(s.kind, s.a1, s.b1, s.a2, s.b2, s.target) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool()[:600]:
            assert skeleton.answer == _independent_answer(skeleton)

    def test_all_coefficients_nonzero(self) -> None:
        """v1 불변식 — "0 + 5i" 생략형 회피를 위해 실수부·허수부 계수 전부 0 아님."""
        for skeleton in _build_pool():
            assert skeleton.a1 != 0
            assert skeleton.b1 != 0
            assert skeleton.a2 != 0
            assert skeleton.b2 != 0


class TestKindFilterSharesCode:
    def test_kind_filter_restricts_output_but_shares_single_code(self) -> None:
        """`kind` 필터가 밴드(연산 종류)를 분리하되 성취기준 코드는 하나를 공유한다 —
        기수 대응코드 자체가 없는 첫 사례(measurement_unit_conversion·radian_conversion
        패턴의 극단형: 코드 분기 자체가 없음)."""
        ids_by_kind: dict[str, set] = {}
        for kind in _ALL_KINDS:
            candidates = _drain(
                ComplexNumberArithmeticSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _SPEC,
                15,
            )
            assert len(candidates) == 15
            assert all(
                c.problem.achievement_standard_codes == [COMPLEX_ARITHMETIC_STANDARD_CODE]
                for c in candidates
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
            gen = ComplexNumberArithmeticSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _SPEC, pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_SPEC) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in _ALL_KINDS:
            candidates = _drain(
                ComplexNumberArithmeticSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _SPEC,
                300,
            )
            assert len(candidates) == 300
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
        candidate = ComplexNumberArithmeticSkeletonGenerator(kind="mul").generate(_SPEC)
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


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = ComplexNumberArithmeticSkeletonGenerator(kind="mul")
        for candidate in _drain(gen, _SPEC, 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for kind in _ALL_KINDS:
            gen = ComplexNumberArithmeticSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _SPEC, 300):
                _assert_no_bad_glyphs(candidate)

    def test_no_double_sign_in_question_or_explanation(self) -> None:
        """실측 발견 회귀 재확인(polynomial_factoring S4-48 교훈 사전 적용) — 음수 허수부가
        '7 + -9i'로 이중부호 표시되지 않는다. '7 - 9i' 형태여야 한다."""
        for kind in _ALL_KINDS:
            gen = ComplexNumberArithmeticSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _SPEC, 300):
                fields = (candidate.problem.question_text, candidate.problem.answer_explanation)
                for field in fields:
                    assert "+ -" not in field
                    assert "- -" not in field
