"""동등문제 생성 오케스트레이터 테스트 — S2-d `run_equivalent_generation`(hermetic·순수).

S2 파이프라인(생성→게이트→dedup→저장)의 전 분기를 실 DB·LLM·네트워크 0으로 커버한다:
accepted_stored·accepted(dry-run)·rejected_gate(오답·비저작권)·needs_review(검수필요)·
rejected_duplicate·generation_failed. store/index는 capturing fake(호출 관찰)이고 embed는
`FakeEmbeddingProvider`(결정론 해시 벡터)다 — 결정론 조합 로직과 reasons 정합만 못 박는다.

저작권: 후보는 전부 자작(자체생성·WHYMATH_GENERATED)이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest
from whymath_backend.l1.problem_bank.embedding import ProblemEmbeddingIndex
from whymath_backend.l1.problem_bank.populate import (
    ConceptTag,
    ProblemBankPopulateReport,
    ProblemBankRecord,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.generator import CandidateProblem, ScriptedGenerator
from whymath_backend.l3.equivalent.orchestrator import (
    GenerationOutcome,
    run_batch,
    run_equivalent_generation,
)
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem
from whymath_backend.schema.provenance import ContentProvenance

# ──────────────────────────────────────────────────────────────────────
# 후보/명세 헬퍼 — S2-a 테스트 헬퍼 미러(전 게이트 통과 기준).
# ──────────────────────────────────────────────────────────────────────
_STANDARD = "[12미적01-01]"
_MISCONCEPTION = "distribution-over-power"
_CONDITIONS = "x**2 - 5*x + 6 = 0"
_ANSWER_MAP = {"x": "3"}


def _problem(**overrides: object) -> Problem:
    kwargs: dict[str, object] = {
        "slug": "wm-orch-quad-root",
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
        "difficulty_overall": 3.0,
        "answer_format": AnswerFormat.자연수,
        "achievement_standard_codes": [_STANDARD],
        "distractor_map": [DistractorEntry(choice_index=1, misconception_id=_MISCONCEPTION)],
        "question_text": "주어진 이차식의 자연수 근을 구하시오.",
        "answer": "3",
        "answer_explanation": "주어진 조건을 풀면 정답은 자연수 세 입니다.",
    }
    kwargs.update(overrides)
    return Problem(**kwargs)  # type: ignore[arg-type]


def _provenance(**overrides: object) -> ContentProvenance:
    kwargs: dict[str, object] = {
        "generation_type": GenerationType.FULLY_GENERATED,
        "license": LicenseType.WHYMATH_GENERATED,
    }
    kwargs.update(overrides)
    return ContentProvenance(**kwargs)  # type: ignore[arg-type]


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset({_MISCONCEPTION}),
        "difficulty_overall": 3.0,
        "answer_format": AnswerFormat.자연수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _candidate(
    *,
    problem: Problem | None = None,
    provenance: ContentProvenance | None = None,
    conditions: str | list[str] = _CONDITIONS,
    answer_map: dict[str, str] | None = None,
    answer_selection: str | None = "largest",  # 두 근 2·3 중 큰 근 3 — S2-i 유일성 확정
    solution_steps: list[str] | None = None,
    concept_tags: list[ConceptTag] | None = None,
) -> CandidateProblem:
    return CandidateProblem(
        problem=problem if problem is not None else _problem(),
        provenance=provenance if provenance is not None else _provenance(),
        conditions=conditions,
        answer_map=answer_map if answer_map is not None else dict(_ANSWER_MAP),
        answer_selection=answer_selection,
        solution_steps=solution_steps,
        concept_tags=concept_tags if concept_tags is not None else [],
    )


# ──────────────────────────────────────────────────────────────────────
# capturing fakes — 실 DB 없이 저장/인덱스 호출을 관찰(hermetic).
# ──────────────────────────────────────────────────────────────────────
class _FakeStore:
    """`ProblemBankSink` 구조 호환 fake — populate 호출·레코드를 캡처(적재 리포트 반환)."""

    def __init__(self) -> None:
        self.calls: list[list[ProblemBankRecord]] = []

    def populate(self, records: list[ProblemBankRecord]) -> ProblemBankPopulateReport:
        self.calls.append(list(records))
        tags = sum(len(r.concept_tags) for r in records)
        return ProblemBankPopulateReport(
            problems_loaded=len(records),
            problem_concepts_loaded=tags,
            concepts_skipped=0,
            skipped_messages=[],
        )


class _FakeIndex(ProblemEmbeddingIndex):
    """`ProblemEmbeddingIndex` 서브클래스 — search/upsert만 결정론 오버라이드(엔진 미접속·hermetic).

    실 클래스를 상속하므로 mypy·`find_near_duplicates`(구체 타입 요구)와 정합하면서, DB에 닿는
    `_get_engine` 경로를 타지 않는다(search/upsert를 완전 대체).
    """

    def __init__(self, *, hits: Sequence[tuple[uuid.UUID, float]] = ()) -> None:
        super().__init__(provider_name="fake", model_name="fake-hash")
        self._hits: list[tuple[uuid.UUID, float]] = list(hits)
        self.upserts: list[tuple[uuid.UUID, int]] = []

    def search(  # type: ignore[override]
        self, vector: Sequence[float], *, top_k: int
    ) -> list[tuple[uuid.UUID, float]]:
        return self._hits[:top_k]

    def upsert(  # type: ignore[override]
        self, problem_id: uuid.UUID, vector: Sequence[float], *, source_text: str
    ) -> None:
        self.upserts.append((problem_id, len(list(vector))))


def _run(candidates: list[CandidateProblem | None], **kwargs: object) -> GenerationOutcome:
    generator = ScriptedGenerator(candidates)
    return run_equivalent_generation(_spec(), generator, **kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# generation_failed.
# ──────────────────────────────────────────────────────────────────────
class TestGenerationFailed:
    def test_generator_returns_none(self) -> None:
        outcome = _run([None])
        assert outcome.status == "generation_failed"
        assert outcome.candidate is None
        assert outcome.acceptance is None
        assert len(outcome.reasons) >= 1

    def test_exhausted_generator_is_failure(self) -> None:
        outcome = _run([])  # 빈 스크립트 → 즉시 소진 → None
        assert outcome.status == "generation_failed"


# ──────────────────────────────────────────────────────────────────────
# accepted (dry-run) — 게이트 통과·저장 좌석 미주입.
# ──────────────────────────────────────────────────────────────────────
class TestAcceptedDryRun:
    def test_all_gates_pass_no_store_is_dry_run(self) -> None:
        outcome = _run([_candidate()])
        assert outcome.status == "accepted"
        assert outcome.acceptance is not None and outcome.acceptance.accepted is True
        assert outcome.stored_problem_id is None
        assert outcome.reasons == []

    def test_dedup_skipped_when_only_one_seat(self) -> None:
        # embed_provider만 주고 dedup_index를 안 주면 dedup 스킵(순수 결정) → dry-run accepted.
        outcome = _run([_candidate()], embed_provider=FakeEmbeddingProvider(dim=8))
        assert outcome.status == "accepted"
        assert outcome.near_duplicates == []


# ──────────────────────────────────────────────────────────────────────
# accepted_stored — 게이트·dedup 통과 + 저장.
# ──────────────────────────────────────────────────────────────────────
class TestAcceptedStored:
    def test_store_injected_persists_and_reports_id(self) -> None:
        store = _FakeStore()
        candidate = _candidate(
            concept_tags=[ConceptTag(concept_src_id="HK06", role="PRIMARY", relevance=0.9)]
        )
        outcome = _run([candidate], store=store)
        assert outcome.status == "accepted_stored"
        assert outcome.stored_problem_id == candidate.problem.problem_id
        # 단건 레코드 배치로 S2-b seam 재사용 — slug·concept_tags 전달 확인.
        assert len(store.calls) == 1
        (records,) = store.calls
        assert len(records) == 1
        assert records[0].slug == "wm-orch-quad-root"
        assert records[0].concept_tags[0].concept_src_id == "HK06"
        # 근 선택(S2-i)이 verify 메타로 영속 — 빠지면 저장 코퍼스가 품질 게이트에서
        # "선택 미명시" 유일성 강등을 당한다(라운드트립 실측 회귀 봉인).
        assert records[0].verify.answer_selection == "largest"

    def test_store_with_embed_upserts_vector_into_index(self) -> None:
        # 저장 + dedup_index/embed 주입 시 발문 벡터를 index에 upsert(배치 누적 dedup 근간).
        store = _FakeStore()
        index = _FakeIndex(hits=[])  # 코퍼스 비어 있음 → 과유사 없음
        provider = FakeEmbeddingProvider(dim=8)
        candidate = _candidate()
        outcome = _run([candidate], store=store, dedup_index=index, embed_provider=provider)
        assert outcome.status == "accepted_stored"
        assert len(index.upserts) == 1
        assert index.upserts[0][0] == candidate.problem.problem_id

    def test_missing_slug_fails_loud_on_store(self) -> None:
        store = _FakeStore()
        candidate = _candidate(problem=_problem(slug=None))
        with pytest.raises(ValueError, match="slug"):
            _run([candidate], store=store)


# ──────────────────────────────────────────────────────────────────────
# rejected_gate — 저작권·정확성 실패(검수필요 아님).
# ──────────────────────────────────────────────────────────────────────
class TestRejectedGate:
    def test_wrong_answer_is_rejected_gate(self) -> None:
        # 오답 → 정확성 failed(검수필요 아님·동치후보 점수) → rejected_gate.
        outcome = _run([_candidate(answer_map={"x": "4"})])
        assert outcome.status == "rejected_gate"
        assert outcome.acceptance is not None
        assert outcome.acceptance.verification == "failed"
        assert outcome.stored_problem_id is None
        assert len(outcome.reasons) >= 1

    def test_non_self_generated_source_is_rejected_gate(self) -> None:
        # 저작권 게이트 실패(source_type != 자체생성) → rejected_gate.
        candidate = _candidate(problem=_problem(source_type=SourceType.AIHub))
        outcome = _run([candidate])
        assert outcome.status == "rejected_gate"
        assert outcome.acceptance is not None and outcome.acceptance.copyright_ok is False

    def test_rejected_gate_does_not_store(self) -> None:
        store = _FakeStore()
        _run([_candidate(answer_map={"x": "4"})], store=store)
        assert store.calls == []


# ──────────────────────────────────────────────────────────────────────
# needs_review — 게이트가 검수필요로 분류.
# ──────────────────────────────────────────────────────────────────────
class TestNeedsReview:
    def test_unverifiable_steps_needs_review(self) -> None:
        # 단계 판정 불가 → verification unverified → 검수필요 → needs_review.
        outcome = _run([_candidate(solution_steps=["f(x)", "g(x)"])])
        assert outcome.status == "needs_review"
        assert outcome.acceptance is not None
        assert outcome.acceptance.equivalence == "검수필요"
        assert outcome.stored_problem_id is None

    def test_standard_mismatch_needs_review(self) -> None:
        # 성취기준 불일치 → 경계 점수 → 검수필요 → needs_review.
        candidate = _candidate(problem=_problem(achievement_standard_codes=[]))
        outcome = _run([candidate])
        assert outcome.status == "needs_review"

    def test_needs_review_does_not_store(self) -> None:
        store = _FakeStore()
        _run([_candidate(solution_steps=["f(x)", "g(x)"])], store=store)
        assert store.calls == []


# ──────────────────────────────────────────────────────────────────────
# rejected_duplicate — 과유사 게이트.
# ──────────────────────────────────────────────────────────────────────
class TestRejectedDuplicate:
    def test_near_duplicate_blocks_before_store(self) -> None:
        existing = uuid.uuid4()
        index = _FakeIndex(hits=[(existing, 0.99)])  # 코사인 0.99 ≥ 0.97 → 과유사
        store = _FakeStore()
        provider = FakeEmbeddingProvider(dim=8)
        outcome = _run([_candidate()], store=store, dedup_index=index, embed_provider=provider)
        assert outcome.status == "rejected_duplicate"
        assert (existing, 0.99) in outcome.near_duplicates
        assert store.calls == []  # 저장 전 차단
        assert index.upserts == []  # 임베딩 적재도 안 함
        assert len(outcome.reasons) >= 1

    def test_below_threshold_is_not_duplicate(self) -> None:
        # 코사인 0.90 < 0.97 → 정당한 유사 문제(과잉 억제 회피) → 저장 통과.
        index = _FakeIndex(hits=[(uuid.uuid4(), 0.90)])
        store = _FakeStore()
        provider = FakeEmbeddingProvider(dim=8)
        outcome = _run([_candidate()], store=store, dedup_index=index, embed_provider=provider)
        assert outcome.status == "accepted_stored"

    def test_custom_threshold_respected(self) -> None:
        index = _FakeIndex(hits=[(uuid.uuid4(), 0.92)])
        provider = FakeEmbeddingProvider(dim=8)
        outcome = _run(
            [_candidate()], dedup_index=index, embed_provider=provider, dedup_threshold=0.90
        )
        assert outcome.status == "rejected_duplicate"


# ──────────────────────────────────────────────────────────────────────
# 구조 dedup(S2-l) — SymPy 정규형 signature로 표현 변형 판박이 차단(임베딩 불요).
# ──────────────────────────────────────────────────────────────────────
class TestStructuralDedup:
    def test_equation_variant_is_structural_duplicate(self) -> None:
        # 같은 방정식의 인수분해 표기(다른 발문·slug) → 구조 signature 동일 → rejected_duplicate.
        sig: set[str] = set()
        c1 = _candidate(conditions="x**2 - 5*x + 6 = 0")
        c2 = _candidate(conditions="(x-2)*(x-3) = 0", problem=_problem(slug="wm-b"))
        o1 = run_equivalent_generation(_spec(), ScriptedGenerator([c1]), signature_index=sig)
        o2 = run_equivalent_generation(_spec(), ScriptedGenerator([c2]), signature_index=sig)
        assert o1.status == "accepted"
        assert o2.status == "rejected_duplicate"
        assert any("구조 중복" in r for r in o2.reasons)

    def test_different_equations_not_duplicates(self) -> None:
        sig: set[str] = set()
        c1 = _candidate(conditions="x**2 - 5*x + 6 = 0")
        c2 = _candidate(
            conditions="x**2 - 7*x + 12 = 0",
            answer_map={"x": "4"},
            problem=_problem(slug="wm-b", answer="4"),
        )
        o1 = run_equivalent_generation(_spec(), ScriptedGenerator([c1]), signature_index=sig)
        o2 = run_equivalent_generation(_spec(), ScriptedGenerator([c2]), signature_index=sig)
        assert o1.status == "accepted"
        assert o2.status == "accepted"

    def test_same_equation_different_selection_not_duplicates(self) -> None:
        # 같은 방정식이라도 큰 근 vs 작은 근은 별개 문제 → signature 다름 → 둘 다 통과.
        sig: set[str] = set()
        c1 = _candidate(conditions="x**2 - 5*x + 6 = 0", answer_selection="largest")
        c2 = _candidate(
            conditions="x**2 - 5*x + 6 = 0",
            answer_map={"x": "2"},
            answer_selection="smallest",
            problem=_problem(slug="wm-b", answer="2"),
        )
        o1 = run_equivalent_generation(_spec(), ScriptedGenerator([c1]), signature_index=sig)
        o2 = run_equivalent_generation(_spec(), ScriptedGenerator([c2]), signature_index=sig)
        assert o1.status == "accepted"
        assert o2.status == "accepted"

    def test_no_signature_index_means_no_structural_dedup(self) -> None:
        # signature_index 미주입이면 구조 dedup 스킵(하위호환·기존 동작).
        c1 = _candidate(conditions="x**2 - 5*x + 6 = 0")
        c2 = _candidate(conditions="(x-2)*(x-3) = 0", problem=_problem(slug="wm-b"))
        o1 = _run([c1])
        o2 = _run([c2])
        assert o1.status == "accepted"
        assert o2.status == "accepted"

    def test_batch_structural_dedup_without_embeddings(self) -> None:
        # 배치는 구조 dedup 기본 ON — 임베딩 좌석 없이도 판박이를 차단(S2-l 핵심 효과).
        c1 = _candidate(conditions="x**2 - 5*x + 6 = 0")
        c2 = _candidate(conditions="(x-2)*(x-3) == 0", problem=_problem(slug="wm-b"))
        outcomes = run_batch(_spec(), ScriptedGenerator([c1, c2]), 2)
        assert outcomes[0].status == "accepted"
        assert outcomes[1].status == "rejected_duplicate"


# ──────────────────────────────────────────────────────────────────────
# 배치 러너 — 누적 dedup·소진.
# ──────────────────────────────────────────────────────────────────────
class TestBatch:
    def test_batch_collects_all_outcomes(self) -> None:
        generator = ScriptedGenerator([_candidate(), None])
        outcomes = run_batch(_spec(), generator, 2)
        assert [o.status for o in outcomes] == ["accepted", "generation_failed"]

    def test_batch_cumulative_dedup_within_batch(self) -> None:
        # 두 후보가 같은 발문 → 첫 후보 저장 시 index에 벡터 upsert → 둘째 후보는 그 벡터를
        # 코퍼스 중복으로 본다. FakeIndex가 upsert된 벡터를 search로 되돌려 누적 dedup을 재현.
        store = _FakeStore()
        provider = FakeEmbeddingProvider(dim=16)

        class _AccumIndex(_FakeIndex):
            """upsert된 (id, 벡터)를 코사인으로 되돌려주는 fake — 배치 누적 dedup 재현."""

            def __init__(self) -> None:
                super().__init__(hits=[])
                self._store: list[tuple[uuid.UUID, list[float]]] = []

            def upsert(  # type: ignore[override]
                self, problem_id: uuid.UUID, vector: Sequence[float], *, source_text: str
            ) -> None:
                self._store.append((problem_id, list(vector)))

            def search(  # type: ignore[override]
                self, vector: Sequence[float], *, top_k: int
            ) -> list[tuple[uuid.UUID, float]]:
                from whymath_backend.l1.embedding_provider import cosine_similarity

                scored = [(pid, cosine_similarity(vector, v)) for pid, v in self._store]
                scored.sort(key=lambda x: x[1], reverse=True)
                return scored[:top_k]

        index = _AccumIndex()
        c1 = _candidate(problem=_problem(slug="wm-a"))
        c2 = _candidate(problem=_problem(slug="wm-b"))  # 같은 발문(판박이)·다른 slug
        generator = ScriptedGenerator([c1, c2])
        outcomes = run_batch(
            _spec(), generator, 2, store=store, dedup_index=index, embed_provider=provider
        )
        assert outcomes[0].status == "accepted_stored"
        assert outcomes[1].status == "rejected_duplicate"
