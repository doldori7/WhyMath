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


class TestOrchestratorWiring:
    def test_batch_all_accepted_no_duplicates(self) -> None:
        # 배치 30회 — 전부 accepted(dry-run)·중복/실패 0(LLM-first 실측 82% 중복과 대비).
        outcomes = run_batch(_spec(), SkeletonEquivalentProblemGenerator(), 30)
        statuses = {o.status for o in outcomes}
        assert statuses == {"accepted"}
