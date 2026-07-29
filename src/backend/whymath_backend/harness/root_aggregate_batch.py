"""근의 합/곱(Vieta) 킬러 문항 배치 — wedge 콘텐츠 적재(순수 결정론·LLM 0).

`problem_corpus_batch`(이차·미적분)의 킬러 형제다. `RootAggregateSkeletonGenerator`로
4 서브밴드(sum/product × 이차/삼차)를 생성 → 기존 오케스트레이터(`run_batch`)·수용 게이트
(`verify_root_aggregate` 경유)·`JsonlCorpusSink`를 **재사용**해 킬러 코퍼스를 적재한다.

기존 band 시스템(`run_corpus_batch`)은 `GeneratorVariant` 전용이라 근집계 생성기(다른
생성자 시그니처)와 맞지 않아 별도 배치로 둔다. 서브밴드별 signature_index는 분리한다
(합/곱/차수가 조건식 구조를 공유할 수 있으나 aggregate payload로 dedup은 이미 구분됨).

산출물은 v0(사람 검수 전) — 게이트 통과 ≠ 학생 노출(초인간 검증 강등전·표본 감사 경유).
CLI: `python -m whymath_backend.harness.root_aggregate_batch [--n N] [--out PATH] [--dry-run]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from whymath_backend.harness.problem_corpus_batch import (
    BandResult,
    CorpusBatchReport,
    JsonlCorpusSink,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l3.equivalent.root_aggregate_skeleton_generator import (
    AggregateKind,
    RootAggregateSkeletonGenerator,
)

__all__ = ["run_root_aggregate_batch"]

# 킬러 스펙 — 근집계 단답이라 distractor 없음(target_misconception_ids=∅), 난이도 4.0(킬러).
# S3-12 성취기준 재태깅(감사 확정): Vieta 문항에 종전 전밴드 [10공수1-02-02](판별식) 하드코딩은
# 계통 오귀속 — 정본 statement 대조로 이차형은 [10공수1-02-03](근과 계수의 관계), 삼차형은
# [10공수1-02-07](간단한 삼차·사차방정식)이 정위치다(차수별 분기).
_STANDARD_CODE_BY_DEGREE: dict[int, str] = {2: "[10공수1-02-03]", 3: "[10공수1-02-07]"}
_SPEC_DIFFICULTY = 4.0
_DEFAULT_N = 30  # 서브밴드당 기본 요청 수(4밴드 → 120문 목표)


def _default_out_path() -> Path:
    # src/backend/whymath_backend/harness/ → repo root 4단계.
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / "problem_bank_killer_v0" / "problems.jsonl"


# 서브밴드 정의(이름, 종류, 차수).
_SUBBANDS: tuple[tuple[str, AggregateKind, Literal[2, 3]], ...] = (
    ("vieta-sum-quad", "sum", 2),
    ("vieta-product-quad", "product", 2),
    ("vieta-sum-cubic", "sum", 3),
    ("vieta-product-cubic", "product", 3),
)


@dataclass(frozen=True, slots=True)
class _RunConfig:
    n_per_band: int
    out_path: Path
    write: bool


def run_root_aggregate_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """4 서브밴드 배치 실행 — 생성→게이트(verify_root_aggregate)→dedup→적재(순수 결정론)."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    for name, kind, degree in _SUBBANDS:
        spec = EquivalenceSpec(
            # 차수별 정위치 성취기준(S3-12) — 이차=근과 계수의 관계·삼차=삼차·사차방정식.
            achievement_standard_codes=frozenset({_STANDARD_CODE_BY_DEGREE[degree]}),
            target_misconception_ids=frozenset(),
            difficulty_overall=_SPEC_DIFFICULTY,
            answer_format=None,
        )
        index: set[str] = set()
        generator = RootAggregateSkeletonGenerator(kind=kind, degree=degree, skip_signatures=index)
        outcomes = run_batch(spec, generator, n_per_band, signature_index=index, store=sink)
        stored = sum(1 for o in outcomes if o.status == "accepted_stored")
        failures = [
            reason
            for outcome in outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(name=name, requested=n_per_band, stored=stored, failure_reasons=failures)
        )

    total_requested = sum(b.requested for b in bands)
    total_stored = sum(b.stored for b in bands)
    written = sink.write(resolved_out) if write else None
    return CorpusBatchReport(
        bands=bands,
        total_requested=total_requested,
        total_stored=total_stored,
        written=written,
        out_path=str(resolved_out),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI — 킬러 근집계 배치. 수율 미달(총 저장 < 요청)이면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.root_aggregate_batch",
        description="근의 합/곱(Vieta) 킬러 문항 배치 적재(4 서브밴드·결정론).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="서브밴드당 요청 수(기본 30).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 killer_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_root_aggregate_batch(
        n_per_band=args.n,
        out_path=Path(args.out) if args.out else None,
        write=not args.dry_run,
    )
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 0 if report.fulfilled else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
