"""귀납 정의 수열 결정론 스켈레톤 생성기(S2-06) — 단위테스트(hermetic·게이트 재사용).

귀납 생성기가 ① 전건 S2-a 4종 게이트 통과 ② answer가 derive_selected_root와 일치(교차 검증·
독립 재계산) ③ 결정론·답 유일(등차·등비 가로질러) ④ **답 유일 → signature 유일**(구조 dedup
오병합 방지) ⑤ 발문 고정 형식((가)(나) 조건 나열 + 점화식)·조건 나열 메타 ⑥ **태거 상호 계약**
(발문이 태거 T1·T2 규칙에 정확히 걸리고, signature_patterns는 생성기가 채우지 않음 — 태거 단일
권위) ⑦ 등차·등비 변형 동시 수록(결정론 인터리브)을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l1.problem_bank.signature_tagger import derive_signatures
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.inductive_sequence_skeleton_generator import (
    InductiveSequenceSkeletonGenerator,
    _build_inductive_pool,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.schema.enums import SignaturePattern

_STANDARD = "[12대수03-06]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.4,
        answer_format=None,
    )


def _drain(gen: InductiveSequenceSkeletonGenerator, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestPool:
    def test_pool_answers_unique_across_kinds(self) -> None:
        # 답 유일(등차·등비 가로질러) — `x − 상수` 접힘이라 답 유일 = signature 유일.
        pool = _build_inductive_pool()
        assert len(pool) >= 30
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))
        assert all(a > 0 for a in answers)

    def test_first_30_include_both_recurrence_kinds(self) -> None:
        # 결정론 인터리브(등차 4:등비 1) — 기본 밴드(30문)에 두 점화 변형이 반드시 함께 실린다.
        kinds = {s.kind for s in _build_inductive_pool()[:30]}
        assert kinds == {"arith", "geo"}


class TestGenerator:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(InductiveSequenceSkeletonGenerator(), 500)
        assert len(candidates) >= 30
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        # 교차 검증 — answer가 폐형 조건식의 독립 SymPy 재계산(derive_selected_root)과 정수 일치.
        for candidate in _drain(InductiveSequenceSkeletonGenerator(), 500):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signatures_unique(self) -> None:
        # 답 유일 → signature 유일(오케스트레이터 구조 dedup 오병합 0).
        cands = _drain(InductiveSequenceSkeletonGenerator(), 500)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_deterministic_sequence(self) -> None:
        a = _drain(InductiveSequenceSkeletonGenerator(), 8)
        b = _drain(InductiveSequenceSkeletonGenerator(), 8)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]

    def test_question_format_and_condition_meta(self) -> None:
        # 발문 고정 형식 — (가)(나) 조건 나열 + 점화식 + aₖ 질의. 조건 나열 메타 2건.
        for candidate in _drain(InductiveSequenceSkeletonGenerator(), 30):
            problem = candidate.problem
            text = problem.question_text or ""
            assert text.startswith("수열 {aₙ}이 다음 조건을 만족시킨다.\n(가) a₁ = ")
            assert "\n(나) aₙ₊₁ = " in text
            assert text.endswith("의 값을 구하시오.")
            assert problem.has_condition_list is True
            assert problem.condition_count == 2
            assert len(problem.conditions_parsed) == 2
            assert candidate.answer_selection == "unique"
            assert problem.question_format == "단답형"
            assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수03-06"]
            assert problem.unit_codes == ["IND-SEQ"]
            assert problem.slug is not None and problem.slug.startswith("wm-indseq-")

    def test_tagger_contract(self) -> None:
        # 태거 상호 계약 — 발문이 T1(조건 나열)+T2(점화식)에 정확히 걸리고, 생성기 자신은
        # signature_patterns를 채우지 않는다(빈 배열 — 태거가 단일 권위·조성 루트가 적용).
        for candidate in _drain(InductiveSequenceSkeletonGenerator(), 30):
            assert candidate.problem.signature_patterns == []
            assert derive_signatures(candidate.problem) == [
                SignaturePattern.CONDITION_LIST,
                SignaturePattern.INDUCTIVE_SEQUENCE,
            ], candidate.problem.question_text

    def test_both_kinds_in_default_band(self) -> None:
        # 기본 밴드 볼륨(30) 안에 등차 점화·등비 점화가 함께 실린다(변형 포함 봉인).
        candidates = _drain(InductiveSequenceSkeletonGenerator(), 30)
        texts = [c.problem.question_text or "" for c in candidates]
        assert any("aₙ + " in t for t in texts)  # 등차 점화
        assert any("·aₙ" in t for t in texts)  # 등비 점화

    def test_difficulty_band(self) -> None:
        # rule-based 난이도 — 재보정(S2-08) 1.7~1.9 대역·복수 값(균일 회귀 차단).
        candidates = _drain(InductiveSequenceSkeletonGenerator(), 60)
        diffs = {c.problem.difficulty_overall for c in candidates}
        assert len(diffs) >= 2
        assert all(d is not None and 1.7 <= d <= 1.9 for d in diffs)

    def test_one_step_below_quad_factoring(self) -> None:
        # 계통 관찰 2 회귀 차단: 귀납 정의 1스텝은 QUAD-EQ 기초 인수분해(2.0)보다 쉬워야 한다.
        from whymath_backend.l3.equivalent.difficulty import estimate_difficulty

        quad_factoring = estimate_difficulty(
            root_kind="integer", lead_coefficient=1, max_abs_coefficient=10
        )
        candidates = _drain(InductiveSequenceSkeletonGenerator(), 60)
        diffs = [c.problem.difficulty_overall for c in candidates]
        assert quad_factoring == 2.0
        assert all(d is not None and d < quad_factoring for d in diffs)
