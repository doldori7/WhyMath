"""유한 확률·경우의 수 파일럿 코퍼스 배치 — S4-13 ①③ 실증(순수 결정론·LLM 0).

`root_aggregate_batch` 형제. `FiniteProbabilitySkeletonGenerator`로 4밴드를 생성 → 기존
오케스트레이터(`run_batch`)·수용 게이트(전수 열거 검산 경유)·`JsonlCorpusSink`를 **재사용**해
파일럿 코퍼스를 적재한다. SymPy 대수 검산이 성립하지 않아 생성 경로 자체가 없던 영역
(`problem_bank_gap_review.md` §3 D7)의 첫 코퍼스다.

**검증 등급 각인(S4-13 ③·S4-17 L1 승격)**: 배치가 `run_batch`에 `verification_tier=
machine_exhaustive`를 주입해 저장 시점에 `verify.verification_tier`로 영속한다(L1
`ProblemVerifyMeta` 정식 필드 — 후처리 재기록 없음). "수치 축은 전수 열거로 증명됐고,
발문↔형식모델 정합은 아직 아니다"를 코퍼스가 스스로 말하게 하는 것이 목적이다 — 이 등급을
읽는 소비처가 `harness/residue_cross_verify_eval`(잔여 축 Wilson 게이트)이며, 이제
`load_problem_bank_records`(L1 정본) 경유로 읽어 원시 JSONL 우회가 없다.

산출물은 v0(사람 검수 전) — **게이트 통과 ≠ 학생 노출**. 잔여 축 교차검증 + Wilson 표본 검수
게이트를 통과해야 노출 자격 논의가 시작된다.

CLI: `python -m whymath_backend.harness.finite_probability_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.finite_probability_skeleton_generator import (
    FiniteBand,
    FiniteProbabilitySkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_finite_probability_batch"]

CORPUS_DIR_NAME = "problem_bank_probability_finite_v0"

# 밴드 → (스펙 난이도, 성취기준 코드). 난이도는 밴드 내 뼈대 난이도의 중앙 부근으로 잡아
# 수용 게이트의 난이도 성분(허용 격차 0.5)이 만점이 되게 한다.
_BANDS: tuple[tuple[FiniteBand, float, str], ...] = (
    ("dice-sum-prob", 2.5, "[12확통02-01]"),
    ("coin-heads-prob", 2.9, "[12확통02-01]"),
    ("marble-all-red-prob", 3.05, "[12확통02-01]"),
    ("dice-sum-count", 2.5, "[12확통01-01]"),
)

_DEFAULT_N = 20  # 밴드당 요청 수(뼈대 풀보다 크면 소진 후 generation_failed로 정직히 남는다)


def _default_out_path() -> Path:
    # src/backend/whymath_backend/harness/ → repo root 4단계.
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_finite_probability_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """4밴드 배치 실행 — 생성(닫힌 공식)→게이트(전수 열거)→dedup→적재→등급 각인."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    for name, difficulty, standard_code in _BANDS:
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({standard_code}),
            target_misconception_ids=frozenset(),
            difficulty_overall=difficulty,
            answer_format=None,
        )
        # 조건 DSL은 대수식이 아니라 `canonical_signature`가 접지 못한다(None) — 구조 dedup은
        # 생성기의 `skip_conditions`(조건 문자열 키)가 담당한다. 뼈대 풀 자체가 상호 배타라
        # 배치 내 중복은 원천적으로 없고, 이 집합은 재실행 시 누적 중복을 막는 좌석이다.
        seen: set[str] = set()
        generator = FiniteProbabilitySkeletonGenerator(band=name, skip_conditions=seen)
        outcomes = run_batch(
            spec,
            generator,
            n_per_band,
            store=sink,
            verification_tier=VerificationTier.MACHINE_EXHAUSTIVE.value,
        )
        stored = 0
        produced = 0  # 생성기가 실제로 후보를 낸 회차 수(풀 소진 이후 회차는 제외).
        failures: list[str] = []
        for outcome in outcomes:
            if outcome.status == "generation_failed":
                # 뼈대 풀 소진은 정상 종료 신호다 — 요청 수를 풀 크기로 자연 절삭한다.
                continue
            produced += 1
            if outcome.status == "accepted_stored":
                stored += 1
                if outcome.candidate is not None:
                    conditions = outcome.candidate.conditions
                    seen.add(conditions if isinstance(conditions, str) else str(conditions))
            else:
                failures.extend(outcome.reasons or [f"status={outcome.status}"])
        # requested=produced라 `fulfilled`(stored>=requested)가 "낸 후보를 전부 적재했는가"를
        # 뜻한다 — 하나라도 게이트에서 거부되면 False로 드러난다(수율 은폐 금지).
        bands.append(
            BandResult(name=name, requested=produced, stored=stored, failure_reasons=failures)
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


def main(argv: list[str] | None = None) -> int:
    """CLI — 파일럿 코퍼스 배치. 게이트 거부가 하나라도 있으면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.finite_probability_batch",
        description="유한 확률·경우의 수 파일럿 코퍼스 배치(4밴드·결정론·전수 열거 검산).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="밴드당 요청 수(기본 20).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 probability_finite_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_finite_probability_batch(
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
