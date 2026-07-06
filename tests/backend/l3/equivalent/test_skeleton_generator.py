"""파라메트릭 스켈레톤 생성기(S2-o) — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본):
  ① 후보는 전부 S2-a 게이트 통과(accepted) — 결정론 코어가 곧 검증 가능성.
  ② answer_map은 derive_selected_root(독립 유도)와 정확히 일치 — 교차 검증.
  ③ 구조 signature 전부 상이 — 판박이가 생성 자체가 안 됨(LLM-first 대비 핵심 개선).
  ④ skip_signatures 존중·풀 소진 시 None·재현 결정론.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l3.equivalent.skeleton_generator import (
    SkeletonEquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.schema.enums import AnswerFormat

_STANDARD = "[10공수1-02-02]"


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset(),
        "difficulty_overall": 2.5,
        "answer_format": AnswerFormat.실수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _draw(generator: SkeletonEquivalentProblemGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(SkeletonEquivalentProblemGenerator(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        # 같은 구성 → 같은 출제 순서(고정 시드·재현).
        a = [c.problem.slug for c in _draw(SkeletonEquivalentProblemGenerator(), 5)]
        b = [c.problem.slug for c in _draw(SkeletonEquivalentProblemGenerator(), 5)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = SkeletonEquivalentProblemGenerator()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 2000  # 무한루프 방어(풀은 유한)
        assert count > 300  # 수백 조합(레퍼토리 ~10개인 LLM-first 대비 핵심)
        assert gen.generate(_spec()) is None  # 소진 후에도 안정적으로 None


class TestMathematicalSoundness:
    def test_first_100_all_pass_acceptance_gate(self) -> None:
        # ① 결정론 코어 = 게이트 통과 가능성 — 표본 100 전건 accepted.
        for candidate in _draw(SkeletonEquivalentProblemGenerator(), 100):
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
        # ② 교차 검증 — 생성기의 answer_map을 독립 유도(derive_selected_root)와 대조.
        for candidate in _draw(SkeletonEquivalentProblemGenerator(), 100):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_signatures_all_distinct(self) -> None:
        # ③ 판박이 무생성 — 표본 200의 구조 signature 전부 상이.
        signatures = set()
        for candidate in _draw(SkeletonEquivalentProblemGenerator(), 200):
            sig = canonical_signature(candidate.conditions, candidate.answer_selection)
            assert sig is not None
            assert sig not in signatures
            signatures.add(sig)

    def test_answers_are_exact_values(self) -> None:
        # 반올림 소수 금지 — 정답은 정수/기약분수 문자열('4/3'류)만.
        for candidate in _draw(SkeletonEquivalentProblemGenerator(), 100):
            assert "." not in candidate.problem.answer
            assert "." not in candidate.answer_map["x"]


class TestCopyrightForcing:
    def test_provenance_is_self_generated(self) -> None:
        candidate = SkeletonEquivalentProblemGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.problem.source_type == "자체생성"
        assert candidate.provenance.license == "WHYMATH_GENERATED"
        assert candidate.provenance.original_source is None


class TestSkipSignatures:
    def test_skip_set_is_respected(self) -> None:
        # 첫 뼈대의 signature를 skip에 넣으면 그 구조는 건너뛴다(재실행 회차 낭비 방지).
        first = SkeletonEquivalentProblemGenerator().generate(_spec())
        assert first is not None
        sig = canonical_signature(first.conditions, first.answer_selection)
        assert sig is not None
        gen = SkeletonEquivalentProblemGenerator(skip_signatures={sig})
        replacement = gen.generate(_spec())
        assert replacement is not None
        assert canonical_signature(replacement.conditions, replacement.answer_selection) != sig

    def test_live_shared_set_skips_incrementally(self) -> None:
        # 오케스트레이터 signature_index와 같은 set을 공유하면 회차 간 증분 반영(살아있는 참조).
        shared: set[str] = set()
        gen = SkeletonEquivalentProblemGenerator(skip_signatures=shared)
        c1 = gen.generate(_spec())
        assert c1 is not None
        # 두 번째 뼈대의 signature를 밖에서 등록 — 다음 호출이 그 구조를 건너뛰는지.
        peek = SkeletonEquivalentProblemGenerator()
        peek.generate(_spec())
        second = peek.generate(_spec())
        assert second is not None
        sig2 = canonical_signature(second.conditions, second.answer_selection)
        assert sig2 is not None
        shared.add(sig2)
        c2 = gen.generate(_spec())
        assert c2 is not None
        assert canonical_signature(c2.conditions, c2.answer_selection) != sig2


class TestDeterministicMetadata:
    """S2-p — 난이도·개념 태깅·problem_id가 뼈대에서 결정론으로 저작되는지."""

    def test_difficulty_is_estimated_not_spec_mirror(self) -> None:
        # 2.5 균일(스펙 미러) 회귀 차단 — 표본 100의 난이도가 실제로 분산되고 척도 안이다.
        candidates = _draw(SkeletonEquivalentProblemGenerator(), 100)
        values = {c.problem.difficulty_overall for c in candidates}
        assert len(values) >= 3
        for value in values:
            assert value is not None and 1.0 <= value <= 5.0

    def test_concept_tags_default_hk06_primary(self) -> None:
        # 기본 개념 태깅 — HK06(이차방정식의 근) PRIMARY. 코퍼스 concepts []의 상환.
        candidate = SkeletonEquivalentProblemGenerator().generate(_spec())
        assert candidate is not None
        assert [(t.concept_src_id, t.role) for t in candidate.concept_tags] == [("HK06", "PRIMARY")]

    def test_concept_tags_injectable(self) -> None:
        # 다른 단원 스켈레톤 대비 — 생성자 주입으로 교체 가능(unit_codes 선례).
        from whymath_backend.l1.problem_bank.populate import ConceptTag

        tags = (ConceptTag(concept_src_id="J0220", role="SUPPORTING", relevance=0.5),)
        candidate = SkeletonEquivalentProblemGenerator(concept_tags=tags).generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["J0220"]

    def test_problem_id_deterministic_across_instances(self) -> None:
        # slug 기반 uuid5 — 같은 내용이면 실행·인스턴스가 달라도 같은 id(재생성 바이트 동일성).
        a = SkeletonEquivalentProblemGenerator().generate(_spec())
        b = SkeletonEquivalentProblemGenerator().generate(_spec())
        assert a is not None and b is not None
        assert a.problem.slug == b.problem.slug
        assert a.problem.problem_id == b.problem.problem_id


class TestSqrtVariant:
    """무리근 variant(S2-p) — (x−p)²=q 완전제곱꼴·SymPy 정확값 answer."""

    def _sqrt_gen(self) -> SkeletonEquivalentProblemGenerator:
        return SkeletonEquivalentProblemGenerator(variant="sqrt")

    def test_first_30_all_pass_acceptance_gate(self) -> None:
        # 무리근도 4종 게이트 전건 통과 — 검증 인프라(evalf·solve·위생)가 sqrt를 수용함의 봉인.
        gen = self._sqrt_gen()
        for _ in range(30):
            candidate = gen.generate(_spec())
            assert candidate is not None
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
        # 교차 검증 — SymPy 표기 answer가 derive_selected_root 반환과 *문자열까지* 일치.
        gen = self._sqrt_gen()
        for _ in range(30):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_answers_are_irrational_exact_values(self) -> None:
        gen = self._sqrt_gen()
        for _ in range(30):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert "sqrt(" in candidate.problem.answer  # 무리근 정확값(반올림 소수 0)
            assert "." not in candidate.problem.answer
            assert candidate.problem.answer_format == "실수"
            assert candidate.answer_selection in {"largest", "smallest"}

    def test_signatures_distinct_and_disjoint_from_rational_pool(self) -> None:
        # 무리근 풀 내부 판박이 0 + 유리근 풀과 구조 서명 서로소(근의 체가 다름 — 충돌 원천 불가).
        sqrt_sigs = set()
        gen = self._sqrt_gen()
        while (candidate := gen.generate(_spec())) is not None:
            sig = canonical_signature(candidate.conditions, candidate.answer_selection)
            assert sig is not None
            assert sig not in sqrt_sigs
            sqrt_sigs.add(sig)
        assert len(sqrt_sigs) >= 100  # sqrt 단답형 풀(형식 파티션 후 122·방어적 하한)

        rational_sigs = set()
        for candidate in _draw(SkeletonEquivalentProblemGenerator(), 200):
            sig = canonical_signature(candidate.conditions, candidate.answer_selection)
            rational_sigs.add(sig)
        assert sqrt_sigs.isdisjoint(rational_sigs)

    def test_deterministic_sequence(self) -> None:
        a_gen, b_gen = self._sqrt_gen(), self._sqrt_gen()
        a = [a_gen.generate(_spec()) for _ in range(5)]
        b = [b_gen.generate(_spec()) for _ in range(5)]
        assert [c.problem.slug for c in a if c] == [c.problem.slug for c in b if c]


class TestSqrtMultipleChoiceVariant:
    """무리근 객관식 variant(S2-p 후속) — (x−p)²=q 4지선다·SymPy 정확값 선지·오개념 주입.

    유리근 객관식과 대칭 — 오답값(반대근·정수부 p 부호 반전)을 코드가 알고, id는 불투명 문자열
    주입(L4 import 0). p≠0 적격 + 해시 파티션으로 무리근 단답형 풀과 서로소.
    """

    _CODES = {
        "opposite_root": ("fake-opposite-id", "fake-opposite-op"),
        "sign_flip": ("fake-sign-flip-id", "fake-sign-flip-op"),
    }

    def _gen(self) -> SkeletonEquivalentProblemGenerator:
        return SkeletonEquivalentProblemGenerator(
            variant="sqrt_multiple_choice",
            distractor_codes=self._CODES,  # type: ignore[arg-type]
        )

    def _mc_spec(self) -> EquivalenceSpec:
        return _spec(target_misconception_ids=frozenset({"fake-opposite-id", "fake-sign-flip-id"}))

    def test_missing_injection_fails_fast(self) -> None:
        try:
            SkeletonEquivalentProblemGenerator(variant="sqrt_multiple_choice")
        except ValueError as error:
            assert "distractor_codes" in str(error)
        else:
            raise AssertionError("distractor_codes 미주입인데 생성자가 통과")

    def test_first_20_all_pass_acceptance_gate(self) -> None:
        gen = self._gen()
        for _ in range(20):
            candidate = gen.generate(self._mc_spec())
            assert candidate is not None
            verdict = evaluate_equivalent_candidate(
                self._mc_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_choices_are_irrational_and_answer_present(self) -> None:
        gen = self._gen()
        for _ in range(20):
            candidate = gen.generate(self._mc_spec())
            assert candidate is not None
            problem = candidate.problem
            assert problem.question_format == "객관식"
            assert problem.choices is not None and len(problem.choices) == 4
            assert len(set(problem.choices)) == 4
            assert all("sqrt(" in choice for choice in problem.choices)  # 4선지 전부 무리근
            assert problem.answer in problem.choices
            assert problem.answer_format == "실수"

    def test_distractor_map_covers_all_wrong_choices(self) -> None:
        candidate = self._gen().generate(self._mc_spec())
        assert candidate is not None
        problem = candidate.problem
        assert problem.choices is not None and problem.distractor_map is not None
        assert len(problem.distractor_map) == 3
        answer_index = problem.choices.index(problem.answer)
        indexes = {entry.choice_index for entry in problem.distractor_map}
        assert answer_index not in indexes
        assert indexes == set(range(4)) - {answer_index}
        ids = {entry.misconception_id for entry in problem.distractor_map}
        assert ids == {"fake-opposite-id", "fake-sign-flip-id"}

    def test_partition_disjoint_from_sqrt_short_pool(self) -> None:
        # 무리근 객관식 풀과 무리근 단답형 풀의 구조 서명 서로소(뼈대당 형식 1개·dedup 충돌 차단).
        mc_sigs = set()
        gen = self._gen()
        while (candidate := gen.generate(self._mc_spec())) is not None:
            mc_sigs.add(canonical_signature(candidate.conditions, candidate.answer_selection))
        assert len(mc_sigs) >= 40  # 무리근 MC 풀(파티션 후 58·방어적 하한)

        short_sigs = set()
        short_gen = SkeletonEquivalentProblemGenerator(variant="sqrt")
        while (candidate := short_gen.generate(_spec())) is not None:
            short_sigs.add(canonical_signature(candidate.conditions, candidate.answer_selection))
        assert mc_sigs.isdisjoint(short_sigs)

    def test_deterministic_sequence(self) -> None:
        a_gen, b_gen = self._gen(), self._gen()
        a = [a_gen.generate(self._mc_spec()) for _ in range(5)]
        b = [b_gen.generate(self._mc_spec()) for _ in range(5)]
        assert [c.problem.slug for c in a if c] == [c.problem.slug for c in b if c]


class TestMultipleChoiceVariant:
    """객관식 variant(S2-p) — 결정론 4지선다·distractor 오개념 주입·형식 파티션.

    오개념 id는 *불투명 문자열*로 주입된다(L3는 L4 카탈로그를 모름) — 테스트도 가짜 id를
    주입해 이 계약을 증명한다(hermetic·L4 import 0). 실 id 결선은 조성 루트(배치 CLI) 소관.
    """

    _CODES = {
        "opposite_root": ("fake-opposite-id", "fake-opposite-op"),
        "sign_flip": ("fake-sign-flip-id", "fake-sign-flip-op"),
    }

    def _mc_gen(self, **kwargs: object) -> SkeletonEquivalentProblemGenerator:
        return SkeletonEquivalentProblemGenerator(
            variant="multiple_choice",
            distractor_codes=self._CODES,  # type: ignore[arg-type]
            **kwargs,  # type: ignore[arg-type]
        )

    def _mc_spec(self) -> EquivalenceSpec:
        # 밴드 스펙 정합 — 타깃 오개념 = 주입 id 집합(조립이 항상 두 오개념을 방출 → Jaccard 1.0).
        return _spec(target_misconception_ids=frozenset({"fake-opposite-id", "fake-sign-flip-id"}))

    def test_missing_injection_fails_fast(self) -> None:
        # 주입 없이 객관식 생성 시도 → 생성자 ValueError(조용한 무매핑 금지).
        try:
            SkeletonEquivalentProblemGenerator(variant="multiple_choice")
        except ValueError as error:
            assert "distractor_codes" in str(error)
        else:
            raise AssertionError("distractor_codes 미주입인데 생성자가 통과")

    def test_choices_structure(self) -> None:
        gen = self._mc_gen()
        for _ in range(30):
            candidate = gen.generate(self._mc_spec())
            assert candidate is not None
            problem = candidate.problem
            assert problem.question_format == "객관식"
            assert problem.choices is not None and len(problem.choices) == 4
            assert len(set(problem.choices)) == 4  # 선지 전부 상이
            # 값 오름차순 정렬(결정론) — Fraction으로 되돌려 확인.
            from fractions import Fraction

            parsed = [Fraction(c) for c in problem.choices]
            assert parsed == sorted(parsed)
            assert problem.answer in problem.choices

    def test_distractor_map_covers_all_wrong_choices(self) -> None:
        gen = self._mc_gen()
        candidate = gen.generate(self._mc_spec())
        assert candidate is not None
        problem = candidate.problem
        assert problem.choices is not None and problem.distractor_map is not None
        assert len(problem.distractor_map) == 3  # 정답 제외 전 선지 매핑
        answer_index = problem.choices.index(problem.answer)
        indexes = {entry.choice_index for entry in problem.distractor_map}
        assert answer_index not in indexes
        assert indexes == set(range(4)) - {answer_index}
        # 주입 id·op_code가 그대로 실린다(하드코딩 0의 증명).
        ids = {entry.misconception_id for entry in problem.distractor_map}
        assert ids == {"fake-opposite-id", "fake-sign-flip-id"}
        ops = {entry.op_code for entry in problem.distractor_map}
        assert ops == {"fake-opposite-op", "fake-sign-flip-op"}

    def test_first_30_all_pass_acceptance_gate(self) -> None:
        # 객관식도 4종 게이트 전건 통과 — 오개념 Jaccard 성분이 밴드 스펙과 정합(1.0).
        gen = self._mc_gen()
        for _ in range(30):
            candidate = gen.generate(self._mc_spec())
            assert candidate is not None
            verdict = evaluate_equivalent_candidate(
                self._mc_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_partition_disjoint_from_short_answer_pool(self) -> None:
        # 뼈대당 형식 1개 — 객관식 풀과 단답형 풀의 구조 signature가 서로소(dedup 충돌 원천 차단).
        mc_sigs = set()
        gen = self._mc_gen()
        while (candidate := gen.generate(self._mc_spec())) is not None:
            mc_sigs.add(canonical_signature(candidate.conditions, candidate.answer_selection))
        assert len(mc_sigs) >= 50  # 적격 뼈대의 해시 1/3 배정(대략 수십~백여 개)

        short_gen = SkeletonEquivalentProblemGenerator()
        short_sigs = set()
        while (candidate := short_gen.generate(_spec())) is not None:
            short_sigs.add(canonical_signature(candidate.conditions, candidate.answer_selection))
        assert mc_sigs.isdisjoint(short_sigs)

    def test_deterministic_sequence(self) -> None:
        a_gen, b_gen = self._mc_gen(), self._mc_gen()
        a = [a_gen.generate(self._mc_spec()) for _ in range(5)]
        b = [b_gen.generate(self._mc_spec()) for _ in range(5)]
        assert [c.problem.slug for c in a if c] == [c.problem.slug for c in b if c]


class TestOrchestratorWiring:
    def test_batch_all_accepted_no_duplicates(self) -> None:
        # 배치 30회 — 전부 accepted(dry-run)·중복/실패 0(LLM-first 실측 82% 중복과 대비).
        outcomes = run_batch(_spec(), SkeletonEquivalentProblemGenerator(), 30)
        statuses = {o.status for o in outcomes}
        assert statuses == {"accepted"}

    def test_batch_sqrt_variant_all_accepted(self) -> None:
        # 무리근 variant도 오케스트레이터 결선에서 전건 accepted.
        gen = SkeletonEquivalentProblemGenerator(variant="sqrt")
        outcomes = run_batch(_spec(), gen, 20)
        assert {o.status for o in outcomes} == {"accepted"}
