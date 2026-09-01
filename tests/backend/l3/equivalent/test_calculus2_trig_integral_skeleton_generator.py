"""고등 미적분Ⅱ 적분법(삼각함수 정적분·넓이·속도와 거리) 스켈레톤 생성기 단위테스트(hermetic).

`Calculus2TrigIntegralSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `Integral`
삼각함수 검증 — calculus1_integral 생성기의 정적분 경로 재확장) ② answer가 독립 재계산
(cos(kπ/2) 순환표)과 일치 ③ `kind` 필터로 밴드가 실제로 분리되고 성취기준 코드도 함께
결정됨(kind→코드 패턴 재실증) ④ trig_area/trig_distance kind는 [0,pi] 구간 제약(sin(x)≥0
구성 불변식) ⑤ concept_src_id가 legacy 437 공간에 실존 ⑥ question_text·answer_explanation
양쪽 모두 신규 Unicode 글리프 미사용(유니코드 π 자체도 회피 확인)을 못 박는다.
LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus2_trig_integral_skeleton_generator import (
    TRIG_AREA_STANDARD_CODE,
    TRIG_DEFINITE_STANDARD_CODE,
    TRIG_DISTANCE_STANDARD_CODE,
    Calculus2TrigIntegralSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪", "π")

_KIND_TO_CODE = {
    "trig_definite": TRIG_DEFINITE_STANDARD_CODE,
    "trig_area": TRIG_AREA_STANDARD_CODE,
    "trig_distance": TRIG_DISTANCE_STANDARD_CODE,
}
_KIND_TO_CONCEPT = {
    "trig_definite": "H:12미적Ⅱ03-01",
    "trig_area": "H:12미적Ⅱ03-05",
    "trig_distance": "H:12미적Ⅱ03-07",
}
_COS_AT_BOUND = {0: 1, 1: 0, 2: -1, 3: 0, 4: 1}


def _spec(kind: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_KIND_TO_CODE[kind]}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.4,
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
    def test_pool_sizes_and_structural_uniqueness(self) -> None:
        pool = _build_pool()
        assert len(pool) == 100 + 15 + 15  # trig_definite(5*20) + area(5*3) + distance(5*3).
        keys = {(s.kind, s.a, s.lower_idx, s.upper_idx) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool():
            expected = skeleton.a * (
                _COS_AT_BOUND[skeleton.lower_idx] - _COS_AT_BOUND[skeleton.upper_idx]
            )
            assert skeleton.answer == expected

    def test_area_and_distance_kinds_stay_within_zero_to_pi(self) -> None:
        """v1 불변식 — trig_area/trig_distance는 경계점이 [0,pi] 안(인덱스 0·1·2)만 사용."""
        for skeleton in _build_pool():
            if skeleton.kind in ("trig_area", "trig_distance"):
                assert skeleton.lower_idx in (0, 1, 2)
                assert skeleton.upper_idx in (0, 1, 2)
                assert skeleton.lower_idx < skeleton.upper_idx


class TestKindFilterDeterminesCode:
    def test_kind_filter_restricts_output_and_sets_expected_code(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리하고 코드도 함께 결정한다 — kind→코드 패턴 재실증."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("trig_definite", "trig_area", "trig_distance"):
            candidates = _drain(
                Calculus2TrigIntegralSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _spec(kind),
                10,
            )
            assert len(candidates) == 10
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
        for kind in ("trig_definite", "trig_area", "trig_distance"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = Calculus2TrigIntegralSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            drained = _drain(gen, _spec(kind), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec(kind)) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in ("trig_definite", "trig_area", "trig_distance"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            candidates = _drain(
                Calculus2TrigIntegralSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
                _spec(kind),
                pool_size,
            )
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
        candidate = Calculus2TrigIntegralSkeletonGenerator(kind="trig_definite").generate(
            _spec("trig_definite")
        )
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec("trig_definite"),
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
        gen = Calculus2TrigIntegralSkeletonGenerator(kind="trig_area")
        for candidate in _drain(gen, _spec("trig_area"), 10):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for kind in ("trig_definite", "trig_area", "trig_distance"):
            pool_size = len(_build_pool(kind))  # type: ignore[arg-type]
            gen = Calculus2TrigIntegralSkeletonGenerator(kind=kind)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(kind), pool_size):
                _assert_no_bad_glyphs(candidate)

    def test_trig_distance_kind_displays_t_not_x(self) -> None:
        """실측 발견 회귀 봉인 — trig_distance는 서술상 변수가 t(시각)인데 x로 표시되던
        버그(calculus1_integral 생성기의 동형 버그를 이 생성기에서도 재발 확인·수정)."""
        gen = Calculus2TrigIntegralSkeletonGenerator(kind="trig_distance")
        for candidate in _drain(gen, _spec("trig_distance"), 15):
            text = candidate.problem.question_text
            assert "sin(t)" in text
            assert "sin(x)" not in text
