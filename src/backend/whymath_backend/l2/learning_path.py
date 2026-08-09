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

**전이 순서 제약(`PATH-03`, 2026-08)**: 위 96.4%가 지배적이었던 근본 원인은 `build_learning_
path`가 막힌 선수 집합 *내부의 직접(1-hop) 엣지만* 순서 신호로 썼다는 데 있다 — A→X→B에서
X가 막힌 선수가 아니면(즉 학생이 X는 이미 아는데 A·B는 둘 다 막힌 경우) A·B 사이에 실제로는
선수 의존이 있는데도 내부 직접 엣지가 0이라 무시됐다. `fetch_ordering_subgraph`(bounded
재귀 CTE)·`derive_ordering_edges`(순수 함수)가 *비-막힌 중간 노드를 경유하는* 전이 의존까지
`MAX_PREREQUISITE_DEPTH`(5홉) 예산 안에서 반영한다. PATH-01 리포트(`harness/
learning_path_orderability_report.py`) 기준 코퍼스 구조적 상한 예측치는 **96/356(27.0%,
직접 축) → 249/356(69.9%, 전이 축·5홉)**로 개선된다(87.1%는 무한 도달 천장이므로 목표치가
아니다 — 진짜 병렬 집합이 존재해 100%가 정답이 아닌 것과 같은 이유). `order_learning_path`·
`_tiebreak`·Kahn 루프는 이 태스크로 변경되지 않는다 — 바뀌는 것은 `build_learning_path`가
그 함수에 *공급하는 엣지의 출처*뿐이다.

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
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept import ConceptEdge
from whymath_backend.l2.prerequisite_recommendation import (
    MAX_PREREQUISITE_DEPTH,
    PrerequisiteGap,
)
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

    **PATH-03(2026-08) 참고**: `build_learning_path`는 더 이상 이 함수를 쓰지 않는다(직접
    1-hop 엣지만으로는 비-막힌 중간 노드를 경유하는 전이 의존을 못 잡음 — 모듈 docstring
    "전이 순서 제약" 절 참조). 이 함수 자체는 삭제하지 않는다 — 다른 소비처(직접 엣지만
    필요한 관측·디버그 용도)를 위해 공개 API로 남긴다.
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


async def fetch_ordering_subgraph(
    session: AsyncSession,
    concept_ids: Collection[uuid.UUID],
    *,
    max_hops: int = MAX_PREREQUISITE_DEPTH,
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """막힌 선수 집합의 각 원소에서 *비-막힌 중간 노드를 경유해도* 도달 가능한 선수 조상을
    bounded 재귀 CTE로 조회 — `derive_ordering_edges`의 원재료(가공 없는 raw 부분그래프).

    반환은 `(descendant_id, ancestor_id, hops)` 삼중항이다 — `descendant_id`는 `concept_ids`
    원소(순회 출발점), `ancestor_id`는 그로부터 `max_hops` 이내 선수 방향(`from_concept_id`)
    으로 도달한 개념(집합 안·밖 모두 포함 — 필터링은 순수 함수 `derive_ordering_edges` 책임),
    `hops`는 도달 거리(1=직접 선수). `ancestor_id`가 `concept_ids` 밖이어도(경유 중간 노드가
    막힌 선수가 아닌 경우) 그대로 반환한다 — "이 경로가 실제로 순서 제약이 되는가"는 여기서
    판단하지 않는다(fetch↔derive 관심사 분리).

    **`build_prerequisite_stmt`(prerequisite_recommendation.py) 패턴 답습**: base(hops=1)
    앵커를 `to_concept_id ∈ concept_ids`로 잡고(집합의 각 원소가 각자 독립된 BFS 출발점 —
    다중 소스 탐색), recursive 가지가 `hops+1`로 선수의 선수를 계속 따라간다
    (`WHERE hops < max_hops`로 bound). `descendant_id`는 재귀 내내 최초 출발점 그대로
    전파되므로(join 시 값 보존) 여러 출발점의 BFS가 한 쿼리에서 섞이지 않는다.

    max_hops=1이면 recursive 가지가 `hops<1`=false라 base만 반환 — 직접 1-hop 엣지와
    동일 집합(계약 보존, `fetch_internal_prerequisite_edges`의 1-hop 계약과 정합).

    **한계(모듈 docstring §전이 순서 제약 명시)**: bounded reachability는 *전이적이지 않다*
    — `max_hops` 예산을 넘는 체인은 조용히 잘린다(방어적 상한이지 완전한 도달성 보장이 아님).
    DAG 보장(`validate.py` prerequisite_cycle hard error)이라 자연 종료하나 부분 적재·미래
    데이터를 대비해 방어적으로 bound한다(`fetch_prerequisites`와 동일 근거).

    SQLAlchemy Core 쿼리빌더만(원시 SQL 0)·읽기 전용(commit 0). 실 SQL이라 단위테스트는
    `derive_ordering_edges`(순수)를 직접 호출하고, 이 좌석은 통합 테스트에서만 검증된다.
    """
    ids = list(concept_ids)
    if len(ids) < 2:
        return []  # 순서 제약은 노드 2개 이상에서만 의미가 있다 — 단락.

    base = (
        select(
            ConceptEdge.to_concept_id.label("descendant_id"),
            ConceptEdge.from_concept_id.label("ancestor_id"),
            literal(1).label("hops"),
        )
        .where(
            ConceptEdge.to_concept_id.in_(ids),
            ConceptEdge.edge_type == EdgeType.PREREQUISITE.value,
        )
        .cte(name="ordering_traversal", recursive=True)
    )
    recursive = (
        select(
            base.c.descendant_id,  # 출발점 보존 — join이 값을 바꾸지 않는다(다중 소스 분리).
            ConceptEdge.from_concept_id.label("ancestor_id"),
            (base.c.hops + 1).label("hops"),
        )
        .join(base, ConceptEdge.to_concept_id == base.c.ancestor_id)
        .where(
            ConceptEdge.edge_type == EdgeType.PREREQUISITE.value,
            base.c.hops < max_hops,
        )
    )
    traversal = base.union_all(recursive)
    stmt = select(traversal.c.descendant_id, traversal.c.ancestor_id, traversal.c.hops)
    rows = (await session.execute(stmt)).all()
    return [(descendant, ancestor, hops) for descendant, ancestor, hops in rows]


def derive_ordering_edges(
    concept_ids: Collection[uuid.UUID],
    subgraph: Sequence[tuple[uuid.UUID, uuid.UUID, int]],
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """bounded 부분그래프 → 막힌 선수 집합 *내부*의 전이 순서 엣지(순수·DB 무관).

    `subgraph`(`fetch_ordering_subgraph` 결과 또는 동형 fixture)의 각 `(descendant, ancestor,
    hops)`에서 **ancestor가 `concept_ids` 안에 있는 것만**(집합 밖 중간 노드는 조상 자체가
    아니라 경유지일 뿐 — 이 함수가 필터한다) `(ancestor, descendant)` 순서 엣지로 뒤집어
    반환한다(선수가 먼저 오는 `order_learning_path`의 `(from, to)` 계약과 정합). 자기 자신
    (`ancestor == descendant`, DAG라 발생 안 하나 방어적)은 제외한다.

    **합성 없음(acceptance⑤)**: `hops`는 필터링에만 쓰고 반환 튜플에 담기지 않는다 — 경로
    edge_strength의 곱·최소·평균 등 어떤 합성값도 만들지 않는다(순수 존재 신호만). 여러
    경로/깊이로 같은 (ancestor, descendant) 쌍이 반복 도달돼도 결과는 1건(dedup).

    반환은 `order_learning_path`가 그대로 소비할 `(from, to)` 튜플 리스트 — 결정론 정렬
    (str(ancestor), str(descendant))로 안정적 순서를 보장한다(호출부 재현성).

    PATH-01 리포트(`harness/learning_path_orderability_report.py`)의 `_reach_within_hops`+
    population 교집합 계산을 프로덕션화한 것이다 — 그 리포트는 코퍼스 JSON 위에서 이 계산의
    *관측판*을 미리 구현해 뒀다(신규 Kahn·정렬 로직 0, 이 함수도 마찬가지로 순서 관계
    *존재 여부*만 도출한다).
    """
    id_set = set(concept_ids)
    edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for descendant, ancestor, _hops in subgraph:
        if ancestor == descendant:
            continue
        if ancestor in id_set and descendant in id_set:
            edges.add((ancestor, descendant))
    return sorted(edges, key=lambda e: (str(e[0]), str(e[1])))


async def build_learning_path(
    session: AsyncSession, gaps: Sequence[PrerequisiteGap]
) -> LearningPath:
    """막힌 선수개념들 → 집합 내부 *전이* 선수 엣지 조회 → 위상정렬 학습 경로(얇은 조합).

    `gaps`(`recommend_prerequisite_gaps` 결과)의 concept_id를 모아 `fetch_ordering_subgraph`
    로 bounded 전이 부분그래프를 조회하고, `derive_ordering_edges`로 집합 내부 순서 엣지만
    도출한 뒤 `order_learning_path`로 위상정렬해 `LearningPath`를 돌려준다(PATH-03, 2026-08
    — 이전엔 `fetch_internal_prerequisite_edges`로 직접 1-hop 엣지만 썼다). 얇은 조합
    (`order_learning_path`·`_tiebreak`·Kahn 루프 변경 0 — 공급하는 엣지의 출처만 바뀐다).

    정직 기록: `fetch_ordering_subgraph`는 `MAX_PREREQUISITE_DEPTH`(5홉) 예산으로 bound된
    도달성이다 — *완전한* transitive closure가 아니라 방어적 상한이므로, 예산을 넘는 체인은
    여전히 순서를 못 잡는다(모듈 docstring "전이 순서 제약" 절 참조).
    """
    ids = [gap.concept_id for gap in gaps]
    subgraph = await fetch_ordering_subgraph(session, ids)
    edges = derive_ordering_edges(ids, subgraph)
    return order_learning_path(gaps, edges)


__all__ = [
    "LearningPath",
    "LearningStep",
    "build_learning_path",
    "derive_ordering_edges",
    "fetch_internal_prerequisite_edges",
    "fetch_ordering_subgraph",
    "order_learning_path",
]
