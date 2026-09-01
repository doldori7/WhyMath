"""초등 두 자리 수 덧셈·뺄셈 파일럿 코퍼스 배치 — W2 초등 축 실증(순수 결정론·LLM 0).

`finite_probability_batch` 형제. `ElementaryAddSubSkeletonGenerator`로 덧셈·뺄셈 2밴드를
생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`를 **재사용**해 파일럿
코퍼스를 적재한다. 초등 축(성취기준 커버율 4.1%)의 첫 코퍼스다 —
`docs/data/problem_bank_coverage_4axis.md` §1.1 "초등학교" 행이 이 배치의 전후 값을 보여준다.

**오케스트레이터 `run_batch`를 쓰지 않고 `run_equivalent_generation`을 직접 반복 호출한다**
(2026-08-05 실측 — `finite_probability_batch`와 같은 이유의 다른 증상). `run_batch`는
`signature_index`(S2-l 구조 dedup)를 항상 켠다 — 이차방정식 도메인에서는 "같은 근 → 같은
문제"가 맞는 판단이지만, 산술식 `canonical_signature`는 방정식을 풀어 *해(x) 값*으로
정규화하므로 "56 - 20 = x"와 "53 - 17 = x"(둘 다 x=36)를 판박이로 오판한다 — 서로 다른
연산 조합으로 같은 답에 도달하는 훈련은 산술 반복학습에서 정당한 다양성이지 중복이 아니다
(실측: 이 오탐이 배치 수율의 ~10~20%를 결정 없이 깎았다). `run_equivalent_generation`을
`signature_index=None`으로 직접 호출하면 이 계층이 스킵되고, 생성기 자체의 `skip_conditions`
(원시 조건 문자열 집합 — *같은* 조건의 재생성만 막음)만 dedup을 담당한다 — 여전히 게이트
(Tier1 정확성 검산)는 매 후보마다 그대로 통과해야 하므로 정확성 방어는 무손실이다.

**검증 등급 각인**: `machine_sampled`(Tier1 수치 샘플링 — `finite_probability_batch`의
`machine_exhaustive`와 다른 등급, 산술은 유한 전수열거가 아니라 SymPy 등식 검산이 근거).

산출물은 v0(사람 검수 전) — **게이트 통과 ≠ 학생 노출**. AI 검수 게이트(초인간 검증 §2 S5
Wilson 표본)는 실 LLM 호출이 필요해 이 저장소의 원격 실행 환경 밖(Kiki 머신)에서만 돈다 —
그 전까지 `is_published=false`(`Problem` 기본값)로 유지된다.

CLI: `python -m whymath_backend.harness.elementary_addsub_batch [--n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.elementary_addsub_skeleton_generator import (
    ElementaryAddSubSkeletonGenerator,
    Operation,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_elementary_addsub_batch"]

CORPUS_DIR_NAME = "problem_bank_elementary_v0"

# 밴드 → (연산·스펙 난이도·성취기준 코드). 난이도는 생성기 밴드(1.2~1.5)의 중앙 부근 —
# 수용 게이트 난이도 성분(허용 격차 0.5)이 만점이 되게 한다(quadratic 배치 관례 미러).
_BANDS: tuple[tuple[Operation, float, str], ...] = (
    ("add", 1.3, "[2수01-06]"),
    ("subtract", 1.3, "[2수01-06]"),
)

_DEFAULT_N = 100  # 밴드당 요청 수(풀보다 크면 소진 후 generation_failed로 정직히 남는다)


def _default_out_path() -> Path:
    # src/backend/whymath_backend/harness/ → repo root 4단계.
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_elementary_addsub_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """2밴드(덧셈·뺄셈) 배치 실행 — 생성(격자 풀)→게이트(Tier1 산술)→dedup→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    # 두 밴드가 서로 다른 연산이라 뼈대 조건 문자열이 자연히 겹치지 않는다 — 다만 재실행 증분
    # 누적을 위해 밴드별로 독립 skip 집합을 둔다(finite_probability_batch 관례 미러).
    for operation, difficulty, standard_code in _BANDS:
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({standard_code}),
            target_misconception_ids=frozenset(),
            difficulty_overall=difficulty,
            answer_format=None,
        )
        seen: set[str] = set()
        # operation 필터 필수(2026-08-05 실측 사고 — 모듈 docstring 참조): 미지정이면 두 밴드가
        # 고정 시드 풀을 각자 처음부터 재생해 *같은* 뼈대를 두 번 낸다(밴드 분리가 무효화됨).
        generator = ElementaryAddSubSkeletonGenerator(operation=operation, skip_conditions=seen)
        # run_batch가 아니라 run_equivalent_generation을 signature_index=None으로 직접 반복
        # 호출한다 — 모듈 docstring 참조(S2-l 구조 dedup이 산술 해값으로 오탐하는 문제 회피).
        outcomes = [
            run_equivalent_generation(
                spec,
                generator,
                store=sink,
                signature_index=None,
                verification_tier=VerificationTier.MACHINE_SAMPLED.value,
            )
            for _ in range(n_per_band)
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
        # 이 배치는 덧셈/뺄셈 둘 다 결정론 스켈레톤에서 나온 다른 뼈대라 두 밴드가 같은 조건
        # 문자열을 만들 수 없다(연산자가 다름) — 밴드 간 skip 공유 불요.
        bands.append(
            BandResult(name=operation, requested=produced, stored=stored, failure_reasons=failures)
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
        prog="python -m whymath_backend.harness.elementary_addsub_batch",
        description="초등 두 자리 수 덧셈·뺄셈 파일럿 코퍼스 배치(2밴드·결정론·Tier1 산술 검산).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="밴드당 요청 수(기본 100).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 elementary_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_elementary_addsub_batch(
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
