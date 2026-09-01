"""초등 두 자리 수 덧셈·뺄셈 파일럿 코퍼스 배치(W2) — 결정론·LLM 0.

검증 축:
  ① 2밴드(덧셈·뺄셈) 전건이 수용 게이트(Tier1 산술 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑤ `run_batch`의 답값-기반 오탐 dedup을 우회했다는 실측 회귀 봉인 — 같은 답을 내는 서로
     다른 (a,b) 조합이 둘 다 저장된다(finite_probability_batch 정신·다른 증상 동일 처방).
  ⑥ 산출물이 항상 `is_published=False`(AI 검수 게이트는 이 환경 밖 — 모듈 docstring).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.elementary_addsub_batch import run_elementary_addsub_batch
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.elementary_addsub_skeleton_generator import (
    ElementaryAddSubSkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[2수01-06]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=1.3,
    answer_format=None,
)


def test_batch_stores_all_bands_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_elementary_addsub_batch(n_per_band=40, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"add", "subtract"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 80  # 40×2밴드, 오탐 dedup 없음(모듈 docstring ⑤).

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    # 2026-08-05 실측 사고 회귀 봉인: operation 필터 없이 밴드별 인스턴스를 새로 만들면 둘 다
    # 고정 시드 풀을 처음부터 재생해 *같은* 뼈대가 두 밴드에서 중복 방출됐다(200개가 두 번씩
    # 400개로 잘못 저장됨). 밴드 간 problem_id가 겹치지 않아야 그 함정에 다시 빠지지 않은 것.
    assert len({r["problem_id"] for r in records}) == len(records)
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False
        assert record["achievement_standard_codes"] == ["[2수01-06]"]


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_elementary_addsub_batch(n_per_band=40, out_path=first)
    run_elementary_addsub_batch(n_per_band=40, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_same_answer_different_operands_both_stored(tmp_path: Path) -> None:
    """56-20=36과 53-17=36처럼 같은 답·다른 조합이 둘 다 저장된다(run_batch 우회 회귀 봉인).

    `run_batch`의 signature_index 경유였다면 answer=36 뼈대 중 하나만 남고 나머지는
    'rejected_duplicate'로 잘렸을 것이다(2026-08-05 실측 — 모듈 docstring 참조).
    """
    out = tmp_path / "problems.jsonl"
    run_elementary_addsub_batch(n_per_band=150, out_path=out)
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    answers = [int(r["answer"]) for r in records if r["question_format"] == "단답형"]
    # 답값 종류 수가 저장 문항 수보다 뚜렷이 적다 — 같은 답을 공유하는 서로 다른 문항이 실존.
    assert len(set(answers)) < len(answers)


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 Tier1 산술 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = ElementaryAddSubSkeletonGenerator()

        def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
            candidate = self._inner.generate(spec)
            if candidate is None:
                return None
            broken = candidate.problem.model_copy(
                update={"answer": str(int(candidate.problem.answer) + 1)}
            )
            return candidate.model_copy(
                update={"problem": broken, "answer_map": {"x": broken.answer}}
            )

    outcomes = [run_equivalent_generation(_SPEC, BrokenGenerator()) for _ in range(8)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(_SPEC, ElementaryAddSubSkeletonGenerator()) for _ in range(11)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 11
