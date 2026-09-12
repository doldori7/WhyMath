"""대학 미적분학 I 곱의 미분법 파일럿 코퍼스 배치 — W2 대학 축 최초 착점(순수 결정론·LLM 0).

`elementary_addsub_batch`·`matrix_ops_batch` 형제. `CalculusProductRuleSkeletonGenerator`로
단일 변형(곱의 미분법·`[CALC1-02-02]`)을 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·
`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 대학 축(W1 리포트 §1.5 — 문제은행
0건)의 첫 코퍼스다.

`run_equivalent_generation`을 `signature_index=None`으로 직접 호출한다 — 선행 두 생성기와
동일 이유(구조 dedup이 조건식을 풀어 *해값*으로 정규화하므로 서로 다른 다항식 조합이 같은
f'(k) 값을 내면 판박이로 오탐한다). 이 생성기는 단일 변형이라 밴드(operation) 분리가 필요
없다 — elementary/matrix가 겪은 "밴드별 인스턴스가 고정 시드 풀을 재생하는" 함정 자체가
발생하지 않는다(밴드가 1개뿐이므로 인스턴스도 1개).

**검증 등급 각인**: `machine_sampled`(Tier1 SymPy 미분 평가 검산 — `calculus_product_rule_
skeleton_generator` docstring의 "검증 설계" 참조).

**개념 태깅 공백**: `calculus_product_rule_skeleton_generator` 모듈 docstring 참조 — 대학
원자(`CALC1-P06`)는 구 437 legacy 개념그래프 경로로 해석되지 않아 `concept_tags=()`로 정직
비워 둔다(가짜 orphan-skip 태그 금지). 후속 U-계열 태스크에서 원자 네이티브 태깅 seam이
생기면 이 배치도 갱신한다.

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.university_calc1_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.calculus_product_rule_skeleton_generator import (
    CalculusProductRuleSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_university_calc1_batch"]

CORPUS_DIR_NAME = "problem_bank_university_calc1_v0"
_STANDARD_CODE = "[CALC1-02-02]"
_SPEC_DIFFICULTY = 3.8  # 생성기가 못 박는 난이도(모든 후보 동일)와 정합(허용격차 0.5 이내).
_BAND_NAME = "product-rule"
_DEFAULT_N = 200  # 풀 목표 300보다 작게 — 풀 소진 없이 안정적으로 채움.


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_university_calc1_batch(
    *, n: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """단일 밴드(곱의 미분법) 배치 실행 — 생성(시드 풀)→게이트(Tier1 미분 평가)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_SPEC_DIFFICULTY,
        answer_format=None,
    )
    seen: set[str] = set()
    generator = CalculusProductRuleSkeletonGenerator(skip_conditions=seen)
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
        prog="python -m whymath_backend.harness.university_calc1_batch",
        description="대학 미적분학 I 곱의 미분법 파일럿 코퍼스 배치(결정론·Tier1 미분 검산).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="요청 수(기본 200).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 university_calc1_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_university_calc1_batch(
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
