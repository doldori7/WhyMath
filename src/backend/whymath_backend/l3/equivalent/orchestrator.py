"""자체생성 동등문제 *생성 오케스트레이터* — S2 파이프라인 end-to-end 결선(S2-d).

S2 부품을 하나로 잇는 마지막 조각이다. 학생 노출 코퍼스에 자체생성 동등문제 1건이 들어가려면
다음 4단계를 *순서대로* 통과해야 하며, 이 모듈이 그 순수 조합을 소유한다(각 단계의 *구현*은 이미
있는 부품이 소유 — 재구현 0):

    생성(S2-d generator) → 수용 게이트(S2-a acceptance) → 과유사 dedup(S2-c embedding)
        → 코퍼스 저장(S2-b problem_bank)

**순수 조합 + 주입 효과**: 이 함수는 결정론 조합 로직만 담고, DB·임베딩 같은 *효과*는 전부 주입된
좌석(`store`·`dedup_index`·`embed_provider`)으로만 일으킨다. 좌석을 주입하지 않으면 그 단계를
건너뛴다 — dedup_index/embed_provider 없으면 dedup 스킵(순수 결정 모드), store 없으면 dry-run
(저장 안 함). 덕분에 전 분기를 실 DB 없이 hermetic하게 못 박을 수 있다(WH-S `run_solver`가 저장소를
주입받아 결정론으로 도는 것과 동형).

**정직성(CLAUDE.md "조용한 실패 금지")**: 모든 거부/검수/중복 사유는 `GenerationOutcome.reasons`에
쌓인다(게이트 사유는 게이트가 이미 채운 것을 이어붙임). 저장 성공만이 `accepted_stored`이며, 저장
좌석을 안 주면 `accepted`(검증은 통과했으나 저장 안 함)로 정직히 구분한다.

7계층: 생성(=LLM 라우터 도메인)은 **L3**다. 오케스트레이터는 L3 게이트(acceptance)·L1 저장
(problem_bank populate)·L1 dedup(problem_bank embedding)·L1 임베딩 provider(embedding_primitives)를
*하향/동계층*으로만 import한다(import-linter L3→L1 허용·L1→L3 역참조는 계약이 차단). L1 부품이
"언제 dedup을 걸지"를 모른 채 순수 질의만 소유하도록 둔 설계(embedding.py docstring)를 여기서
결선한다 — dedup 게이트를 *부르는* 책임이 바로 이 생성 파이프라인이다.
"""

from __future__ import annotations

import uuid
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l1.embedding_primitives import EmbeddingProvider
from whymath_backend.l1.problem_bank.embedding import (
    ProblemEmbeddingIndex,
    find_near_duplicates,
    problem_embedding_text,
)
from whymath_backend.l1.problem_bank.populate import (
    ProblemBankPopulateReport,
    ProblemBankRecord,
    ProblemProvenanceMeta,
    ProblemVerifyMeta,
)
from whymath_backend.l3.equivalent.acceptance import (
    AcceptanceVerdict,
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.schema.enums import GenerationType, LicenseType, SourceType

__all__ = [
    "GenerationOutcome",
    "ProblemBankSink",
    "run_batch",
    "run_equivalent_generation",
]

# 과유사 dedup 기본 임계값 — S2-c 좌석 상수(코사인 0.97·"거의 동일" 밴드)를 그대로 물려받는다.
# (`l1/problem_bank/embedding._NEAR_DUPLICATE_THRESHOLD`와 같은 값·같은 근거 — 판박이만 거른다.)
_DEFAULT_DEDUP_THRESHOLD = 0.97


@runtime_checkable
class ProblemBankSink(Protocol):
    """코퍼스 저장 좌석 — 레코드 배치를 `problem`/`problem_concept`에 멱등 upsert(적재 리포트 반환).

    S2-b `ProblemBankStore.populate`와 *구조적으로 동일*한 좌석이라 실 store가 그대로 주입된다.
    테스트는 이 좌석을 구현하는 capturing fake를 주입해 실 DB 없이 저장 호출을 관찰한다(hermetic).
    오케스트레이터는 후보 1건을 단일 레코드 배치(`[record]`)로 넘겨 S2-b의 단건 저장 seam을
    재사용한다(신규 저장 경로 0 — 배치 upsert 규약·concept 해석·orphan skip을 그대로 물려받음).
    """

    def populate(self, records: list[ProblemBankRecord]) -> ProblemBankPopulateReport:
        """레코드 배치를 멱등 적재하고 리포트를 반환."""
        ...


class GenerationOutcome(BaseModel):
    """오케스트레이터 1회 실행 결과 — 최종 상태 + 각 단계 산출물 + 사유(감사·운영·학생 비노출).

    `status` 6종:
      - `accepted_stored` — 게이트·dedup 통과 + 저장 좌석에 실제 적재 완료(`stored_problem_id`).
      - `accepted` — 게이트·dedup 통과했으나 저장 좌석 미주입(dry-run·저장 안 함).
      - `rejected_gate` — S2-a 수용 게이트에서 거부(저작권·정확성·위생·비동치·동치 아님).
      - `needs_review` — 게이트가 `검수필요`로 분류(사람 검수 큐 — 자동 저장 보류).
      - `rejected_duplicate` — S2-c 과유사 게이트에서 코퍼스 판박이로 판정(저장 차단).
      - `generation_failed` — 생성기가 후보를 내지 못함(None).

    `reasons`는 모든 거부/검수/중복 사유의 누적(조용한 실패 금지). `near_duplicates`는 과유사로
    잡힌 (problem_id, 코사인 유사도) 목록이다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "accepted_stored",
        "accepted",
        "rejected_gate",
        "rejected_duplicate",
        "needs_review",
        "generation_failed",
    ] = Field(description="파이프라인 최종 판정(6종).")
    candidate: CandidateProblem | None = Field(
        default=None,
        description="평가 대상 후보(생성 실패 시 None).",
    )
    acceptance: AcceptanceVerdict | None = Field(
        default=None,
        description="S2-a 게이트 판정(생성 실패 시 None).",
    )
    near_duplicates: list[tuple[uuid.UUID, float]] = Field(
        default_factory=list,
        description="과유사로 잡힌 (problem_id, 유사도) 목록(rejected_duplicate 시 비지 않음).",
    )
    stored_problem_id: uuid.UUID | None = Field(
        default=None,
        description="저장된 문제 problem_id(accepted_stored 시에만).",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="거부/검수/중복 사유 누적(사람 가독·학생 비노출·조용한 실패 금지).",
    )


def _enum_value(value: object) -> str | None:
    """enum/문자열/None을 문자열 값으로 정규화(use_enum_values=True 대응·acceptance 미러)."""
    if value is None:
        return None
    if isinstance(value, (SourceType, LicenseType, GenerationType)):
        return str(value.value)
    return str(value)


def _to_record(candidate: CandidateProblem) -> ProblemBankRecord:
    """후보 번들 → S2-b 저장 레코드(단건). slug·problem·concept_tags·verify·provenance 조립.

    저장 seam(`ProblemBankStore.populate`)이 소비하는 것은 slug·problem·concept_tags뿐이나,
    `ProblemBankRecord`는 authoring 메타(verify·provenance)도 필드로 요구하므로 후보에서 그대로
    옮겨 담는다(적재엔 미사용·계약 충족). 안정 키 `slug`는 멱등 upsert의 근간이라 후보 문제에
    반드시 있어야 한다 — 없으면 fail-loud(생성기 계약 위반·조용한 통과 금지).
    """
    slug = candidate.problem.slug
    if not slug:
        raise ValueError(
            "저장 대상 후보의 problem.slug가 비어 있습니다 — 멱등 upsert 안정 키가 없어 저장할 수 "
            "없습니다(생성기가 slug를 채워야 합니다)."
        )
    return ProblemBankRecord(
        slug=slug,
        problem=candidate.problem,
        concept_tags=tuple(candidate.concept_tags),
        verify=ProblemVerifyMeta(
            conditions=candidate.conditions,
            answer_map=dict(candidate.answer_map),
            solution_steps=candidate.solution_steps,
        ),
        provenance=ProblemProvenanceMeta(
            generation_type=_enum_value(candidate.provenance.generation_type) or "",
            license=_enum_value(candidate.provenance.license) or "",
            original_source=_enum_value(candidate.provenance.original_source),
        ),
    )


def run_equivalent_generation(
    spec: EquivalenceSpec,
    generator: EquivalentProblemGenerator,
    *,
    dedup_index: ProblemEmbeddingIndex | None = None,
    embed_provider: EmbeddingProvider | None = None,
    store: ProblemBankSink | None = None,
    dedup_threshold: float = _DEFAULT_DEDUP_THRESHOLD,
) -> GenerationOutcome:
    """동등문제 후보 1건을 생성→게이트→dedup→저장으로 흘려 최종 판정을 낸다(순수 조합·주입 효과).

    파이프라인(각 단계 실패 시 조기 종료·사유는 `reasons`에 누적):
      1. **생성**(S2-d) — `generator.generate(spec)`. None이면 `generation_failed`.
      2. **수용 게이트**(S2-a) — `evaluate_equivalent_candidate`. `accepted`가 아니면 게이트가
         `검수필요`로 분류했으면 `needs_review`, 그 외(저작권/정확성/위생/비동치)는 `rejected_gate`.
      3. **과유사 dedup**(S2-c·`dedup_index`+`embed_provider` 주입 시) — 후보 발문을 임베딩해
         `find_near_duplicates`로 코퍼스와 비교, 과유사면 `rejected_duplicate`.
      4. **저장**(S2-b·`store` 주입 시) — 후보를 `problem`/`problem_concept`에 멱등 적재하고
         (임베딩 좌석까지 주면) 그 벡터를 `dedup_index`에 upsert해 *이후 후보가 이 문제를 코퍼스
         중복으로 보게* 한다(배치 누적 dedup 근간). `accepted_stored`. store 미주입이면 `accepted`.

    좌석 주입 규약:
      - `dedup_index`·`embed_provider` 둘 다 줘야 dedup이 돈다(하나만 주면 dedup 스킵·순수 결정).
      - `store` 없으면 dry-run(검증만·저장 0). 저장 후 임베딩 영속은 `dedup_index`+`embed_provider`
        가 함께 주입됐을 때만 일어난다(임베딩 저장소 seam이 곧 dedup_index — 같은 벡터 재사용).
    """
    reasons: list[str] = []

    # ── 1. 생성(S2-d) ──
    candidate = generator.generate(spec)
    if candidate is None:
        return GenerationOutcome(
            status="generation_failed",
            reasons=["생성기가 후보를 반환하지 못했습니다(None) — 생성 실패."],
        )

    # ── 2. 수용 게이트(S2-a) ──
    verdict = evaluate_equivalent_candidate(
        spec,
        candidate.problem,
        provenance=candidate.provenance,
        conditions=candidate.conditions,
        answer_map=candidate.answer_map,
        solution_steps=candidate.solution_steps,
        answer_selection=candidate.answer_selection,
    )
    reasons.extend(verdict.reasons)
    if not verdict.accepted:
        # 게이트가 `검수필요`로 보냈으면 needs_review(사람 큐), 그 외는 rejected_gate(거부).
        status: Literal["needs_review", "rejected_gate"] = (
            "needs_review" if verdict.equivalence == "검수필요" else "rejected_gate"
        )
        return GenerationOutcome(
            status=status,
            candidate=candidate,
            acceptance=verdict,
            reasons=reasons,
        )

    # ── 3. 과유사 dedup(S2-c) — 좌석 둘 다 주입 시에만 ──
    candidate_vec: list[float] | None = None
    if dedup_index is not None and embed_provider is not None:
        text = problem_embedding_text(candidate.problem)
        candidate_vec = embed_provider.embed([text])[0]
        near = find_near_duplicates(dedup_index, candidate_vec, threshold=dedup_threshold)
        if near:
            reasons.append(
                f"과유사 중복 — 기존 코퍼스 {len(near)}건과 코사인 ≥ {dedup_threshold}"
                "(거의 동일한 판박이·저장 차단)."
            )
            return GenerationOutcome(
                status="rejected_duplicate",
                candidate=candidate,
                acceptance=verdict,
                near_duplicates=near,
                reasons=reasons,
            )

    # ── 4. 저장(S2-b) — 좌석 주입 시에만 ──
    if store is not None:
        record = _to_record(candidate)
        store.populate([record])
        # 저장한 문제의 발문 벡터를 dedup_index에 영속 — 이후 후보가 이 문제를 코퍼스 중복으로
        # 보게 한다(배치 누적 dedup). dedup 단계에서 이미 계산한 벡터를 재사용(재임베딩 0).
        if dedup_index is not None and embed_provider is not None:
            if candidate_vec is None:  # 방어(위 dedup 블록이 항상 채우나 명시) — pragma: no cover
                candidate_vec = embed_provider.embed([problem_embedding_text(candidate.problem)])[0]
            dedup_index.upsert(
                candidate.problem.problem_id,
                candidate_vec,
                source_text=problem_embedding_text(candidate.problem),
            )
        return GenerationOutcome(
            status="accepted_stored",
            candidate=candidate,
            acceptance=verdict,
            stored_problem_id=candidate.problem.problem_id,
            reasons=reasons,
        )

    # ── dry-run(저장 좌석 미주입) — 검증은 통과했으나 저장 안 함 ──
    return GenerationOutcome(
        status="accepted",
        candidate=candidate,
        acceptance=verdict,
        reasons=reasons,
    )


def run_batch(
    spec: EquivalenceSpec,
    generator: EquivalentProblemGenerator,
    n: int,
    *,
    dedup_index: ProblemEmbeddingIndex | None = None,
    embed_provider: EmbeddingProvider | None = None,
    store: ProblemBankSink | None = None,
    dedup_threshold: float = _DEFAULT_DEDUP_THRESHOLD,
) -> list[GenerationOutcome]:
    """생성기를 n회 돌려 각 후보의 outcome을 수집(코퍼스 배치 생성 데모).

    같은 `dedup_index`·`store`를 공유하므로 과유사 판정은 *직전까지 저장된 분에 대비* 누적으로
    걸린다 — 앞선 후보가 저장되며 그 벡터가 index에 실려, 같은 배치 안의 뒤 후보가 판박이면
    `rejected_duplicate`로 잡힌다(배치 내 중복도 차단). 생성기 소진 시 남은 회차는
    `generation_failed`(ScriptedGenerator가 None을 방출)로 정직히 기록된다.
    """
    return [
        run_equivalent_generation(
            spec,
            generator,
            dedup_index=dedup_index,
            embed_provider=embed_provider,
            store=store,
            dedup_threshold=dedup_threshold,
        )
        for _ in range(n)
    ]
