"""원자 축(atom axis) 런타임 접근 좌석 — async 세션 단일 엔진 조회·조인 (ARCH-13).

`atom_node_projection.fetch_atom_node_meta`(sync psycopg·검색 좌석용)의 **async 쌍**이다. 두 개를
나란히 두는 이유는 소비 평면이 다르기 때문이다:
  - **sync**: L1 검색 좌석(`retrieval.search_atoms`)이 이미 블로킹 인덱스 위에서 돌아 같은 sync
    엔진에서 enrichment를 한다 — 그대로 둔다.
  - **async**(이 모듈): L2 추천 좌석은 `AsyncSession`으로 `concept`/`concept_edge`를 읽는다. 여기서
    메타만 *다른 엔진*으로 가져오면 한 요청 안에서 두 엔진이 code 문자열로 조인되는
    **교차 엔진 조인**이 된다 — 원자 축과 구 437이 같은 테이블에 code로 병존하므로(MEMORY 슬 S0-1
    "437과 원자는 concept/concept_edge 동일 테이블 code 병존") 그 조인은 *축이 어긋나도 조용히
    성립*한다. ARCH-13은 이 지점을 없앤다.

선례(신규 패턴 0): `l1/skill_graph/resolve.py::get_behavior_areas`가 이미 async 세션에서
`AtomNode`를 직접 읽고, `l1/concept_visualization/overlay.py::get_visualizability`가 같은 code-PK
런타임 조회 패턴이다. `AtomNode` 자체도 "backend async-PG 조인으로 하기 위한 백킹"으로 설계됐다
(`atom_node_projection` 모듈 docstring).

────────────────────────────────────────────────────────────────────────────
"미스"의 의미 — 축 밖(off-axis)이지 단순 누락이 아니다
────────────────────────────────────────────────────────────────────────────
runtime truth source는 **원자 백본 단일**이다(S0-4·Kiki 결정·구 437은 `legacy_snapshot`). 따라서
`atom_node`에 없는 code는 "메타가 아직 안 붙은 원자"가 아니라 **원자 축 밖의 code**(구 437 UC 등)로
읽어야 한다. 이 모듈의 반환 dict에서 빠진 code는 그런 의미이며, 호출자는 그것을 *조용히 None으로
흘리지 말고* 제외 사유로 계상해야 한다(`l2/axis_exclusions.py`·CLAUDE.md "침묵 실패 금지").

redaction(우선순위 #2): 노출 컬럼은 안전 메타 3종(name_ko·subject_area·review_status)뿐 —
`atom_node`에 본문 컬럼(core_proposition·description·formal_definition)이 *없어* 조회 자체가
구조적으로 불가하다.

7계층: L1 데이터 기반의 런타임 조회·조인 재료 제공. 축을 근거로 무엇을 버릴지는 소비처(L2)가 정한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.l1.atom_graph.atom_node_projection import AtomNodeMeta

if TYPE_CHECKING:
    # `SQLColumnExpression`은 Core 컬럼과 ORM 매핑 속성(`InstrumentedAttribute`)의 공통 상위다 —
    # 호출부가 `Concept.code`(ORM 속성)를 그대로 넘길 수 있게 이 타입으로 받는다.
    from sqlalchemy.sql.elements import SQLColumnExpression
    from sqlalchemy.sql.selectable import Select

# 원자 축 *안전* 메타 컬럼 — `AtomNodeMeta` 필드 순서와 1:1 대응(조인 SELECT가 이 순서로 언팩).
# 본문 컬럼은 `atom_node`에 존재하지 않으므로 이 튜플에 담길 수조차 없다(redaction·구조적 차단).
ATOM_AXIS_META_COLUMNS = (AtomNode.name_ko, AtomNode.subject_area, AtomNode.review_status)

# `Select`의 행 타입 파라미터는 불변(invariant)이라 구체 튜플을 넓은 타입으로 못 받는다 →
# 제네릭으로 통과시켜 호출부의 정밀한 행 타입을 보존한다(`.outerjoin()`이 Self를 돌려주므로 성립).
_TP = TypeVar("_TP", bound="tuple[Any, ...]")


def atom_axis_outerjoin(stmt: Select[_TP], code_column: SQLColumnExpression[str]) -> Select[_TP]:
    """`code_column` ↔ `atom_node.code` **LEFT OUTER JOIN**을 붙여 축 판정을 쿼리 안으로 옮긴다.

    축 울타리(원자 축 밖 제외)는 이 조인이 **단일 진실**이다 — 파이썬에서 code 접두사를 추측하거나
    별도 엔진을 왕복하지 않는다(ARCH-13의 본론).

    **INNER가 아니라 OUTER인 이유**: INNER면 축 밖 행이 SQL 단계에서 사라져 "몇 건이 왜 빠졌는지"를
    셀 수 없다. 축 판정은 쿼리가 하고(단일 출처), 제외와 계상은 호출자가 한다(표면화) — 조용한
    소실을 만들지 않기 위한 의도적 분업이다(CLAUDE.md "침묵 실패 금지").

    호출자는 `ATOM_AXIS_META_COLUMNS`를 SELECT 목록에 함께 넣어 `atom_meta_from_row`로 복원한다.
    """
    return stmt.outerjoin(AtomNode, AtomNode.code == code_column)


def atom_meta_from_row(
    name_ko: str | None, subject_area: str | None, review_status: str | None
) -> AtomNodeMeta | None:
    """OUTER JOIN 결과 3열 → `AtomNodeMeta`. **전부 NULL이 아니라 `name_ko` NULL = 축 밖**.

    `atom_node.name_ko`·`review_status`는 NOT NULL이므로 조인이 성립했다면 둘 다 값이 있다. 즉
    `name_ko is None`은 "매칭 행 없음"(=원자 축 밖)과 정확히 동치다 — `subject_area`는 원래
    nullable이라 축 판정 근거로 쓸 수 없다(단원/소단원/일부 원자에서 비어 있음).
    """
    if name_ko is None or review_status is None:
        return None
    return AtomNodeMeta(name_ko=name_ko, subject_area=subject_area, review_status=review_status)


async def fetch_atom_axis_meta(
    session: AsyncSession, codes: Sequence[str]
) -> dict[str, AtomNodeMeta]:
    """code 목록 → 원자 축 안전 메타 dict (**async 세션 단일 IN 조회**·N+1 0).

    `fetch_atom_node_meta`(sync)와 같은 컬럼·같은 반환 계약이나 호출 세션의 엔진을 그대로 쓴다 —
    별도 sync 엔진 왕복(`asyncio.to_thread`)과 교차 엔진 조인이 사라진다.

    **결과에 없는 code = 원자 축 밖**(위 모듈 docstring). 입력이 비면 쿼리를 생략하고 빈 dict.
    """
    ids = [str(code) for code in codes]
    if not ids:
        return {}
    stmt = select(AtomNode.code, *ATOM_AXIS_META_COLUMNS).where(AtomNode.code.in_(ids))
    rows = (await session.execute(stmt)).all()
    return {
        row.code: AtomNodeMeta(
            name_ko=row.name_ko,
            subject_area=row.subject_area,
            review_status=row.review_status,
        )
        for row in rows
    }


__all__ = [
    "ATOM_AXIS_META_COLUMNS",
    "atom_axis_outerjoin",
    "atom_meta_from_row",
    "fetch_atom_axis_meta",
]
