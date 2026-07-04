"""원자 의미검색 *조회 좌석* — pgvector 검색 + 메타 enrichment·검수 게이팅 (원자 백본·S0-4a).

`l1/concept_graph/retrieval.py`(구 437 개념 의미검색 조회 좌석)의 *원자 백본* 짝이다 —
백킹만 교체한 **정밀 미러**다. Phase 2b(`embedding.py`)가 원자 안전 표현을 `atom_embedding`
(pgvector)에 멱등 적재했고, Phase 2a(`atom_node_projection.py`)가 원자 *안전 메타*를 `atom_node`
(PG)에 code 키로 적재했다. 이 모듈은 그 *적재된 임베딩을 조회*하고 **메타를 PG 조인으로 enrich**
하며 **검수 게이팅**을 거는 좌석이다 — 질의 텍스트 1건을 임베딩(provider 재사용)해
`AtomEmbeddingIndex.search`로 코사인 상위 top_k를 랭킹하고, 그 code들로 `atom_node`를 조회해
`name_ko`·`subject_area`·`review_status`를 붙인다(있으면).

────────────────────────────────────────────────────────────────────────────
runtime truth source = 원자(1개) — S0-4a 전환의 핵심 (사용자 결정)
────────────────────────────────────────────────────────────────────────────
`GET /v1/concepts/search`(HTTP 표면)가 런타임에 구 437(`concept_embedding`/`concept_node`)을
읽는 것이 "runtime truth source=1"을 깨는 *유일 지점*이었다. 이 좌석이 그 지점을 원자 축으로
전환한다 — 표면은 `search_concepts` 대신 `search_atoms`를 호출하고, 결과 키(`atom_code`)가
런타임 정본이 된다. 구 `search_concepts` 좌석은 *삭제하지 않고 존치*(S0-4b에서 legacy_snapshot
audit용)하되 런타임 API 호출만 이 좌석으로 옮긴다.

────────────────────────────────────────────────────────────────────────────
concept 판과의 차이 (백킹만 교체·나머지 정밀 미러)
────────────────────────────────────────────────────────────────────────────
  - **키**: `atom_code`(원자ID/소단원/단원코드·`atom_embedding`/`atom_node` 공간) — UC 아님.
  - **임베딩 인덱스**: `AtomEmbeddingIndex`(`ConceptEmbeddingIndex` 대체·`.search`는 동형 튜플).
  - **메타 조회**: `fetch_atom_node_meta`(`fetch_node_meta` 대체·`atom_node` 조인).
  - **영역 축**: concept의 `domain`↔원자 `subject_area`(파라미터·필드명 대응). subject_area는
    nullable이라 메타가 있어도 값이 None일 수 있다(단원/소단원 등).
  - **review_status는 상수 'ai_estimated'**: 원자 메타(`atom_node`)는 전 행이 AI 추정이다
    (`ATOM_REVIEW_STATUS_AI_ESTIMATED`). 따라서 **`reviewed_only=True`면 원자는 전부 제외된다**
    (게이팅이 `review_status == "reviewed"`만 남기므로·정직). 이는 구 437(reviewed/pending 혼재)과
    다른 동작이다 — 원자 검수 승격 전까지 gated 모드는 빈 결과가 정상이다.

────────────────────────────────────────────────────────────────────────────
노출 계약 (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
이 좌석은 **학생 직접 노출이 아니다** — L2(약개념 추천)·L4(오개념↔개념 연결)·교사 도구가
*소비*하는 내부 조회 표면이다. enrichment로 추가되는 건 *안전 표시·게이팅 필드*뿐이다:
`name_ko`·`subject_area`·`review_status`. **본문(core_proposition·description·formal_definition)은
0** — `atom_node`에 컬럼 자체가 없어(redaction) 조회로 흐를 경로가 구조적으로 없다. 검색은 임베딩
*벡터* 위에서만 돌고(`atom_embedding`엔 원문이 없다), 메타 조인은 안전 필드만 SELECT한다.

7계층: L1 데이터 *조회 서빙*. **L2/L4 로직을 구현하지 않는다** — 좌석만 제공하고, L2/L4가 이
좌석을 *호출*하는 건 후속(역방향 의존 금지·CLAUDE.md 경계). HTTP 표면(L5)은 `api/concepts.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.l1.atom_graph.atom_node_projection import fetch_atom_node_meta
from whymath_backend.l1.atom_graph.embedding import AtomEmbeddingIndex

# provider 공간 식별자(provider→model 규약)는 적재와 *같은 seam*을 재사용한다(신규 0). 같은
# 규약을 search가 써야 적재 행과 같은 임베딩 공간을 본다(provider/model 불일치 시 빈 결과).
# 레이어-중립 L1 프리미티브(`l1/embedding_primitives.py`)에서 가져온다(L1→L1·역방향 의존 0).
from whymath_backend.l1.embedding_primitives import (
    normalize_embedding_input,
    provider_model_identity,
)

if TYPE_CHECKING:
    from whymath_backend.l1.embedding_primitives import EmbeddingProvider

# 게이팅 비교 리터럴 — 'reviewed'로 승격된 원자만 통과시키는 값. 현재 `atom_node.review_status`는
# 전 행 'ai_estimated'(AI 추정)이라 `reviewed_only=True`면 원자는 전부 제외된다(정직).
_REVIEWED: str = "reviewed"


@dataclass(frozen=True, slots=True)
class AtomSearchHit:
    """원자 의미검색 결과 1건 — atom_code + 코사인 유사도 + *안전* 메타(enrich).

    `ConceptSearchHit`의 *원자 백본* 짝이다. `atom_code`는 원자 정본 키(`atom_embedding`·
    backend `concept.code`와 동일 공간·원자ID/소단원코드/단원코드). `similarity`는 질의 임베딩과의
    코사인 [-1, 1](클수록 의미 근접). `name_ko`·`subject_area`·`review_status`는 `atom_node`
    (PG 프로젝션) 조인으로 붙인 *안전 표시·게이팅 필드*다 — `atom_node`에 해당 원자 메타가
    없으면(적재 누락) **None**(graceful). concept의 `domain` 자리에 원자는 `subject_area`를 두며,
    subject_area는 nullable이라 메타가 있어도 None일 수 있다. **본문(core_proposition·description·
    formal_definition)은 미포함** — 프로젝션 테이블에 컬럼 자체가 없다(redaction·노출 계약).
    소비처(L2/L4·교사 도구)는 atom_code 키 + 이 안전 메타로 동작한다.
    """

    atom_code: str
    similarity: float
    name_ko: str | None = None
    subject_area: str | None = None
    review_status: str | None = None


def search_atoms(
    query_text: str,
    *,
    top_k: int,
    provider: EmbeddingProvider,
    reviewed_only: bool = False,
    min_similarity: float | None = None,
    subject_area: str | None = None,
    index: AtomEmbeddingIndex | None = None,
    settings: Settings | None = None,
) -> list[AtomSearchHit]:
    """질의 텍스트 → 임베딩 → 코사인 상위 top_k → 메타 enrich·검수/임계/영역 게이팅(랭킹 결과).

    `search_concepts`의 *원자 백본* 짝(백킹만 교체). 흐름: ① `provider.embed([query_text])`로 질의
    1건 임베딩 ② `AtomEmbeddingIndex.search`로 적재 임베딩과 코사인 비교(상위 K·유사도 내림차순)
    ③ 잡힌 code들로 `fetch_atom_node_meta`(atom_node PG 조인)를 한 번 호출해 `name_ko`·
    `subject_area`·`review_status`를 붙임 ④ `reviewed_only`·`min_similarity`·`subject_area`
    게이팅으로 히트를 *제외*(유사도 정렬 유지·게이팅은 필터).

    **enrichment graceful**: `atom_node`에 없는 code는 메타 None으로 채운다(적재 누락에 안전 —
    검색 자체는 계속). 메타 조회는 검색 좌석과 같은 sync 엔진 평면에서 IN 한 방으로 일어난다
    (N+1 없음·index가 주입한 엔진을 메타 조회에도 공유).

    **게이팅(`reviewed_only`)**: 기본 False=recall 보존. True면 상위 top_k 창에서
    `review_status == "reviewed"`인 히트만 남긴다 — 메타가 없어 reviewed 확인 불가인 code는
    보수적으로 제외(정직). **주의(구 437과 다름)**: `atom_node.review_status`는 현재 전 행
    상수 'ai_estimated'이므로, `reviewed_only=True`면 원자는 *전부* 제외돼 빈 결과가 된다(원자
    검수 승격 전까지 정상 동작·정직 표기).

    **임계 게이팅(`min_similarity`)**: 기본 None=임계 없음(순수 랭킹). 값이 주어지면
    `similarity < min_similarity`인 히트를 제외한다 — semantic search *실패*가 조용히 하류로
    전파되는 것을 좌석에서 선택적으로 막는 안전 노브다. 코사인 유사도 축은 [-1, 1].

    **영역 스코프(`subject_area`)**: 기본 None=전 영역(concept의 `domain` 스코프에 대응). 값이
    주어지면 enrich된 `atom_node.subject_area`가 *정확히 일치*하는 히트만 남긴다 — 학교급/영역만
    다른 동명 원자의 embedding collision을 호출자가 좁힌다. 메타가 없거나 subject_area가 None이라
    확인 불가인 code는 보수적으로 제외(reviewed_only와 동일 규약·정직).

    세 게이팅 모두 *창 내 필터*라 결과가 top_k보다 적을 수 있다(정렬은 유지). 필터가 회수 후
    적용되므로, 강한 스코프에서 top_k를 넉넉히 주면(over-fetch) recall을 보전할 수 있다.

    provider·index는 *주입 가능*하다(테스트 격리·Fake). index 미주입 시 적재(Phase 2b)와 같은
    provider 공간 식별자(`provider_model_identity`)로 `AtomEmbeddingIndex`를 만든다 — 같은 공간
    행만 봐야 적재 결과가 잡힌다.

    memory 모드 graceful(조용한 무동작 금지): `vector_store != pgvector`면 영속 임베딩 store가
    없다(적재가 불가능했다) → **빈 리스트**를 돌려준다(예외 아님·embed도 생략). pgvector 모드인데
    빈 결과면 그건 *진짜로 매칭이 없거나 미적재*다(같은 정직 신호). top_k<=0이면 빈 리스트.
    """
    resolved = settings if settings is not None else get_settings()

    # memory 모드 — 영속 store 부재로 적재 자체가 불가능했다. 조용한 무동작 금지: 빈 결과를
    # 명시적으로 돌려주고(예외·None 아님) 호출자가 안내한다(적재 CLI의 memory 거부와 동형).
    if resolved.vector_store != "pgvector":
        return []

    if top_k <= 0:
        return []

    provider_name, model_name = provider_model_identity(provider, resolved)
    idx = (
        index
        if index is not None
        else AtomEmbeddingIndex(
            provider_name=provider_name, model_name=model_name, settings=resolved
        )
    )

    # 질의 1건 임베딩(배치 API에 단건 — provider 계약은 입력 순서·길이 보존). 결과가 1건이 아니면
    # provider가 계약을 어긴 것(방어). 질의도 원자 표현(`atom_embedding_text`→`join_embedding_text`)
    # 과 *같은* NFKC 정규화를 거쳐 표기 흔들림에 의한 무매칭을 막는다.
    vectors = provider.embed([normalize_embedding_input(query_text)])
    if len(vectors) != 1:
        raise RuntimeError(
            f"질의 임베딩이 1건이 아닙니다(받음: {len(vectors)}) "
            "— provider.embed가 단건 입력에 1행을 돌려줘야 합니다."
        )

    # search는 (atom_code, similarity)를 유사도 내림차순으로 돌려준다(Phase 2b 백킹).
    hits = idx.search(vectors[0], top_k=top_k)
    if not hits:
        return []

    # 메타 enrichment — 잡힌 code들로 atom_node를 단일 IN 조회(PG 조인·N+1 없음). 검색 좌석이
    # 쓴 *같은 sync 엔진*을 메타 조회에도 공유한다(index가 엔진을 들고 있으면 그걸 넘김 — 별
    # 엔진 생성·연결 폭주 방지). 없는 code는 dict에서 빠지고 아래에서 None으로 채운다(graceful).
    codes = [code for code, _sim in hits]
    meta = fetch_atom_node_meta(codes, engine=idx._engine, settings=resolved)

    results: list[AtomSearchHit] = []
    for atom_code, similarity in hits:
        node = meta.get(atom_code)
        if reviewed_only and (node is None or node.review_status != _REVIEWED):
            # 게이팅 필터 — reviewed 아니거나 메타 미적재(확인 불가)면 제외(보수적·정직).
            # 현재 원자는 전 행 'ai_estimated'라 이 분기가 원자를 전부 제외한다(docstring 참조).
            continue
        if min_similarity is not None and similarity < min_similarity:
            # 임계 게이팅 — 근접도 미만은 제외(semantic 실패의 침묵 전파 차단). 정렬은 유지.
            continue
        if subject_area is not None and (node is None or node.subject_area != subject_area):
            # 영역 스코프 — 불일치·메타 미적재(확인 불가)면 제외(collision 방어·보수적·정직).
            continue
        results.append(
            AtomSearchHit(
                atom_code=atom_code,
                similarity=similarity,
                name_ko=node.name_ko if node is not None else None,
                subject_area=node.subject_area if node is not None else None,
                review_status=node.review_status if node is not None else None,
            )
        )
    return results


__all__ = [
    "AtomSearchHit",
    "search_atoms",
]
