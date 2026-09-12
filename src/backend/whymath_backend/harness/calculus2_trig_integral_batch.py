"""고등 미적분Ⅱ 적분법(삼각함수 정적분·넓이·속도와 거리) 파일럿 코퍼스 배치 — W2 Phase4 #2
(결정론·LLM 0).

`calculus1_integral_batch`(S4-45) 형제. `Calculus2TrigIntegralSkeletonGenerator`로 3밴드
(trig_definite→[12미적Ⅱ-03-01]·trig_area→[12미적Ⅱ-03-05]·trig_distance→[12미적Ⅱ-03-07])
를 생성 → 수용 게이트(`l3/verify_answer` Tier1 SymPy `Integral` 경유)·`JsonlCorpusSink`를
**재사용**해 파일럿 코퍼스를 적재한다. 세 성취기준의 첫 코퍼스다.

`kind` 필터 필수(형제 배치 관례 계승) — 미지정이면 세 밴드가 고정 시드 풀을 처음부터
재생해 같은 뼈대를 중복 방출한다. `kind`가 성취기준 코드도 결정하므로(형제 생성기들의
"kind→코드" 관례) 밴드별로 해당 코드의 `EquivalenceSpec`을 구성한다.

**검증 등급 각인**: `machine_sampled`(Tier1 SymPy 정적분 평가 검산).

밴드당 요청 수는 각 kind의 실제 풀 크기(trig_definite 100·trig_area/trig_distance 15)를
그대로 상한으로 쓴다 — 형제 생성기와 달리 area/distance 풀이 작아([0,π] 제약) 절삭할
여지가 없다.

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.calculus2_trig_integral_batch
[--trig-definite-n N] [--trig-area-n N] [--trig-distance-n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.calculus2_trig_integral_skeleton_generator import (
    TRIG_AREA_STANDARD_CODE,
    TRIG_DEFINITE_STANDARD_CODE,
    TRIG_DISTANCE_STANDARD_CODE,
    Calculus2TrigIntegralKind,
    Calculus2TrigIntegralSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_calculus2_trig_integral_batch"]

CORPUS_DIR_NAME = "problem_bank_calculus2_trig_integral_v0"
_DEFAULT_TRIG_DEFINITE_N = 100
_DEFAULT_TRIG_AREA_N = 15
_DEFAULT_TRIG_DISTANCE_N = 15

_KIND_TO_CODE: dict[Calculus2TrigIntegralKind, str] = {
    "trig_definite": TRIG_DEFINITE_STANDARD_CODE,
    "trig_area": TRIG_AREA_STANDARD_CODE,
    "trig_distance": TRIG_DISTANCE_STANDARD_CODE,
}
_DIFFICULTY_BY_KIND: dict[Calculus2TrigIntegralKind, float] = {
    "trig_definite": 3.4,
    "trig_area": 3.3,
    "trig_distance": 3.5,
}


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_calculus2_trig_integral_batch(
    *,
    trig_definite_n: int = _DEFAULT_TRIG_DEFINITE_N,
    trig_area_n: int = _DEFAULT_TRIG_AREA_N,
    trig_distance_n: int = _DEFAULT_TRIG_DISTANCE_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """3밴드(trig_definite/trig_area/trig_distance) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    plan: tuple[tuple[Calculus2TrigIntegralKind, int], ...] = (
        ("trig_definite", trig_definite_n),
        ("trig_area", trig_area_n),
        ("trig_distance", trig_distance_n),
    )
    bands = [
        _run_band(
            name=kind,
            spec=EquivalenceSpec(
                achievement_standard_codes=frozenset({_KIND_TO_CODE[kind]}),
                target_misconception_ids=frozenset(),
                difficulty_overall=_DIFFICULTY_BY_KIND[kind],
                answer_format=None,
            ),
            generator=Calculus2TrigIntegralSkeletonGenerator(kind=kind),
            n=n,
            sink=sink,
        )
        for kind, n in plan
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
        prog="python -m whymath_backend.harness.calculus2_trig_integral_batch",
        description="미적분Ⅱ 적분법(삼각함수 정적분·넓이·속도와거리) 파일럿 코퍼스 배치"
        "(3밴드·결정론).",
    )
    parser.add_argument(
        "--trig-definite-n",
        type=int,
        default=_DEFAULT_TRIG_DEFINITE_N,
        help="trig_definite 밴드 요청 수.",
    )
    parser.add_argument(
        "--trig-area-n", type=int, default=_DEFAULT_TRIG_AREA_N, help="trig_area 밴드 요청 수."
    )
    parser.add_argument(
        "--trig-distance-n",
        type=int,
        default=_DEFAULT_TRIG_DISTANCE_N,
        help="trig_distance 밴드 요청 수.",
    )
    parser.add_argument(
        "--out", default=None, help="출력 코퍼스 경로(기본 calculus2_trig_integral_v0)."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_calculus2_trig_integral_batch(
        trig_definite_n=args.trig_definite_n,
        trig_area_n=args.trig_area_n,
        trig_distance_n=args.trig_distance_n,
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
