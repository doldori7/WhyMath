"""개념 의미검색 *조회 좌석* — pgvector 검색 + 메타 enrichment·검수 게이팅 (소비 슬라이스 1).

슬3(`embedding.py`)이 개념 안전 표현을 `concept_embedding`(pgvector)에 멱등 적재했고, 소비 슬1
(`node_projection.py`)이 개념 *안전 메타*를 `concept_node`(PG)에 UC 키로 적재했다. 이 모듈은 그
*적재된 임베딩을 조회*하고(슬4 좌석) **메타를 PG 조인으로 enrich**하며 **검수 게이팅**을 거는
좌석이다 — 질의 텍스트 1건을 임베딩(provider 재사용)해 `ConceptEmbeddingIndex.search`로 코사인
상위 top_k를 랭킹하고, 그 UC들로 `concept_node`를 조회해 `name_ko`·`domain`·`review_status`를
붙인다(있으면).

────────────────────────────────────────────────────────────────────────────
메타 브리지 = PG 프로젝션 (확정 설계 결정 — backend↔Neo4j 런타임 연결 안 함)
────────────────────────────────────────────────────────────────────────────
슬4 좌석은 enrichment를 *후속*으로 미뤘다 — 그 사유가 **UC↔backend-PG 키 공간 차이**였다
(`concept_embedding.concept_id`는 UC 키인데 backend PG `concept` 테이블은 UUID PK+`code`라 UC
컬럼이 없었다). 소비 슬1이 그 다리를 놓는다: graph.json 개념 메타를 **UC 키 PG 테이블
(`concept_node`)로 프로젝션**하고, enrichment를 **PG 조인**(검색이 잡은 UC들로 `concept_node`
IN 조회)으로 한다. backend는 async-PG 단일 평면을 유지한다(런타임 Neo4j 드라이버 도입 0). 검색
좌석이 이미 sync(블로킹 임베딩+psycopg)라 enrichment 조회도 같은 sync 엔진 평면에서 일어난다
(`search` 직후 같은 워커 스레드 — HTTP 표면이 `asyncio.to_thread`로 격리).

────────────────────────────────────────────────────────────────────────────
노출 계약 (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
이 좌석은 **학생 직접 노출이 아니다** — L2(약개념 추천)·L4(오개념↔개념 연결)·교사 도구가
*소비*하는 내부 조회 표면이다(소비 로직은 후속·여기선 좌석만). enrichment로 추가되는 건
*안전 표시·게이팅 필드*뿐이다: `name_ko`·`domain`·`review_status`. **본문(description·
formal_definition)은 0** — `concept_node`에 컬럼 자체가 없어(`node_projection` redaction) 조회로
흐를 경로가 구조적으로 없다. 검색은 임베딩 *벡터* 위에서만 돌고(`concept_embedding`엔 원문이
없다), 메타 조인은 안전 필드만 SELECT한다. 금기 표현(우열·정답 빠르게)도 0.

검수 게이팅(`reviewed_only`)은 *필터*다 — 유사도 정렬은 유지하고, `reviewed_only=True`면 상위
top_k 창에서 `review_status != "reviewed"`(또는 메타 미적재로 확인 불가)인 히트를 *제외*한다.
기본 `False`는 recall 보존(pending 개념도 검색에 노출 — 의미검색 자체는 전량 대상). 검수 게이팅이
"검수 안 된 개념 노출 차단"이라는 *조회 정책*이므로, 메타가 없어 reviewed임을 확인 못 하는 UC는
gated 모드에서 보수적으로 뺀다(정직 — 확실하지 않으면 노출 안 함).

7계층: L1 데이터 *조회 서빙*. **L2/L4 로직을 구현하지 않는다** — 좌석만 제공하고, L2/L4가 이
좌석을 *호출*하는 건 후속(역방향 의존 금지·CLAUDE.md 경계). HTTP 표면(L5)은 `api/concepts.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.concept_graph.embedding import ConceptEmbeddingIndex
from whymath_backend.l1.concept_graph.node_projection import fetch_node_meta

# provider 공간 식별자(provider→model 규약)는 적재(슬3)와 *같은 seam*을 재사용한다(신규 0). 같은
# 규약을 search가 써야 적재 행과 같은 임베딩 공간을 본다(provider/model 불일치 시 빈 결과).
from whymath_backend.l4.misconception.semantic.pgvector_index import _provider_model_identity

if TYPE_CHECKING:
    from whymath_backend.l4.misconception.semantic.provider import EmbeddingProvider

# 게이팅 비교 리터럴 — graph.json `review_status`(use_enum_values)가 싣는 reviewed 값.
# `node_projection`이 같은 문자열을 `concept_node.review_status`에 적재한다(plain text).
_REVIEWED: str = "reviewed"


@dataclass(frozen=True, slots=True)
class ConceptSearchHit:
    """개념 의미검색 결과 1건 — UC concept_id + 코사인 유사도 + *안전* 메타(enrich·소비 슬1).

    `concept_id`는 Universal Concept ID(UC.<domain>.<topic>.<slug>·슬2 Neo4j 노드 키·슬3
    concept_embedding과 동일 공간)다. `similarity`는 질의 임베딩과의 코사인 [-1, 1](클수록 의미
    근접). `name_ko`·`domain`·`review_status`는 `concept_node`(PG 프로젝션) 조인으로 붙인 *안전
    표시·게이팅 필드*다 — `concept_node`에 해당 UC 메타가 없으면(적재 누락) **None**(graceful).
    **본문(description·formal_definition)은 미포함** — 프로젝션 테이블에 컬럼 자체가 없다
    (redaction·노출 계약). 소비처(L2/L4·교사 도구)는 UC 키 + 이 안전 메타로 동작한다.
    """

    concept_id: str
    similarity: float
    name_ko: str | None = None
    domain: str | None = None
    review_status: str | None = None


def search_concepts(
    query_text: str,
    *,
    top_k: int,
    provider: EmbeddingProvider,
    reviewed_only: bool = False,
    index: ConceptEmbeddingIndex | None = None,
    settings: Settings | None = None,
) -> list[ConceptSearchHit]:
    """질의 텍스트 → 임베딩 → 코사인 상위 top_k → 메타 enrich·검수 게이팅(랭킹된 결과).

    흐름: ① `provider.embed([query_text])`로 질의 1건 임베딩 ② `ConceptEmbeddingIndex.search`로
    적재 임베딩과 코사인 비교(상위 K·유사도 내림차순) ③ 잡힌 UC들로 `fetch_node_meta`(concept_node
    PG 조인)를 한 번 호출해 `name_ko`·`domain`·`review_status`를 붙임 ④ `reviewed_only`면 reviewed
    아닌(또는 메타 없는) 히트를 *제외*(유사도 정렬 유지·게이팅은 필터). 임계값 필터는 없다(순수
    랭킹 — 점수 컷은 소비처 몫).

    **enrichment graceful**: `concept_node`에 없는 UC는 메타 None으로 채운다(적재 누락에 안전 —
    검색 자체는 계속). 메타 조회는 검색 좌석과 같은 sync 엔진 평면에서 IN 한 방으로 일어난다
    (N+1 없음·index가 주입한 엔진을 메타 조회에도 공유).

    **게이팅(`reviewed_only`)**: 기본 False=recall 보존(pending 개념도 노출). True면 상위 top_k
    창에서 `review_status == "reviewed"`인 히트만 남긴다 — 메타가 없어 reviewed 확인 불가인 UC는
    보수적으로 제외(정직). 게이팅은 *필터*라 결과가 top_k보다 적을 수 있다(창 내 필터 — 정렬 유지).

    provider·index는 *주입 가능*하다(테스트 격리·Fake). index 미주입 시 적재(슬3)와 같은 provider
    공간 식별자(`_provider_model_identity`)로 `ConceptEmbeddingIndex`를 만든다 — 같은 공간 행만
    봐야 적재 결과가 잡힌다.

    memory 모드 graceful(조용한 무동작 금지): `vector_store != pgvector`면 영속 임베딩 store가
    없다(적재가 불가능했다) → **빈 리스트**를 돌려준다(예외 아님·embed도 생략). pgvector 모드인데
    빈 결과면 그건 *진짜로 매칭이 없거나 미적재*다(같은 정직 신호). top_k<=0이면 빈 리스트.
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
    if not hits:
        return []

    # 메타 enrichment — 잡힌 UC들로 concept_node를 단일 IN 조회(PG 조인·N+1 없음). 검색 좌석이
    # 쓴 *같은 sync 엔진*을 메타 조회에도 공유한다(index가 엔진을 들고 있으면 그걸 넘김 — 별
    # 엔진 생성·연결 폭주 방지). 없는 UC는 dict에서 빠지고 아래에서 None으로 채운다(graceful).
    concept_ids = [cid for cid, _sim in hits]
    meta = fetch_node_meta(concept_ids, engine=idx._engine, settings=resolved)

    results: list[ConceptSearchHit] = []
    for concept_id, similarity in hits:
        node = meta.get(concept_id)
        if reviewed_only and (node is None or node.review_status != _REVIEWED):
            # 게이팅 필터 — reviewed 아니거나 메타 미적재(확인 불가)면 제외(보수적·정직).
            continue
        results.append(
            ConceptSearchHit(
                concept_id=concept_id,
                similarity=similarity,
                name_ko=node.name_ko if node is not None else None,
                domain=node.domain if node is not None else None,
                review_status=node.review_status if node is not None else None,
            )
        )
    return results


__all__ = [
    "ConceptSearchHit",
    "search_concepts",
]
