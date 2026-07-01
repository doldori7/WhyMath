"""오개념 의미 매칭 — 임베딩 제공자 좌석 (하위호환 re-export shim).

임베딩 제공자 *구현체·팩토리*는 레이어-중립 L1(`l1/embedding_provider.py`)로 이동했다
(감사 I4: L1 적재기가 이 모듈을 *위로* import하던 L1→L4 역방향 의존 제거·의존성 역전).
이 모듈은 기존 import 경로(`...semantic.provider import ...`)를 유지하기 위한 **얇은
re-export shim**이다 — L4·api·harness·테스트가 무수정으로 계속 이 경로를 쓸 수 있다.

`... as ...` 명시 별칭 = PEP 484 명시적 re-export(mypy no-implicit-reexport 충족).
새 코드는 `whymath_backend.l1.embedding_provider`에서 직접 import하는 것을 권장한다.
"""

from __future__ import annotations

from whymath_backend.l1.embedding_provider import EmbeddingProvider as EmbeddingProvider
from whymath_backend.l1.embedding_provider import FakeEmbeddingProvider as FakeEmbeddingProvider
from whymath_backend.l1.embedding_provider import LocalEmbeddingProvider as LocalEmbeddingProvider
from whymath_backend.l1.embedding_provider import OpenAIEmbeddingProvider as OpenAIEmbeddingProvider
from whymath_backend.l1.embedding_provider import build_provider as build_provider
from whymath_backend.l1.embedding_provider import cosine_similarity as cosine_similarity

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "build_provider",
    "cosine_similarity",
]
