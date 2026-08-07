"""대학 미적분학 I 곱의 미분법 파일럿 코퍼스 배치(W2) — 결정론·LLM 0.

검증 축(elementary_addsub_batch·matrix_ops_batch 대칭):
  ① 단일 밴드(product-rule) 전건이 수용 게이트(Tier1 미분 평가 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑤ 산출물이 항상 `is_published=False`·`concept_tags` 관련 `problem_concepts_loaded=0`
     (개념 태깅 공백 — 모듈 docstring 참조. 가짜 태그로 위장하지 않았음을 확인).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.university_calc1_batch import run_university_calc1_batch
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.calculus_product_rule_skeleton_generator import (
    CalculusProductRuleSkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[CALC1-02-02]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.8,
    answer_format=None,
)


def test_batch_stores_band_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_university_calc1_batch(n=60, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"product-rule"}
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
        assert record["achievement_standard_codes"] == ["[CALC1-02-02]"]
        # 개념 태깅 공백(모듈 docstring) — 가짜 orphan-skip 태그 대신 정직하게 빈 목록.
        assert record["concepts"] == []


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_university_calc1_batch(n=60, out_path=first)
    run_university_calc1_batch(n=60, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 Tier1 미분 평가 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = CalculusProductRuleSkeletonGenerator()

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

    outcomes = [run_equivalent_generation(_SPEC, BrokenGenerator()) for _ in range(8)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(_SPEC, CalculusProductRuleSkeletonGenerator()) for _ in range(11)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 11
