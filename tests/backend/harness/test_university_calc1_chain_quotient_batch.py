"""대학 CALC1(몫의 미분법·연쇄법칙) 파일럿 코퍼스 배치(W2 Phase1 #6) — 결정론·LLM 0.

검증 축(university_calc1_batch·quad_ineq_batch 대칭):
  ① 2밴드(quotient-rule/chain-rule) 전건이 수용 게이트(Tier1 SymPy 미분 평가 검산)를
     통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **밴드 간 problem_id 중복 0**.
  ⑤ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑥ 산출물이 항상 `is_published=False`이고 `concepts`가 빈 배열(대학 원자 태깅 공백).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.university_calc1_chain_quotient_batch import (
    run_university_calc1_chain_quotient_batch,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.calculus_chain_quotient_rule_skeleton_generator import (
    CalculusChainRuleSkeletonGenerator,
    CalculusQuotientRuleSkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_QUOTIENT_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[CALC1-02-03]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.9,
    answer_format=None,
)
_CHAIN_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[CALC1-02-04]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.8,
    answer_format=None,
)


def test_batch_stores_all_bands_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_university_calc1_chain_quotient_batch(n_per_band=150, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"quotient-rule", "chain-rule"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 300  # 150×2밴드.

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    assert len({r["problem_id"] for r in records}) == len(records)  # 전건 고유.
    codes_seen = {r["achievement_standard_codes"][0] for r in records}
    assert codes_seen == {"[CALC1-02-03]", "[CALC1-02-04]"}
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False
        assert record["concepts"] == []


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_university_calc1_chain_quotient_batch(n_per_band=120, out_path=first)
    run_university_calc1_chain_quotient_batch(n_per_band=120, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 Tier1 산술 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = CalculusQuotientRuleSkeletonGenerator()

        def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
            candidate = self._inner.generate(spec)
            if candidate is None:
                return None
            broken = candidate.problem.model_copy(
                update={"answer": str(int(candidate.problem.answer) + 1)}
            )
            return candidate.model_copy(
                update={"problem": broken, "answer_map": {"y": broken.answer}}
            )

    outcomes = [run_equivalent_generation(_QUOTIENT_SPEC, BrokenGenerator()) for _ in range(8)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(_CHAIN_SPEC, CalculusChainRuleSkeletonGenerator())
        for _ in range(11)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 11
