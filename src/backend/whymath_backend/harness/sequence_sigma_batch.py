"""수열의 합 — Σ 성질·여러 가지 수열의 합 파일럿 코퍼스 배치 — W2 Phase 1 #2(결정론·LLM 0).

`quad_ineq_batch`·`elementary_addsub_batch`·`matrix_ops_batch` 형제. `SigmaLinearitySkeleton
Generator`([12대수03-04])·`PowerSumSkeletonGenerator`([12대수03-05], kind=square/cube 2밴드)
로 3밴드를 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`를 **재사용**해
파일럿 코퍼스를 적재한다. 두 성취기준의 첫 코퍼스다.

`kind` 필터 필수(`quad_ineq_batch`의 `direction` 관례 계승) — 미지정이면 두 밴드가 고정 시드
풀을 처음부터 재생해 같은 뼈대를 중복 방출한다(`elementary_addsub_batch` 2026-08-05 사고).

`run_equivalent_generation`을 `signature_index=None`으로 직접 호출한다 — 선행 생성기들과
동일 이유(구조 dedup이 조건식을 해값으로 정규화하므로 서로 다른 뼈대가 같은 합을 내면
판박이로 오탐한다).

**검증 등급 각인**: `machine_sampled`(Tier1 산술 검산).

[12대수03-07](수학적 귀납법)은 이 배치에서 의도적으로 다루지 않는다 — 증명 서술형이라
SymPy Tier1 산술 검산 범위 밖(검증 권위 부재, S4-28 스코프 명시 제외).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.sequence_sigma_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.sequence_sigma_skeleton_generator import (
    PowerSumKind,
    PowerSumSkeletonGenerator,
    SigmaLinearitySkeletonGenerator,
)
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_sequence_sigma_batch"]

CORPUS_DIR_NAME = "problem_bank_sequence_sigma_v0"
_SIGMA_STANDARD_CODE = "[12대수03-04]"
_POWER_STANDARD_CODE = "[12대수03-05]"
_SIGMA_SPEC_DIFFICULTY = 2.0
_POWER_SPEC_DIFFICULTY = 2.1
# 밴드당 요청 수 — sigma는 풀 290+로 넉넉해 100, power는 풀이 작아(square 18·cube 14) 30으로
# 자연 절삭(요청>풀이면 풀 크기로 수렴 — quad_ineq 관례).
_DEFAULT_SIGMA_N = 100
_DEFAULT_POWER_N = 30


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_sequence_sigma_batch(
    *,
    sigma_n: int = _DEFAULT_SIGMA_N,
    power_n: int = _DEFAULT_POWER_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """3밴드(sigma-linear/power-square/power-cube) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    sigma_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_SIGMA_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_SIGMA_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="sigma-linear",
            spec=sigma_spec,
            generator=SigmaLinearitySkeletonGenerator(),
            n=sigma_n,
            sink=sink,
        )
    )

    power_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_POWER_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_POWER_SPEC_DIFFICULTY,
        answer_format=None,
    )
    power_kinds: tuple[PowerSumKind, ...] = ("square", "cube")
    for kind in power_kinds:
        bands.append(
            _run_band(
                name=f"power-{kind}",
                spec=power_spec,
                generator=PowerSumSkeletonGenerator(kind=kind),
                n=power_n,
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
        prog="python -m whymath_backend.harness.sequence_sigma_batch",
        description="수열의 합(Σ 성질·거듭제곱 합) 파일럿 코퍼스 배치(3밴드·결정론·Tier1 검산).",
    )
    parser.add_argument(
        "--sigma-n", type=int, default=_DEFAULT_SIGMA_N, help="sigma-linear 요청 수."
    )
    parser.add_argument(
        "--power-n", type=int, default=_DEFAULT_POWER_N, help="power 밴드당 요청 수."
    )
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 sequence_sigma_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_sequence_sigma_batch(
        sigma_n=args.sigma_n,
        power_n=args.power_n,
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
