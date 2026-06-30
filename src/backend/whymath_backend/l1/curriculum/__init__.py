"""L1 교육과정 Overlay — 개념그래프 graph.json → backend `curriculum_entry`(KR 셀) 적재 인프라.

L1 데이터 기반 적재 아크의 *교육과정 Overlay* 부분이다. `Concept`에서 제거된 교육과정 필드
(`subject`·`curriculum_version`·`grade_introduced`·`semester_introduced`)를 대신해 교육과정 분류를
담는 단일 진실이 `curriculum_entry` Overlay다(math_dsl_risk_register Q5·Q8·Q10-③ "노드는 의미만·
교육과정은 Overlay"). P1-2 슬라이스가 ORM(`db/models/curriculum_entry.py`)·계약
(`schema/curriculum_entry.py`)·마이그레이션(`1551744048aa`)만 세우고 코퍼스 로더는 *후속 몫*으로
보류했는데, 이 패키지가 그 로더를 담는다.

`l1/concept_graph`(개념 노드·엣지 적재)의 *교육과정 Overlay* 짝이며 같은 sync 좌석·멱등 규약을
따른다:
  - `load_kr_curriculum_entries_from_graph_json` — graph.json `concepts`를 개념당 1개의 KR 셀
    (concept_id × "KR")로 매핑(domain→domain_label·grade_band_hint→grade_band/introduced_grade·
    standard_codes→national_standard_codes). KR 상수(교육부 고시 제2022-33호·NCIC·공공누리 1유형)는
    graph.json source_citation에서 정직 도출.
  - `CurriculumEntryStore`·`populate_kr_curriculum_entries` — backend `curriculum_entry`에 entry_id
    PK 충돌 멱등 upsert(재적재는 갱신·`created_at` 보존). 셀의 concept_id는 FK 아닌 느슨참조라 개념
    선적재에 의존하지 않는다(독립 적재 가능). Phase 1 범위는 KR만(US·IMO는 코퍼스 부재).

7계층: L1 데이터 기반의 *Overlay 적재 인프라*. 소비(자동 커리큘럼 정렬·L6)는 이 좌석을 호출하되
여기서 구현하지 않는다(후속·역방향 의존 금지).
"""

from __future__ import annotations

from whymath_backend.l1.curriculum.curriculum_loader import (
    CurriculumEntryStore,
    load_kr_curriculum_entries_from_graph_json,
    populate_kr_curriculum_entries,
)
from whymath_backend.l1.curriculum.populate import main as populate_main

__all__ = [
    "CurriculumEntryStore",
    "load_kr_curriculum_entries_from_graph_json",
    "populate_kr_curriculum_entries",
    "populate_main",
]
