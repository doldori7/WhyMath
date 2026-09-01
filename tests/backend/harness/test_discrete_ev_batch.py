"""고등 이산확률변수 기댓값 파일럿 코퍼스 배치(W2) — 결정론·LLM 0.

검증 축(elementary_addsub_batch·matrix_ops_batch·university_calc1_batch·middle_function_
batch 대칭):
  ① 단일 밴드(expected-value) 전건이 수용 게이트(Tier1 유리수 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑤ 산출물이 항상 `is_published=False`이고, 개념 태깅이 실제로 채워진다(legacy 437 공간
     실존 개념 — 대학 축 concept_tags 공백과 대비).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from whymath_backend.harness.discrete_ev_batch import run_discrete_ev_batch
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.discrete_expected_value_skeleton_generator import (
    DiscreteExpectedValueSkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[12확통03-02]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.8,
    answer_format=None,
)


def test_batch_stores_band_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_discrete_ev_batch(n=60, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"expected-value"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 60

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    assert len({r["problem_id"] for r in records}) == len(records)  # 전건 고유.
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False
        assert record["achievement_standard_codes"] == ["[12확통03-02]"]
        assert record["concepts"] == [
            {"concept_src_id": "H:12확통03-02", "role": "PRIMARY", "relevance": 0.95}
        ]


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_discrete_ev_batch(n=60, out_path=first)
    run_discrete_ev_batch(n=60, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 어긋나게 만든 생성기는 Tier1 유리수 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = DiscreteExpectedValueSkeletonGenerator()

        def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
            candidate = self._inner.generate(spec)
            if candidate is None:
                return None
            broken_value = Fraction(candidate.problem.answer) + 1
            broken_answer = (
                str(broken_value.numerator)
                if broken_value.denominator == 1
                else f"{broken_value.numerator}/{broken_value.denominator}"
            )
            broken = candidate.problem.model_copy(update={"answer": broken_answer})
            return candidate.model_copy(
                update={"problem": broken, "answer_map": {"y": broken_answer}}
            )

    outcomes = [run_equivalent_generation(_SPEC, BrokenGenerator()) for _ in range(8)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(_SPEC, DiscreteExpectedValueSkeletonGenerator())
        for _ in range(11)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 11
