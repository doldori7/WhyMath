"""고등 이차부등식 경계값 결정론 스켈레톤 생성기 — W2 Phase1 #1 단위테스트(hermetic·게이트 재사용).

`QuadraticInequalityBoundarySkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(기존 게이트
인프라 무변경 재사용 재실증) ② answer가 독립 재계산(근의 합 정의)과 일치 ③ 풀 유일·소진 시
None ④ `direction` 필터로 밴드가 실제로 분리됨(elementary_addsub 2026-08-05 실측 사고의
재발 방지 회귀 봉인) ⑤ 발문이 답(경계값 α,β 숫자)을 직접 노출하지 않음(문제 자명화 방지)
⑥ 개념 태깅·표기 정갈함·위생 게이트 무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.quadratic_inequality_boundary_skeleton_generator import (
    QuadraticInequalityBoundarySkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

_STANDARD = "[10공수1-02-11]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.6,
        answer_format=None,
    )


def _drain(gen: QuadraticInequalityBoundarySkeletonGenerator, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) >= 250
        keys = {(s.r1, s.r2, s.a, s.direction) for s in pool}
        assert len(keys) == len(pool)

    def test_roots_strictly_ordered_and_distinct(self) -> None:
        for skeleton in _build_pool():
            assert skeleton.r1 < skeleton.r2

    def test_direction_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`direction` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인.

        이 생성기는 검증 조건이 "r1+r2=y"(부등호 방향 무관)라 outer/inner가 같은 (r1,r2)
        조합에서 같은 조건 문자열을 공유할 수 있다(matrix_ops와 달리 정상 설계 — 문제
        question_text는 방향에 따라 실제로 다르다). 그래서 진짜 회귀 신호는 두 가지다:
        ① `direction=X`로 만든 인스턴스는 X 아닌 뼈대를 절대 안 낸다(필터가 실제로 먹힘)
        ② 두 밴드를 합쳐도 problem_id가 전건 고유하다(같은 콘텐츠가 두 번 저장되지 않음 —
        elementary_addsub 사고의 진짜 증상은 "조건 중복"이 아니라 "problem_id 중복"이었다).
        """
        ids_by_direction: dict[str, set] = {}
        for direction in ("outer", "inner"):
            candidates = _drain(
                QuadraticInequalityBoundarySkeletonGenerator(direction=direction), 30
            )
            assert len(candidates) == 30
            expected_sign = "> 0" if direction == "outer" else "< 0"
            assert all(expected_sign in c.problem.question_text for c in candidates), direction
            ids_by_direction[direction] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_direction["outer"] & ids_by_direction["inner"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_direction(self) -> None:
        for direction in ("outer", "inner"):
            pool_size = len([s for s in _build_pool() if s.direction == direction])
            gen = QuadraticInequalityBoundarySkeletonGenerator(direction=direction)
            drained = _drain(gen, pool_size + 5)
            assert len(drained) == pool_size, direction
            assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(QuadraticInequalityBoundarySkeletonGenerator(), 150)
        assert len(candidates) >= 150
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_answer_matches_independent_root_sum(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(r1+r2)과 일치."""
        for skeleton in _build_pool()[:100]:
            assert skeleton.result == skeleton.r1 + skeleton.r2

    def test_gate_rejects_wrong_answer(self) -> None:
        """변별력 — 정답을 1 틀리게 만든 후보는 Tier1 산술 검산에서 거부된다."""
        candidate = QuadraticInequalityBoundarySkeletonGenerator().generate(_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestCandidateShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(QuadraticInequalityBoundarySkeletonGenerator(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_is_fixed(self) -> None:
        for candidate in _drain(QuadraticInequalityBoundarySkeletonGenerator(), 30):
            assert candidate.problem.difficulty_overall == 2.6

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = QuadraticInequalityBoundarySkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK16"

    def test_solution_steps_intentionally_none(self) -> None:
        candidate = QuadraticInequalityBoundarySkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_question_text_uses_no_unverified_glyphs(self) -> None:
        """그리스 문자(α·β) 등 렌더 검증 안 된 기호를 쓰지 않는다 — 2026-08-05 실측
        회귀 봉인(`notation_coverage_eval` 게이트가 신규 글리프 유입을 차단 — 최초
        설계는 α·β를 썼다가 게이트 거부로 순수 서술형으로 교정됐다). 경계는 "경계가
        되는 두 값"으로만 서술 지칭하고, r1·r2 숫자를 계산 없이 직접 노출하지 않는다
        (숫자는 계수로만 등장 — 발문에 답 자체가 그대로 적히면 문제가 자명해진다)."""
        for candidate in _drain(QuadraticInequalityBoundarySkeletonGenerator(), 80):
            text = candidate.problem.question_text
            assert "α" not in text
            assert "β" not in text
            assert "경계가 되는 두 값" in text or "경계값" in text

    def test_no_double_sign_or_redundant_unit_coefficient_in_display(self) -> None:
        """이중부호·불필요한 계수 1 생략 — 계수가 두 자리(예 '21x')일 때 그 안의 '1x'를
        계수-1 항으로 오탐하지 않도록 자릿수 경계를 지켜 검사한다(다른 생성기들의 단순
        `"1x" not in text` 체크는 이 도메인처럼 두 자리 계수(B=-a(r1+r2))가 나오면
        거짓 실패한다 — 실측으로 발견해 정규식으로 교정)."""
        import re

        for candidate in _drain(QuadraticInequalityBoundarySkeletonGenerator(), 100):
            text = candidate.problem.question_text
            assert "+ -" not in text
            assert "- -" not in text
            assert re.search(r"(?<!\d)1x\b", text) is None, text


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        first = QuadraticInequalityBoundarySkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        second = QuadraticInequalityBoundarySkeletonGenerator(skip_conditions=seen).generate(
            _spec()
        )
        assert second is not None
        assert second.conditions != first.conditions
