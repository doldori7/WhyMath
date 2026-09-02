"""고등 일반각과 호도법(도-라디안 변환) 파일럿 코퍼스 배치 — W2 Phase4 #5(결정론·LLM 0).

`RadianConversionSkeletonGenerator`로 2밴드(deg_to_rad·rad_to_deg)를 생성 → 수용
게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를
적재한다. `[12대수02-01]`의 첫 코퍼스다(S4-47·S4-48 다항식 웨이브의 연속).

두 밴드는 **같은 성취기준 코드를 공유**한다(measurement_unit_conversion 배치 관례
계승) — `kind` 필터가 방향(도→라디안/라디안→도)만 가른다.

**검증 등급 각인**: `machine_sampled`(Tier1 수치 검산 — SymPy가 `pi`를 상수로 직접
평가, 자유변수 없는 경로).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.radian_conversion_batch [--deg-to-rad-n N]
[--rad-to-deg-n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.equivalent.radian_conversion_skeleton_generator import (
    RADIAN_STANDARD_CODE,
    RadianConversionSkeletonGenerator,
)
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_radian_conversion_batch"]

CORPUS_DIR_NAME = "problem_bank_radian_conversion_v0"
_DEFAULT_DEG_TO_RAD_N = 72
_DEFAULT_RAD_TO_DEG_N = 72

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({RADIAN_STANDARD_CODE}),
    target_misconception_ids=frozenset(),
    difficulty_overall=2.0,
    answer_format=None,
)


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_radian_conversion_batch(
    *,
    deg_to_rad_n: int = _DEFAULT_DEG_TO_RAD_N,
    rad_to_deg_n: int = _DEFAULT_RAD_TO_DEG_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """2밴드(deg_to_rad/rad_to_deg) 배치 실행 — 생성→게이트→적재(단일 코드 공유)."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    plan: tuple[tuple[str, str, int], ...] = (
        ("deg_to_rad", "radian-deg_to_rad", deg_to_rad_n),
        ("rad_to_deg", "radian-rad_to_deg", rad_to_deg_n),
    )
    bands = [
        _run_band(
            name=name,
            generator=RadianConversionSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
            n=n,
            sink=sink,
        )
        for kind, name, n in plan
    ]

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
    generator: object,
    n: int,
    sink: JsonlCorpusSink,
) -> BandResult:
    """단일 밴드 실행 — n회 시도·게이트 통과분만 적재·풀 소진은 정상 종료로 간주."""
    outcomes = [
        run_equivalent_generation(
            _SPEC,
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
        prog="python -m whymath_backend.harness.radian_conversion_batch",
        description="고등 일반각과 호도법(도-라디안 변환) 파일럿 코퍼스 배치(2밴드·결정론).",
    )
    parser.add_argument(
        "--deg-to-rad-n", type=int, default=_DEFAULT_DEG_TO_RAD_N, help="deg_to_rad 밴드 요청 수."
    )
    parser.add_argument(
        "--rad-to-deg-n", type=int, default=_DEFAULT_RAD_TO_DEG_N, help="rad_to_deg 밴드 요청 수."
    )
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 radian_conversion_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_radian_conversion_batch(
        deg_to_rad_n=args.deg_to_rad_n,
        rad_to_deg_n=args.rad_to_deg_n,
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
