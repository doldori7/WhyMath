"""L2 학습 경로 생성 — 막힌 선수개념들의 *선수 위상정렬*(근본→말단) 순서화, 단 **조건부**다.

개념그래프 소비 아크의 *학습 경로* 좌석이다. 직전 슬라이스 `recommend_prerequisite_gaps`
(막힌 선수 추천)가 "어떤 선수개념들이 막혔는지"를 weakness 정렬로 골랐다면, 이 좌석은 그
막힌 선수개념들 *사이의 선수 의존*을 위상정렬(topological sort)해 **"무엇부터 복습해야
하는가 — 근본 선수 먼저, 그 위에 쌓이는 말단 나중"**의 학습 *순서*를 돌려준다.

**무조건적 서술이 아니다(2026-08 실측, `PATH-02`)**: 엔드포인트 기본값(`max_depth=1`)에서
막힌 선수 집합 *내부*의 직접 선수 엣지가 0인 사례가 **96.4%**다 — 그 경우 Kahn의 in-degree가
전부 0이라 실제로는 `_tiebreak`만으로 정렬되고(`ordering_basis="tiebreak_only"`), "위상정렬"은
남은 3.6%에서만 비자명하게 작동한다(`ordering_basis="topological"`). `LearningPath.
ordering_edge_count`·`ordering_basis`가 이 구분을 응답에 정직하게 노출한다 — 둘 다
`is_cycle_residual`과 대칭인 정직 표기이며(사이클은 실제 발생 0건인 방어적 축, 제약 0은
지배적 축), 결정 로직(`_tiebreak`·Kahn 루프·엣지 공급)은 이 태스크로 변경되지 않는다.

────────────────────────────────────────────────────────────────────────────
왜 위상정렬인가 — depth 정렬과 다르다
────────────────────────────────────────────────────────────────────────────
`recommend_prerequisite_gaps`의 `depth`는 *원래 후행 개념 C로부터의 거리*다(1=직접 선수·
2=선수의 선수…). 하지만 막힌 선수들 *사이에도* 선수 의존이 있다 — 예컨대 C의 직접 선수
두 개 A·B가 있고 A가 B의 선수라면(A→B), A를 먼저 다져야 B가 선다. depth만으로는 이
*막힌 선수 집합 내부의 의존 순서*를 못 짚는다(둘 다 depth=1일 수 있다).

그래서 막힌 선수들을 노드로, 그들 *사이*의 직접 선수 엣지를 간선으로 두고 **Kahn 위상정렬**
한다. in-degree 0(선수 의존이 없는 *근본*) 노드를 먼저 방출하고, 그 위에 의존하던 노드를
뒤에 방출한다. 이는 LTHC(기초 우선)의 기계적 구현 — 근본 결손을 먼저 메우고 그 위에
쌓는다.

────────────────────────────────────────────────────────────────────────────
엣지 방향 — from(선수)→to(후행)에서 to의 in-degree 증가
────────────────────────────────────────────────────────────────────────────
`concept_edge`는 `from_concept_id`가 `to_concept_id`의 *선수*다(`EdgeType.PREREQUISITE`).
따라서 막힌 선수 집합 내부에서 `(from, to)` 엣지는 "from을 알아야 to를 안다"를 뜻한다.
위상정렬에서 **to의 in-degree를 올린다** — in-degree 0 = 선수 의존이 없는 근본이라 먼저
방출된다(근본→말단). 집합 *밖*으로 나가는 엣지(끝점이 막힌 선수 아님)는 무시한다 — 이
경로는 *막힌 선수들 사이*의 순서만 다룬다.

────────────────────────────────────────────────────────────────────────────
사이클 방어 — 정직한 잔여(honest residual)
────────────────────────────────────────────────────────────────────────────
선수 그래프는 데이터셋 v1에서 *비순환 보장*이다(`validate.py` prerequisite_cycle hard
error). 그래도 부분 적재·미래 데이터를 대비해 **방어적으로** 사이클을 처리한다: Kahn이
모든 노드를 방출하지 못하면(잔여 = 사이클에 속한 노드) 그 잔여를 *조용히 버리지 않고*
deterministic 순서로 append하며 `is_cycle_residual=True`·`has_cycle=True`로 표시한다.
누락 0(전 노드 등장)·정직 표시(CLAUDE.md "환각 발견 시 조용히 넘어가지 말고 로그").

────────────────────────────────────────────────────────────────────────────
redaction·노출 계약 (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
`LearningStep`은 *안전 표시·구조 메타 필드*만 담는다(concept_code·concept_name·weakness·
depth·edge_strength). **description·formal_definition·intuitive_explanation 슬롯이 *없다*
(frozen pydantic·삼중 방어). 이 좌석은 학생 직접 노출이 아니라 *내부 조회·순서화 좌석*이다.

7계층: L2 학습자 모델이 L1 데이터(concept_edge ORM)를 *조회*(L_n→L_{n-1} 허용). 순수 코어
(`order_learning_path`)는 DB·async 없이 Sequence 주입(L4 코칭 미러). ORM 쿼리빌더만
(원시 SQL 0·읽기 전용·commit 0). L4 코칭·L5 노출은 부착하지 않는다(역방향 의존 회피).
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept import ConceptEdge
from whymath_backend.l2.prerequisite_recommendation import PrerequisiteGap
from whymath_backend.schema.enums import EdgeType


class LearningStep(BaseModel):
    """학습 경로의 단일 단계 — 위상정렬된 막힌 선수개념 1건 + 순서·구조 메타.

    `position`은 0-based 학습 순서(0=가장 먼저 다질 근본 선수)다. `is_cycle_residual`은
    이 노드가 위상정렬로 방출되지 못한 *사이클 잔여*임을 표시한다(정직한 잔여·기본 False).
    **본문(description·formal_definition·intuitive_explanation) 슬롯이 없다** — frozen
    스키마에 *슬롯 자체가 없어* 구조적으로 흐를 수 없다(redaction·노출 계약).
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(description="0-based 학습 순서(0=가장 먼저 다질 근본 선수).")
    concept_id: uuid.UUID = Field(description="막힌 선수개념 id(backend `concept` UUID PK).")
    concept_code: str | None = Field(
        default=None, description="선수개념 코드(=UC·개념그래프 키). orphan이면 null."
    )
    concept_name: str | None = Field(
        default=None, description="선수개념 표시명(안전 메타·본문 아님). 미적재 시 null."
    )
    weakness: float | None = Field(
        default=None,
        description="두 신호(bkt·irt) 중 최저값(막힘 정도). 미측정이면 null.",
    )
    depth: int = Field(
        description="원래 후행 개념으로부터의 선수 거리(1=직접 선수). 그래프 구조 메타."
    )
    edge_strength: float | None = Field(
        default=None,
        description="선수관계 강도 [0,1](강한 선수일수록 결정적). 미기재 시 null.",
    )
    is_cycle_residual: bool = Field(
        default=False,
        description="위상정렬로 방출되지 못한 사이클 잔여 노드 표시(정직·기본 False).",
    )


class LearningPath(BaseModel):
    """막힌 선수개념들의 위상정렬된 학습 경로 — 근본(먼저)→말단(나중) 순서.

    `steps`는 position 0..n-1 연속의 `LearningStep` 튜플이다. `has_cycle`이 True면
    선수 그래프에 사이클이 있어 일부 노드가 위상정렬로 방출되지 못하고 잔여로 append됐음을
    뜻한다(정직 표시·기본 False). frozen·본문 슬롯 없음(redaction 계약).

    `ordering_edge_count`·`ordering_basis`는 `has_cycle`과 대칭인 정직 표기다(`PATH-02`) —
    `steps`의 순서 *자체*만 봐서는 "제약이 있어 위상정렬됐는지" vs "제약이 0이라 tiebreak만
    적용됐는지"를 구분할 수 없다(두 경우 우연히 같은 순서가 나올 수 있음). 기본값
    (`max_depth=1`)에서는 96.4%가 `tiebreak_only`다.
    """

    model_config = ConfigDict(frozen=True)

    steps: tuple[LearningStep, ...] = Field(
        description="위상정렬된 학습 단계들(position 0..n-1 연속·근본 먼저)."
    )
    has_cycle: bool = Field(
        default=False,
        description="선수 그래프에 사이클이 있어 잔여 노드가 발생했는지(정직 표시).",
    )
    ordering_edge_count: int = Field(
        default=0,
        description=(
            "Kahn이 실제로 소비한 집합 내부 제약 엣지 수(집합 밖·중복 엣지 제외 후). "
            "0이면 순서가 전부 _tiebreak로만 정해졌다는 뜻."
        ),
    )
    ordering_basis: Literal["topological", "tiebreak_only", "empty"] = Field(
        default="empty",
        description=(
            "'topological'=제약 엣지 ≥1개가 순서에 실제로 반영됨 · "
            "'tiebreak_only'=제약 엣지 0(steps는 있음, weakness 등 tiebreak만으로 정렬) · "
            "'empty'=steps 자체가 없음(입력 gaps 0건)."
        ),
    )


def _tiebreak(gap: PrerequisiteGap) -> tuple[int, float, int, float, str]:
    """Kahn 풀·잔여 정렬의 완전 결정론 키 — 가장 약한 *근본* 선수를 먼저(LTHC).

    튜플 = (weakness None 여부 0/1, weakness asc, depth 음수화(desc), edge_strength None
    여부 표현(desc·None은 뒤), str(concept_id)). 즉:
      ① weakness None을 가장 뒤로(`(1, 0.0)` vs `(0, weakness)` — 측정 있는 약한 선수 우선).
      ② depth desc — `recommend_prerequisite_gaps`의 depth *asc*와 **반대**다. 추천은 가까운
         (직접) 선수를 먼저 보여주지만, 학습 *순서*는 깊은(근본) 선수를 먼저 다져야 하므로
         depth가 큰(더 근본인) 쪽을 앞으로 보낸다 — 음수화로 desc.
      ③ edge_strength desc — 강한 선수(더 결정적)를 먼저·None은 가장 뒤로.
      ④ str(concept_id) — 최종 결정론 tie-break.

    in-degree 0 풀에서 이 키로 정렬해 매번 1개를 방출하면 "가장 약하고 근본인 선수 먼저"가
    된다. 위상정렬 구조(엣지 제약)는 이 키보다 *우선*한다 — 키는 풀 안의 동률 선택만 가른다.
    """
    weak_present = 0 if gap.weakness is not None else 1
    weak_value = gap.weakness if gap.weakness is not None else 0.0
    depth_desc = -gap.depth  # depth desc — 깊은(근본) 선수 먼저(추천의 depth asc와 반대).
    # edge_strength desc·None은 뒤로 — None이면 가장 약하게(+inf) 두어 마지막으로 민다.
    strength_desc = -gap.edge_strength if gap.edge_strength is not None else float("inf")
    return (weak_present, weak_value, depth_desc, strength_desc, str(gap.concept_id))


def order_learning_path(
    gaps: Sequence[PrerequisiteGap],
    internal_edges: Sequence[tuple[uuid.UUID, uuid.UUID]],
) -> LearningPath:
    """막힌 선수개념들을 *집합 내부 선수 엣지*로 Kahn 위상정렬 — 근본 먼저·순수·결정론.

    순수 코어(L4 코칭 미러·DB/async 없음). `gaps`는 막힌 선수개념 목록(`recommend_
    prerequisite_gaps` 결과)·`internal_edges`는 그 집합 *내부*의 `(from=선수, to=후행)`
    직접 선수 엣지(`fetch_internal_prerequisite_edges` 결과)다.

    알고리즘:
      ① **dedup** — `gaps`를 순회하며 같은 concept_id의 *첫 등장*만 유지(순서 보존).
      ② **adj·indeg 구성** — 모든 node를 indeg 0으로 초기화. 각 `(frm, to)` 엣지는
         **frm·to 둘 다 node 집합 안에 있을 때만** 처리(집합 밖 엣지 무시)·중복 엣지는
         skip(indeg 두 번 안 올림). **from→to에서 to의 indeg 증가**(in-degree 0 = 선수
         의존 없는 근본).
      ③ **Kahn** — in-degree 0 풀을 매번 `_tiebreak`로 정렬해 1개씩 방출(가장 약한 근본
         먼저)·방출 시 후행 indeg 감소·0 되면 풀 추가. position 0-based 연속 부여.
      ④ **잔여(사이클)** — Kahn이 못 방출한 노드를 `_tiebreak` 정렬해 deterministic
         append·`is_cycle_residual=True`·`LearningPath.has_cycle=True`(정직·누락 0).

    완전 결정론(같은 입력 → 항상 같은 steps). 빈 입력 → 빈 steps·has_cycle False·
    ordering_basis="empty".

    `ordering_edge_count`·`ordering_basis`(`PATH-02`)는 위 ②에서 이미 구성된 `adj`에서
    파생만 한다(신규 순회·쿼리 0, `_tiebreak`·Kahn 루프·엣지 공급 로직 변경 0) —
    `sum(len(v) for v in adj.values())`가 집합 밖·중복 엣지가 이미 걸러진 뒤의 실제 소비
    제약 엣지 수다.
    """
    # ① dedup — 같은 concept_id 첫 등장만(순서 보존). dict가 삽입 순서를 보존한다.
    nodes: dict[uuid.UUID, PrerequisiteGap] = {}
    for gap in gaps:
        if gap.concept_id not in nodes:
            nodes[gap.concept_id] = gap

    # ② adj·indeg 구성 — 모든 node indeg 0 초기화·node 집합 밖 엣지·중복 엣지 방어.
    adj: dict[uuid.UUID, set[uuid.UUID]] = {cid: set() for cid in nodes}
    indeg: dict[uuid.UUID, int] = {cid: 0 for cid in nodes}
    for frm, to in internal_edges:
        if frm not in nodes or to not in nodes:
            continue  # 집합 밖 엣지(끝점이 막힌 선수 아님) 무시 — 이 경로는 내부 순서만.
        if to in adj[frm]:
            continue  # 중복 엣지 방어 — 같은 (frm,to)가 indeg를 두 번 못 올린다.
        adj[frm].add(to)
        indeg[to] += 1  # from→to에서 to의 indeg 증가(in-degree 0 = 근본 → 먼저 방출).

    # ③ Kahn — in-degree 0 풀에서 매번 _tiebreak로 정렬해 1개씩 방출(가장 약한 근본 먼저).
    pool: list[uuid.UUID] = [cid for cid in nodes if indeg[cid] == 0]
    steps: list[LearningStep] = []
    position = 0
    while pool:
        pool.sort(key=lambda cid: _tiebreak(nodes[cid]))
        cid = pool.pop(0)  # 가장 약한 근본(결정론) 1개 방출.
        steps.append(_to_step(nodes[cid], position, is_cycle_residual=False))
        position += 1
        for nxt in sorted(adj[cid], key=lambda c: str(c)):  # 결정론 순회.
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                pool.append(nxt)

    # ④ 잔여(사이클) — Kahn이 못 방출한 노드를 deterministic append(정직·누락 0).
    emitted = {step.concept_id for step in steps}
    residual = [nodes[cid] for cid in nodes if cid not in emitted]
    has_cycle = bool(residual)
    for gap in sorted(residual, key=_tiebreak):
        steps.append(_to_step(gap, position, is_cycle_residual=True))
        position += 1

    # ⑤ ordering_edge_count·ordering_basis(PATH-02) — ②의 adj에서 파생만, 신규 순회 0.
    edge_count = sum(len(v) for v in adj.values())
    if not steps:
        ordering_basis: Literal["topological", "tiebreak_only", "empty"] = "empty"
    elif edge_count > 0:
        ordering_basis = "topological"
    else:
        ordering_basis = "tiebreak_only"

    return LearningPath(
        steps=tuple(steps),
        has_cycle=has_cycle,
        ordering_edge_count=edge_count,
        ordering_basis=ordering_basis,
    )


def _to_step(gap: PrerequisiteGap, position: int, *, is_cycle_residual: bool) -> LearningStep:
    """`PrerequisiteGap` → `LearningStep`(안전 표시·구조 메타만 전사·본문 슬롯 없음)."""
    return LearningStep(
        position=position,
        concept_id=gap.concept_id,
        concept_code=gap.concept_code,
        concept_name=gap.concept_name,
        weakness=gap.weakness,
        depth=gap.depth,
        edge_strength=gap.edge_strength,
        is_cycle_residual=is_cycle_residual,
    )


async def fetch_internal_prerequisite_edges(
    session: AsyncSession, concept_ids: Collection[uuid.UUID]
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """주어진 concept_id 집합 *내부*의 직접 선수 엣지(from·to 둘 다 집합 안)만 조회.

    `concept_ids`(막힌 선수들)의 *양 끝점이 모두 집합 안*인 `EdgeType.PREREQUISITE` 엣지의
    `(from_concept_id, to_concept_id)`를 돌려준다. 집합 밖으로 나가는 엣지는 SQL where에서
    이미 배제된다(`from.in_(ids) AND to.in_(ids)`). 노드 2개 미만이면 내부 엣지가 있을 수
    없어 단락한다(빈 리스트).

    SQLAlchemy Core 쿼리빌더만(원시 SQL 0)·읽기 전용(commit 0). 실 SQL이라 단위테스트는
    `order_learning_path`(순수)를 직접 호출하고, 이 좌석은 통합 테스트에서만 검증된다.
    """
    ids = list(concept_ids)
    if len(ids) < 2:
        return []  # 내부 엣지는 노드 2개 이상에서만 가능 — 단락.
    stmt = select(ConceptEdge.from_concept_id, ConceptEdge.to_concept_id).where(
        ConceptEdge.edge_type == EdgeType.PREREQUISITE.value,
        ConceptEdge.from_concept_id.in_(ids),
        ConceptEdge.to_concept_id.in_(ids),
    )
    rows = (await session.execute(stmt)).all()
    return [(frm, to) for frm, to in rows]


async def build_learning_path(
    session: AsyncSession, gaps: Sequence[PrerequisiteGap]
) -> LearningPath:
    """막힌 선수개념들 → 집합 내부 선수 엣지 조회 → 위상정렬 학습 경로(얇은 조합).

    `gaps`(`recommend_prerequisite_gaps` 결과)의 concept_id를 모아 `fetch_internal_
    prerequisite_edges`로 집합 *내부* 선수 엣지를 조회하고, `order_learning_path`로
    위상정렬해 `LearningPath`를 돌려준다. 얇은 조합(신규 로직 0).

    정직 기록: 여기서 쓰는 내부 엣지는 막힌 선수 집합 *내* 직접 엣지만이다 — 두 막힌 선수
    사이에 *비-막힌(weak 아닌)* 중간 노드를 경유하는 transitive 의존은 반영하지 않는다
    (예: A→X→B에서 X가 막힌 선수가 아니면 A·B 사이 순서는 못 잡는다). 후속 범위.
    """
    ids = [gap.concept_id for gap in gaps]
    edges = await fetch_internal_prerequisite_edges(session, ids)
    return order_learning_path(gaps, edges)


__all__ = [
    "LearningPath",
    "LearningStep",
    "build_learning_path",
    "fetch_internal_prerequisite_edges",
    "order_learning_path",
]
