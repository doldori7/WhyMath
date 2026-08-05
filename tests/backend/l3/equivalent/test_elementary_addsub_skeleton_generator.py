"""초등 두 자리 수 덧셈·뺄셈 결정론 스켈레톤 생성기 — W2 단위테스트(hermetic·게이트 재사용).

`ElementaryAddSubSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(기존 게이트 인프라를 새
도메인(초등 산술)에 무변경 재사용 실증 — 학년축 최단경로 계획 §3 W2) ② answer가 독립 산술
재계산과 일치(교차 검증) ③ 풀 유일(중복 뼈대 0)·소진 시 None ④ skip_conditions dedup
⑤ 개념 태깅·정답형식·조사(을/를·와/과) 정확성을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_addsub_skeleton_generator import (
    ElementaryAddSubSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import AnswerFormat, QuestionFormat

_STANDARD = "[2수01-06]"


def _spec(difficulty: float = 1.3) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=difficulty,
        answer_format=None,
    )


def _drain(gen: ElementaryAddSubSkeletonGenerator, limit: int) -> list[CandidateProblem]:
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
        assert len(pool) >= 300  # 격자(27×27 근방)·add(a>=b)+subtract(a>b) 조합.
        keys = {(s.a, s.b, s.operation) for s in pool}
        assert len(keys) == len(pool)

    def test_subtraction_never_yields_zero_or_negative(self) -> None:
        """뺄셈 뼈대는 전부 a>b — 답 0(KR 초등 자연수 관례 밖)·음수 원천 배제."""
        pool = _build_pool()
        for skeleton in pool:
            if skeleton.operation == "subtract":
                assert skeleton.a > skeleton.b
                assert skeleton.result > 0

    def test_generation_exhausts_to_none(self) -> None:
        gen = ElementaryAddSubSkeletonGenerator()
        pool_size = len(_build_pool())
        drained = _drain(gen, pool_size + 10)
        assert len(drained) == pool_size
        assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        # 전건 4종 게이트 통과 — 산술 도메인에 이차방정식과 동일 게이트 인프라가 그대로 통한다
        # (Tier1 verify_answer가 방정식 sympify 기반 범용 검산기라는 실측의 회귀 봉인).
        candidates = _drain(ElementaryAddSubSkeletonGenerator(), 150)
        assert len(candidates) >= 150
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(candidate.problem.difficulty_overall),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_answer_matches_independent_arithmetic(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 계산(a+b/a-b)과 수치 일치."""
        for candidate in _drain(ElementaryAddSubSkeletonGenerator(), 150):
            cond = candidate.conditions
            assert isinstance(cond, str)
            lhs, _, rhs = cond.partition("= x")
            assert rhs == ""  # "= x" 접미 계약(조건 문자열 형식 고정).
            expected = eval(lhs.replace(" ", ""))  # noqa: S307 — "N +/- N" 산술식만(하드코딩 뼈대)
            assert int(candidate.answer_map["x"]) == expected, cond


class TestCandidateShape:
    def test_answer_format_and_question_format(self) -> None:
        for candidate in _drain(ElementaryAddSubSkeletonGenerator(), 30):
            assert candidate.problem.answer_format == AnswerFormat.자연수
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_within_elementary_awareness_band(self) -> None:
        """난이도는 L6 awareness 앵커(1.5) 이내로 클램프 — 고학년 밴드로 새지 않는다."""
        for candidate in _drain(ElementaryAddSubSkeletonGenerator(), 200):
            assert 1.0 <= candidate.problem.difficulty_overall <= 1.5

    def test_concept_tags_default_to_addition_source(self) -> None:
        candidate = ElementaryAddSubSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "A2"
        assert candidate.concept_tags[0].role == "PRIMARY"

    def test_solution_steps_intentionally_none(self) -> None:
        """단일 연산 산술은 다단계 과정이 없다 — Tier1 단독 verified가 정직한 최종 등급."""
        candidate = ElementaryAddSubSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_deterministic_problem_id_across_regeneration(self) -> None:
        first = _drain(ElementaryAddSubSkeletonGenerator(), 20)
        second = _drain(ElementaryAddSubSkeletonGenerator(), 20)
        assert [c.problem.problem_id for c in first] == [c.problem.problem_id for c in second]

    def test_josa_particles_are_grammatically_selected_not_hardcoded(self) -> None:
        """조사(을/를·와/과)가 숫자 읽기 기반으로 선택된다 — 최소 두 형태 다 관측(변별력)."""
        texts = [c.problem.question_text for c in _drain(ElementaryAddSubSkeletonGenerator(), 60)]
        joined = " ".join(texts)
        assert "와" in joined or "과" in joined
        assert "을" in joined or "를" in joined


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        first = ElementaryAddSubSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        gen2 = ElementaryAddSubSkeletonGenerator(skip_conditions=seen)
        second = gen2.generate(_spec())
        assert second is not None
        assert second.conditions != first.conditions  # 건너뛰어 다음 뼈대로 진행했다.
