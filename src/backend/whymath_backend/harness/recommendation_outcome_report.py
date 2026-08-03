"""추천 폐루프 회계 리포트 — 처치 건수와 "결과 미결합"을 구분해 보여준다 (REC-03 acceptance③).

`l2/recommendation_evidence.py`가 `/me/next-problem`의 처치(학생에게 실제로 반환된 추천)를
`evidence_event`에 쌓기 시작한다. 이 리포트는 그 처치 건수를 관측 가능하게 만든다 — 단, **결과
결합(추천→정답 여부 조인)은 아직 존재하지 않는다**는 사실을 같은 화면에서 분명히 한다.

**결합 0이 효과 0으로 읽히면 안 된다**(acceptance③ 핵심): `session_id`가 매 처치마다 새로 발급되는
placeholder라(모듈 docstring 참조) 처치↔결과를 이을 조인 키가 아직 없다. 그래서 "결과 결합 0건"은
"추천이 효과 없다"가 아니라 "결합 배선이 아직 없다"는 뜻이며, 이 리포트는 그 이유(S3-01 파일럿
이후 실 session_id 배선 대기)를 항상 함께 표기한다.

**게이트가 아니다**(`visualization_reach_report`·`assessment_seat_reach_report`와 동일 원칙) —
처치 건수가 0이어도 exit 1을 내지 않는다.

사용:
    python -m whymath_backend.harness.recommendation_outcome_report
    python -m whymath_backend.harness.recommendation_outcome_report --json out/rec_outcome.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.l2.recommendation_evidence import (
    EVENT_TYPE_RECOMMENDATION_TREATMENT,
)

__all__ = [
    "OutcomeReport",
    "build_report",
    "collect_treatment_count",
    "dump_json",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# 결과 결합이 아직 배선되지 않은 이유 — 리포트가 "0건"을 "효과 없음"으로 오독되지 않게 항상 병기.
_OUTCOME_NOT_WIRED_REASON: str = (
    "결과 결합 미배선 — session_id가 처치마다 새로 발급되는 placeholder라 조인 키가 없다"
    "(S3-01 파일럿 이후 실 session_id 배선 대기, REC-03 acceptance④ 범위 밖 동결)"
)


@dataclass(slots=True, frozen=True)
class OutcomeReport:
    """추천 폐루프 회계 관측 결과 — 처치 건수 + 결과 미결합 사유(항상 명시)."""

    treatment_count: int
    outcome_linked_count: int
    outcome_not_wired_reason: str


async def collect_treatment_count(session: AsyncSession) -> int:
    """`evidence_event`에서 추천 처치(`EVENT_TYPE_RECOMMENDATION_TREATMENT`) 행 수를 센다."""
    result = await session.execute(
        select(func.count())
        .select_from(EvidenceEvent)
        .where(EvidenceEvent.event_type == EVENT_TYPE_RECOMMENDATION_TREATMENT)
    )
    return result.scalar_one()


def build_report(treatment_count: int) -> OutcomeReport:
    """처치 건수(DB 조회 결과) → `OutcomeReport`(순수·부작용 0).

    `outcome_linked_count`는 항상 0이다 — 하드코딩이 아니라 **결합 배선 자체가 없다는 구조적
    사실**이다(session_id 축이 매 처치마다 새로 발급되는 placeholder). 배선이 생기면 이 함수도
    같이 바뀌어야 한다(그 시점까지는 0이 맞다).
    """
    return OutcomeReport(
        treatment_count=treatment_count,
        outcome_linked_count=0,
        outcome_not_wired_reason=_OUTCOME_NOT_WIRED_REASON,
    )


def render_report(report: OutcomeReport) -> str:
    """관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음)."""
    return "\n".join(
        [
            "# 추천 폐루프 회계 리포트 (REC-03)",
            "",
            "> 관측 리포트다 — **exit 게이트가 아니다**(처치 건수가 0이어도 실패시키지 않는다).",
            "",
            f"- 처치(학생에게 실제로 반환된 추천) 건수: **{report.treatment_count}**",
            f"- 결과 결합 건수: **{report.outcome_linked_count}**",
            f"  - {report.outcome_not_wired_reason}",
            "  - **이 0을 '추천 효과 없음'으로 읽지 마라** — 결합 배선이 없다는 뜻일 뿐이다.",
            "",
        ]
    )


def report_to_json(report: OutcomeReport) -> dict[str, Any]:
    return {
        "treatment_count": report.treatment_count,
        "outcome_linked_count": report.outcome_linked_count,
        "outcome_not_wired_reason": report.outcome_not_wired_reason,
    }


def dump_json(report: OutcomeReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


async def _run() -> OutcomeReport:  # pragma: no cover - 라이브 PG 연결 glue
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        count = await collect_treatment_count(session)
    return build_report(count)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 추천 폐루프 회계 리포트를 stdout에 출력. **0=성공(0건이어도) / 2=DB 오류**."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.recommendation_outcome_report",
        description="추천 폐루프 회계 리포트(REC-03) — 처치 건수 + 결과 미결합 사유. 게이트 아님.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="JSON 산출물 경로(선택)",
    )
    args = parser.parse_args(argv)

    try:
        report = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 오류는 타입명과 함께 보고하고 exit 2
        print(
            f"DB 오류 — 처치 건수 조회 실패({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover - 엔트리포인트
    sys.exit(main())
