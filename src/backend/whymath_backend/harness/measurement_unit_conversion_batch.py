"""초등 길이·들이·무게 단위 관계 파일럿 코퍼스 배치 — W2 Phase 3 #5(결정론·LLM 0).

`elementary_area_measure_batch`(S4-30) 형제. `MeasurementUnitConversionSkeletonGenerator`
로 4밴드(mm_to_cm/km_to_m→[4수03-16]·L_to_mL→[4수03-18]·kg_to_g→[4수03-21])를 생성 →
수용 게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를
적재한다. 세 성취기준의 첫 코퍼스다.

`pair` 필터 필수(형제 넓이 환산 배치 관례 계승) — 미지정이면 네 밴드가 고정 시드 풀을
처음부터 재생해 같은 뼈대를 중복 방출한다. `pair`가 성취기준 코드도 결정하므로(gcd_lcm·
conic_section_focus 생성기의 "kind→코드" 관례) 밴드별로 해당 코드의 `EquivalenceSpec`을
구성한다.

**검증 등급 각인**: `machine_sampled`(Tier1 산술 검산).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.measurement_unit_conversion_batch [--mm-cm-n N]
[--km-m-n N] [--l-ml-n N] [--kg-g-n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.measurement_unit_conversion_skeleton_generator import (
    LENGTH_STANDARD_CODE,
    MASS_STANDARD_CODE,
    VOLUME_STANDARD_CODE,
    MeasurementUnitConversionSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_measurement_unit_conversion_batch"]

CORPUS_DIR_NAME = "problem_bank_measurement_unit_conversion_v0"
_DEFAULT_MM_CM_N = 100
_DEFAULT_KM_M_N = 20
_DEFAULT_L_ML_N = 30
_DEFAULT_KG_G_N = 30


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_measurement_unit_conversion_batch(
    *,
    mm_cm_n: int = _DEFAULT_MM_CM_N,
    km_m_n: int = _DEFAULT_KM_M_N,
    l_ml_n: int = _DEFAULT_L_ML_N,
    kg_g_n: int = _DEFAULT_KG_G_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """4밴드(mm_to_cm/km_to_m/L_to_mL/kg_to_g) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()

    plan: tuple[tuple[str, str, str, int], ...] = (
        ("mm_to_cm", LENGTH_STANDARD_CODE, "conversion-mm_to_cm", mm_cm_n),
        ("km_to_m", LENGTH_STANDARD_CODE, "conversion-km_to_m", km_m_n),
        ("L_to_mL", VOLUME_STANDARD_CODE, "conversion-L_to_mL", l_ml_n),
        ("kg_to_g", MASS_STANDARD_CODE, "conversion-kg_to_g", kg_g_n),
    )
    bands = [
        _run_band(
            name=name,
            spec=EquivalenceSpec(
                achievement_standard_codes=frozenset({code}),
                target_misconception_ids=frozenset(),
                difficulty_overall=1.9,
                answer_format=None,
            ),
            generator=MeasurementUnitConversionSkeletonGenerator(pair=pair),  # type: ignore[arg-type]
            n=n,
            sink=sink,
        )
        for pair, code, name, n in plan
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
        prog="python -m whymath_backend.harness.measurement_unit_conversion_batch",
        description="초등 길이·들이·무게 단위 관계 파일럿 코퍼스 배치(4밴드·결정론).",
    )
    parser.add_argument("--mm-cm-n", type=int, default=_DEFAULT_MM_CM_N, help="mm/cm 밴드 요청 수.")
    parser.add_argument("--km-m-n", type=int, default=_DEFAULT_KM_M_N, help="km/m 밴드 요청 수.")
    parser.add_argument("--l-ml-n", type=int, default=_DEFAULT_L_ML_N, help="L/mL 밴드 요청 수.")
    parser.add_argument("--kg-g-n", type=int, default=_DEFAULT_KG_G_N, help="kg/g 밴드 요청 수.")
    parser.add_argument(
        "--out", default=None, help="출력 코퍼스 경로(기본 measurement_unit_conversion_v0)."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_measurement_unit_conversion_batch(
        mm_cm_n=args.mm_cm_n,
        km_m_n=args.km_m_n,
        l_ml_n=args.l_ml_n,
        kg_g_n=args.kg_g_n,
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
