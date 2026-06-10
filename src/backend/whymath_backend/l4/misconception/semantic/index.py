"""오개념 의미 매칭 — 벡터 인덱스 좌석 (slice 104).

카탈로그 항목의 사전 임베딩을 보관하고, 질의 벡터에 대해 코사인 유사도 상위 후보를
돌려주는 *벡터 인덱스* 좌석이다. 카탈로그가 30종(소규모·고정)이라 인메모리 선형 스캔이
정답이다 — 좌석을 Protocol로 두어 *대규모 시 pgvector로 교체*할 자리만 확보한다.

────────────────────────────────────────────────────────────────────────────
후속 슬라이스 (slice 105+, 명시적 미구현)
────────────────────────────────────────────────────────────────────────────
PgVectorIndex(pgvector 백엔드 영속화)는 *후속*이다. 본 슬라이스는 좌석(VectorIndex
Protocol)과 인메모리 구현만 둔다. 후속에서 추가할 것:
  - `Misconception` 표현 임베딩을 PostgreSQL `vector` 컬럼에 적재(슬98 `embedding_id`는
    현재 참조 자리만 — 실 벡터 컬럼은 스키마 밖).
  - alembic 마이그레이션(pgvector 확장 활성 + 벡터 컬럼 + ivfflat/hnsw 인덱스).
  - 통합 게이트(`WHYMATH_RUN_INTEGRATION`)로 라이브 PG 도달성 검증.
무리한 pgvector 영속화 코드를 *지금* 작성하지 않는다(카탈로그 30종엔 인메모리가 최적이며,
조기 영속화는 슬98 벡터 store 의사결정[pgvector vs Qdrant]과 결선돼야 함).

7계층: 이 인덱스도 L4가 호출하는 *하위 인프라 좌석*이다(임베딩 저장·검색 = 영속/검색
계층). L4 SemanticMatcher는 인덱스 구현을 모르고 VectorIndex Protocol만 본다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from whymath_backend.l4.misconception.semantic.provider import cosine_similarity


@dataclass(slots=True, frozen=True)
class IndexHit:
    """벡터 인덱스 검색 결과 1건 — 항목 키 + 코사인 유사도.

    `key`는 카탈로그 항목 식별자(매처는 misconception.id를 쓴다). `similarity`는 질의
    벡터와의 코사인 [-1, 1].
    """

    key: str
    similarity: float


@runtime_checkable
class VectorIndex(Protocol):
    """키→벡터를 보관하고 질의 벡터로 상위 유사 항목을 찾는 좌석(구조적 타이핑).

    `add`로 (키, 벡터)를 적재하고 `search`로 질의 벡터에 대한 코사인 상위 K를 받는다.
    인메모리·pgvector 등 구현 무관 — 매처는 이 인터페이스만 의존한다.
    """

    def add(self, key: str, vector: Sequence[float]) -> None:
        """단일 (키, 벡터) 적재."""
        ...

    def search(self, vector: Sequence[float], *, top_k: int) -> list[IndexHit]:
        """질의 벡터에 대한 코사인 상위 top_k IndexHit(유사도 내림차순)."""
        ...


class InMemoryVectorIndex:
    """인메모리 코사인 벡터 인덱스 — 카탈로그 30종 규모의 정답 구현.

    벡터를 리스트로 보관하고 질의마다 선형 스캔으로 코사인을 계산한다(O(N·D), N=30 항목).
    소규모·고정 카탈로그엔 충분하고 *라이브 의존 0*이라 테스트·프로덕션 양쪽에서 그대로
    쓴다. 대규모(수천+ 또는 학생 풀이 코퍼스)면 pgvector(ANN)로 교체한다(모듈 docstring
    후속). 동률 유사도는 *삽입 순서*를 안정 유지한다(파이썬 sort는 stable) — 카탈로그
    순서(=doc 명시 순서)가 보존되도록 적재 순서를 카탈로그 순서로 맞춘다(매처 책임).
    """

    def __init__(self) -> None:
        # 삽입 순서 보존 리스트(동률 정렬 안정성의 근거). dict가 아니라 리스트인 이유:
        # 같은 키 재적재를 막지 않고(매처가 1회만 적재) 순서를 그대로 보존하기 위함.
        self._entries: list[tuple[str, tuple[float, ...]]] = []

    def add(self, key: str, vector: Sequence[float]) -> None:
        """단일 (키, 벡터) 적재 (VectorIndex 구현). 벡터는 불변 튜플로 보관."""
        self._entries.append((key, tuple(float(x) for x in vector)))

    def search(self, vector: Sequence[float], *, top_k: int) -> list[IndexHit]:
        """질의 벡터에 대한 코사인 상위 top_k(유사도 내림차순·동률은 삽입 순서).

        top_k<=0이면 빈 리스트. 코사인은 provider.cosine_similarity(영벡터·차원 불일치
        방어 포함)로 계산한다. 임계값 필터는 *매처*가 적용한다(인덱스는 순수 랭킹만).
        """
        if top_k <= 0:
            return []
        hits = [
            IndexHit(key=key, similarity=cosine_similarity(vector, vec))
            for key, vec in self._entries
        ]
        # 유사도 내림차순. sort는 stable이라 동률은 삽입(=카탈로그) 순서 유지.
        hits.sort(key=lambda h: h.similarity, reverse=True)
        return hits[:top_k]

    def __len__(self) -> int:
        """적재된 항목 수(테스트·디버그용)."""
        return len(self._entries)
