"""발문-수식 정합 감사기 테스트 — 초인간 검증 S3(순수·결정론·라이브 0).

StatementConsistencyAuditor가 발문-조건 불일치·선택 문구 불일치를 검출하고 정상 문항은
통과시키며, acceptance 좌석이 미주입 시 비트동일·주입 시 statement_mismatch를 차단함을 동결.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.defect_seeder import build_defect_seeded_set
from whymath_backend.l3.equivalent.retag import (
    AuditVerdict,
    StatementConsistencyAuditor,
    TagAuditor,
)
from whymath_backend.l3.equivalent.skeleton_generator import (
    SkeletonEquivalentProblemGenerator,
)

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[10공수1-02-02]"}), difficulty_overall=2.5
)


def _candidate() -> object:
    gen = SkeletonEquivalentProblemGenerator(variant="short_answer")
    c = gen.generate(_SPEC)
    assert c is not None
    return c


def test_auditor_passes_consistent_statement() -> None:
    c = _candidate()
    auditor = StatementConsistencyAuditor(conditions=c.conditions)
    verdict = auditor.audit(c.problem, answer_selection=c.answer_selection)
    assert verdict.consistency_ok


def test_auditor_detects_statement_mismatch() -> None:
    # 발문 수식 숫자를 조건과 다르게 바꾼 후보 → 불일치 검출.
    c = _candidate()
    data = c.problem.model_dump()
    # question_text의 계수 하나를 변조(조건은 그대로).
    data["question_text"] = c.problem.question_text.replace("= 0", "+ 1 = 0")
    from whymath_backend.schema.problem import Problem

    mutated = Problem.model_validate(data)
    auditor = StatementConsistencyAuditor(conditions=c.conditions)
    verdict = auditor.audit(mutated, answer_selection=c.answer_selection)
    assert not verdict.consistency_ok
    assert verdict.reason is not None and "구조가 다름" in verdict.reason


def test_auditor_detects_selection_word_mismatch() -> None:
    # 발문은 "큰 근"인데 selection=smallest → 불일치.
    c = _candidate()
    auditor = StatementConsistencyAuditor(conditions=c.conditions)
    verdict = auditor.audit(c.problem, answer_selection="smallest")
    # 발문이 큰 근을 요구하면 smallest와 어긋난다(단, 발문이 작은 근이면 통과 — 후보 의존).
    if "큰 근" in (c.problem.question_text or ""):
        assert not verdict.consistency_ok


def test_auditor_passes_when_no_equation_extractable() -> None:
    # 발문에 방정식이 없으면 감사 불가 → 통과(반증기·오탐 금지).
    c = _candidate()
    data = c.problem.model_dump()
    data["question_text"] = "이 문제의 답을 구하시오."
    from whymath_backend.schema.problem import Problem

    plain = Problem.model_validate(data)
    auditor = StatementConsistencyAuditor(conditions=c.conditions)
    assert auditor.audit(plain, answer_selection=c.answer_selection).consistency_ok


def test_protocol_isinstance() -> None:
    auditor = StatementConsistencyAuditor(conditions="x**2 = 1")
    assert isinstance(auditor, TagAuditor)


# ── acceptance 좌석 — 미주입 비트동일 / 주입 시 statement_mismatch 차단 ──────


def test_acceptance_bit_identical_without_auditor() -> None:
    # tag_auditor 미주입이면 consistency_ok=True·기존 필드 동일(비트동일).
    c = _candidate()
    v = evaluate_equivalent_candidate(
        _SPEC,
        c.problem,
        provenance=c.provenance,
        conditions=c.conditions,
        answer_map=c.answer_map,
        answer_selection=c.answer_selection,
    )
    assert v.accepted is True
    assert v.consistency_ok is True


def test_acceptance_blocks_statement_mismatch_with_auditor() -> None:
    # statement_mismatch 결함 문항을 감사기와 함께 태우면 accepted=False.
    items = build_defect_seeded_set(n_defective=60, n_clean=0, seed=20260708)
    mismatch_items = [it for it in items if it.defect_class == "statement_mismatch"]
    assert mismatch_items
    for it in mismatch_items:
        c = it.candidate
        auditor = StatementConsistencyAuditor(conditions=c.conditions)
        v = evaluate_equivalent_candidate(
            it.spec,
            c.problem,
            provenance=c.provenance,
            conditions=c.conditions,
            answer_map=c.answer_map,
            answer_selection=c.answer_selection,
            tag_auditor=auditor,
        )
        assert not v.accepted
        assert not v.consistency_ok


def test_fake_auditor_seam() -> None:
    # 가짜 감사기가 False를 내면 게이트가 차단한다(좌석 계약 확인).
    class _FakeReject:
        def audit(self, candidate: object, *, answer_selection: str | None) -> AuditVerdict:
            return AuditVerdict(False, "가짜 거부")

    c = _candidate()
    v = evaluate_equivalent_candidate(
        _SPEC,
        c.problem,
        provenance=c.provenance,
        conditions=c.conditions,
        answer_map=c.answer_map,
        answer_selection=c.answer_selection,
        tag_auditor=_FakeReject(),
    )
    assert not v.accepted and not v.consistency_ok
