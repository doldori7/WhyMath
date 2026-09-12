"""고등 2×2 행렬 연산 결정론 스켈레톤 생성기 — W2 단위테스트(hermetic·게이트 재사용).

`MatrixOpsSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(초등 산술에 이어 두 번째
비다항 도메인에서 게이트 인프라 무변경 재사용 재실증) ② answer가 독립 재계산(성분 덧셈/
뺄셈/스칼라배/내적)과 일치 ③ 풀 유일·소진 시 None ④ `operation` 필터로 밴드가 실제로
분리됨(2026-08-05 elementary_addsub 실측 사고의 재발 방지 회귀 봉인) ⑤ 개념 태깅·정답형식을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.matrix_ops_skeleton_generator import (
    MatrixOperation,
    MatrixOpsSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_STANDARD = "[10공수1-04-02]"


def _spec(difficulty: float = 2.0) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=difficulty,
        answer_format=None,
    )


def _drain(gen: MatrixOpsSkeletonGenerator, limit: int) -> list[CandidateProblem]:
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
        assert len(pool) >= 400  # 4연산 × 시드 샘플(연산당 최대 120).
        keys = {(s.a, s.b, s.k, s.operation, s.row, s.col) for s in pool}
        assert len(keys) == len(pool)

    def test_scalar_mul_never_yields_zero_scalar(self) -> None:
        for skeleton in _build_pool():
            if skeleton.operation == "scalar_mul":
                assert skeleton.k != 0

    def test_operation_filter_partitions_pool_disjointly(self) -> None:
        """`operation` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인의 핵심.

        필터 없이 인스턴스를 여러 개 만들면 고정 시드 풀을 매번 처음부터 재생해 *같은* 뼈대가
        여러 밴드에서 중복 방출된다(elementary_addsub_batch에서 실제로 발생 → 400개 중 200개가
        중복). operation을 지정하면 그 연산의 조건 문자열만 나와야 한다.
        """
        seen_conditions: set[str] = set()
        for operation in ("add", "subtract", "scalar_mul", "multiply"):
            candidates = _drain(MatrixOpsSkeletonGenerator(operation=operation), 30)
            assert len(candidates) == 30
            conditions = {c.conditions for c in candidates}
            assert not (
                conditions & seen_conditions
            ), f"{operation} 밴드가 이전 밴드와 조건을 공유 — 밴드 분리 실패(회귀)."
            seen_conditions |= conditions

    def test_generation_exhausts_to_none_per_operation(self) -> None:
        for operation in ("add", "subtract", "scalar_mul", "multiply"):
            pool_size = len([s for s in _build_pool() if s.operation == operation])
            gen = MatrixOpsSkeletonGenerator(operation=operation)
            drained = _drain(gen, pool_size + 5)
            assert len(drained) == pool_size, operation
            assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        for operation in ("add", "subtract", "scalar_mul", "multiply"):
            candidates = _drain(MatrixOpsSkeletonGenerator(operation=operation), 60)
            assert len(candidates) >= 60, operation
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _spec(candidate.problem.difficulty_overall),
                    candidate.problem,
                    provenance=candidate.provenance,
                    conditions=candidate.conditions,
                    answer_map=candidate.answer_map,
                    solution_steps=candidate.solution_steps,
                )
                assert (
                    verdict.accepted is True
                ), f"{candidate.problem.slug} 미수용: {verdict.reasons}"
                assert verdict.verification == "verified"

    def test_answer_matches_independent_recomputation(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(성분 덧셈/뺄셈/스칼라배/내적)과 일치."""
        pool_by_op: dict[MatrixOperation, list] = {  # type: ignore[type-arg]
            "add": [],
            "subtract": [],
            "scalar_mul": [],
            "multiply": [],
        }
        for skeleton in _build_pool():
            pool_by_op[skeleton.operation].append(skeleton)

        for skeleton in pool_by_op["add"][:50]:
            i, j = skeleton.row, skeleton.col
            assert skeleton.result_entry == skeleton.a[i][j] + skeleton.b[i][j]
        for skeleton in pool_by_op["subtract"][:50]:
            i, j = skeleton.row, skeleton.col
            assert skeleton.result_entry == skeleton.a[i][j] - skeleton.b[i][j]
        for skeleton in pool_by_op["scalar_mul"][:50]:
            i, j = skeleton.row, skeleton.col
            assert skeleton.result_entry == skeleton.k * skeleton.a[i][j]
        for skeleton in pool_by_op["multiply"][:50]:
            i, j = skeleton.row, skeleton.col
            expected = skeleton.a[i][0] * skeleton.b[0][j] + skeleton.a[i][1] * skeleton.b[1][j]
            assert skeleton.result_entry == expected


class TestCandidateShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(MatrixOpsSkeletonGenerator(operation="add"), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_bands_by_operation(self) -> None:
        for operation, expected in (
            ("add", 2.0),
            ("subtract", 2.0),
            ("scalar_mul", 2.0),
            ("multiply", 2.8),
        ):
            candidate = MatrixOpsSkeletonGenerator(operation=operation).generate(_spec())
            assert candidate is not None
            assert candidate.problem.difficulty_overall == expected

    def test_concept_tags_default_to_matrix_ops_source(self) -> None:
        candidate = MatrixOpsSkeletonGenerator(operation="add").generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK43"

    def test_solution_steps_intentionally_none(self) -> None:
        """성분 1개짜리 스칼라 조건은 다단계 과정이 없다 — Tier1 단독 verified가 정직하다."""
        candidate = MatrixOpsSkeletonGenerator(operation="multiply").generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_question_text_contains_both_matrices_when_applicable(self) -> None:
        add_candidate = MatrixOpsSkeletonGenerator(operation="add").generate(_spec())
        assert add_candidate is not None
        assert add_candidate.problem.question_text.count("[[") == 2  # A와 B 둘 다 노출.

        scalar_candidate = MatrixOpsSkeletonGenerator(operation="scalar_mul").generate(_spec())
        assert scalar_candidate is not None
        assert scalar_candidate.problem.question_text.count("[[") == 1  # A만(B 없음).


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        gen1 = MatrixOpsSkeletonGenerator(operation="add", skip_conditions=seen)
        first = gen1.generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        gen2 = MatrixOpsSkeletonGenerator(operation="add", skip_conditions=seen)
        second = gen2.generate(_spec())
        assert second is not None
        assert second.conditions != first.conditions
