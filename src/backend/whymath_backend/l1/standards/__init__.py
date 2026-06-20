"""L1 성취기준 — NCIC 코퍼스 → backend 영속/적재 인프라 (P1 코퍼스 로더).

L1 데이터 기반 적재 아크의 *성취기준* 부분이다. P1-2 슬라이스가 성취기준의 ORM
(`db/models/achievement_standard.py`·`concept_standard_link.py`)·계약(`schema/standard.py`)·
마이그레이션만 세우고 코퍼스 로더는 *후속 몫*으로 보류했는데, 이 패키지가 그 로더를 담는다 —
data-pipeline NCIC 수집기가 낸 *Collection JSON*(단일 객체·jsonl 아님)을 backend 영속 두 테이블
(`achievement_standard`·`concept_standard_link`)로 멱등 적재한다.

`l1/concept_graph`(개념 노드·엣지 적재)의 성취기준 짝이며 같은 sync 좌석·멱등 규약을 따른다:
  - `load_standards`·`AchievementStandardStore` — 성취기준 Collection의 `standards` 배열을
    backend `achievement_standard`에 `norm_id` PK 충돌 멱등 upsert. 코퍼스 `code`→`official_code`
    rename(혼동 회피)을 로더가 메운다. official_code 비유일(2022·2015 충돌)은 2행으로 적재된다.
  - `load_links`·`ConceptStandardLinkStore` — 링크 Collection의 `links` 배열을 backend
    `concept_standard_link`에 의미키 `(concept_code, norm_id, link_type)` 충돌 멱등 upsert. 코퍼스
    `concept_src_id`→`concept_code` store-direct rename(concept_code는 FK 아닌 느슨참조라 *해석
    없이* 그대로 저장 — backend_edge가 UC→UUID로 해석한 것과 대비). 실 FK `norm_id`가 적재 성취기준
    집합에 없으면 orphan으로 skip한다(FK 위반 방지·backend_edge orphan skip 미러).

7계층: L1 데이터 기반의 *영속/적재 인프라*. 소비(커리큘럼 정렬·진단·개념↔기준 조회)는 이 좌석을
호출하되 여기서 구현하지 않는다(후속·역방향 의존 금지).
"""

from __future__ import annotations

from whymath_backend.l1.standards.populate import main as populate_main
from whymath_backend.l1.standards.standard_loader import (
    AchievementStandardStore,
    ConceptStandardLinkStore,
    load_links,
    load_standards,
)

__all__ = [
    "AchievementStandardStore",
    "ConceptStandardLinkStore",
    "load_links",
    "load_standards",
    "populate_main",
]
