"""L4 오개념 *의미(임베딩) 매칭* 좌석 + 코어 (slice 104).

substring(AND)+정규식 보조(`diagnose`)가 못 잡던 *패러프레이즈·동의어*(의미 recall)를
임베딩 코사인 유사도로 보완한다. `diagnose()`는 *불변*이고 의미 매칭은 *추가 API*다.

구성:
  - EmbeddingProvider 좌석 + Fake(테스트)·Local(bge-m3)·OpenAI(te-3-large) 구현
  - VectorIndex 좌석 + InMemoryVectorIndex(카탈로그 30종 규모 정답)
  - SemanticMatcher / semantic_matches(추가 API)

**정직 스코프**(CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지"): 의미 recall(패러프레이즈·
동의어)은 개선하나 *방향·부정·등치*("연속⇒미분" vs 역)는 임베딩만으로 못 가린다(방향맹).
방향 판별은 LLM-judged/NLI = 후속. pgvector 영속화도 후속(index.py 모듈 docstring).

7계층: L4 매처가 *하위 인프라 좌석*(임베딩·벡터 인덱스)을 호출(L_n→L_{n-1}). L4는 임베딩
구현을 모른다(Protocol만).
"""

from __future__ import annotations

from whymath_backend.l4.misconception.semantic.index import (
    IndexHit,
    InMemoryVectorIndex,
    VectorIndex,
    build_vector_index,
)
from whymath_backend.l4.misconception.semantic.matcher import (
    SemanticMatcher,
    catalog_text,
    semantic_matches,
)
from whymath_backend.l4.misconception.semantic.pgvector_index import (
    PgVectorIndex,
    populate_pgvector,
    text_hash,
)
from whymath_backend.l4.misconception.semantic.provider import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    LocalEmbeddingProvider,
    OpenAIEmbeddingProvider,
    build_provider,
    cosine_similarity,
)

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "IndexHit",
    "InMemoryVectorIndex",
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "PgVectorIndex",
    "SemanticMatcher",
    "VectorIndex",
    "build_provider",
    "build_vector_index",
    "catalog_text",
    "cosine_similarity",
    "populate_pgvector",
    "semantic_matches",
    "text_hash",
]
