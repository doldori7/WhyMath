"""수열의 합 — Σ 성질·여러 가지 수열의 합 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`SigmaLinearitySkeletonGenerator`·`PowerSumSkeletonGenerator`가 ① 전건 S2-a 4종 게이트
통과 ② answer가 독립 재계산(닫힌 합 공식)과 일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로
밴드가 실제로 분리됨(2026-08-05 elementary_addsub 사고의 재발 방지 회귀 봉인) ⑤ 계수 1
생략·조사(을/를) 정합 ⑥ Σ 등 신규 Unicode 글리프 미사용(2026-08-07 quad_ineq 사고 재발
방지) ⑦ 개념 태깅·위생 게이트 무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import re

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.sequence_sigma_skeleton_generator import (
    PowerSumSkeletonGenerator,
    SigmaLinearitySkeletonGenerator,
    _build_power_sum_pool,
    _build_sigma_pool,
)
from whymath_backend.schema.enums import QuestionFormat

_SIGMA_STANDARD = "[12대수03-04]"
_POWER_STANDARD = "[12대수03-05]"


def _sigma_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_SIGMA_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.0,
        answer_format=None,
    )


def _power_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_POWER_STANDARD}),
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


class TestSigmaLinearityPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_sigma_pool()
        assert len(pool) >= 200
        keys = {(s.scale, s.constant, s.count) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_formula(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(a·n(n+1)/2 + b·n)과 일치."""
        for skeleton in _build_sigma_pool()[:100]:
            expected = (
                skeleton.scale * skeleton.count * (skeleton.count + 1) // 2
                + skeleton.constant * skeleton.count
            )
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_sigma_pool())
        gen = SigmaLinearitySkeletonGenerator()
        drained = _drain(gen, _sigma_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_sigma_spec()) is None


class TestSigmaLinearityAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(SigmaLinearitySkeletonGenerator(), _sigma_spec(), 150)
        assert len(candidates) >= 150
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _sigma_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        """변별력 — 정답을 1 틀리게 만든 후보는 Tier1 산술 검산에서 거부된다."""
        candidate = SigmaLinearitySkeletonGenerator().generate(_sigma_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _sigma_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestSigmaLinearityShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(SigmaLinearitySkeletonGenerator(), _sigma_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = SigmaLinearitySkeletonGenerator().generate(_sigma_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12대수03-04"

    def test_no_unverified_glyphs_and_no_josa_or_coefficient_defects(self) -> None:
        """Σ 등 신규 글리프 미사용 + 조사(을/를) 정합 + 계수 1 생략 — 2026-08-07 실측 회귀 봉인.

        `QuadraticInequalityBoundarySkeletonGenerator`의 α·β 사고(신규 글리프가 렌더 검증
        게이트를 걷어참)를 이 생성기는 처음부터 순수 한국어 서술로 회피한다. 조사 하드코딩
        (예 '8를') 사고도 별도 실측으로 발견해 `josa.eul_reul`로 교정했다 — 그 회귀를 봉인.
        """
        for candidate in _drain(SigmaLinearitySkeletonGenerator(), _sigma_spec(), 150):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "∑" not in text
            assert "를 더한" not in text or not re.search(r"[13678]를 더한", text)
            assert "를 곱한" not in text or not re.search(r"[13678]를 곱한", text)
            assert re.search(r"(?<!\d)1k\b", text) is None, text


class TestSigmaLinearitySkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        """`skip_signatures`는 canonical_signature(=답값) 기준 비교(생성기 실제 계약)."""
        seen: set[str] = set()
        first = SigmaLinearitySkeletonGenerator(skip_signatures=seen).generate(_sigma_spec())
        assert first is not None
        signature = canonical_signature(first.conditions, "unique")  # type: ignore[arg-type]
        assert signature is not None
        seen.add(signature)

        second = SigmaLinearitySkeletonGenerator(skip_signatures=seen).generate(_sigma_spec())
        assert second is not None
        assert second.conditions != first.conditions


class TestPowerSumPool:
    def test_pool_nonempty_and_split_by_kind(self) -> None:
        pool = _build_power_sum_pool()
        assert len(pool) >= 25
        squares = [s for s in pool if s.kind == "square"]
        cubes = [s for s in pool if s.kind == "cube"]
        assert len(squares) >= 10
        assert len(cubes) >= 10

    def test_answer_matches_independent_formula(self) -> None:
        """교차 검증 — square: n(n+1)(2n+1)/6, cube: (n(n+1)/2)² 독립 재계산과 일치."""
        for skeleton in _build_power_sum_pool():
            if skeleton.kind == "square":
                expected = skeleton.count * (skeleton.count + 1) * (2 * skeleton.count + 1) // 6
            else:
                expected = (skeleton.count * (skeleton.count + 1) // 2) ** 2
            assert skeleton.answer == expected

    def test_kind_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인(quad_ineq 미러).

        square·cube가 답 기준 dedup을 전체 풀에서 공유하므로(같은 답이 우연히 겹치면 한쪽만
        남는다), 진짜 회귀 신호는 problem_id 전건 고유성이다.
        """
        ids_by_kind: dict[str, set] = {}
        for kind in ("square", "cube"):
            candidates = _drain(PowerSumSkeletonGenerator(kind=kind), _power_spec(), 10)
            assert len(candidates) == 10
            expected_word = "제곱" if kind == "square" else "세제곱"
            assert all(expected_word in c.problem.question_text for c in candidates), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_kind["square"] & ids_by_kind["cube"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("square", "cube"):
            pool_size = len([s for s in _build_power_sum_pool() if s.kind == kind])
            gen = PowerSumSkeletonGenerator(kind=kind)
            drained = _drain(gen, _power_spec(), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_power_spec()) is None


class TestPowerSumAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in ("square", "cube"):
            candidates = _drain(PowerSumSkeletonGenerator(kind=kind), _power_spec(), 10)
            assert len(candidates) >= 10
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _power_spec(),
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
        candidate = PowerSumSkeletonGenerator(kind="square").generate(_power_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _power_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestPowerSumShape:
    def test_question_format_and_no_choices(self) -> None:
        for kind in ("square", "cube"):
            for candidate in _drain(PowerSumSkeletonGenerator(kind=kind), _power_spec(), 10):
                assert candidate.problem.question_format == QuestionFormat.단답형
                assert candidate.problem.choices is None
                assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = PowerSumSkeletonGenerator(kind="cube").generate(_power_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12대수03-05"

    def test_no_unverified_glyphs(self) -> None:
        for kind in ("square", "cube"):
            for candidate in _drain(PowerSumSkeletonGenerator(kind=kind), _power_spec(), 10):
                text = candidate.problem.question_text
                assert "Σ" not in text
                assert "∑" not in text
                assert "²" not in text
                assert "³" not in text
