"""L1 개념그래프 — 백엔드 영속/적재 인프라(의미 임베딩 좌석·슬라이스 3).

L1 개념그래프 적재 아크의 백엔드 부분이다. 슬1(정형화·UC 매핑·검증)·슬2(Neo4j 멱등 적재)는
`data-pipeline` 패키지에서 완료됐고, 이 백엔드 패키지는 슬3 = 개념의 *의미 임베딩을 pgvector에
적재*하는 영속 좌석을 담는다(슬2 Neo4j와 *동일 UC 키*로 이중 store 일관).

구성:
  - `ConceptEmbeddingIndex` — pgvector 영속 인덱스(`concept_embedding` 테이블·UC PK upsert·코사인
    검색). L4 `PgVectorIndex`(misconception_embedding)를 개념용으로 미러링.
  - `concept_embedding_text` — 개념 임베딩 입력 표현 직렬화(**안전 필드만**: name_ko·metaphor·
    accepted_expressions — description·formal_definition 절대 미사용·redaction).
  - `load_concepts_from_graph_json` — 슬1 산출 `graph.json`(UC 키·정제) → (concept_id, 표현) 목록.
  - `populate_concept_embeddings` — 표현을 임베딩(기존 provider seam 재사용)해 멱등 upsert.

7계층: L1 데이터 기반의 *영속/검색 인프라*. 의미검색 로직(L2/L3/L4)은 이 좌석을 호출하되
여기서 구현하지 않는다(슬4+ 후속).
"""

from __future__ import annotations

from whymath_backend.l1.concept_graph.embedding import (
    ConceptEmbeddingIndex,
    concept_embedding_text,
    load_concepts_from_graph_json,
    populate_concept_embeddings,
)

__all__ = [
    "ConceptEmbeddingIndex",
    "concept_embedding_text",
    "load_concepts_from_graph_json",
    "populate_concept_embeddings",
]
