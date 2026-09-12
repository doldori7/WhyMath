"""고등 미적분Ⅱ 몫의 미분법 파일럿 코퍼스 배치(W2 Phase2 #5·최종) — 결정론·LLM 0.

검증 축(university_calc1_chain_quotient_batch·discrete_ev_batch 대칭):
  ① 단일 밴드가 수용 게이트(Tier1 SymPy 미분 평가 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ 전건 `problem_id` 고유.
  ⑤ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑥ 산출물이 항상 `is_published=False`이고 `concepts`가 정상 태깅됨(대학 축과 대비 —
     이 K-12 개념은 legacy 437 공간에 실존).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.highschool_quotient_rule_batch import (
    run_highschool_quotient_rule_batch,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.highschool_quotient_rule_skeleton_generator import (
    HighschoolQuotientRuleSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[12미적Ⅱ-02-04]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.7,
    answer_format=None,
)


def test_batch_stores_all_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_highschool_quotient_rule_batch(n=200, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"quotient-rule"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 200

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    assert len({r["problem_id"] for r in records}) == len(records)  # 전건 고유.
    codes_seen = {r["achievement_standard_codes"][0] for r in records}
    assert codes_seen == {"[12미적Ⅱ-02-04]"}
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False
        assert record["concepts"] == [
            {"concept_src_id": "H:12미적Ⅱ02-04", "role": "PRIMARY", "relevance": 0.95}
        ]


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_highschool_quotient_rule_batch(n=120, out_path=first)
    run_highschool_quotient_rule_batch(n=120, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 Tier1 미분 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = HighschoolQuotientRuleSkeletonGenerator()

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
    gen = HighschoolQuotientRuleSkeletonGenerator()
    outcomes = [run_equivalent_generation(_SPEC, gen) for _ in range(11)]
    assert [o.status for o in outcomes] == ["accepted"] * 11
