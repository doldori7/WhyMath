"""초등 나눗셈(두 자리 수) 몫과 나머지 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`TwoDigitDivisionSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `floor()` 조건이
주어진 정보만으로 몫·나머지를 독립 재유도함을 재확인) ② answer가 나눗셈 항등식(dividend=
divisor*quotient+remainder)과 일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로 밴드가 실제로
분리됨(2026-08-05 elementary_addsub 사고 재발 방지 회귀 봉인) ⑤ 조사(을/를·으로/로) 정합
(2026-08-07 실측 발견 — 숫자별 받침에 따라 달라지는데 하드코딩돼 있었다) ⑥ 개념 태깅·위생
게이트 무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import re

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_division_remainder_skeleton_generator import (
    TwoDigitDivisionSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.lang.josa import euro_ro
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_STANDARD = "[4수01-07]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.6,
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
    def test_pool_nonempty_and_remainder_invariant(self) -> None:
        pool = _build_pool()
        assert len(pool) >= 1000
        for skeleton in pool:
            assert 0 <= skeleton.remainder < skeleton.divisor
            assert skeleton.dividend == skeleton.divisor * skeleton.quotient + skeleton.remainder

    def test_kind_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("quotient", "remainder"):
            candidates = _drain(TwoDigitDivisionSkeletonGenerator(kind=kind), _spec(), 30)
            assert len(candidates) == 30
            word = "몫" if kind == "quotient" else "나머지"
            assert all(word in c.problem.question_text for c in candidates), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_kind["quotient"] & ids_by_kind["remainder"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("quotient", "remainder"):
            pool_size = len(_build_pool(kind))
            gen = TwoDigitDivisionSkeletonGenerator(kind=kind)
            drained = _drain(gen, _spec(), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec()) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in ("quotient", "remainder"):
            candidates = _drain(TwoDigitDivisionSkeletonGenerator(kind=kind), _spec(), 300)
            assert len(candidates) == 300
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _spec(),
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
        candidate = TwoDigitDivisionSkeletonGenerator(kind="quotient").generate(_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(),
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
        gen = TwoDigitDivisionSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = TwoDigitDivisionSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "D3"

    def test_josa_is_dynamic_not_hardcoded(self) -> None:
        """'20로'·'2016를' 같은 비문을 봉인 — 2026-08-07 실측 회귀 봉인(를/을·로/으로 하드코딩
        발견 후 josa.eul_reul·josa.euro_ro로 교정)."""
        gen = TwoDigitDivisionSkeletonGenerator()
        checked_euro_ro = 0
        for candidate in _drain(gen, _spec(), 400):
            text = candidate.problem.question_text
            m = re.search(r"(\d+)로 나누었을 때", text)
            if m:
                divisor = m.group(1)
                assert euro_ro(divisor) == "로", f"'{divisor}로'는 비문일 수 있음: {text}"
                checked_euro_ro += 1
            assert re.search(r"\d+으로로 나누었을 때", text) is None
        assert checked_euro_ro > 0  # 최소 1건은 "로"(받침 무/ㄹ) 케이스를 실제로 통과했는지 확인.
