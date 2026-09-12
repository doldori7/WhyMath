"""고등 다항식의 덧셈·뺄셈·곱셈 스켈레톤 생성기 단위테스트(hermetic).

`PolynomialArithmeticSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(순수 정수 산술
검증 — SymPy 전개 불요 설계 재실증) ② answer가 독립 재계산(대응 계수 합/차·배분법칙
전개 계수)과 일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로 밴드가 실제로 분리되고 성취기준
코드도 함께 결정됨(2개 kind가 1개 코드를 공유하는 measurement_unit_conversion 패턴
재실증) ⑤ concept_src_id가 legacy 437 공간에 실존 ⑥ question_text·answer_explanation
양쪽 모두 신규 Unicode 글리프 미사용을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.polynomial_arithmetic_skeleton_generator import (
    GONGSU_STANDARD_CODE,
    KISU_ADDSUB_STANDARD_CODE,
    KISU_MUL_STANDARD_CODE,
    PolynomialArithmeticSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪")

_KIND_TO_CODE = {
    "gongsu_add": GONGSU_STANDARD_CODE,
    "gongsu_sub": GONGSU_STANDARD_CODE,
    "kisu_add": KISU_ADDSUB_STANDARD_CODE,
    "kisu_sub": KISU_ADDSUB_STANDARD_CODE,
    "kisu_mul": KISU_MUL_STANDARD_CODE,
}
_KIND_TO_CONCEPT = {
    "gongsu_add": "HK01",
    "gongsu_sub": "HK01",
    "kisu_add": "10기수1-01-01",
    "kisu_sub": "10기수1-01-01",
    "kisu_mul": "10기수1-01-02",
}
_ALL_KINDS = ("gongsu_add", "gongsu_sub", "kisu_add", "kisu_sub", "kisu_mul")


def _spec(kind: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_KIND_TO_CODE[kind]}),
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


def _independent_answer(s: object) -> int:
    a1, b1, a2, b2 = s.a1, s.b1, s.a2, s.b2  # type: ignore[attr-defined]
    if s.kind in ("gongsu_add", "kisu_add"):  # type: ignore[attr-defined]
        return a1 + a2 if s.target == "x" else b1 + b2  # type: ignore[attr-defined]
    if s.kind in ("gongsu_sub", "kisu_sub"):  # type: ignore[attr-defined]
        return a1 - a2 if s.target == "x" else b1 - b2  # type: ignore[attr-defined]
    if s.target == "x2":  # type: ignore[attr-defined]
        return a1 * a2
    if s.target == "x1":  # type: ignore[attr-defined]
        return a1 * b2 + a2 * b1
    return b1 * b2


class TestPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) == 300 * 5
        keys = {(s.kind, s.a1, s.b1, s.a2, s.b2, s.target) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool()[:500]:
            assert skeleton.answer == _independent_answer(skeleton)


class TestKindFilterDeterminesCode:
    def test_kind_filter_restricts_output_and_sets_expected_code(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리하고 코드도 함께 결정한다 — 2개 kind가 1개
        코드를 공유하는 measurement_unit_conversion 패턴 재실증."""
        ids_by_kind: dict[str, set] = {}
        for kind in _ALL_KINDS:
            candidates = _drain(
                PolynomialArithmeticSkeletonGenerator(kind=kind), _spec(kind), 15  # type: ignore[arg-type]
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

    def test_gongsu_add_and_kisu_add_are_distinct_bands_of_shared_code(self) -> None:
        assert _KIND_TO_CODE["gongsu_add"] != _KIND_TO_CODE["kisu_add"]
        assert _KIND_TO_CODE["gongsu_add"] == _KIND_TO_CODE["gongsu_sub"]
        assert _KIND_TO_CODE["kisu_add"] == _KIND_TO_CODE["kisu_sub"]

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in _ALL_KINDS:
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = PolynomialArithmeticSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _spec(kind), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec(kind)) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in _ALL_KINDS:
            candidates = _drain(
                PolynomialArithmeticSkeletonGenerator(kind=kind), _spec(kind), 300  # type: ignore[arg-type]
            )
            assert len(candidates) == 300
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
        candidate = PolynomialArithmeticSkeletonGenerator(kind="kisu_mul").generate(
            _spec("kisu_mul")
        )
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec("kisu_mul"),
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
        gen = PolynomialArithmeticSkeletonGenerator(kind="kisu_mul")
        for candidate in _drain(gen, _spec("kisu_mul"), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for kind in _ALL_KINDS:
            gen = PolynomialArithmeticSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(kind), 300):
                _assert_no_bad_glyphs(candidate)
