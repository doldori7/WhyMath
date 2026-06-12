"""L1 개념그래프 — 백엔드 영속/적재 + 의미검색 조회 인프라(슬라이스 3·4).

L1 개념그래프 적재 아크의 백엔드 부분이다. 슬1(정형화·UC 매핑·검증)·슬2(Neo4j 멱등 적재)는
`data-pipeline` 패키지에서 완료됐고, 이 백엔드 패키지는 슬3 = 개념의 *의미 임베딩을 pgvector에
적재*하는 영속 좌석(슬2 Neo4j와 *동일 UC 키*로 이중 store 일관)과, 슬4 = 그 적재 임베딩을
*조회*하는 검색 좌석을 담는다.

구성:
  - `ConceptEmbeddingIndex` — pgvector 영속 인덱스(`concept_embedding` 테이블·UC PK upsert·코사인
    검색). L4 `PgVectorIndex`(misconception_embedding)를 개념용으로 미러링.
  - `concept_embedding_text` — 개념 임베딩 입력 표현 직렬화(**안전 필드만**: name_ko·metaphor·
    accepted_expressions — description·formal_definition 절대 미사용·redaction).
  - `load_concepts_from_graph_json` — 슬1 산출 `graph.json`(UC 키·정제) → (concept_id, 표현) 목록.
  - `populate_concept_embeddings` — 표현을 임베딩(기존 provider seam 재사용)해 멱등 upsert.
  - `search_concepts`·`ConceptSearchHit` (슬4) — 질의 텍스트를 임베딩해 `ConceptEmbeddingIndex.
    search`로 코사인 상위 top_k 랭킹(조회 좌석). 소비 슬1부터 안전 메타(name_ko·domain·
    review_status)를 PG 조인으로 enrich하고, `reviewed_only` 게이팅을 지원한다.
  - `ConceptNodeRecord`·`ConceptNodeStore`·`load_concept_nodes_from_graph_json`·
    `populate_concept_nodes` (소비 슬1) — graph.json 개념 *안전 메타*를 `concept_node`(PG)에 UC
    키로 멱등 적재(메타 브리지=PG 프로젝션·backend↔Neo4j 런타임 연결 0). 검색 enrichment·게이팅
    PG 조인의 백킹. **description·formal_definition 미적재**(redaction·안전 필드만).

7계층: L1 데이터 기반의 *영속/검색 인프라*. 의미검색 *소비* 로직(L2/L4가 이 좌석으로 무엇을
하는지)은 이 좌석을 호출하되 여기서 구현하지 않는다(후속·역방향 의존 금지).
"""

from __future__ import annotations

from whymath_backend.l1.concept_graph.backend_edge import (
    BackendConceptEdgeRecord,
    BackendEdgeStore,
    load_backend_edges_from_graph_json,
    populate_backend_edges,
)
from whymath_backend.l1.concept_graph.embedding import (
    ConceptEmbeddingIndex,
    concept_embedding_text,
    load_concepts_from_graph_json,
    populate_concept_embeddings,
)
from whymath_backend.l1.concept_graph.node_projection import (
    ConceptNodeMeta,
    ConceptNodeRecord,
    ConceptNodeStore,
    fetch_node_meta,
    load_concept_nodes_from_graph_json,
    populate_concept_nodes,
)
from whymath_backend.l1.concept_graph.retrieval import (
    ConceptSearchHit,
    search_concepts,
)

__all__ = [
    "BackendConceptEdgeRecord",
    "BackendEdgeStore",
    "ConceptEmbeddingIndex",
    "ConceptNodeMeta",
    "ConceptNodeRecord",
    "ConceptNodeStore",
    "ConceptSearchHit",
    "concept_embedding_text",
    "fetch_node_meta",
    "load_backend_edges_from_graph_json",
    "load_concept_nodes_from_graph_json",
    "load_concepts_from_graph_json",
    "populate_backend_edges",
    "populate_concept_embeddings",
    "populate_concept_nodes",
    "search_concepts",
]
