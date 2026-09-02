"""고등 확률의 덧셈정리·여사건·곱셈정리 파일럿 코퍼스 배치(W2 Phase3 #3) — 결정론·LLM 0.

검증 축(binomial_distribution_batch 대칭):
  ① 3밴드(addition/complement/multiplication) 전건이 수용 게이트(Tier1 유리수 산술 검산)를
     통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **밴드 간 problem_id 중복 0**.
  ⑤ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑥ 산출물이 항상 `is_published=False`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.probability_law_batch import run_probability_law_batch
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.equivalent.probability_law_skeleton_generator import (
    AdditionLawSkeletonGenerator,
    MultiplicationLawSkeletonGenerator,
)
from whymath_backend.l3.verification_tier import VerificationTier

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_ADDITION_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[12확통02-02]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.8,
    answer_format=None,
)
_MULTIPLICATION_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[12확통02-06]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.0,
    answer_format=None,
)


def test_batch_stores_all_bands_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_probability_law_batch(
        addition_n=100, complement_n=60, multiplication_n=100, out_path=out
    )

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"addition", "complement", "multiplication"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 260  # 100(덧셈) + 60(여사건) + 100(곱셈).

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    assert len({r["problem_id"] for r in records}) == len(records)  # 전건 고유.
    codes_seen = {r["achievement_standard_codes"][0] for r in records}
    assert codes_seen == {"[12확통02-02]", "[12확통02-03]", "[12확통02-06]"}
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_probability_law_batch(addition_n=50, complement_n=30, multiplication_n=50, out_path=first)
    run_probability_law_batch(addition_n=50, complement_n=30, multiplication_n=50, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 다른 값으로 만든 생성기는 Tier1 유리수 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = AdditionLawSkeletonGenerator()

        def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
            candidate = self._inner.generate(spec)
            if candidate is None:
                return None
            broken = candidate.problem.model_copy(update={"answer": "9999/10000"})
            return candidate.model_copy(
                update={"problem": broken, "answer_map": {"y": broken.answer}}
            )

    outcomes = [run_equivalent_generation(_ADDITION_SPEC, BrokenGenerator()) for _ in range(8)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(_MULTIPLICATION_SPEC, MultiplicationLawSkeletonGenerator())
        for _ in range(11)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 11
