"""WH-1 2단계 종료 게이트 *ops CLI* — 전역 집계를 스크립트로 노출(HTTP 미노출 컨벤션).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4 2단계 *종료 기준*. 코호트/전역
집계는 admin auth 범위 밖이라 HTTP로 노출하지 않고(me.py `get_my_harness_metrics` 주석:
"코호트 전체 집계는 ops/스크립트가 직접 호출") *스크립트*가 직접 돌린다 — 이 CLI가 그 표면이다.

사용법:
    python -m whymath_backend.harness.agreement_gate_cli \\
        [--alpha 0.05] [--min-probes 5] [--threshold 0.55]

동작: 설정의 임베딩 provider(`build_provider` — 로컬 bge-m3/OpenAI)로 의미 매처 후보를 *1회*
구축해 recall 게이트(라벨 프로브)·정밀도 가드(FP 프로브)를 돌리고 결합 판정(`Phase2Report`)을
**JSON으로 stdout**에 낸다(머신 파싱·ops 파이프라인용). **종료 코드로 판정을 인코딩**한다:
  - 0 = READY(2단계 종료 충족: recall 유의 개선 AND 정밀도 무회귀)
  - 1 = NOT_READY(recall 비개선 또는 정밀도 회귀)
  - 2 = NO_DATA(프로브 부족 — 판정 보류)
따라서 `python -m ... && <다음 단계>`로 게이트를 *집행*할 수 있다(green일 때만 진행).

정직 스코프(설계 §8.4·`agreement_gate` 모듈): 오프라인·시스템 지표(라벨 프로브셋)다 — LIVE
per-user ground-truth가 아니다. 라이브 임베딩 도달은 ops 실행 환경(Phaiakes9) 책임이다.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from whymath_backend.config import get_settings
from whymath_backend.harness.agreement_gate import Phase2ExitVerdict, Phase2Report
from whymath_backend.harness.agreement_gate_semantic import run_semantic_phase2_report
from whymath_backend.l4.misconception.semantic.provider import build_provider

__all__ = ["Runner", "main"]

# 결합 판정 → 프로세스 종료 코드. ops 파이프라인이 종료 코드로 게이트를 집행하게 한다.
_EXIT_BY_VERDICT: dict[Phase2ExitVerdict, int] = {
    Phase2ExitVerdict.READY: 0,
    Phase2ExitVerdict.NOT_READY: 1,
    Phase2ExitVerdict.NO_DATA: 2,
}

# 러너 좌석 — (alpha, min_probes, threshold) → Phase2Report. 기본은 라이브 임베딩,
# 테스트는 합성 리포트를 주입해 임베딩 없이 CLI 배선(인자·직렬화·종료 코드)을 검증한다.
Runner = Callable[..., Phase2Report]


def _default_runner(
    *, alpha: float, min_probes: int, threshold: float | None
) -> Phase2Report:  # pragma: no cover — 라이브 임베딩 좌석(integration 테스트가 실측)
    """기본 러너 — 설정 provider(bge-m3/OpenAI)로 의미 매처 후보를 구축해 전체 리포트 산출."""
    provider = build_provider(get_settings())
    return run_semantic_phase2_report(
        provider=provider, alpha=alpha, min_probes=min_probes, threshold=threshold
    )


def main(argv: list[str] | None = None, *, runner: Runner = _default_runner) -> int:
    """CLI 엔트리 — 리포트를 JSON으로 stdout에 내고 결합 판정을 종료 코드로 반환.

    종료 코드: 0=READY·1=NOT_READY·2=NO_DATA(`_EXIT_BY_VERDICT`). `runner`는 테스트 주입 좌석
    (기본은 라이브 임베딩). stdout은 *순수 JSON*만(ops 파싱) — 사람읽는 로그는 stderr가 아닌
    note 필드 안에 담는다.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.agreement_gate_cli",
        description=(
            "WH-1 2단계 종료 게이트 — 의미 매처 후보가 substring 기준선을 라벨 프로브셋에서 "
            "유의하게 능가하고(recall) 거짓양성을 늘리지 않는지(정밀도) 전역 집계로 판정."
        ),
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="유의수준(단측 McNemar). recall·정밀도 양쪽에 적용(기본 0.05).",
    )
    parser.add_argument(
        "--min-probes",
        type=int,
        default=5,
        help="프로브가 이보다 적으면 NO_DATA(판정 보류·날조 0). 기본 5.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="의미 매처 코사인 임계값. 생략 시 Settings.misconception_semantic_threshold(0.55).",
    )
    args = parser.parse_args(argv)
    alpha: float = args.alpha
    min_probes: int = args.min_probes
    threshold: float | None = args.threshold

    report = runner(alpha=alpha, min_probes=min_probes, threshold=threshold)
    print(report.model_dump_json(indent=2))
    return _EXIT_BY_VERDICT[report.decision.verdict]


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, main이 테스트 대상
    sys.exit(main())
