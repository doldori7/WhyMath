"""개념 의미 임베딩 적재 — pgvector 영속 좌석 (L1 개념그래프 아크 슬라이스 3).

슬1 산출 `graph.json`(UC 키·정제)의 각 개념을 *안전 필드 표현*으로 임베딩해 `concept_embedding`
테이블(pgvector)에 멱등 upsert한다. 슬2 Neo4j 적재와 *동일 UC 키*라 그래프↔벡터가 한 키로
join된다(이중 store 단일 키). L4 오개념 영속(`pgvector_index.PgVectorIndex`·`populate_pgvector`)을
개념용으로 미러링하고, **임베딩 provider seam은 L4 것을 그대로 재사용**한다(신규 금지 — 같은
임베딩 공간 규약·Fake 주입·지연 로드).

────────────────────────────────────────────────────────────────────────────
redaction (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
임베딩 입력 표현은 **자체 작성 안전 필드만** 쓴다 — `name_ko`(한국어 명칭)·`metaphor`(은유)·
`accepted_expressions`(허용표현). **`description`·`formal_definition`은 절대 읽지 않는다**:
성취기준 *본문* 근접 복제 위험 필드이고, 슬1 정형화에서 `Concept` 모델 슬롯 부재로 이미
제거돼 `graph.json`에도 없다(`_provenance.json`의 redacted 목록). 이 모듈은 그 키를 *읽지도
않으므로* 입력이 오염돼도 본문이 임베딩에 유입되지 않는다(이중 방어). 임베딩 *벡터*만 적재하고
원문은 `concept_embedding`에 저장하지 않는다(ORM docstring·중복·프라이버시).

────────────────────────────────────────────────────────────────────────────
sync 엔진 (async 전용 코드베이스에 *벡터 store 좌석에 한정*된 sync 드라이버)
────────────────────────────────────────────────────────────────────────────
앱 본체는 async 전용(asyncpg)이고, 이 모듈만 sync 엔진(psycopg)을 쓴다(L4 `pgvector_index`와
동일 사유 — pgvector add/search가 동기). 엔진·psycopg import는 *지연*(lazy)이라 모듈 import만으로는
드라이버 로드·연결이 없다. sync URL은 `Settings.sync_database_url`(async URL에서 드라이버만
`+psycopg`로 파생)에서 오고 자격증명은 코드에 0(env).

7계층: 이 적재기는 L1 데이터 기반의 *영속/적재 인프라*다. 의미검색 *조회*(L2/L3/L4)는 후속
슬라이스(슬4+)에서 좌석으로 얹는다 — 여기선 저장소·적재만 소유한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings

# 임베딩 provider seam 재사용(신규 금지·CLAUDE.md 로컬 우선) — 좌석 Protocol·표현 해시·공간
# 식별자는 *레이어-중립 L1*(`l1/embedding_primitives.py`)이 소유한다. 과거엔 이 심볼들이 L4
# (`semantic.pgvector_index`)에 살아 L1이 L4를 위로 import(지연 import로 가린 순환)했으나,
# 프리미티브를 L1로 내려 의존을 *아래로* 뒤집었다(L1→L1·순환 0). L4 오개념 의미 매칭도 같은
# 프리미티브를 쓰므로 좌석 공유는 유지된다.
from whymath_backend.l1.embedding_primitives import (
    join_embedding_text,
    provider_model_identity,
    text_hash,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from whymath_backend.l1.embedding_primitives import EmbeddingProvider

# graph.json에서 임베딩 입력으로 *허용된* 안전 필드(자체 작성·본문 아님). 이 집합 밖 키는
# 임베딩에 쓰지 않는다(특히 description·formal_definition은 graph.json에 부재이며 읽지도 않음).
_SAFE_TEXT_FIELDS: tuple[str, ...] = ("name_ko", "metaphor", "accepted_expressions")


@dataclass(frozen=True, slots=True)
class ConceptText:
    """임베딩 대상 한 개념 — UC concept_id + 안전 필드로 합성한 표현.

    `text`는 `concept_embedding_text`가 안전 필드만으로 만든 표현이다(본문 미포함). 적재기가
    이 표현을 임베딩하고 upsert한다.
    """

    concept_id: str
    text: str


def concept_embedding_text(
    *,
    name_ko: str | None,
    metaphor: str | None = None,
    accepted_expressions: str | None = None,
) -> str:
    """개념을 임베딩할 자연어 표현으로 직렬화 — **안전 필드만**(name_ko·metaphor·accepted).

    L4 `catalog_text`(f"{name_kr}. {canonical_statement}")의 개념판이다. 의미 신호를 키우려고
    명칭·은유·허용표현을 잇되, **description·formal_definition은 인자로 받지도 않는다**(redaction —
    본문 근접 필드 구조적 차단). 비어 있는 필드는 건너뛰고, 남은 조각을 `". "`로 잇는다.
    name_ko가 비면(이론상 graph.json은 name_ko 필수) 나머지만으로 표현을 만든다(빈 표현 가능 —
    호출자가 빈 표현을 임베딩하지 않도록 거를 수 있으나, 여기선 합성만 한다).
    """
    return join_embedding_text(name_ko, metaphor, accepted_expressions)


def load_concepts_from_graph_json(path: Path) -> list[ConceptText]:
    """슬1 산출 `graph.json` → 임베딩 대상 (UC concept_id, 안전 표현) 목록.

    `graph.json`은 슬1 `transform-v1`이 만든 정제 산출이다(UC 키·redaction 청결). 여기서는
    `concepts` 배열의 각 항목에서 `concept_id`(UC)와 **안전 필드(name_ko·metaphor·
    accepted_expressions)만** 읽어 표현을 합성한다 — `description`·`formal_definition`은 읽지
    않는다(graph.json에 부재이며, 있더라도 이 함수가 무시).

    표현이 빈(안전 필드 전부 공백) 개념은 제외한다(임베딩 무의미 — 빈 벡터 적재 방지). flashcards_
    raw·intl_raw 등 그래프 외 자산은 임베딩 대상이 아니므로 읽지 않는다.

    Raises:
        FileNotFoundError: graph.json 부재.
        ValueError: concept_id 없는 항목(슬1 산출은 항상 UC를 갖는다 — 방어).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[ConceptText] = []
    for record in payload.get("concepts", []):
        concept_id = str(record.get("concept_id", "")).strip()
        if not concept_id:
            raise ValueError(f"graph.json 개념에 concept_id가 없습니다: {record!r}")
        text = concept_embedding_text(
            name_ko=record.get("name_ko"),
            metaphor=record.get("metaphor"),
            accepted_expressions=record.get("accepted_expressions"),
        )
        if not text:
            # 안전 필드가 전부 비어 임베딩할 표현이 없는 개념 — 제외(빈 벡터 적재 방지).
            continue
        out.append(ConceptText(concept_id=concept_id, text=text))
    return out


class ConceptEmbeddingIndex:
    """개념 pgvector 영속 인덱스 — `concept_embedding` 테이블 upsert/검색(UC PK·sync).

    L4 `PgVectorIndex`(misconception_embedding)를 개념용으로 미러링한다. `upsert`는 PK 충돌
    upsert(`INSERT ... ON CONFLICT(concept_id) DO UPDATE`)로 멱등 적재하고, `search`는 코사인
    거리(`<=>`)로 상위 후보를 찾는다(`similarity = 1 - distance`). **같은 임베딩 공간(provider·
    model) 행만** 비교한다(서로 다른 모델 벡터 혼재 방지). sync 엔진은 지연 생성·캐시하고,
    psycopg 연결마다 pgvector 어댑터를 등록한다(`register_vector`).

    provider/model은 *임베딩 공간 식별자*다 — 같은 provider라도 model이 다르면 다른 공간으로
    본다. 호출자(적재기)는 upsert/search에 *같은* provider·model을 일관되게 넘겨야 한다. 차원
    불일치는 pgvector가 적재 시점에 오류로 막는다(컬럼 `vector(N)`).
    """

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._model_name = model_name
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(L4 pgvector_index 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 psycopg 격리 엔진 생성(L4 패턴 미러).

        첫 호출에서 `create_engine(settings.sync_database_url)`로 sync 엔진을 만들고 인스턴스에
        캐시한다. psycopg/SQLAlchemy/pgvector import는 *이 시점*에만 일어난다(모듈 import 깨짐
        방지). 각 raw 연결에 pgvector 어댑터를 등록하는 connect 리스너를 건다.
        """
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, concept_id: str, vector: Sequence[float], *, source_text: str) -> None:
        """단일 (UC concept_id, 벡터) upsert (멱등·표현 해시 기록).

        `INSERT ... ON CONFLICT(concept_id) DO UPDATE` — provider/model/dim/text_hash/updated_at을
        함께 적재한다. 같은 키 재적재는 행을 갱신(멱등). `source_text`는 임베딩한 *표현*(안전
        필드 합성)이고, 그 해시만 `text_hash`로 보관한다(원문 미저장 — 변경 감지용 해시만).
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept_embedding import ConceptEmbedding

        values = [float(x) for x in vector]
        stmt = pg_insert(ConceptEmbedding).values(
            concept_id=concept_id,
            embedding=values,
            provider=self._provider_name,
            model=self._model_name,
            dim=len(values),
            text_hash=text_hash(source_text),
        )
        # PK 충돌 시 갱신 — updated_at은 now()로 새로 찍는다(server_default는 INSERT 전용).
        stmt = stmt.on_conflict_do_update(
            index_elements=[ConceptEmbedding.concept_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "provider": stmt.excluded.provider,
                "model": stmt.excluded.model,
                "dim": stmt.excluded.dim,
                "text_hash": stmt.excluded.text_hash,
                "updated_at": func.now(),
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)

    def search(self, vector: Sequence[float], *, top_k: int) -> list[tuple[str, float]]:
        """질의 벡터에 대한 코사인 상위 top_k (concept_id, similarity)(유사도 내림차순).

        `1 - (embedding <=> :q)`(코사인 거리→유사도)로 점수를 내고 *같은 provider·model 행만*
        본다(임베딩 공간 일치). top_k<=0이면 빈 리스트. 거리 오름차순 = 유사도 내림차순으로
        정렬·LIMIT. NULL 거리(영벡터 등 정의 불가)는 0 유사도로 안전 처리.

        반환 타입은 단순 튜플 목록이다 — L4 `IndexHit`를 빌리지 않는 이유: 이 좌석은 L1 의미검색
        groundwork이고 조회 인터페이스(L2/L4 결선)는 슬4+에서 정의한다(현재는 적재 검증·통합
        라운드트립 용도). 조회 좌석이 생기면 그 타입으로 흡수한다.
        """
        if top_k <= 0:
            return []
        from sqlalchemy import select

        from whymath_backend.db.models.concept_embedding import ConceptEmbedding

        query = [float(x) for x in vector]
        distance = ConceptEmbedding.embedding.cosine_distance(query)
        stmt = (
            select(
                ConceptEmbedding.concept_id,
                distance.label("distance"),
            )
            .where(
                ConceptEmbedding.provider == self._provider_name,
                ConceptEmbedding.model == self._model_name,
            )
            .order_by(distance)
            .limit(top_k)
        )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return [
            (
                row.concept_id,
                (1.0 - float(row.distance)) if row.distance is not None else 0.0,
            )
            for row in rows
        ]


def _build_sync_engine(settings: Settings) -> Engine:
    """기본 sync(psycopg) 엔진 생성 + pgvector 어댑터 등록 (지연 import·L4 pgvector_index 미러).

    psycopg/SQLAlchemy/pgvector import는 *호출 시점*에만(모듈 import 깨짐 방지). `sync_database_url`
    (async URL에서 드라이버만 `+psycopg`로 파생)로 sync 엔진을 만들고, 각 raw 연결에
    `register_vector`를 거는 connect 리스너를 단다 — psycopg가 vector 타입을 바인딩/디코딩하게.
    `db_disable_pool`(통합테스트)면 NullPool(매 체크아웃 새 연결)로 다중 루프 충돌을 회피한다.
    """
    from pgvector.psycopg import register_vector
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import NullPool

    if settings.db_disable_pool:
        engine = create_engine(settings.sync_database_url, poolclass=NullPool)
    else:
        engine = create_engine(settings.sync_database_url)

    @event.listens_for(engine, "connect")
    def _register_vector_on_connect(dbapi_connection: object, _record: object) -> None:
        # 각 새 psycopg 연결에 vector 어댑터 등록(바인딩 list[float]→vector·디코딩 역). 확장은
        # 마이그레이션이 CREATE EXTENSION으로 보장하므로 여기선 타입 등록만 한다.
        register_vector(dbapi_connection)

    return engine


def populate_concept_embeddings(
    concepts: Sequence[ConceptText],
    provider: EmbeddingProvider,
    *,
    settings: Settings | None = None,
    index: ConceptEmbeddingIndex | None = None,
) -> int:
    """개념 표현을 임베딩해 `ConceptEmbeddingIndex`에 멱등 upsert 적재(영속 사전 임베딩).

    L4 `populate_pgvector`의 개념판이다 — 각 개념의 안전 표현(`ConceptText.text`)을 배치 1회
    임베딩해 UC concept_id로 upsert한다. provider/model은 임베딩 공간 식별자로 행에 박히고,
    같은 공간만 search가 본다. 멱등(재실행 시 갱신). 반환은 적재 행 수(=concepts 길이).

    provider의 model 이름은 *Settings*에서 해석한다(`provider_model_identity` 재사용 —
    local→embedding_model_local·openai→embedding_model_openai·fake→fake-hash). provider 객체가
    model을 노출하지 않으므로(좌석은 embed만), 같은 규약을 upsert/search 양쪽이 공유하도록
    여기서 결정한다(L4와 동일). review_status 무관 전량 적재(게이팅은 조회 몫).
    """
    resolved = settings if settings is not None else get_settings()
    provider_name, model_name = provider_model_identity(provider, resolved)
    idx = (
        index
        if index is not None
        else ConceptEmbeddingIndex(
            provider_name=provider_name, model_name=model_name, settings=resolved
        )
    )
    texts = [c.text for c in concepts]
    vectors = provider.embed(texts)
    if len(vectors) != len(concepts):
        raise RuntimeError(
            f"임베딩 개수({len(vectors)})가 개념 개수({len(concepts)})와 다릅니다 "
            "— provider.embed가 입력 순서·길이를 보존해야 합니다."
        )
    for concept, vec in zip(concepts, vectors, strict=True):
        idx.upsert(concept.concept_id, vec, source_text=concept.text)
    return len(concepts)


__all__ = [
    "ConceptEmbeddingIndex",
    "ConceptText",
    "concept_embedding_text",
    "load_concepts_from_graph_json",
    "populate_concept_embeddings",
]
