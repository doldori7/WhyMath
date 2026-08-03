"""L1 오개념 표적 프로브 역인덱스 조회 — mids→후보 문항 (REC-02).

WH-1 하네스 도구6 `select_probe`(`l4/misconception/probe_selection.py`)가 판별 문항을 고르려면
"이 오개념(들)을 태깅한 문항"을 조회할 좌석이 필요하다. 이 모듈은 `Problem.distractor_map`
JSONB(P3b 신규 컬럼 — 마이그레이션 0·재사용만)에서 그 역인덱스를 조회한다.

**조회 좌석이며 선택 로직은 담지 않는다**(REC-02 acceptance ①). 어떤 문항이 어떤 오개념을 더 잘
판별하는지·학생 θ에서 정보량이 얼마인지는 전혀 모른다 — 그건 L4 `probe_selection.py`(순수) 몫이다.

JSONB 매칭은 SQL 연산자(`@>`/`->>`)가 아니라 **Python 레벨 순회**로 한다(저장소 관례 —
`l4/misconception/crosslink_standard_signal.py`가 `distractor_map`을 다루는 기존 방식과 동일하며,
`@>`/`->>` 선례는 저장소에 0건이다). 코퍼스 규모(distractor_map 태깅 1,616문항)에서 전체 스캔은
비용이 낮다.

설계 분리(코드베이스 패턴 — `l1/misconception/resolve.py` 청사진 그대로):
  - **순수 코어**(`_extract_tags`·`_classify_rows`) — dict 파싱·사유 분류는 DB 무관·I/O 0.
  - **얇은 DB 시암**(`_fetch_tagged_rows`·`_fetch_attempted_ids`) — 단순 스캔 + 미응답 IN쿼리
    (빈 입력이면 즉시 빈 반환).
  - **공개 진입점**(`lookup_probe_candidates_by_mids`) — 시암 호출 후 순수 조립에 위임.

정직 회계(REC-02 acceptance ④의 원재료 — 사유별 집계 자체는 L4 `probe_supply.py`가 최종 조립):
  - `missing_difficulty`: 태깅은 됐으나 `difficulty_overall`이 NULL인 문항 수.
  - `fully_administered`: 태깅+난이도 있으나 이 학생이 이미 채점 응답(정오 확정)한 문항 수.
  - `matched_target_mids`: `target_mids` 중 코퍼스에 실제로 태깅된 것(이 집합과 `target_mids`의
    차집합이 "오개념 미태깅" 사유가 된다 — L4가 계산).

7계층: L1 데이터 기반. L4를 알지 못한다(`l4.misconception.probe_selection.ProbeCandidate`를
반환하지 않고 이 모듈 로컬 `ProbeCandidateRow`를 반환 — L4가 변환한다).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.problem import Problem as ProblemORM

__all__ = [
    "ProbeCandidateRow",
    "ProbeLookupResult",
    "lookup_probe_candidates_by_mids",
]


# ──────────────────────────────────────────────────────────────────────────
# 결과 모델 (frozen pydantic — 불변 조회 결과)
# ──────────────────────────────────────────────────────────────────────────
class ProbeCandidateRow(BaseModel):
    """조회된 후보 문항 1행 — 선택 로직 없는 원재료(L4가 `ProbeCandidate`로 변환).

    `difficulty_overall`은 이 행이 `kept`에 담기는 조건 자체가 "난이도 보유"라 실제로는
    항상 값이 있다(None 허용은 방어적 타입).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: uuid.UUID
    difficulty_overall: float | None
    irt_difficulty_b: float | None
    irt_a: float | None
    misconception_tags: frozenset[str]


class ProbeLookupResult(BaseModel):
    """`lookup_probe_candidates_by_mids` 결과 — 후보 + 정직 회계 원재료."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kept: tuple[ProbeCandidateRow, ...]
    missing_difficulty: int
    fully_administered: int
    matched_target_mids: frozenset[str]


# ──────────────────────────────────────────────────────────────────────────
# 순수 코어 — dict 파싱·사유 분류(DB 무관·I/O 0)
# ──────────────────────────────────────────────────────────────────────────
def _extract_tags(distractor_map: list[dict[str, object]] | None) -> frozenset[str]:
    """`distractor_map`(raw ORM JSONB — `DistractorEntry.model_dump()` 형태) → mid 집합.

    ORM에서 읽은 원본은 파싱된 pydantic 모델이 아니라 dict 리스트이므로 `.get()`으로 안전하게
    읽는다(속성 접근이 아님 — `schema.Problem.distractor_map`(파싱된 축)과는 다른 경로).
    `misconception_id`가 없거나 문자열이 아닌 엔트리는 방어적으로 건너뛴다(형태 오염 방어).
    """
    if not distractor_map:
        return frozenset()
    tags: set[str] = set()
    for entry in distractor_map:
        mid = entry.get("misconception_id")
        if isinstance(mid, str) and mid:
            tags.add(mid)
    return frozenset(tags)


def _classify_rows(
    rows: Sequence[tuple[uuid.UUID, frozenset[str], float | None, float | None, float | None]],
    target_mids: frozenset[str],
    attempted_ids: frozenset[uuid.UUID],
) -> tuple[list[ProbeCandidateRow], int, int, frozenset[str]]:
    """target_mids와 교차하는 행들을 사유별로 분류(순수·결정론).

    입력 `rows`는 이미 "태그가 target_mids와 교차하는" 행만 담고 있다고 가정한다(호출자가
    필터). 각 행은 **난이도 부재 → 전부 응답함 → 유지** 순서로 배타 분류한다(먼저 걸린 사유
    하나에만 계상). `matched_target_mids`는 사유와 무관하게 "코퍼스에 실제로 태깅된" target_mids
    전체를 모은다(missing_difficulty/fully_administered로 빠진 행의 mid도 "미태깅"은 아니다).
    """
    kept: list[ProbeCandidateRow] = []
    missing_difficulty = 0
    fully_administered = 0
    matched: set[str] = set()
    for problem_id, tags, difficulty_overall, irt_difficulty_b, irt_a in rows:
        matched |= tags & target_mids
        if difficulty_overall is None:
            missing_difficulty += 1
            continue
        if problem_id in attempted_ids:
            fully_administered += 1
            continue
        kept.append(
            ProbeCandidateRow(
                problem_id=problem_id,
                # Numeric(3,2) 컬럼은 Decimal로 올 수 있음 — float 명시 캐스팅(api/me.py 선례).
                difficulty_overall=float(difficulty_overall),
                irt_difficulty_b=irt_difficulty_b,
                irt_a=irt_a,
                misconception_tags=tags,
            )
        )
    return kept, missing_difficulty, fully_administered, frozenset(matched)


# ──────────────────────────────────────────────────────────────────────────
# 얇은 DB 시암 — 단순 스캔 + 미응답 IN쿼리(N+1 회피·읽기 전용)
# ──────────────────────────────────────────────────────────────────────────
async def _fetch_tagged_rows(session: AsyncSession) -> Sequence[Row[Any]]:
    """`distractor_map` 보유 문항 전체 스캔 — mid 매칭은 호출자가 Python에서 수행.

    저장소에 JSONB `@>`/`->>` 연산자 선례가 0건이라(전부 Python 순회 관례), SQL은 존재 필터만
    맡긴다. 코퍼스 규모(태깅 1,616문항)에서 단일 스캔 비용은 낮다.
    """
    stmt = select(
        ProblemORM.problem_id,
        ProblemORM.distractor_map,
        ProblemORM.difficulty_overall,
        ProblemORM.irt_difficulty_b,
        ProblemORM.irt_a,
    ).where(ProblemORM.distractor_map.isnot(None))
    result = await session.execute(stmt)
    return result.all()


async def _fetch_attempted_ids(
    session: AsyncSession, user_id: uuid.UUID, problem_ids: frozenset[uuid.UUID]
) -> frozenset[uuid.UUID]:
    """이 학생이 이미 채점 응답(정오 확정)한 문항 id 집합 — `api/me.py` IRT CAT 선례 그대로.

    `problem_ids`가 빈 집합이면 쿼리 없이 즉시 빈 집합(빈 IN 쿼리 회피).
    """
    if not problem_ids:
        return frozenset()
    stmt = select(ProblemAttempt.problem_id).where(
        ProblemAttempt.user_id == user_id,
        ProblemAttempt.problem_id.in_(problem_ids),
        ProblemAttempt.is_correct.isnot(None),
    )
    result = await session.execute(stmt)
    return frozenset(pid for (pid,) in result.all() if pid is not None)


# ──────────────────────────────────────────────────────────────────────────
# 공개 진입점
# ──────────────────────────────────────────────────────────────────────────
async def lookup_probe_candidates_by_mids(
    session: AsyncSession, *, user_id: uuid.UUID, target_mids: frozenset[str]
) -> ProbeLookupResult:
    """target_mids를 태깅한 후보 문항을 역인덱스 조회(미응답 제외·난이도 보유만·읽기 전용).

    `target_mids`가 비면 쿼리 없이 즉시 빈 결과. 아니면 태깅 문항 전체를 스캔해 태그를
    한 번만 파싱하고, target_mids와 교차하는 행만 추려 그 문항 id로만 미응답 여부를
    조회한 뒤(2번째 쿼리), 순수 `_classify_rows`로 최종 분류한다.
    """
    if not target_mids:
        return ProbeLookupResult(
            kept=(),
            missing_difficulty=0,
            fully_administered=0,
            matched_target_mids=frozenset(),
        )

    raw_rows = await _fetch_tagged_rows(session)
    parsed_rows = [
        (problem_id, _extract_tags(distractor_map), difficulty_overall, irt_difficulty_b, irt_a)
        for problem_id, distractor_map, difficulty_overall, irt_difficulty_b, irt_a in raw_rows
    ]
    matched_rows = [row for row in parsed_rows if not row[1].isdisjoint(target_mids)]
    matched_problem_ids = frozenset(row[0] for row in matched_rows)

    attempted_ids = await _fetch_attempted_ids(session, user_id, matched_problem_ids)
    kept, missing_difficulty, fully_administered, matched_target_mids = _classify_rows(
        matched_rows, target_mids, attempted_ids
    )
    return ProbeLookupResult(
        kept=tuple(kept),
        missing_difficulty=missing_difficulty,
        fully_administered=fully_administered,
        matched_target_mids=matched_target_mids,
    )
