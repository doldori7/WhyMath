"""오개념 의미 매칭 — 벡터 인덱스 좌석 (slice 104).

카탈로그 항목의 사전 임베딩을 보관하고, 질의 벡터에 대해 코사인 유사도 상위 후보를
돌려주는 *벡터 인덱스* 좌석이다. 카탈로그가 30종(소규모·고정)이라 인메모리 선형 스캔이
정답이다 — 좌석을 Protocol로 두어 *대규모 시 pgvector로 교체*할 자리만 확보한다.

────────────────────────────────────────────────────────────────────────────
pgvector 영속 백엔드 (slice 105, 구현됨 — `pgvector_index.PgVectorIndex`)
────────────────────────────────────────────────────────────────────────────
PgVectorIndex(pgvector 백엔드 영속화)는 슬105에서 *이 좌석의 영속 구현*으로 추가됐다(슬104는
좌석 Protocol + 인메모리 구현만 뒀다). 슬105가 더한 것:
  - `Misconception` 표현 임베딩을 PostgreSQL `vector` 컬럼(`misconception_embedding` 테이블)에
    적재(`pgvector_index.PgVectorIndex`·`populate_pgvector`). 슬98 결정(벡터 DB=pgvector)의
    첫 실 결선 — 슬98 `embedding_id`(concept/user의 참조 필드)와는 별 테이블이다.
  - alembic 마이그레이션(`CREATE EXTENSION vector` + `vector(1024)` 컬럼). **30종은 seq-scan이
    최적이라 HNSW/IVFFlat 인덱스는 두지 않는다** — 스케일 코퍼스(개념그래프 401+·문제은행·학생
    풀이)가 *fixed-dim + HNSW cosine 인덱스*의 자리다(후속·과장 금지: pgvector는 30종에서
    인메모리보다 빠르지 않고 *영속화 + 스케일 groundwork*다).
  - 통합 게이트(`WHYMATH_RUN_INTEGRATION`)로 라이브 PG 도달성·add/search·recall 검증.
`build_vector_index(settings)` 팩토리가 `config.vector_store`(기본 `memory`)에 따라 인메모리/
pgvector를 만든다(기본 동작 무변경 — pgvector는 opt-in). 카탈로그 30종엔 여전히 인메모리가
최적이고, PgVectorIndex는 사전 임베딩을 *프로세스 밖에 영속*(재기동·다중 워커 공유)하는 값이다.

7계층: 이 인덱스도 L4가 호출하는 *하위 인프라 좌석*이다(임베딩 저장·검색 = 영속/검색
계층). L4 SemanticMatcher는 인덱스 구현을 모르고 VectorIndex Protocol만 본다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from whymath_backend.config import Settings, get_settings
from whymath_backend.l4.misconception.semantic.provider import cosine_similarity

if TYPE_CHECKING:
    from whymath_backend.l4.misconception.semantic.pgvector_index import PgVectorIndex


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


def build_vector_index(
    settings: Settings | None = None,
    *,
    provider_name: str,
    model_name: str,
) -> VectorIndex:
    """`Settings.vector_store`에 따라 벡터 인덱스를 만든다(좌석 팩토리·build_provider 미러).

    `memory`(기본)=`InMemoryVectorIndex`(코사인 선형 스캔·라이브 의존 0). `pgvector`=
    `PgVectorIndex`(영속·sync psycopg 엔진·지연 import). **기본 동작 무변경** — pgvector는
    opt-in이고, memory 경로는 psycopg/pgvector를 import하지 않는다(PgVectorIndex import는 이
    함수의 pgvector 분기 *안*에서만).

    `provider_name`·`model_name`은 pgvector의 *임베딩 공간 식별자*다(같은 공간 행만 비교).
    memory 분기는 이 둘을 무시한다(인메모리는 단일 프로세스·단일 공간이라 식별 불요) — 인터페이스
    대칭을 위해 양쪽에 받되 pgvector만 쓴다. 호출자(매처)는 add/search에 일관된 식별자를 넘겨야
    한다(provider별 model 해석은 호출자 책임 — 보통 `_provider_model_identity`).
    """
    resolved = settings if settings is not None else get_settings()
    if resolved.vector_store == "pgvector":
        # 지연 import — memory 경로(기본)는 psycopg/pgvector·sync 드라이버를 안 끌어온다.
        from whymath_backend.l4.misconception.semantic.pgvector_index import PgVectorIndex

        index: PgVectorIndex = PgVectorIndex(
            provider_name=provider_name, model_name=model_name, settings=resolved
        )
        return index
    # 기본 memory — 카탈로그 30종 최적·라이브 의존 0.
    return InMemoryVectorIndex()
