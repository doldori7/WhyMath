"""고등 표본평균의 평균·분산 파일럿 코퍼스 배치 — W2 Phase 3 #4(순수 결정론·LLM 0).

`binomial_distribution_batch`(S4-34) 형제. `SampleMeanDistributionSkeletonGenerator`로
2밴드(mean/variance·`[12확통03-06]`)를 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·
`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 이 성취기준의 첫 코퍼스다.

`kind` 필터 필수(형제 배치 관례 계승) — 미지정이면 두 밴드가 고정 시드 풀을 처음부터
재생해 같은 뼈대를 중복 방출한다. `run_equivalent_generation`을 `signature_index=None`으로
호출한다 — 형제 배치와 동일 이유(구조 dedup이 조건식을 해값으로 정규화하므로 서로 다른
(mu, sigma_sq, n) 조합이 같은 평균/분산을 내면 오탐).

**검증 등급 각인**: `machine_sampled`(Tier1 유리수 산술 검산).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.sample_mean_distribution_batch [--n N] [--out PATH]
[--dry-run]`
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
from whymath_backend.l3.equivalent.sample_mean_distribution_skeleton_generator import (
    SampleMeanDistributionSkeletonGenerator,
    SampleMeanStatKind,
)
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_sample_mean_distribution_batch"]

CORPUS_DIR_NAME = "problem_bank_sample_mean_distribution_v0"
_STANDARD_CODE = "[12확통03-06]"
_SPEC_DIFFICULTY = 2.85  # mean(2.6)/variance(3.1) 평균과 정합(허용격차 0.5 이내).
_DEFAULT_N = 200  # 밴드당 요청 수(풀 17400보다 훨씬 작게 절삭).


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_sample_mean_distribution_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """2밴드(mean/variance) 배치 실행 — 생성(구조 키 풀)→게이트(Tier1 유리수 검산)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_SPEC_DIFFICULTY,
        answer_format=None,
    )

    kinds: tuple[SampleMeanStatKind, ...] = ("mean", "variance")
    bands = [
        _run_band(
            name=kind,
            spec=spec,
            generator=SampleMeanDistributionSkeletonGenerator(kind=kind),
            n=n_per_band,
            sink=sink,
        )
        for kind in kinds
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
        prog="python -m whymath_backend.harness.sample_mean_distribution_batch",
        description="표본평균의 평균·분산 파일럿 코퍼스 배치(2밴드·결정론·Tier1 유리수 검산).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="밴드당 요청 수(기본 200).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 sample_mean_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_sample_mean_distribution_batch(
        n_per_band=args.n,
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
