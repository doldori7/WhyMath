"""L2 약개념 추천 — BKT/IRT 약점 진단 + 개념그래프 안전 메타 enrich (개념그래프 소비 슬2).

L1 개념그래프 *소비* 아크의 다음 좌석이다. 적재 아크(슬1~4)·브리지(#167)로 backend `concept`
(UUID PK·`code`=UC)·`concept_node`(UC PK)·`concept_embedding`(UC)가 *동일 UC 키*로 사중 store에
연결됐고, 소비 슬1(`l1/concept_graph/retrieval.search_concepts`)이 의미검색에 `concept_node` 안전
메타를 enrich하는 길을 열었다. 이 모듈은 그 enrich 경로를 *학습자 약점*으로 끌어온다 — L2
학습자 모델(BKT/IRT)이 식별한 약개념에 `concept_node`(UC) 안전 그래프 메타(name_ko·domain·
review_status)를 붙여 "지금 무엇을 복습할지" 후보를 돌려준다.

────────────────────────────────────────────────────────────────────────────
재사용 좌석 (신규 진단·정렬 로직 0)
────────────────────────────────────────────────────────────────────────────
① 진단·약점 정렬 — `l2.concept_diagnosis.compute_concept_diagnoses`를 *그대로* 입력으로 쓴다
   (BKT 최신 숙달 + IRT θ 융합·agreement·*약점 먼저* 정렬 이미 수행). 여기서 IRT/BKT 융합이나
   약점 정렬을 재구현하지 않는다 — 진단 결과에 *필터·enrich·상한*만 얹는다.
② UC enrich — `l1.concept_graph.node_projection.fetch_node_meta`(UC 리스트 → concept_node 안전
   메타 단일 IN 조회)를 재사용한다. 검색 좌석(`search_concepts`)이 enrich에 쓴 *같은* 좌석이다.

────────────────────────────────────────────────────────────────────────────
sync 엔진 재사용 (검색 좌석과 동일 패턴 — 신규 동시성 0)
────────────────────────────────────────────────────────────────────────────
`fetch_node_meta`는 *sync 엔진*(블로킹 psycopg)이고 이 함수는 async다. 검색 좌석(api/concepts·
coach)이 sync 좌석을 `asyncio.to_thread`로 워커 스레드에 격리하는 *바로 그 패턴*을 따른다 —
이벤트 루프를 막지 않게(CLAUDE.md p50<2s·동시 요청 보호). 새 동시성 패턴을 발명하지 않는다.

────────────────────────────────────────────────────────────────────────────
redaction·노출 계약 (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
enrich되는 건 *안전 표시·게이팅 필드*뿐(name_ko·domain·review_status). **description·
formal_definition·intuitive_explanation은 어디에도 유입되지 않는다** — `concept_node`에 컬럼
자체가 없어(`node_projection`·`ConceptNodeMeta` redaction) 조회로 흐를 경로가 구조적으로 없다.
이 좌석은 *학생 직접 노출이 아니라* 내부 조회 좌석이다(소비 슬1 노출 계약과 일관) — 우열 매기기·
정답 빠르게 등 금기 표현 0.

검수 게이팅(`reviewed_only`)은 *필터*다 — 약점 정렬은 유지하고, True면 `review_status ==
"reviewed"`인 개념만 남긴다(메타 없어 확인 불가인 UC는 보수적 제외 — 소비 슬1 게이팅 규약과
일관·"확실하지 않으면 노출 안 함"). 기본 False는 recall 보존.

7계층: L2 학습자 모델이 L1 `fetch_node_meta`를 *호출*(L_n→L_{n-1} 허용·경계 준수). L4 코칭·L5
노출은 부착하지 않는다(역방향 의존 회피 — 코칭은 L4·HTTP 표면은 api/me).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l1.concept_graph.node_projection import ConceptNodeMeta, fetch_node_meta
from whymath_backend.l2.concept_diagnosis import (
    Agreement,
    ConceptDiagnosis,
    compute_concept_diagnoses,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# 검수 게이팅 비교 리터럴 — `concept_node.review_status`가 싣는 reviewed 값(retrieval `_REVIEWED`
# 와 동일 규약). graph.json `use_enum_values`가 같은 문자열을 적재한다.
_REVIEWED: str = "reviewed"


class WeakConceptRecommendation(BaseModel):
    """약개념 추천 1건 — 진단 약점 신호 + `concept_node`(UC) 안전 그래프 메타(enrich·소비 슬2).

    `compute_concept_diagnoses`의 약점 진단(BKT/IRT)에 `concept_node` 안전 메타를 붙인 형태다.
    `weakness`는 비교 가능한 두 신호(bkt_mastery·irt_mastery_proxy) 중 *최저값*(정렬·필터 기준).
    `domain`·`review_status`·`name_ko`는 `concept_node`(PG 프로젝션) UC 조인으로 붙인 *안전
    표시·게이팅 필드*다 — 메타 미적재 UC(또는 orphan으로 UC 없음)면 **None**(graceful).
    **본문(description·formal_definition)은 미포함** — `concept_node`에 컬럼 자체가 없어 구조적
    으로 흐를 수 없다(redaction·노출 계약).
    """

    concept_id: uuid.UUID = Field(description="개념 id(backend `concept` UUID PK).")
    concept_code: str | None = Field(
        default=None, description="개념 코드(=UC·개념그래프 키). orphan이면 null."
    )
    concept_name: str | None = Field(
        default=None, description="개념명(backend `concept`.name_ko·orphan이면 null)."
    )
    bkt_mastery: float | None = Field(
        default=None, description="BKT 최신 숙달 P(L). 측정 없으면 null."
    )
    irt_mastery_proxy: float | None = Field(
        default=None, description="logistic(θ)∈[0,1] — IRT 능력 프록시. θ 없으면 null."
    )
    weakness: float | None = Field(
        default=None,
        description="두 신호(bkt_mastery·irt_mastery_proxy) 중 최저값(약점 정렬·필터 기준). "
        "비교 가능한 신호가 없으면 null(이 경우 추천에서 제외).",
    )
    agreement: Agreement = Field(
        description="BKT↔IRT 일치 신호(agree·irt_higher·bkt_higher·insufficient)."
    )
    domain: str | None = Field(
        default=None,
        description="개념 영역명(concept_node 조인·안전 표시 필드). 메타 미적재 시 null.",
    )
    review_status: str | None = Field(
        default=None,
        description="검수 상태('reviewed'/'pending'·concept_node 조인·게이팅 플래그). "
        "메타 미적재 시 null.",
    )
    name_ko: str | None = Field(
        default=None,
        description="개념 한국어 표시명(concept_node 조인·안전 표시 필드). 메타 미적재 시 null.",
    )


def _weakness_of(diagnosis: ConceptDiagnosis) -> float | None:
    """비교 가능한 신호(bkt_mastery·irt_mastery_proxy) 중 최저값 — 둘 다 없으면 None.

    `compute_concept_diagnoses`의 약점 정렬 키와 *동일 정의*(최저 신호 = 약점). 신호가 하나도
    없으면 추천 근거가 없으므로 None을 돌려 호출부가 제외한다(insufficient도 한쪽 신호는 있으면
    그 값으로 약점 판정 — 신호 0건만 제외).
    """
    signals = [v for v in (diagnosis.bkt_mastery, diagnosis.irt_mastery_proxy) if v is not None]
    return min(signals) if signals else None


async def recommend_weak_concepts(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 10,
    mastery_threshold: float = 0.7,
    reviewed_only: bool = False,
    meta_engine: Engine | None = None,
) -> list[WeakConceptRecommendation]:
    """학습자 약점(BKT/IRT) → 약점 필터 → `concept_node`(UC) 안전 메타 enrich → 상위 N 추천.

    흐름:
      ① `compute_concept_diagnoses`로 개념별 진단(BKT 최신 + IRT θ 융합·*약점 먼저* 정렬)을 받는다
         — 진단·정렬은 L2 좌석 재사용(신규 0). 정렬은 이미 약점 우선이라 이 함수가 보존한다.
      ② **약점 필터** — 비교 가능한 신호(bkt_mastery·irt_mastery_proxy 중 존재) 최저값이
         `mastery_threshold` *미만*인 개념만(약점). 신호가 하나도 없으면 추천 근거 없음으로 제외.
      ③ **UC enrich** — 약점 후보들의 `concept_code`(None 아닌 UC)를 모아 `fetch_node_meta`를
         *단일 호출*(N+1 0)로 `concept_node` 안전 메타를 받아 붙인다. UC 없거나(orphan) 메타
         미적재면 enrich 필드 None graceful. `fetch_node_meta`는 sync(블로킹 psycopg)라
         `asyncio.to_thread`로 워커 스레드에 격리한다(검색 좌석 패턴 미러·이벤트 루프 보호).
      ④ **검수 게이팅** — `reviewed_only=True`면 `review_status == "reviewed"`인 개념만(메타
         없어 확인 불가인 UC는 보수적 제외 — 소비 슬1 규약). 기본 False는 recall 보존.
      ⑤ **상한** — 약점 정렬을 보존하며 상위 `limit`개만 반환.

    user_id 스코핑·읽기 전용(마이그레이션 불필요). `meta_engine` 주입 가능(테스트 격리·검색
    좌석이 같은 엔진을 공유하듯). enrich되는 건 안전 필드(name_ko·domain·review_status)뿐 —
    본문(description·formal_definition)은 `concept_node`에 컬럼이 없어 구조적으로 0(redaction).
    """
    # ① 진단(약점 먼저 정렬) — L2 좌석 재사용. 융합·정렬·합집합은 이 좌석이 이미 수행.
    diagnoses = await compute_concept_diagnoses(session, user_id)

    # ② 약점 필터 — 최저 신호 < 임계인 개념만(신호 0건은 None → 제외). 정렬은 보존(in-place 순서).
    weak: list[tuple[ConceptDiagnosis, float]] = []
    for diagnosis in diagnoses:
        weakness = _weakness_of(diagnosis)
        if weakness is not None and weakness < mastery_threshold:
            weak.append((diagnosis, weakness))

    if not weak:
        return []

    # ③ UC enrich — 약점 후보의 UC(concept_code) 중복 제거해 단일 IN 조회. orphan(UC None)은 제외.
    #    fetch_node_meta는 sync 엔진(블로킹)이라 워커 스레드로 격리(검색 좌석 to_thread 패턴 미러).
    uc_list = sorted({d.concept_code for d, _ in weak if d.concept_code is not None})
    meta: dict[str, ConceptNodeMeta] = {}
    if uc_list:
        meta = await asyncio.to_thread(fetch_node_meta, uc_list, engine=meta_engine)

    # ④/⑤ 게이팅 필터 + 상한 — 약점 정렬 보존하며 reviewed 필터 후 상위 limit.
    out: list[WeakConceptRecommendation] = []
    for diagnosis, weakness in weak:
        node = meta.get(diagnosis.concept_code) if diagnosis.concept_code is not None else None
        if reviewed_only and (node is None or node.review_status != _REVIEWED):
            # 게이팅 — reviewed 아니거나 메타 미적재(확인 불가)면 제외(보수적·정직·소비 슬1 규약).
            continue
        out.append(
            WeakConceptRecommendation(
                concept_id=diagnosis.concept_id,
                concept_code=diagnosis.concept_code,
                concept_name=diagnosis.concept_name,
                bkt_mastery=diagnosis.bkt_mastery,
                irt_mastery_proxy=diagnosis.irt_mastery_proxy,
                weakness=weakness,
                agreement=diagnosis.agreement,
                domain=node.domain if node is not None else None,
                review_status=node.review_status if node is not None else None,
                name_ko=node.name_ko if node is not None else None,
            )
        )
        if len(out) >= limit:
            break  # 상한 — 약점 정렬 보존하며 상위 N(게이팅 후 카운트).

    return out


__all__ = [
    "WeakConceptRecommendation",
    "recommend_weak_concepts",
]
