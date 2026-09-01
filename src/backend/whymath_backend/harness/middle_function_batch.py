"""중등 일차함수 함숫값 파일럿 코퍼스 배치 — W2 중등 축 착점(순수 결정론·LLM 0).

`elementary_addsub_batch`·`matrix_ops_batch`·`university_calc1_batch` 형제.
`LinearFunctionValueSkeletonGenerator`로 단일 변형(함숫값·`[9수02-14]`)을 생성 → 수용
게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를
적재한다. 중등 축 0커버 37개 중 첫 코퍼스다.

`run_equivalent_generation`을 `signature_index=None`으로 직접 호출한다 — 선행 세 생성기와
동일 이유(구조 dedup이 조건식을 풀어 *해값*으로 정규화하므로 서로 다른 (a,b,k) 조합이 같은
f(k) 값을 내면 판박이로 오탐한다). 단일 변형이라 밴드 분리(operation 필터)도 불요.

**검증 등급 각인**: `machine_sampled`(Tier1 대입 평가 검산 — `linear_function_value_
skeleton_generator` docstring의 "검증 설계" 참조).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.middle_function_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.linear_function_value_skeleton_generator import (
    LinearFunctionValueSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_middle_function_batch"]

CORPUS_DIR_NAME = "problem_bank_middle_function_v0"
_STANDARD_CODE = "[9수02-14]"
_SPEC_DIFFICULTY = 1.8  # 생성기가 못 박는 난이도(모든 후보 동일)와 정합(허용격차 0.5 이내).
_BAND_NAME = "function-value"
_DEFAULT_N = 200  # 풀 목표 300보다 작게 — 풀 소진 없이 안정적으로 채움.


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_middle_function_batch(
    *, n: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """단일 밴드(함숫값) 배치 실행 — 생성(시드 풀)→게이트(Tier1 대입 평가)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_SPEC_DIFFICULTY,
        answer_format=None,
    )
    seen: set[str] = set()
    generator = LinearFunctionValueSkeletonGenerator(skip_conditions=seen)
    outcomes = [
        run_equivalent_generation(
            spec,
            generator,
            store=sink,
            signature_index=None,
            verification_tier=VerificationTier.MACHINE_SAMPLED.value,
        )
        for _ in range(n)
    ]

    stored = 0
    produced = 0  # 생성기가 실제로 후보를 낸 회차 수(풀 소진 이후 회차는 제외).
    failures: list[str] = []
    for outcome in outcomes:
        if outcome.status == "generation_failed":
            continue  # 풀 소진은 정상 종료 신호 — 요청 수를 풀 크기로 자연 절삭.
        produced += 1
        candidate = outcome.candidate
        if outcome.status == "accepted_stored":
            stored += 1
            if candidate is not None:
                conditions = candidate.conditions
                seen.add(conditions if isinstance(conditions, str) else str(conditions))
        else:
            failures.extend(outcome.reasons or [f"status={outcome.status}"])
    bands = [
        BandResult(name=_BAND_NAME, requested=produced, stored=stored, failure_reasons=failures)
    ]

    written = sink.write(resolved_out) if write else None
    return CorpusBatchReport(
        bands=bands,
        total_requested=produced,
        total_stored=stored,
        written=written,
        out_path=str(resolved_out),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI — 파일럿 코퍼스 배치. 게이트 거부가 하나라도 있으면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.middle_function_batch",
        description="중등 일차함수 함숫값 파일럿 코퍼스 배치(결정론·Tier1 대입 검산).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="요청 수(기본 200).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 middle_function_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_middle_function_batch(
        n=args.n,
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
