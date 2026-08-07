"""`pedagogy_content_slot` 상태별 건수 관측 리포트 — PED-06 acceptance①.

설계 정본: `docs/architecture/ai_content_generation_gap_review_2.md` §2 G2/G3·§3 D6.
`slot_generator.py`(DRAFT 생성) → `prescreen.py`(DRAFT→PRESCREENED) → `review.py`
(PRESCREENED→APPROVED|REJECTED)까지 5단계 상태기계는 완비돼 있는데, 그 파이프라인의
**프로덕션 호출자가 0개**다(전수 grep 확인 — 유일한 실행자는
`tests/backend/api/test_e2e_pedagogy_pilot_integration.py` 1개 E2E 파일럿). 이 모듈은 그
"입구도 출구도 없다"는 사실을 *수치로* 드러낸다 — 파이프라인을 열거나(신규 저작·LLM 생성)
새 소비 경로를 잇는 것은 이 모듈의 역할이 아니다(§3 D6 "관측 축으로 한정").

**관측 전용 — 게이트가 아니다**(`harness/visualization_reach_report.py`·
`harness/attempt_grading_shadow_report.py`와 동일 원칙). `main()`은 총 건수가 0이든
얼마든 항상 exit 0을 낸다 — 이 리포트가 판정하는 것은 "얼마나 쌓였는가"이지 "쌓여야 할
양"이 아니다.

**변별력 (acceptance①의 "실행 전/후 값이 실제로 바뀌는지")**: 이 리포트는 DB의 실제
`pedagogy_content_slot` 행을 그대로 세므로, E2E 파일럿(`test_pilot_pipeline_e2e`)이
실행되어 슬롯을 적재하면 `total`·`DRAFT`(생성 직후)·`PRESCREENED`(예심 후)·
`APPROVED`/`REJECTED`(검수 후) 값이 실측으로 증가한다 — 파일럿이 try/finally로 정리하므로
파일럿 종료 후에는 다시 0으로 돌아온다(`tests/infra` 쪽 discriminating 테스트가 이 변화를
직접 관측·복원해 봉인한다).

`total == 0`을 "측정 실패"로 오인하지 않도록 렌더에서 명시적으로 구분한다 — 이 파이프라인이
*가동된 적이 없다는 사실 자체*가 이 리포트가 보고하려는 진짜 발견이다(0건은 정직한 관측치,
"모른다"가 아니다 — None-vs-0 원칙의 반대 방향: 여기서는 0이 실제로 의미 있는 참값이다).

사용:
    python -m whymath_backend.ops.pedagogy_content_slot_reach_report
    python -m whymath_backend.ops.pedagogy_content_slot_reach_report --json out/slot_reach.json

7계층: `ops`는 계층 계약(import-linter `layers`) 밖의 단독 진입점이다(`ops/__init__.py`
docstring) — 이 모듈이 `db.models.pedagogy_dsl`을 직접 import해도 계약 위반이 아니다.
반대로 어느 계층도 이 모듈을 import해서는 안 된다(CLI 전용 진입점).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.pedagogy_dsl import PedagogyContentSlot

__all__ = [
    "ALL_STATUSES",
    "PedagogyContentSlotReachReport",
    "build_report",
    "fetch_status_counts",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# ORM CHECK 제약(`db/models/pedagogy_dsl.py::PedagogyContentSlot.__table_args__`)과 동결
# 정합 — 여기 없는 상태가 나오면 스키마가 이미 이 리포트 모르게 바뀐 것이다(build_report가
# 그 드리프트를 조용히 삼키지 않고 잡아낸다).
ALL_STATUSES: tuple[str, ...] = ("DRAFT", "PRESCREENED", "APPROVED", "REJECTED")


# ──────────────────────────────────────────────────────────────────────────
# 조회 — status GROUP BY 건수(얇은 I/O, 집계 로직 0 — 순수 코어는 build_report)
# ──────────────────────────────────────────────────────────────────────────
async def fetch_status_counts(session: AsyncSession) -> dict[str, int]:
    """`pedagogy_content_slot`을 `status`로 GROUP BY해 건수 dict를 얻는다(I/O만·집계 0).

    DB에 실제로 존재하는 상태만 키로 돌아온다(0건인 상태는 아예 나타나지 않는다) — 상태
    화이트리스트(`ALL_STATUSES`) 대조·0 채움은 `build_report`(순수 코어)가 맡는다.
    """
    stmt = select(PedagogyContentSlot.status, func.count()).group_by(PedagogyContentSlot.status)
    rows = (await session.execute(stmt)).all()
    return {str(status): int(count) for status, count in rows}


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 상태별 건수 리포트(순수 코어 — DB·LLM·HTTP 0)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class PedagogyContentSlotReachReport:
    """`pedagogy_content_slot` 상태별 건수 집계 결과 전량(불변).

    `by_status`는 `ALL_STATUSES` 4개 키를 **항상 전부** 담는다(DB에 없는 상태는 0으로
    명시 채움 — 조용히 키가 빠지면 "그 상태가 0건"과 "이 리포트가 그 상태를 놓쳤다"가
    구분되지 않는다). `unknown_statuses`는 화이트리스트 밖 값이 실제로 관측되면 담기는
    드리프트 감지 축이다(정상 상태에서는 항상 빈 dict).
    """

    total: int
    by_status: dict[str, int]
    unknown_statuses: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return report_to_json(self)


def build_report(counts: Mapping[str, int]) -> PedagogyContentSlotReachReport:
    """`fetch_status_counts` 산출 dict → `PedagogyContentSlotReachReport`(순수·부작용 0).

    `ALL_STATUSES` 화이트리스트에 있는 상태는 관측치가 없어도 0으로 채워 반환한다(분모
    누락 방지). 화이트리스트 밖 상태(스키마 CHECK 제약과 어긋난 값 — 통상 발생 불가하나
    마이그레이션 드리프트를 조용히 삼키지 않기 위해 별도 버킷으로 분리한다)는
    `unknown_statuses`에 담고 `total`에는 포함시킨다(실제 행 수는 항상 정직하게 보존).
    """
    by_status = {status: int(counts.get(status, 0)) for status in ALL_STATUSES}
    unknown = {status: n for status, n in counts.items() if status not in ALL_STATUSES}
    total = sum(by_status.values()) + sum(unknown.values())
    return PedagogyContentSlotReachReport(
        total=total, by_status=by_status, unknown_statuses=unknown
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def render_report(report: PedagogyContentSlotReachReport) -> str:
    """리포트를 마크다운으로 렌더(순수·입력 외 계산 없음).

    `total == 0`은 "이 파이프라인을 실행한 적이 없음"으로 명시한다(§3 D6·모듈 docstring) —
    측정 실패가 아니라 정직한 참값 0임을 분명히 한다.
    """
    lines = [
        "# 교수법 콘텐츠 슬롯 파이프라인 도달성 리포트 (PED-06)",
        "",
        "> 관측 전용 리포트다 — **exit 게이트가 아니다**. 프로덕션 호출자 0·학생 reader 0인",
        "> `pedagogy_content_slot` 파이프라인(`slot_generator`→`prescreen`→`review`)의 현재",
        "> 적재량을 그대로 보고한다(`docs/architecture/ai_content_generation_gap_review_2.md`",
        "> §2 G2/G3·§3 D6).",
        "",
    ]
    if report.total == 0:
        lines.append(
            "- **총 건수: 0** — 이 파이프라인을 실행한 적이 없음(측정 실패가 아니라 정직한 "
            "관측치 — 프로덕션 호출자 0·유일한 실행자는 E2E 파일럿 테스트 1개)."
        )
    else:
        lines.append(f"- 총 건수: **{report.total}**")
    lines += ["", "## 상태별 건수", "", "| status | 건수 |", "|---|---:|"]
    for status in ALL_STATUSES:
        lines.append(f"| {status} | {report.by_status.get(status, 0)} |")
    if report.unknown_statuses:
        lines += [
            "",
            "## ⚠ 화이트리스트 밖 상태 관측 (스키마 드리프트 의심)",
            "",
            "| status | 건수 |",
            "|---|---:|",
        ]
        for status, count in sorted(report.unknown_statuses.items()):
            lines.append(f"| `{status}` | {count} |")
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: PedagogyContentSlotReachReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict."""
    return {
        "total": report.total,
        "by_status": dict(report.by_status),
        "unknown_statuses": dict(report.unknown_statuses),
    }


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 접속·출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI — DB에서 `pedagogy_content_slot`을 상태별로 세어 리포트를 출력.

    **게이트가 아니다**(항상 exit 0, DB 접속 실패만 exit 2) — 건수가 0이든 얼마든 이
    도구의 역할은 관측이지 판정이 아니다.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.pedagogy_content_slot_reach_report",
        description=(
            "pedagogy_content_slot 상태별(DRAFT/PRESCREENED/APPROVED/REJECTED) 건수를 관측한다"
            "(PED-06·관측 전용·게이트 아님)."
        ),
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    async def _run() -> PedagogyContentSlotReachReport:
        # lazy import — CLI를 실제로 실행할 때만 DB 세션 팩토리를 물게 한다(다른 함수의
        # 모듈 top-level import는 순수 유지 — attempt_grading_shadow_report와 동일 관례).
        from whymath_backend.db.session import get_session

        async for session in get_session():
            counts = await fetch_status_counts(session)
            return build_report(counts)
        raise RuntimeError("DB 세션을 얻지 못함")  # pragma: no cover — get_session은 항상 1회 yield

    try:
        report = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 접속 실패 등은 타입명과 함께 보고 후 exit 2
        print(f"입력/접속 오류({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
