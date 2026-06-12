"""개념 의미검색 *조회 좌석* — 적재된 pgvector 임베딩 질의 (L1 개념그래프 아크 슬라이스 4).

슬3(`embedding.py`)이 개념의 안전 표현을 `concept_embedding`(pgvector) 테이블에 멱등 적재했다.
이 모듈은 그 *적재된 임베딩을 조회*하는 좌석이다 — 질의 텍스트 1건을 임베딩(provider 재사용)해
`ConceptEmbeddingIndex.search`(슬3 백킹 프리미티브)로 코사인 상위 top_k를 랭킹해 돌려준다.
슬3 `search` docstring이 예고한 "조회 좌석이 생기면 그 타입으로 흡수한다"의 그 좌석이다.

────────────────────────────────────────────────────────────────────────────
노출 계약 (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
이 좌석은 **학생 직접 노출이 아니다** — L2(약개념 추천)·L4(오개념↔개념 연결)·교사 도구가
*소비*하는 내부 조회 표면이다(그 소비 로직은 후속 슬라이스·여기선 좌석만). 반환은 `concept_id`
(UC 키)와 `similarity`(코사인 점수)뿐이다 — **본문(description·formal_definition) 0**. 애초에
검색은 임베딩 *벡터* 위에서만 돌고(`concept_embedding`엔 원문이 없다·슬3 redaction), 결과도
UC 식별자 + 점수만이라 본문이 흐를 경로가 구조적으로 없다.

`name_ko` 같은 *안전 필드* enrichment는 *깔끔할 때만* 실을 수 있으나(task §1.A), backend에서
지금은 깔끔하지 않다 — `concept_embedding.concept_id`는 **UC 키**(`UC.<domain>.<topic>.<slug>`·
슬2 Neo4j 노드 키와 동일 공간)인데 backend PG `concept` 테이블은 **UUID PK + `code`**로 키잉돼
*UC 컬럼이 없다*(다른 키 공간 — `concepts.py` edges 핸들러 docstring "Neo4j concept_graph와
별개·다른 키 공간"과 동일 사실). UC↔PG/Neo4j 메타 브리지는 *별도 설계 결정*(backend가 Neo4j에
붙을지 vs PG에 UC 프로젝션을 둘지)이라 후속 enrichment 슬라이스 몫이다. 그래서 이 좌석은
`concept_id + similarity`만 돌려주고, name_ko·풍부 메타는 무거운 결합 없이 후속에서 얹는다
(backend↔Neo4j 결합·무거운 프로젝션 금지 — task §1.A 제약).

7계층: L1 데이터 *조회 서빙*. **L2/L4 로직을 구현하지 않는다** — 좌석만 제공하고, L2/L4가
이 좌석을 *호출*하는 건 후속(역방향 의존 금지·CLAUDE.md 경계). HTTP 표면(L5)은 `api/concepts.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.concept_graph.embedding import ConceptEmbeddingIndex

# provider 공간 식별자(provider→model 규약)는 적재(슬3)와 *같은 seam*을 재사용한다(신규 0). 같은
# 규약을 search가 써야 적재 행과 같은 임베딩 공간을 본다(provider/model 불일치 시 빈 결과).
from whymath_backend.l4.misconception.semantic.pgvector_index import _provider_model_identity

if TYPE_CHECKING:
    from whymath_backend.l4.misconception.semantic.provider import EmbeddingProvider


@dataclass(frozen=True, slots=True)
class ConceptSearchHit:
    """개념 의미검색 결과 1건 — UC concept_id + 코사인 유사도.

    `concept_id`는 Universal Concept ID(UC.<domain>.<topic>.<slug>·슬2 Neo4j 노드 키와 동일
    공간)다. `similarity`는 질의 임베딩과의 코사인 [-1, 1](클수록 의미 근접). **name_ko 등
    풍부 메타는 미포함** — 모듈 docstring(노출 계약)의 UC↔PG 키 공간 차이로 enrichment는
    후속 슬라이스다. 소비처(L2/L4·교사 도구)는 UC 키로 그래프/메타를 별도 해석한다.
    """

    concept_id: str
    similarity: float


def search_concepts(
    query_text: str,
    *,
    top_k: int,
    provider: EmbeddingProvider,
    index: ConceptEmbeddingIndex | None = None,
    settings: Settings | None = None,
) -> list[ConceptSearchHit]:
    """질의 텍스트 → 임베딩 → `ConceptEmbeddingIndex.search` 코사인 상위 top_k(랭킹된 결과).

    흐름(task §1.A): ① `provider.embed([query_text])`로 질의 1건을 임베딩 ②
    `ConceptEmbeddingIndex.search(vector, top_k=top_k)`로 적재 임베딩과 코사인 비교(상위 K) ③
    `(concept_id, similarity)`를 `ConceptSearchHit`로 랭킹 반환(유사도 내림차순 — search가 거리
    오름차순 정렬). 임계값 필터는 두지 않는다(순수 랭킹 — 임계값이 필요한 소비처가 점수로 자른다).

    provider·index는 *주입 가능*하다(테스트 격리·Fake). index 미주입 시 적재(슬3)와 같은 provider
    공간 식별자(`_provider_model_identity`)로 `ConceptEmbeddingIndex`를 만든다 — 같은 공간 행만
    봐야 적재 결과가 잡힌다. provider/model 규약·sync 엔진·지연 로드는 전부 슬3·L4 좌석 재사용
    (신규 seam 0).

    memory 모드 graceful(조용한 무동작 금지·task §1.A): `vector_store != pgvector`면 영속 임베딩
    store가 없다(적재가 불가능했다) → **빈 리스트**를 돌려준다(예외 아님·조용한 None 아님). 호출자
    (HTTP 표면)가 이 빈 결과를 503/명시 안내로 표면화한다(좌석은 정직하게 "없음"을 반환). pgvector
    모드인데 빈 결과면 그건 *진짜로 매칭이 없거나 미적재*다(같은 정직 신호).

    top_k<=0이면 빈 리스트(search 계약과 동일 경계 — 임베딩도 생략하지 않으나 search가 즉시 빈
    반환). 빈/공백 query_text는 provider가 영벡터 등으로 임베딩하고 search가 코사인 0 근방으로
    처리한다(좌석은 입력 정제를 강요하지 않음 — 검증은 HTTP 표면의 q 필수 제약이 한다).
    """
    resolved = settings if settings is not None else get_settings()

    # memory 모드 — 영속 store 부재로 적재 자체가 불가능했다. 조용한 무동작 금지: 빈 결과를
    # 명시적으로 돌려주고(예외·None 아님) 호출자가 안내한다(슬3 populate CLI의 memory 거부와 동형).
    if resolved.vector_store != "pgvector":
        return []

    if top_k <= 0:
        return []

    provider_name, model_name = _provider_model_identity(provider, resolved)
    idx = (
        index
        if index is not None
        else ConceptEmbeddingIndex(
            provider_name=provider_name, model_name=model_name, settings=resolved
        )
    )

    # 질의 1건 임베딩(배치 API에 단건 — provider 계약은 입력 순서·길이 보존). 결과가 1건이 아니면
    # provider가 계약을 어긴 것(방어). 빈 입력이 아니므로 정상 provider는 정확히 1행을 돌려준다.
    vectors = provider.embed([query_text])
    if len(vectors) != 1:
        raise RuntimeError(
            f"질의 임베딩이 1건이 아닙니다(받음: {len(vectors)}) "
            "— provider.embed가 단건 입력에 1행을 돌려줘야 합니다."
        )

    # search는 (concept_id, similarity) 튜플을 유사도 내림차순으로 돌려준다(슬3 백킹 프리미티브).
    hits = idx.search(vectors[0], top_k=top_k)
    return [
        ConceptSearchHit(concept_id=concept_id, similarity=similarity)
        for concept_id, similarity in hits
    ]


__all__ = [
    "ConceptSearchHit",
    "search_concepts",
]
