"""초등 직육면체 부피·부피 단위·원주 파일럿 코퍼스 배치 — W2 Phase 3 #1(결정론·LLM 0).

`elementary_area_measure_batch`(S4-30, [6수03-12]·[6수03-17]) 형제. `RectangularPrismVolume
SkeletonGenerator`([6수03-19])·`VolumeUnitConversionSkeletonGenerator`([6수03-18])·
`CircleCircumferenceSkeletonGenerator`([6수03-15])로 3밴드를 생성 → 수용 게이트(`l3/verify_answer`
Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 세 성취기준의 첫 코퍼스다.

**검증 등급 각인**: `machine_sampled`(Tier1 산술 검산).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.elementary_volume_measure_batch [--volume-n N]
[--volume-unit-n N] [--circumference-n N] [--out PATH] [--dry-run]`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from whymath_backend.harness.problem_corpus_batch import (
    BandResult,
    CorpusBatchReport,
    JsonlCorpusSink,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.elementary_volume_measure_skeleton_generator import (
    CircleCircumferenceSkeletonGenerator,
    RectangularPrismVolumeSkeletonGenerator,
    VolumeUnitConversionSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_elementary_volume_measure_batch"]

CORPUS_DIR_NAME = "problem_bank_elementary_volume_measure_v0"
_VOLUME_STANDARD_CODE = "[6수03-19]"
_VOLUME_UNIT_STANDARD_CODE = "[6수03-18]"
_CIRCUMFERENCE_STANDARD_CODE = "[6수03-15]"
_VOLUME_SPEC_DIFFICULTY = 2.0
_VOLUME_UNIT_SPEC_DIFFICULTY = 1.8
_CIRCUMFERENCE_SPEC_DIFFICULTY = 2.1
# 밴드당 요청 수 — 부피는 넉넉한 풀(260), 단위환산·원주는 값 범위가 작다(각 50).
_DEFAULT_VOLUME_N = 200
_DEFAULT_VOLUME_UNIT_N = 50
_DEFAULT_CIRCUMFERENCE_N = 50


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_elementary_volume_measure_batch(
    *,
    volume_n: int = _DEFAULT_VOLUME_N,
    volume_unit_n: int = _DEFAULT_VOLUME_UNIT_N,
    circumference_n: int = _DEFAULT_CIRCUMFERENCE_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """3밴드(volume/volume-unit/circumference) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    volume_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_VOLUME_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_VOLUME_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="volume",
            spec=volume_spec,
            generator=RectangularPrismVolumeSkeletonGenerator(),
            n=volume_n,
            sink=sink,
        )
    )

    volume_unit_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_VOLUME_UNIT_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_VOLUME_UNIT_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="volume-unit",
            spec=volume_unit_spec,
            generator=VolumeUnitConversionSkeletonGenerator(),
            n=volume_unit_n,
            sink=sink,
        )
    )

    circumference_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_CIRCUMFERENCE_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_CIRCUMFERENCE_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="circumference",
            spec=circumference_spec,
            generator=CircleCircumferenceSkeletonGenerator(),
            n=circumference_n,
            sink=sink,
        )
    )

    total_stored = sum(b.stored for b in bands)
    written = sink.write(resolved_out) if write else None
    return CorpusBatchReport(
        bands=bands,
        total_requested=sum(b.requested for b in bands),
        total_stored=total_stored,
        written=written,
        out_path=str(resolved_out),
    )


def _run_band(
    *,
    name: str,
    spec: EquivalenceSpec,
    generator: object,
    n: int,
    sink: JsonlCorpusSink,
) -> BandResult:
    """단일 밴드 실행 — n회 시도·게이트 통과분만 적재·풀 소진은 정상 종료로 간주."""
    outcomes = [
        run_equivalent_generation(
            spec,
            generator,  # type: ignore[arg-type]
            store=sink,
            signature_index=None,
            verification_tier=VerificationTier.MACHINE_SAMPLED.value,
        )
        for _ in range(n)
    ]
    stored = 0
    produced = 0
    failures: list[str] = []
    for outcome in outcomes:
        if outcome.status == "generation_failed":
            continue  # 풀 소진 — 정상 종료 신호.
        produced += 1
        if outcome.status == "accepted_stored":
            stored += 1
        else:
            failures.extend(outcome.reasons or [f"status={outcome.status}"])
    return BandResult(name=name, requested=produced, stored=stored, failure_reasons=failures)


def main(argv: list[str] | None = None) -> int:
    """CLI — 파일럿 코퍼스 배치. 게이트 거부가 하나라도 있으면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.elementary_volume_measure_batch",
        description="초등 직육면체 부피·부피 단위·원주 파일럿 코퍼스 배치(3밴드·결정론).",
    )
    parser.add_argument(
        "--volume-n", type=int, default=_DEFAULT_VOLUME_N, help="부피 밴드 요청 수."
    )
    parser.add_argument(
        "--volume-unit-n", type=int, default=_DEFAULT_VOLUME_UNIT_N, help="부피 단위환산 요청 수."
    )
    parser.add_argument(
        "--circumference-n", type=int, default=_DEFAULT_CIRCUMFERENCE_N, help="원주 요청 수."
    )
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 volume_measure_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_elementary_volume_measure_batch(
        volume_n=args.volume_n,
        volume_unit_n=args.volume_unit_n,
        circumference_n=args.circumference_n,
        out_path=Path(args.out) if args.out else None,
        write=not args.dry_run,
    )
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    rejected = sum(len(b.failure_reasons) for b in report.bands)
    if rejected:
        print(f"게이트 거부 {rejected}건 — 저작 결함(조용한 통과 금지).", file=sys.stderr)
        return 1
    return 0 if report.total_stored > 0 else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
