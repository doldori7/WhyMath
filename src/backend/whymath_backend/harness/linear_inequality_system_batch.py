"""고등 연립일차부등식(미지수 1개) 파일럿 코퍼스 배치 — W2 Phase4 #7(결정론·LLM 0).

`LinearInequalitySystemSkeletonGenerator`로 2밴드(gongsu_sysineq→[10공수1-02-09]·
kisu_sysineq→[10기수1-02-07])를 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·
`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 두 성취기준의 첫 코퍼스다
(polynomial_factoring_batch·S4-48의 형제·연속).

`kind` 필터 필수(polynomial_factoring·polynomial_arithmetic 배치 관례 계승) —
미지정이면 두 밴드가 고정 시드 풀을 처음부터 재생해 같은 뼈대를 중복 방출한다. `kind`가
성취기준 코드도 결정하므로(1 kind = 1 코드) 밴드별로 해당 코드의 `EquivalenceSpec`을
구성한다.

**검증 등급 각인**: `machine_sampled`(Tier1 정수 산술 검산 — 경계 부등식의 등식 경계
재확인 설계로 SymPy 전개 불요).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.linear_inequality_system_batch [--gongsu-n N]
[--kisu-n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.linear_inequality_system_skeleton_generator import (
    GONGSU_SYSINEQ_STANDARD_CODE,
    KISU_SYSINEQ_STANDARD_CODE,
    LinearInequalitySystemSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_linear_inequality_system_batch"]

CORPUS_DIR_NAME = "problem_bank_linear_inequality_system_v0"
_DEFAULT_GONGSU_N = 300
_DEFAULT_KISU_N = 300


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_linear_inequality_system_batch(
    *,
    gongsu_n: int = _DEFAULT_GONGSU_N,
    kisu_n: int = _DEFAULT_KISU_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """2밴드(gongsu_sysineq/kisu_sysineq) 배치 실행 — 생성→게이트→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    plan: tuple[tuple[str, str, str, int], ...] = (
        ("gongsu_sysineq", GONGSU_SYSINEQ_STANDARD_CODE, "sysineq-gongsu", gongsu_n),
        ("kisu_sysineq", KISU_SYSINEQ_STANDARD_CODE, "sysineq-kisu", kisu_n),
    )
    bands = [
        _run_band(
            name=name,
            spec=EquivalenceSpec(
                achievement_standard_codes=frozenset({code}),
                target_misconception_ids=frozenset(),
                difficulty_overall=2.3,
                answer_format=None,
            ),
            generator=LinearInequalitySystemSkeletonGenerator(kind=kind),  # type: ignore[arg-type]
            n=n,
            sink=sink,
        )
        for kind, code, name, n in plan
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
        prog="python -m whymath_backend.harness.linear_inequality_system_batch",
        description="고등 연립일차부등식(미지수 1개) 파일럿 코퍼스 배치(2밴드·결정론).",
    )
    parser.add_argument(
        "--gongsu-n", type=int, default=_DEFAULT_GONGSU_N, help="gongsu_sysineq 밴드 요청 수."
    )
    parser.add_argument(
        "--kisu-n", type=int, default=_DEFAULT_KISU_N, help="kisu_sysineq 밴드 요청 수."
    )
    parser.add_argument(
        "--out", default=None, help="출력 코퍼스 경로(기본 linear_inequality_system_v0)."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_linear_inequality_system_batch(
        gongsu_n=args.gongsu_n,
        kisu_n=args.kisu_n,
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
