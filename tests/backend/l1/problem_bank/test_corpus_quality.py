"""문제 코퍼스 *품질 게이트* — 각 시드가 S2-a 수용 게이트를 통과함을 실증(계약 봉인).

"코퍼스는 S2-a 게이트 통과분"이라는 적재 계약(`l1/problem_bank/populate` 모듈 docstring)을 이
테스트가 봉인한다. 적재 파이프라인(L1)은 계층 규칙상 게이트(L3)를 부르지 않으므로, *테스트*가
계층 밖에서 L1 로더 + L3 게이트를 동시 import해 각 시드를 게이트에 태워 `accepted`(또는 최소
`verification=="verified"`)를 확인한다. verify 메타(conditions·answer_map)는 코퍼스 authoring
필드에서 읽는다. PG·LLM 불요(게이트는 순수·결정론).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whymath_backend.l1.problem_bank.populate import ProblemBankRecord, load_problem_bank_records
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.schema.provenance import ContentProvenance


def _corpus_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "corpus"
        / "problem_bank_v1"
        / "problems.jsonl"
    )


def _records() -> list[ProblemBankRecord]:
    corpus = _corpus_path()
    if not corpus.exists():
        pytest.skip("실 코퍼스 미존재(data/corpus/problem_bank_v1/problems.jsonl)")
    return load_problem_bank_records(corpus)


def _evaluate(record: ProblemBankRecord) -> object:
    """시드 레코드로 EquivalenceSpec/Provenance를 조립해 S2-a 게이트에 태운다(자기-정합 spec).

    spec는 시드 자신의 대응 필드(성취기준·오개념·난이도·답형태)로 구성하므로 동등성 성분은 모두
    만점(원본=후보). 즉 정확성(verify)·저작권(provenance)·위생(본문 슬립)만이 통과의 변수다.
    """
    problem = record.problem
    misc = frozenset(entry.misconception_id for entry in (problem.distractor_map or []))
    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset(problem.achievement_standard_codes),
        target_misconception_ids=misc,
        difficulty_overall=problem.difficulty_overall or 3.0,
        answer_format=problem.answer_format,
    )
    provenance = ContentProvenance(
        generation_type=record.provenance.generation_type,
        license=record.provenance.license,
        original_source=record.provenance.original_source,
    )
    return evaluate_equivalent_candidate(
        spec,
        problem,
        provenance=provenance,
        conditions=record.verify.conditions,
        answer_map=record.verify.answer_map,
        solution_steps=record.verify.solution_steps,
    )


def test_every_seed_passes_acceptance_gate() -> None:
    records = _records()
    assert len(records) >= 3  # 손저작 시드 3~5개
    for record in records:
        verdict = _evaluate(record)
        # 계약: 최소 정확성 검증(verified) — 시드가 S2-a 정확성 게이트를 실증.
        assert verdict.verification == "verified", (  # type: ignore[attr-defined]
            f"{record.slug} 정확성 미검증: {verdict.reasons}"  # type: ignore[attr-defined]
        )


def test_every_seed_is_accepted() -> None:
    # 더 강한 실증 — 4종 게이트 모두 통과(accepted=True). 자기-정합 spec이라 동치후보 보장.
    for record in _records():
        verdict = _evaluate(record)
        assert verdict.accepted is True, (  # type: ignore[attr-defined]
            f"{record.slug} 미수용: {verdict.reasons}"  # type: ignore[attr-defined]
        )


def test_seeds_have_no_metadata_only_sources() -> None:
    # 저작권 레일 — 코퍼스 전건 자체생성(평가원/EBS/교과서 본문 복제 0).
    for record in _records():
        assert record.problem.source_type == "자체생성"
        assert record.provenance.license == "WHYMATH_GENERATED"
