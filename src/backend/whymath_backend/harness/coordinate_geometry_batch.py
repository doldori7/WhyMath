"""좌표평면 — 두 점 사이의 거리·직선의 방정식 파일럿 코퍼스 배치 — W2 Phase 1 #3(결정론·LLM 0).

`quad_ineq_batch`·`sequence_sigma_batch` 형제. `PointDistanceSkeletonGenerator`([10공수2-01-01])
·`LineEquationSkeletonGenerator`([10공수2-01-02])로 2밴드를 생성 → 수용 게이트(`l3/verify_answer`
Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 신규 도메인(고1 도형의
방정식)의 첫 코퍼스다.

`run_equivalent_generation`을 `signature_index=None`으로 직접 호출한다 — 이 도메인은 서로 다른
좌표쌍이 같은 거리·같은 a+b를 내는 것이 정상이라(구조 dedup은 생성기 내부에서 원시 파라미터
튜플로 이미 수행) 오케스트레이터의 답-기준 구조 dedup을 거치면 정당한 재출현이 오탐 거부된다
(quad_ineq_batch와 동일 이유).

**검증 등급 각인**: `machine_sampled`(Tier1 산술 검산).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.coordinate_geometry_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.coordinate_geometry_skeleton_generator import (
    LineEquationSkeletonGenerator,
    PointDistanceSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_coordinate_geometry_batch"]

CORPUS_DIR_NAME = "problem_bank_coordinate_geometry_v0"
_DISTANCE_STANDARD_CODE = "[10공수2-01-01]"
_LINE_STANDARD_CODE = "[10공수2-01-02]"
_DISTANCE_SPEC_DIFFICULTY = 2.0
_LINE_SPEC_DIFFICULTY = 2.2
_DEFAULT_N = 200  # 밴드당 요청 수(풀 목표 260보다 작게 — 풀 소진 없이 안정적으로 채움).


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_coordinate_geometry_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """2밴드(distance/line) 배치 실행 — 생성(구조 키 풀)→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    distance_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_DISTANCE_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_DISTANCE_SPEC_DIFFICULTY,
        answer_format=None,
    )
    line_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_LINE_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_LINE_SPEC_DIFFICULTY,
        answer_format=None,
    )

    bands = [
        _run_band(
            name="distance",
            spec=distance_spec,
            generator=PointDistanceSkeletonGenerator(),
            n=n_per_band,
            sink=sink,
        ),
        _run_band(
            name="line",
            spec=line_spec,
            generator=LineEquationSkeletonGenerator(),
            n=n_per_band,
            sink=sink,
        ),
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
        prog="python -m whymath_backend.harness.coordinate_geometry_batch",
        description="좌표평면(두 점 거리·직선의 방정식) 파일럿 코퍼스 배치(2밴드·결정론·Tier1).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="밴드당 요청 수(기본 200).")
    parser.add_argument(
        "--out", default=None, help="출력 코퍼스 경로(기본 coordinate_geometry_v0)."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_coordinate_geometry_batch(
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
