"""데이터 무결성 게이트 — orphan·dangling·duplicate 6종 단일 CLI (OPS-55).

배경
----
`docs/reviews/eos_plan52_crosswalk_2026-09.md` §H2(갭 후보 #12)가 지목한 공백: 이 저장소는
hypertable·cross-dataset·오프라인 독립성 등의 이유로 다수 참조 컬럼을 **의도적으로 FK가 아닌
"느슨참조"**(모델 docstring 표현)로 둔다(`concept_node.concept_id`·`concept.behavior_skills`·
`solution_nodes.problem_id` 등). DB 제약이 막지 못하므로, 참조 대상이 삭제·재-ID(rename)되면
참조하는 행은 조용히 고아가 된다 — 실측 선례 = `scripts/diagnose_atom_orphans.py`(S2-04, "prod
미적분 raw 129건 orphan"). 이 CLI가 그 점검을 **6종 단일 지점**으로 정례화한다(주간 지표 #4 산출원).

6종 판정 항목
------------
① ORPHAN_CONCEPT           — `concept_node.concept_id`(검색 투영) 중 `concept.code`(런타임
  그래프, 동일 UC 키공간 — `concept.py` 주석 "code = concept_id(개념그래프 UC)")에 없는 것.
② ORPHAN_SKILL              — `concept.behavior_skills`·`concept_node.behavior_skills`·
  `skill_node.prerequisite_skill_ids`(모두 배열·느슨참조)가 가리키는 skill_id 중
  `skill_node.skill_id`에 없는 것.
③ ORPHAN_PROBLEM            — WH-S 솔버 자산(`solution_nodes`·`verified_lemmas`·
  `verified_solutions`·`dead_end_log`·`problem_embedding`의 `problem_id` — 전부 "WH-S 오프라인
  독립성" 느슨참조로 모델 docstring 확정)이 가리키는 problem_id 중 `problem.problem_id`에 없는 것.
④ DANGLING_CURRICULUM_REF   — `concept_node.standard_codes`·`skill_node.standard_codes`(NCIC
  성취기준 코드 배열·느슨참조)가 가리키는 코드 중 `achievement_standard.official_code`에 없는 것.
⑤ DUPLICATE_CANONICAL_ID    — `concept.code`(canonical_id — `math.<area>.<slug>`, Part 9 재-ID)가
  *다른* 개념 행의 `aliases`(구 키 별칭 배열)에도 값으로 들어있는 경우. `code`는 DB UNIQUE라
  같은 컬럼 내부 중복은 이미 불가능하지만, `aliases`는 배열이라 DB 제약이 못 잡는 교차 충돌
  (한 식별자가 A의 canonical이면서 B의 alias로도 존재 — 키 해석이 행마다 달라지는 위험)이다.
⑥ EVENT_SCHEMA_INVALID      — `attempt_event.event_data`가 채워진 행 중 `event_type`이
  `schema/event_data_contract.py`의 `EVENT_DATA_CONTRACT`(계약 있는 7종)에 해당하는데 그 Pydantic
  계약으로 재검증(`model_validate`)했을 때 실패하는 것(invariant ⑫ "event_data 자유 JSONB 금지·
  타입별 계약"의 사후 감사 — 생산 좌석은 `build_event_data`가 이미 강제하나, 이 게이트는 과거
  적재분·생산 좌석 우회분의 드리프트를 잡는다).

종료 코드
--------
- 0 : 6종 전부 위반 0건.
- 1 : 위반 ≥1건.

스캔 대상 개수를 모든 kind에 함께 출력한다(CLAUDE.md "절단 출력을 부재 판정에 쓰지 않는다" —
0건이 "위반 없음"인지 "스캔 대상 자체가 0"인지 항상 구분 가능하게 한다).

사용
----
    python -m whymath_backend.ops.integrity_violations_gate
    python -m whymath_backend.ops.integrity_violations_gate --json report.json
    # attempt_event가 큰 prod에서 ⑥ 스캔 범위를 최근 N일로 제한(기본은 전건 — 정확성 우선):
    python -m whymath_backend.ops.integrity_violations_gate --event-since-days 30

DB 왕복은 실 PostgreSQL을 요구한다(hermetic 단위테스트는 `main(scan_fn=...)` 주입으로 CLI
배선만 검증 — `role_grant_cli.py` 선례). 실 DB 6종 각각의 검출 변별력(주입 성공/실패 양쪽 신호)은
`@pytest.mark.integration` 통합테스트가 검증한다.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.session import dispose_engine, get_sessionmaker
from whymath_backend.schema.event_data_contract import EVENT_DATA_CONTRACT

__all__ = [
    "KIND_DANGLING_CURRICULUM_REF",
    "KIND_DUPLICATE_CANONICAL_ID",
    "KIND_EVENT_SCHEMA_INVALID",
    "KIND_ORPHAN_CONCEPT",
    "KIND_ORPHAN_PROBLEM",
    "KIND_ORPHAN_SKILL",
    "ALL_KINDS",
    "IntegrityReport",
    "ScanFn",
    "Violation",
    "main",
    "scan_integrity",
]

_EXIT_OK = 0
_EXIT_VIOLATIONS = 1

KIND_ORPHAN_CONCEPT = "ORPHAN_CONCEPT"
KIND_ORPHAN_SKILL = "ORPHAN_SKILL"
KIND_ORPHAN_PROBLEM = "ORPHAN_PROBLEM"
KIND_DANGLING_CURRICULUM_REF = "DANGLING_CURRICULUM_REF"
KIND_DUPLICATE_CANONICAL_ID = "DUPLICATE_CANONICAL_ID"
KIND_EVENT_SCHEMA_INVALID = "EVENT_SCHEMA_INVALID"

ALL_KINDS: tuple[str, ...] = (
    KIND_ORPHAN_CONCEPT,
    KIND_ORPHAN_SKILL,
    KIND_ORPHAN_PROBLEM,
    KIND_DANGLING_CURRICULUM_REF,
    KIND_DUPLICATE_CANONICAL_ID,
    KIND_EVENT_SCHEMA_INVALID,
)

# WH-S 솔버 자산 5테이블 — 전부 모듈 docstring이 "problem_id는 FK 아닌 느슨참조(WH-S 오프라인
# 독립성)"로 명시 확정한 것만 대상(느슨참조 23파일 전수 확장은 의도적 비대상 — 과공학 방지).
_ORPHAN_PROBLEM_SOURCE_TABLES: tuple[str, ...] = (
    "solution_nodes",
    "verified_lemmas",
    "verified_solutions",
    "dead_end_log",
    "problem_embedding",
)


@dataclass(slots=True, frozen=True)
class Violation:
    kind: str
    identifier: str
    detail: str


@dataclass(slots=True)
class IntegrityReport:
    # kind → 스캔한 참조/행 개수(0건 위반이 "스캔 대상 0"과 구분되게 — 절단 출력 금지 규칙).
    scanned: dict[str, int] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return _EXIT_OK if not self.violations else _EXIT_VIOLATIONS

    def violations_by_kind(self, kind: str) -> list[Violation]:
        return [v for v in self.violations if v.kind == kind]


async def _check_orphan_concept(session: AsyncSession) -> tuple[int, list[Violation]]:
    scanned = (await session.execute(text("SELECT count(*) FROM concept_node"))).scalar_one()
    rows = await session.execute(text("""
            SELECT cn.concept_id
              FROM concept_node cn
             WHERE NOT EXISTS (SELECT 1 FROM concept c WHERE c.code = cn.concept_id)
             ORDER BY cn.concept_id
            """))
    violations = [
        Violation(
            kind=KIND_ORPHAN_CONCEPT,
            identifier=concept_id,
            detail=f"concept_node.concept_id={concept_id!r} 이(가) concept.code에 없다.",
        )
        for (concept_id,) in rows
    ]
    return int(scanned), violations


async def _check_orphan_skill(session: AsyncSession) -> tuple[int, list[Violation]]:
    refs_sql = text("""
        WITH refs AS (
            SELECT unnest(behavior_skills) AS skill_id, 'concept.behavior_skills' AS src
              FROM concept
             UNION ALL
            SELECT unnest(behavior_skills), 'concept_node.behavior_skills'
              FROM concept_node
             UNION ALL
            SELECT unnest(prerequisite_skill_ids), 'skill_node.prerequisite_skill_ids'
              FROM skill_node
        )
        SELECT skill_id, array_agg(DISTINCT src ORDER BY src) AS sources
          FROM refs
         WHERE NOT EXISTS (SELECT 1 FROM skill_node sn WHERE sn.skill_id = refs.skill_id)
         GROUP BY skill_id
         ORDER BY skill_id
        """)
    scanned_sql = text("""
        SELECT count(DISTINCT skill_id) FROM (
            SELECT unnest(behavior_skills) AS skill_id FROM concept
             UNION ALL
            SELECT unnest(behavior_skills) FROM concept_node
             UNION ALL
            SELECT unnest(prerequisite_skill_ids) FROM skill_node
        ) refs
        """)
    scanned = (await session.execute(scanned_sql)).scalar_one()
    rows = await session.execute(refs_sql)
    violations = [
        Violation(
            kind=KIND_ORPHAN_SKILL,
            identifier=skill_id,
            detail=(
                f"skill_id={skill_id!r} 이(가) skill_node.skill_id에 없다 "
                f"(참조원: {', '.join(sources)})."
            ),
        )
        for (skill_id, sources) in rows
    ]
    return int(scanned), violations


async def _check_orphan_problem(session: AsyncSession) -> tuple[int, list[Violation]]:
    union_all = " UNION ALL ".join(
        f"SELECT problem_id, '{table}' AS src FROM {table}"
        for table in _ORPHAN_PROBLEM_SOURCE_TABLES
    )
    scanned_sql = text(f"SELECT count(DISTINCT problem_id) FROM ({union_all}) refs")
    violations_sql = text(f"""
        WITH refs AS ({union_all})
        SELECT problem_id, array_agg(DISTINCT src ORDER BY src) AS sources
          FROM refs
         WHERE NOT EXISTS (SELECT 1 FROM problem p WHERE p.problem_id = refs.problem_id)
         GROUP BY problem_id
         ORDER BY problem_id
        """)
    scanned = (await session.execute(scanned_sql)).scalar_one()
    rows = await session.execute(violations_sql)
    violations = [
        Violation(
            kind=KIND_ORPHAN_PROBLEM,
            identifier=str(problem_id),
            detail=(
                f"problem_id={problem_id} 이(가) problem.problem_id에 없다 "
                f"(참조원: {', '.join(sources)})."
            ),
        )
        for (problem_id, sources) in rows
    ]
    return int(scanned), violations


async def _check_dangling_curriculum_ref(session: AsyncSession) -> tuple[int, list[Violation]]:
    refs_cte = """
        WITH refs AS (
            SELECT unnest(standard_codes) AS code, 'concept_node.standard_codes' AS src
              FROM concept_node
             UNION ALL
            SELECT unnest(standard_codes), 'skill_node.standard_codes'
              FROM skill_node
        )
    """
    scanned = (
        await session.execute(text(refs_cte + "SELECT count(DISTINCT code) FROM refs"))
    ).scalar_one()
    rows = await session.execute(text(refs_cte + """
            SELECT code, array_agg(DISTINCT src ORDER BY src) AS sources
              FROM refs
             WHERE NOT EXISTS (
                 SELECT 1 FROM achievement_standard a WHERE a.official_code = refs.code
             )
             GROUP BY code
             ORDER BY code
            """))
    violations = [
        Violation(
            kind=KIND_DANGLING_CURRICULUM_REF,
            identifier=code,
            detail=(
                f"성취기준 코드={code!r} 이(가) achievement_standard.official_code에 없다 "
                f"(참조원: {', '.join(sources)})."
            ),
        )
        for (code, sources) in rows
    ]
    return int(scanned), violations


async def _check_duplicate_canonical_id(session: AsyncSession) -> tuple[int, list[Violation]]:
    scanned = (await session.execute(text("SELECT count(*) FROM concept"))).scalar_one()
    rows = await session.execute(text("""
            SELECT c1.code, array_agg(DISTINCT c2.code ORDER BY c2.code) AS alias_holder_codes
              FROM concept c1
              JOIN concept c2
                ON c1.code = ANY(c2.aliases)
               AND c1.concept_id != c2.concept_id
             GROUP BY c1.code
             ORDER BY c1.code
            """))
    violations = [
        Violation(
            kind=KIND_DUPLICATE_CANONICAL_ID,
            identifier=code,
            detail=(
                f"canonical_id={code!r} 이(가) 다른 개념의 aliases에도 존재한다 "
                f"(alias 보유 개념: {', '.join(holders)})."
            ),
        )
        for (code, holders) in rows
    ]
    return int(scanned), violations


async def _check_event_schema_invalid(
    session: AsyncSession, *, since_days: int | None
) -> tuple[int, list[Violation]]:
    contracted_types = sorted(et.value for et in EVENT_DATA_CONTRACT)
    where_clauses = ["event_type = ANY(:types)", "event_data IS NOT NULL"]
    params: dict[str, Any] = {"types": contracted_types}
    if since_days is not None:
        where_clauses.append("event_at >= :since")
        params["since"] = datetime.now(UTC) - timedelta(days=since_days)
    where_sql = " AND ".join(where_clauses)

    scanned = (
        await session.execute(text(f"SELECT count(*) FROM attempt_event WHERE {where_sql}"), params)
    ).scalar_one()

    rows = await session.execute(
        text(
            f"SELECT event_id, event_at, event_type, event_data "
            f"FROM attempt_event WHERE {where_sql} ORDER BY event_id"
        ),
        params,
    )
    violations: list[Violation] = []
    for event_id, event_at, event_type, event_data in rows:
        model = EVENT_DATA_CONTRACT.get(event_type)
        if model is None:  # pragma: no cover — WHERE 절이 이미 계약 있는 타입만 통과시킨다
            continue
        try:
            model.model_validate(event_data)
        except ValidationError as exc:
            violations.append(
                Violation(
                    kind=KIND_EVENT_SCHEMA_INVALID,
                    identifier=f"attempt_event#{event_id}",
                    detail=(
                        f"event_type={event_type!r}(event_at={event_at}) 의 event_data가 "
                        f"계약 위반 — {exc.error_count()}건: {exc.errors()[0].get('msg', '')}"
                    ),
                )
            )
    return int(scanned), violations


async def scan_integrity(
    session: AsyncSession, *, event_since_days: int | None = None
) -> IntegrityReport:
    """6종 전부를 실 세션으로 스캔해 `IntegrityReport`를 합성한다."""
    report = IntegrityReport()

    checks: list[tuple[str, Callable[[], Awaitable[tuple[int, list[Violation]]]]]] = [
        (KIND_ORPHAN_CONCEPT, lambda: _check_orphan_concept(session)),
        (KIND_ORPHAN_SKILL, lambda: _check_orphan_skill(session)),
        (KIND_ORPHAN_PROBLEM, lambda: _check_orphan_problem(session)),
        (KIND_DANGLING_CURRICULUM_REF, lambda: _check_dangling_curriculum_ref(session)),
        (KIND_DUPLICATE_CANONICAL_ID, lambda: _check_duplicate_canonical_id(session)),
        (
            KIND_EVENT_SCHEMA_INVALID,
            lambda: _check_event_schema_invalid(session, since_days=event_since_days),
        ),
    ]
    for kind, check in checks:
        scanned, violations = await check()
        report.scanned[kind] = scanned
        report.violations.extend(violations)
    return report


ScanFn = Callable[[], Awaitable[IntegrityReport]]


async def _default_scan_fn(*, event_since_days: int | None) -> IntegrityReport:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await scan_integrity(session, event_since_days=event_since_days)


def _render_stdout(report: IntegrityReport) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("데이터 무결성 게이트 (OPS-55·v_integrity_violations)")
    lines.append("=" * 60)
    for kind in ALL_KINDS:
        scanned = report.scanned.get(kind, 0)
        kind_violations = report.violations_by_kind(kind)
        lines.append(f"[{kind}] 스캔 {scanned}건 · 위반 {len(kind_violations)}건")
        for v in kind_violations[:10]:
            lines.append(f"    ✗ {v.identifier}: {v.detail}")
        if len(kind_violations) > 10:
            lines.append(f"    … 외 {len(kind_violations) - 10}건 (JSON 리포트 참조)")
    lines.append("-" * 60)
    total = len(report.violations)
    verdict = "정상(exit 0)" if total == 0 else f"위반 발견 {total}건(exit 1)"
    lines.append(f"결과: {verdict}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _write_json(report: IntegrityReport, path: str) -> None:
    payload = {
        "scanned": report.scanned,
        "violations": [dataclasses.asdict(v) for v in report.violations],
        "exit_code": report.exit_code,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None, *, scan_fn: ScanFn | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.integrity_violations_gate",
        description="데이터 무결성 게이트 — orphan·dangling·duplicate 6종 단일 CLI.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="JSON 리포트 저장 경로(선택).",
    )
    parser.add_argument(
        "--event-since-days",
        dest="event_since_days",
        type=int,
        default=None,
        help=(
            "⑥ EVENT_SCHEMA_INVALID 스캔을 최근 N일로 제한(기본 None=전건). attempt_event가 "
            "큰 prod에서 스캔 비용을 줄이되, 제한 시 그 범위만 판정함을 stdout에 명시한다."
        ),
    )
    args = parser.parse_args(argv)

    async def _run() -> IntegrityReport:
        fn = (
            scan_fn
            if scan_fn is not None
            else (lambda: _default_scan_fn(event_since_days=args.event_since_days))
        )
        try:
            return await fn()
        finally:
            if scan_fn is None:
                await dispose_engine()

    report = asyncio.run(_run())

    if args.event_since_days is not None:
        print(f"※ EVENT_SCHEMA_INVALID 스캔 범위: 최근 {args.event_since_days}일만(전건 아님).")
    print(_render_stdout(report))
    if args.json_path is not None:
        _write_json(report, args.json_path)
        print(f"JSON 리포트 저장: {args.json_path}")

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
