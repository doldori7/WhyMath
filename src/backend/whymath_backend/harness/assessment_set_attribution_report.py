"""조립 세트(청사진 테스트셋) 시행 귀속 관측 리포트 — ASM-10 acceptance②.

설계 정본: `docs/architecture/assessment_module_gap_review_r2.md` §3 D5. `POST /v1/me/
assessments/assemble`(ASM-04)은 청사진을 만족하는 문항 집합을 `Assessment`(`assessment_type=
실전모의고사`) 행으로 앉히고, `pattern_diagnosis` JSONB에 세트 헤더(`kind=blueprint_test_set`)
+ 문항 N건(`kind=blueprint_item`, 각 `problem_id`)을 담는다. `PATCH /assessments/{id}/complete`
는 `completed_at` 시각만 찍고 결과 산출 코드가 0이다. **`problem_attempt`에는 `assessment_id`
컬럼이 없다** — 학생이 이 세트의 문항을 풀어도 그 시도가 *이 세트에서 나왔는지* 판별할 방법이
근본적으로 없다(전수 grep 실측). 이 리포트는 그 갭을 가시화한다 — **해소하지 않는다**(스키마
변경·마이그레이션·엔드포인트 0, acceptance⑦).

**게이트가 아니다**(`assessment_seat_reach_report`와 동일 원칙) — 어떤 카운트가 얼마이든 exit
1을 내지 않는다. 목표는 활성화가 아니라 가시화다.

**"귀속 0건"과 "아무도 안 풀었다"를 혼동하지 않는다**(acceptance③) — 세트 문항에 대한 시도가
*존재하지만* 그 시도가 이 세트에서 나온 것인지 판별 불가능한 상태를 `unattributable_attempt_
count`로 별도 계상한다. 이 값이 0인 것은 "학생이 실제로 아무 문항도 풀지 않았다"일 수도 있고
"판별 불가 축이 작동하지 않는다"일 수도 있으므로, acceptance⑤의 델타 테스트(합성 세트+합성
시도를 넣었다 뺐다 하며 카운터가 실제로 움직이는지)가 그 변별력을 보증한다.

산출 5축:
  1. 세트 수(`assessment_type=실전모의고사` 행 전건).
  2. 세트별 선언 문항 수(헤더 `selected_item_count`) vs 관측 문항 수(`kind=blueprint_item` 실제
     개수) — 어긋나면 헤더와 문항 배열이 불일치(조립 회계 오류 신호).
  3. 귀속 불능 시도 수 — 세트 문항의 (user_id, problem_id) 쌍에 `problem_attempt`가 하나라도
     있으면 그 문항은 "판별 불가"로 계상한다(세트에서 나왔다는 뜻이 아니다 — 반대도 배제 못함).
  4. 빈 완료 세트 — `completed_at`은 찍혔으나 `concept_diagnosis`·`recommended_path`·
     `strong_points`가 전부 빈 배열인 세트(결과 산출물 0인 완료 — D5의 핵심 관측 대상).
  5. 중복 청사진 세트 — 같은 사용자가 정확히 같은 문항 id 집합을 가진 세트를 2건 이상 가진
     경우(ASM-04가 자인한 멱등 창 미설정의 실제 영향 — 0일 수도 있다).

`pattern_diagnosis` 헤더가 없거나 형태가 다른 행은 조용히 버리지 않고 `malformed_count`로 별도
계상한다(조용한 유실 금지 — ARCH-18 3분류 관례).

사용:
    python -m whymath_backend.harness.assessment_set_attribution_report
    python -m whymath_backend.harness.assessment_set_attribution_report --json out/asm10.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.assessment import Assessment
from whymath_backend.db.session import get_sessionmaker
from whymath_backend.schema.enums import AssessmentType

__all__ = [
    "RawTestSetRow",
    "TestSetAttributionReport",
    "TestSetCollection",
    "TestSetSeat",
    "build_report",
    "collect_test_set_rows",
    "dump_json",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

_KIND_SET = "blueprint_test_set"
_KIND_ITEM = "blueprint_item"


@dataclass(slots=True, frozen=True)
class RawTestSetRow:
    """`실전모의고사` Assessment 행 1건의 원시 투영 — `collect_test_set_rows`의 산출 단위.

    `TestSetCollection.attempted_pairs`와 짝을 이뤄 `build_report`(순수)의 입력이 된다.
    """

    assessment_id: uuid.UUID
    user_id: uuid.UUID | None
    completed_at: datetime | None
    pattern_diagnosis: list[dict[str, Any]]
    concept_diagnosis: list[dict[str, Any]]
    recommended_path: list[dict[str, Any]]
    strong_points: list[dict[str, Any]]


@dataclass(slots=True, frozen=True)
class TestSetCollection:
    """`collect_test_set_rows`의 유일한 산출물 — `build_report`의 유일한 입력.

    `attempted_pairs`는 세트 문항의 (user_id, problem_id) 후보 중 `problem_attempt`가 실재하는
    쌍만 담는다(전수 attempt 테이블 스캔이 아니라 후보로 좁힌 IN 조회 — 대형 코퍼스 보호).
    """

    rows: tuple[RawTestSetRow, ...]
    attempted_pairs: frozenset[tuple[uuid.UUID, uuid.UUID]]


@dataclass(slots=True, frozen=True)
class TestSetSeat:
    """세트 1건의 리포트 투영."""

    assessment_id: uuid.UUID
    declared_item_count: int | None
    observed_item_count: int
    completed: bool
    unattributable_attempt_count: int
    empty_completion: bool
    malformed_pattern_diagnosis: bool


@dataclass(slots=True, frozen=True)
class TestSetAttributionReport:
    """귀속 관측 결과 전량(불변·렌더/직렬화의 단일 입력)."""

    seats: tuple[TestSetSeat, ...]
    total_sets: int
    total_unattributable_attempts: int
    empty_completion_count: int
    malformed_count: int
    duplicate_blueprint_group_count: int
    duplicate_blueprint_extra_row_count: int


def _parse_pattern_diagnosis(
    pattern_diagnosis: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """`pattern_diagnosis` 배열 → (세트 헤더 또는 None, 문항 항목 리스트).

    헤더가 없거나 형태가 아닌 행(딕셔너리가 아닌 항목 포함)은 조용히 버리지 않고 헤더=None으로
    반환해 호출자가 `malformed`로 계상하게 한다.
    """
    header: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    for entry in pattern_diagnosis:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == _KIND_SET and header is None:
            header = entry
        elif kind == _KIND_ITEM:
            items.append(entry)
    return header, items


def _item_problem_id(item: dict[str, Any]) -> uuid.UUID | None:
    """문항 항목의 `problem_id` 문자열을 UUID로 복원 — 형태가 아니면 None(조용히 삼키지 않고
    호출자가 계상에서 제외하게 한다)."""
    raw = item.get("problem_id")
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def collect_test_set_rows(session: AsyncSession) -> TestSetCollection:
    """`실전모의고사` Assessment 전건 + 그 세트 문항들에 대한 시도 존재 여부를 조회.

    전부 ORM 쿼리빌더로만 조립한다(원시 SQL 금지 — CLAUDE.md 원칙). 세트 문항의 (user_id,
    problem_id) 후보로 IN 조회를 좁혀, `problem_attempt` 전수 스캔을 피한다.
    """
    result = await session.execute(
        select(Assessment).where(Assessment.assessment_type == AssessmentType.실전모의고사)
    )
    assessments = result.scalars().all()
    rows = tuple(
        RawTestSetRow(
            assessment_id=a.assessment_id,
            user_id=a.user_id,
            completed_at=a.completed_at,
            pattern_diagnosis=a.pattern_diagnosis,
            concept_diagnosis=a.concept_diagnosis,
            recommended_path=a.recommended_path,
            strong_points=a.strong_points,
        )
        for a in assessments
    )

    candidate_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for row in rows:
        if row.user_id is None:
            continue
        _, items = _parse_pattern_diagnosis(row.pattern_diagnosis)
        for item in items:
            pid = _item_problem_id(item)
            if pid is not None:
                candidate_pairs.add((row.user_id, pid))

    attempted: set[tuple[uuid.UUID, uuid.UUID]] = set()
    if candidate_pairs:
        user_ids = {u for u, _ in candidate_pairs}
        problem_ids = {p for _, p in candidate_pairs}
        attempt_result = await session.execute(
            select(ProblemAttempt.user_id, ProblemAttempt.problem_id)
            .where(
                ProblemAttempt.user_id.in_(user_ids),
                ProblemAttempt.problem_id.in_(problem_ids),
            )
            .distinct()
        )
        for uid, pid in attempt_result.all():
            if uid is not None and pid is not None and (uid, pid) in candidate_pairs:
                attempted.add((uid, pid))

    return TestSetCollection(rows=rows, attempted_pairs=frozenset(attempted))


def build_report(collection: TestSetCollection) -> TestSetAttributionReport:
    """DB 조회 결과(`TestSetCollection`) → `TestSetAttributionReport`(순수·부작용 0·DB 불요)."""
    seats: list[TestSetSeat] = []
    dup_signatures: dict[tuple[uuid.UUID, frozenset[uuid.UUID]], list[uuid.UUID]] = {}

    for row in collection.rows:
        header, items = _parse_pattern_diagnosis(row.pattern_diagnosis)
        malformed = header is None
        declared_count = header.get("selected_item_count") if header is not None else None
        observed_count = len(items)

        item_problem_ids: list[uuid.UUID] = []
        unattributable = 0
        for item in items:
            pid = _item_problem_id(item)
            if pid is None:
                continue
            item_problem_ids.append(pid)
            if row.user_id is not None and (row.user_id, pid) in collection.attempted_pairs:
                unattributable += 1

        completed = row.completed_at is not None
        empty_completion = (
            completed
            and not row.concept_diagnosis
            and not row.recommended_path
            and not row.strong_points
        )

        seats.append(
            TestSetSeat(
                assessment_id=row.assessment_id,
                declared_item_count=declared_count,
                observed_item_count=observed_count,
                completed=completed,
                unattributable_attempt_count=unattributable,
                empty_completion=empty_completion,
                malformed_pattern_diagnosis=malformed,
            )
        )

        if row.user_id is not None and item_problem_ids:
            signature = (row.user_id, frozenset(item_problem_ids))
            dup_signatures.setdefault(signature, []).append(row.assessment_id)

    dup_groups = {sig: ids for sig, ids in dup_signatures.items() if len(ids) > 1}

    return TestSetAttributionReport(
        seats=tuple(seats),
        total_sets=len(seats),
        total_unattributable_attempts=sum(s.unattributable_attempt_count for s in seats),
        empty_completion_count=sum(1 for s in seats if s.empty_completion),
        malformed_count=sum(1 for s in seats if s.malformed_pattern_diagnosis),
        duplicate_blueprint_group_count=len(dup_groups),
        duplicate_blueprint_extra_row_count=sum(len(ids) - 1 for ids in dup_groups.values()),
    )


def render_report(report: TestSetAttributionReport) -> str:
    """귀속 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음)."""
    lines: list[str] = [
        "# 조립 세트 시행 귀속 관측 리포트 (ASM-10 D5)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**. `problem_attempt`에 `assessment_id`가 없어",
        "> 시도가 이 세트에서 나왔는지 판별할 방법이 근본적으로 없다는 사실을 가시화한다.",
        "> 컬럼 신설·채점·점수 산출은 이 리포트의 범위 밖이다(관측 결과가 별도 발화 조건).",
        "",
        f"- 세트(실전모의고사) 전건: **{report.total_sets}**",
        f"- `pattern_diagnosis` 헤더 형태 이상(malformed): **{report.malformed_count}**",
        f"- 귀속 판별 불가 시도(세트 문항에 시도가 있으나 이 세트발인지 불명): "
        f"**{report.total_unattributable_attempts}**",
        f"- 빈 완료 세트(completed_at은 있으나 결과 산출물 3종 전부 빈 배열): "
        f"**{report.empty_completion_count}**",
        f"- 중복 청사진 그룹(같은 사용자·같은 문항 집합 2건 이상): "
        f"**{report.duplicate_blueprint_group_count}**"
        f"(중복분 총 {report.duplicate_blueprint_extra_row_count}행)",
        "",
        "## 세트별 상세",
        "",
        "| assessment_id | 선언 문항 수 | 관측 문항 수 | 완료 | 귀속불가 시도 | 빈 완료 | "
        "형태이상 |",
        "|---|---:|---:|---|---:|---|---|",
    ]
    for seat in report.seats:
        declared = "—" if seat.declared_item_count is None else str(seat.declared_item_count)
        lines.append(
            f"| {seat.assessment_id} | {declared} | {seat.observed_item_count} | "
            f"{'예' if seat.completed else '아니오'} | {seat.unattributable_attempt_count} | "
            f"{'예' if seat.empty_completion else '아니오'} | "
            f"{'예' if seat.malformed_pattern_diagnosis else '아니오'} |"
        )
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: TestSetAttributionReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정)."""
    return {
        "total_sets": report.total_sets,
        "total_unattributable_attempts": report.total_unattributable_attempts,
        "empty_completion_count": report.empty_completion_count,
        "malformed_count": report.malformed_count,
        "duplicate_blueprint_group_count": report.duplicate_blueprint_group_count,
        "duplicate_blueprint_extra_row_count": report.duplicate_blueprint_extra_row_count,
        "seats": [
            {
                "assessment_id": str(seat.assessment_id),
                "declared_item_count": seat.declared_item_count,
                "observed_item_count": seat.observed_item_count,
                "completed": seat.completed,
                "unattributable_attempt_count": seat.unattributable_attempt_count,
                "empty_completion": seat.empty_completion,
                "malformed_pattern_diagnosis": seat.malformed_pattern_diagnosis,
            }
            for seat in report.seats
        ],
    }


def dump_json(report: TestSetAttributionReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 조회·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
async def _run() -> TestSetAttributionReport:  # pragma: no cover — 라이브 PG 연결 glue
    """세션을 열어 세트 행을 조회하고 리포트를 조립한다(DB 조회 전용·쓰기 0)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        collection = await collect_test_set_rows(session)
    return build_report(collection)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 귀속 관측 리포트를 stdout에 출력. **0=성공(0건이어도) / 2=DB 오류**.

    DB 접속·쿼리 실패는 예외 타입명을 stderr에 포함해 보고한다(CLAUDE.md 침묵 실패 금지).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.assessment_set_attribution_report",
        description=(
            "조립 세트(청사진 테스트셋) 시행 귀속 관측 리포트(ASM-10 D5) — 세트 수·문항 수 "
            "정합·귀속 판별 불가 시도·빈 완료·중복 청사진. 게이트 아님(exit 0/2)."
        ),
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
            f"DB 오류 — 세트 행 조회 실패({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
