"""[LEGACY_SNAPSHOT · audit_only] 구 437 :Concept Neo4j 적재 격하(S0-4c).

런타임 읽기 0 — backend는 pgvector 단일 평면(런타임 Neo4j 드라이버 도입 0·`retrieval.py` 참조).
:Atom이 runtime 그래프이고 :Concept는 audit 전용 스냅샷이다. 물리 삭제 불요(격하만·행 보존).
상세: docs/data/atom_graph_v1.md·docs/handoff/atom_backbone_next_session.md §5.5.

개념 그래프 → Neo4j 멱등 적재(단계 7).

정본: docs/data/concept_graph.md §2.3(Cypher DDL)·§4 단계 7(저장·멱등 MERGE)·
§5 #9(적재 멱등성 invariant)·§6.1(접속 env). ncic/load.py(PG 적재)의 *지연 import +
env 접속 + create_all 멱등* 패턴을 Neo4j로 미러링한다.

설계 핵심
---------
1. **지연 import**: `neo4j` 드라이버는 `[neo4j]` extra라 이 모듈은 *extra 없이도 import 가능*
   해야 한다(write_graph_json 등 다른 사용자). `neo4j` import는 `connect_driver` 안에서만 한다.
2. **드라이버 주입**: `load_graph(...)`는 `driver` 인자를 받는다 — 단위테스트가 FAKE 드라이버를
   주입해 *실 Neo4j 없이* 발행 Cypher를 검증한다(미설치 환경에서도 import·테스트 가능).
3. **멱등(§5 #9)**: 노드는 `MERGE (c:Concept {concept_id}) SET c += $props`, 엣지는 양끝
   `MATCH` 후 `MERGE (src)-[r:TYPE]->(dst) SET r += $props`. 재실행해도 노드·엣지 수 불변.
4. **제약(§2.3)**: `CREATE CONSTRAINT concept_id_unique IF NOT EXISTS`(멱등 DDL)를 적재 전 보장.
5. **reltype 안전**: Cypher 관계 타입은 파라미터화 불가 → 닫힌 `Relation` enum(7종 allowlist)에서만
   대문자 reltype을 끌어온다(임의 문자열 주입 불가). 값은 enum 검증을 거친 것만 들어온다.
6. **전량 적재 + review_status 플래그**: pending 노드도 *적재*하되 `review_status` 속성으로 표식해
   끝점이 pending인 엣지의 고아를 막는다(게이팅은 적재가 아니라 *조회/후속*). §4 분포: reviewed 114·
   pending 289.

법적·redaction(CLAUDE.md·§3): `graph.json`은 슬라이스 1 정형화에서 이미 청결(description·
formal_definition 슬롯 부재). 이 로더는 모델 dump 키만 적재하므로 본문이 *구조적으로* 재유입될 수
없다. 시크릿 0 — 접속 자격은 env(`NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD`) 전용·하드코딩 금지.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from data_pipeline.concept_graph.models import Relation
from data_pipeline.concept_graph.transform import TransformResult

logger = logging.getLogger("data_pipeline.concept_graph.load")

# Neo4j 접속 env 키(§6.1). 시크릿은 코드에 두지 않고 *전적으로* env에서 읽는다(CLAUDE.md 보안).
ENV_URI = "NEO4J_URI"
ENV_USER = "NEO4J_USER"
ENV_PASSWORD = "NEO4J_PASSWORD"

# 노드 라벨·제약명(§2.3 DDL과 1:1). 제약명을 상수로 고정해 통합테스트가 존재를 단언한다.
NODE_LABEL = "Concept"
CONSTRAINT_NAME = "concept_id_unique"

# 제약 DDL(§2.3) — IF NOT EXISTS라 재실행 멱등.
CONSTRAINT_CYPHER = (
    f"CREATE CONSTRAINT {CONSTRAINT_NAME} IF NOT EXISTS "
    f"FOR (c:{NODE_LABEL}) REQUIRE c.concept_id IS UNIQUE"
)

# 조회 인덱스(§2.3) — 운영 조회용. 멱등 DDL.
INDEX_CYPHERS: tuple[str, ...] = (
    f"CREATE INDEX concept_domain IF NOT EXISTS FOR (c:{NODE_LABEL}) ON (c.domain)",
    f"CREATE INDEX concept_name_ko IF NOT EXISTS FOR (c:{NODE_LABEL}) ON (c.name_ko)",
)

# 노드 멱등 upsert — concept_id로 MERGE 후 나머지 속성 일괄 SET(`+=` 병합).
NODE_MERGE_CYPHER = f"MERGE (c:{NODE_LABEL} {{concept_id: $concept_id}})\n" "SET c += $props"

# 관계 reltype은 파라미터화 불가 → enum allowlist에서만 포맷(주입 차단). 끝점은 MATCH(없으면 미생성)
# — 노드를 먼저 전량 적재하므로 정상 경로에선 양끝이 항상 존재한다.
_EDGE_MERGE_TEMPLATE = (
    f"MATCH (src:{NODE_LABEL} {{concept_id: $src}})\n"
    f"MATCH (dst:{NODE_LABEL} {{concept_id: $dst}})\n"
    "MERGE (src)-[r:%s]->(dst)\n"
    "SET r += $props"
)

# enum 검증을 통과한 relation 값 → Cypher reltype(대문자). 닫힌 집합이라 주입 불가.
_RELTYPE_BY_RELATION: dict[str, str] = {r.value: r.value.upper() for r in Relation}

# 노드 속성으로 적재하지 않는 키(concept_id는 MERGE 키라 props에서 제외 — 중복 SET 방지).
_NODE_MERGE_KEY = "concept_id"

# 엣지 속성으로 적재하지 않는 키(끝점·relation은 MATCH/reltype에 쓰고 r 속성엔 넣지 않음).
_EDGE_NON_PROP_KEYS: frozenset[str] = frozenset({"src_concept_id", "dst_concept_id", "relation"})


@runtime_checkable
class _Result(Protocol):
    """neo4j Result 최소 인터페이스(주입 FAKE도 만족하도록 좁게)."""

    def single(self) -> Any: ...


@runtime_checkable
class _Session(Protocol):
    """neo4j Session 최소 인터페이스 — `run` + context manager."""

    def run(self, query: str, **parameters: Any) -> _Result: ...

    def __enter__(self) -> _Session: ...

    def __exit__(self, *exc: object) -> Any: ...


@runtime_checkable
class _Driver(Protocol):
    """neo4j Driver 최소 인터페이스 — `session` + `close`."""

    def session(self, **kwargs: Any) -> _Session: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class LoadReport:
    """Neo4j 적재 결과 요약(멱등 — 재실행해도 같은 수)."""

    constraints: int = 0
    indexes: int = 0
    nodes_merged: int = 0
    edges_merged: int = 0
    edges_skipped: int = 0

    def summary(self) -> str:
        """사람 가독 요약."""
        return (
            f"Neo4j 적재: 제약 {self.constraints}·인덱스 {self.indexes}, "
            f"노드 MERGE {self.nodes_merged}개, 엣지 MERGE {self.edges_merged}개"
            + (f", 엣지 skip {self.edges_skipped}건" if self.edges_skipped else "")
        )


def _node_props(concept: Mapping[str, Any]) -> dict[str, Any]:
    """Concept dump → Neo4j 노드 속성(MERGE 키 concept_id 제외, None 제거).

    `use_enum_values=True`라 review_status 등 enum은 이미 문자열이다. None 속성은 빼서 Neo4j에
    null 속성을 만들지 않는다(Neo4j는 null 속성을 저장하지 않음 — 명시 제거로 의도 일치).
    리스트(standard_codes 등)는 그대로 — Neo4j는 동질 리스트를 속성으로 저장한다.
    """
    return {
        key: value for key, value in concept.items() if key != _NODE_MERGE_KEY and value is not None
    }


def _edge_props(edge: Mapping[str, Any]) -> dict[str, Any]:
    """ConceptEdge dump → Neo4j 관계 속성(끝점·relation 제외). strength·evidence·evidence_source."""
    return {
        key: value
        for key, value in edge.items()
        if key not in _EDGE_NON_PROP_KEYS and value is not None
    }


def _edge_cypher(relation: str) -> str | None:
    """relation 값 → 엣지 MERGE Cypher(닫힌 enum allowlist). 미지원 값은 None(주입 차단)."""
    reltype = _RELTYPE_BY_RELATION.get(relation)
    if reltype is None:
        return None
    return _EDGE_MERGE_TEMPLATE % reltype


def ensure_schema(session: _Session) -> tuple[int, int]:
    """제약·인덱스 DDL 보장(§2.3) — 멱등(IF NOT EXISTS). (제약수, 인덱스수) 반환."""
    session.run(CONSTRAINT_CYPHER)
    for index_cypher in INDEX_CYPHERS:
        session.run(index_cypher)
    return 1, len(INDEX_CYPHERS)


def merge_nodes(session: _Session, concepts: Sequence[Mapping[str, Any]]) -> int:
    """개념을 노드로 멱등 MERGE(전량 — pending 포함). review_status 등 속성 SET. 적재 수 반환."""
    count = 0
    for concept in concepts:
        concept_id = concept.get(_NODE_MERGE_KEY)
        if not concept_id:
            logger.warning("concept_id 없는 노드 skip: %r", concept)
            continue
        session.run(
            NODE_MERGE_CYPHER,
            concept_id=concept_id,
            props=_node_props(concept),
        )
        count += 1
    return count


def merge_edges(session: _Session, edges: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    """엣지를 관계로 멱등 MERGE(양끝 MATCH 후). (적재수, skip수) 반환.

    relation이 enum allowlist 밖이거나 끝점 누락이면 skip(주입 차단·고아 방지). 정상 경로(노드 전량
    선적재)에선 끝점이 항상 존재한다.
    """
    merged = 0
    skipped = 0
    for edge in edges:
        relation = str(edge.get("relation", ""))
        src = edge.get("src_concept_id")
        dst = edge.get("dst_concept_id")
        cypher = _edge_cypher(relation)
        if cypher is None or not src or not dst:
            logger.warning("엣지 skip(relation/끝점): %r", edge)
            skipped += 1
            continue
        session.run(cypher, src=src, dst=dst, props=_edge_props(edge))
        merged += 1
    return merged, skipped


def connect_driver(
    *,
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> _Driver:
    """env(또는 인자)로 Neo4j 드라이버 생성 — `[neo4j]` extra 필요(지연 import).

    인자 미지정 시 env(`NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD`)에서 읽는다. 시크릿은 코드에 두지
    않는다(CLAUDE.md 보안). 드라이버 미설치 시 RuntimeError로 extra 설치를 안내한다.

    Raises:
        RuntimeError: `[neo4j]` extra 미설치 시.
        ValueError: 접속 env(URI·USER·PASSWORD) 누락 시.
    """
    resolved_uri = uri or os.environ.get(ENV_URI)
    resolved_user = user or os.environ.get(ENV_USER)
    resolved_password = password or os.environ.get(ENV_PASSWORD)
    missing = [
        name
        for name, value in (
            (ENV_URI, resolved_uri),
            (ENV_USER, resolved_user),
            (ENV_PASSWORD, resolved_password),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Neo4j 접속 정보 누락: " + ", ".join(missing) + " — "
            "env로 설정하세요(시크릿 하드코딩 금지). "
            "예: export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=…"
        )
    try:
        from neo4j import GraphDatabase
    except ModuleNotFoundError as exc:  # pragma: no cover - 환경 안내 경로
        raise RuntimeError(
            "Neo4j 적재에는 [neo4j] extra가 필요합니다 — "
            "`pip install -e '.[neo4j]'` 후 재시도하세요."
        ) from exc

    # missing 체크로 셋 다 non-None 보장(타입 좁히기 — 드라이버 시그니처 유무와 무관히 안전).
    assert resolved_uri is not None and resolved_user is not None and resolved_password is not None
    driver: _Driver = GraphDatabase.driver(
        resolved_uri,
        auth=(resolved_user, resolved_password),
    )
    return driver


def load_graph(
    result: TransformResult,
    *,
    driver: _Driver,
    database: str | None = None,
) -> LoadReport:
    """정형화 산출(개념·엣지) → Neo4j 멱등 적재(단계 7). 드라이버는 호출자가 주입(테스트 격리).

    순서: ① 제약·인덱스 DDL(§2.3) ② 노드 전량 MERGE(pending 포함·review_status 플래그) ③ 엣지
    MERGE(양끝 MATCH 후). 모두 MERGE라 재실행해도 노드·엣지 수 불변(§5 #9). flashcards·intl raw는
    그래프 적재 대상이 아니다(L6/국제트랙 — 슬라이스 1에서 패스스루로만 보존).

    Args:
        result: transform_dataset 산출(`concepts`·`edges`).
        driver: neo4j 드라이버(또는 호환 FAKE). 생명주기는 호출자 책임(여기서 close 안 함).
        database: 대상 DB명(멀티-DB 환경). None이면 기본 DB.

    Returns:
        적재 결과 요약(LoadReport).
    """
    concept_dumps = [c.model_dump() for c in result.concepts]
    edge_dumps = [e.model_dump() for e in result.edges]

    session_kwargs: dict[str, Any] = {}
    if database is not None:
        session_kwargs["database"] = database

    with driver.session(**session_kwargs) as session:
        constraints, indexes = ensure_schema(session)
        nodes = merge_nodes(session, concept_dumps)
        edges, skipped = merge_edges(session, edge_dumps)

    report = LoadReport(
        constraints=constraints,
        indexes=indexes,
        nodes_merged=nodes,
        edges_merged=edges,
        edges_skipped=skipped,
    )
    logger.info(report.summary())
    return report


__all__ = [
    "CONSTRAINT_CYPHER",
    "CONSTRAINT_NAME",
    "ENV_PASSWORD",
    "ENV_URI",
    "ENV_USER",
    "INDEX_CYPHERS",
    "LoadReport",
    "NODE_LABEL",
    "NODE_MERGE_CYPHER",
    "connect_driver",
    "ensure_schema",
    "load_graph",
    "merge_edges",
    "merge_nodes",
]
