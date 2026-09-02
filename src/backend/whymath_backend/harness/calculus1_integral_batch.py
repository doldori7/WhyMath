"""고등 미적분Ⅰ 적분(부정적분·정적분·넓이·속도와 거리) 파일럿 코퍼스 배치 — W2 Phase4 #1
(결정론·LLM 0).

`combination_binomial_batch`(S4-41) 형제. `Calculus1IntegralSkeletonGenerator`로 4밴드
(antiderivative→[12미적Ⅰ-03-02]·definite→[12미적Ⅰ-03-04]·area→[12미적Ⅰ-03-05]·
distance→[12미적Ⅰ-03-06])를 생성 → 수용 게이트(`l3/verify_answer` Tier1 SymPy `Integral`
경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 네 성취기준의 첫 코퍼스다.

`kind` 필터 필수(형제 배치 관례 계승) — 미지정이면 네 밴드가 고정 시드 풀을 처음부터
재생해 같은 뼈대를 중복 방출한다. `kind`가 성취기준 코드도 결정하므로(gcd_lcm·
conic_section_focus·measurement_unit_conversion 생성기의 "kind→코드" 관례) 밴드별로
해당 코드의 `EquivalenceSpec`을 구성한다.

**검증 등급 각인**: `machine_sampled`(Tier1 SymPy 정적분 평가 검산).

**성능 메모**: `Integral` 심볼릭 평가가 형제 생성기들의 산술/유리수 검증보다 느리다(스파이크
실측 ~0.4초/건) — 밴드당 기본 요청 수를 100으로 낮춰 배치 총 소요를 통제한다(풀 목표
300보다 작게 절삭).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.calculus1_integral_batch [--n-per-band N] [--out PATH]
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
from whymath_backend.l3.equivalent.calculus1_integral_skeleton_generator import (
    ANTIDERIVATIVE_STANDARD_CODE,
    AREA_STANDARD_CODE,
    DEFINITE_STANDARD_CODE,
    DISTANCE_STANDARD_CODE,
    Calculus1IntegralKind,
    Calculus1IntegralSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_calculus1_integral_batch"]

CORPUS_DIR_NAME = "problem_bank_calculus1_integral_v0"
_DEFAULT_N_PER_BAND = 100  # 풀 목표 300보다 작게 — Integral 검증 비용 고려한 통제.

_KIND_TO_CODE: dict[Calculus1IntegralKind, str] = {
    "antiderivative": ANTIDERIVATIVE_STANDARD_CODE,
    "definite": DEFINITE_STANDARD_CODE,
    "area": AREA_STANDARD_CODE,
    "distance": DISTANCE_STANDARD_CODE,
}
_DIFFICULTY_BY_KIND: dict[Calculus1IntegralKind, float] = {
    "antiderivative": 3.3,
    "definite": 3.0,
    "area": 3.1,
    "distance": 3.2,
}


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_calculus1_integral_batch(
    *, n_per_band: int = _DEFAULT_N_PER_BAND, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """4밴드(antiderivative/definite/area/distance) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    kinds: tuple[Calculus1IntegralKind, ...] = ("antiderivative", "definite", "area", "distance")
    bands = [
        _run_band(
            name=kind,
            spec=EquivalenceSpec(
                achievement_standard_codes=frozenset({_KIND_TO_CODE[kind]}),
                target_misconception_ids=frozenset(),
                difficulty_overall=_DIFFICULTY_BY_KIND[kind],
                answer_format=None,
            ),
            generator=Calculus1IntegralSkeletonGenerator(kind=kind),
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
        prog="python -m whymath_backend.harness.calculus1_integral_batch",
        description="미적분Ⅰ 적분(부정적분·정적분·넓이·속도와거리) 파일럿 코퍼스 배치"
        "(4밴드·결정론).",
    )
    parser.add_argument(
        "--n-per-band", type=int, default=_DEFAULT_N_PER_BAND, help="밴드당 요청 수(기본 100)."
    )
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 calculus1_integral_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_calculus1_integral_batch(
        n_per_band=args.n_per_band,
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
