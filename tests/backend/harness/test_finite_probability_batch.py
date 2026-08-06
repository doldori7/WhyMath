"""유한 확률 파일럿 코퍼스 배치(S4-13 ①③) — 결정론·LLM 0.

검증 축:
  ① 4밴드 전건이 수용 게이트(전수 열거 검산)를 통과해 적재된다.
  ② 산출 JSONL의 모든 레코드가 `verify.verification_tier=machine_exhaustive`를 갖는다
     (L1 `ProblemVerifyMeta` 정식 필드(S4-17)·코퍼스가 스스로 "무엇이 증명됐는가"를 말한다).
  ③ 재실행 바이트 결정론 — 같은 입력이면 같은 파일.
  ④ 검산 재료 없는 등급은 구조적으로 나올 수 없다 — `verification_tier`는 `ProblemVerifyMeta`의
     `conditions`/`answer_map`과 같은 저장 시점에 함께 조립되므로(S4-17 네이티브 각인) 등급만
     떠 있는 레코드를 만드는 별도 후처리 경로 자체가 없다.
  ⑤ **저작 결함 변별력**: 정답을 틀리게 만든 생성기는 게이트에서 거부된다(적재 0).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.finite_probability_batch import run_finite_probability_batch
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.finite_probability_skeleton_generator import (
    FiniteProbabilitySkeletonGenerator,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l3.verification_tier import VerificationTier

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[12확통02-01]"}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.5,
    answer_format=None,
)


def test_batch_stores_all_bands_and_stamps_tier(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_finite_probability_batch(n_per_band=20, out_path=out)

    assert report.total_stored == report.written and report.written is not None
    assert {b.name for b in report.bands} == {
        "dice-sum-prob",
        "coin-heads-prob",
        "marble-all-red-prob",
        "dice-sum-count",
    }
    assert all(not b.failure_reasons for b in report.bands), [
        b.failure_reasons for b in report.bands
    ]

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == report.written
    for record in records:
        verify = record["verify"]
        assert verify["verification_tier"] == VerificationTier.MACHINE_EXHAUSTIVE.value
        assert verify["answer_kind"] in {"finite_probability", "finite_count"}
        assert verify["conditions"].startswith("space=")
        # 저작권 구조 봉인 — 자체생성 고정(본문 복제 경로 원천 차단).
        assert record["source_type"] == "자체생성"
        assert record["license"] == "WHYMATH_GENERATED"


def test_batch_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    run_finite_probability_batch(n_per_band=20, out_path=first)
    run_finite_probability_batch(n_per_band=20, out_path=second)
    assert first.read_bytes() == second.read_bytes()


def test_gate_rejects_authoring_defect() -> None:
    """**변별력 실측** — 정답을 1 틀리게 만든 생성기는 전수 열거 검산에서 거부된다.

    저작 경로(닫힌 조합 공식)와 검산 경로(전수 열거)가 다른 원리이므로, 저작 쪽 오류가
    검산 쪽에서 재현되지 않고 드러난다(생성자≠검증자의 실측 확인).
    """

    class BrokenGenerator:
        """정답 문자열만 오염시키는 생성기 — 그 밖은 정상 뼈대."""

        def __init__(self) -> None:
            self._inner = FiniteProbabilitySkeletonGenerator(band="dice-sum-count")

        def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
            candidate = self._inner.generate(spec)
            if candidate is None:
                return None
            broken = candidate.problem.model_copy(
                update={"answer": str(int(candidate.problem.answer) + 1)}
            )
            return candidate.model_copy(update={"problem": broken})

    count_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({"[12확통01-01]"}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.5,
        answer_format=None,
    )
    outcomes = run_batch(count_spec, BrokenGenerator(), 8)
    assert [o.status for o in outcomes] == ["rejected_gate"] * 8
    assert any("전수 열거" in reason for o in outcomes for reason in o.reasons)


def test_healthy_generator_is_accepted_for_contrast() -> None:
    """대조군 — 같은 밴드의 정상 생성기는 전건 통과(위 거부가 무차별 거부가 아님)."""
    outcomes = run_batch(_SPEC, FiniteProbabilitySkeletonGenerator(band="dice-sum-prob"), 11)
    assert [o.status for o in outcomes] == ["accepted"] * 11
