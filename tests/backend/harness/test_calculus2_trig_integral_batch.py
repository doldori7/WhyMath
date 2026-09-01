"""미적분Ⅱ 적분법(삼각함수 정적분·넓이·속도와 거리) 파일럿 코퍼스 배치(W2 Phase4 #2) —
결정론·LLM 0.

검증 축(calculus1_integral_batch 대칭):
  ① 3밴드(trig_definite/trig_area/trig_distance) 전건이 수용 게이트(Tier1 SymPy `Integral`
     정적분 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_sampled`를 갖는다.
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ **밴드 간 problem_id 중복 0**.
  ⑤ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
  ⑥ 산출물이 항상 `is_published=False`.
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.calculus2_trig_integral_batch import (
    run_calculus2_trig_integral_batch,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.calculus2_trig_integral_skeleton_generator import (
    TRIG_AREA_STANDARD_CODE,
    TRIG_DEFINITE_STANDARD_CODE,
    TRIG_DISTANCE_STANDARD_CODE,
    Calculus2TrigIntegralSkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

_TRIG_DEFINITE_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({TRIG_DEFINITE_STANDARD_CODE}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.4,
    answer_format=None,
)
_TRIG_AREA_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({TRIG_AREA_STANDARD_CODE}),
    target_misconception_ids=frozenset(),
    difficulty_overall=3.3,
    answer_format=None,
)


def test_batch_stores_all_bands_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_calculus2_trig_integral_batch(
        trig_definite_n=30, trig_area_n=15, trig_distance_n=15, out_path=out
    )

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {"trig_definite", "trig_area", "trig_distance"}
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]
    assert report.total_stored == 60  # 30 + 15 + 15.

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    assert len({r["problem_id"] for r in records}) == len(records)  # 전건 고유.
    codes_seen = {r["achievement_standard_codes"][0] for r in records}
    assert codes_seen == {
        TRIG_DEFINITE_STANDARD_CODE,
        TRIG_AREA_STANDARD_CODE,
        TRIG_DISTANCE_STANDARD_CODE,
    }
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_SAMPLED.value
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"
        assert record["is_published"] is False


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_calculus2_trig_integral_batch(
        trig_definite_n=20, trig_area_n=10, trig_distance_n=10, out_path=first
    )
    run_calculus2_trig_integral_batch(
        trig_definite_n=20, trig_area_n=10, trig_distance_n=10, out_path=second
    )
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 Tier1 정적분 검산에서 거부된다."""

    class BrokenGenerator:
        def __init__(self) -> None:
            self._inner = Calculus2TrigIntegralSkeletonGenerator(kind="trig_definite")

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

    outcomes = [run_equivalent_generation(_TRIG_DEFINITE_SPEC, BrokenGenerator()) for _ in range(6)]
    assert [o.status for o in outcomes] == ["rejected_gate"] * 6
    assert any("Tier1" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = [
        run_equivalent_generation(
            _TRIG_AREA_SPEC, Calculus2TrigIntegralSkeletonGenerator(kind="trig_area")
        )
        for _ in range(8)
    ]
    assert [o.status for o in outcomes] == ["accepted"] * 8
