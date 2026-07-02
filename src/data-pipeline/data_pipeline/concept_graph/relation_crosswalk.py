"""관계 어휘 crosswalk — L1 pipeline `Relation` ↔ L2 backend `EdgeType` 단일 명세.

**왜 필요한가(Part 3 항목 ② 갭):** 관계 어휘가 코드베이스에 3중으로 존재하고 이름이 어긋난다.
  - pipeline `Relation`(models.py) = **L1 canonical 데이터 어휘**(7종·소문자).
  - backend `EdgeType`(whymath_backend/schema/enums.py) = **L2 런타임 투영 어휘**(6종·대문자).
  - atom `AtomRelation`(atom_graph/models.py) = 원자 백본(1종·prerequisite).
이름이 다르고(예: pipeline `generalization` ↔ backend `EXTENDS`·`composition` ↔ `COMPOSED_OF`)
단일 진실 원천이 없었다. 이 모듈이 pipeline→backend **투영 계약**을 명문화하고, 거버넌스
테스트(`test_relation_vocabulary_governance.py`)가 이를 동결한다. 사람이 읽는 정본 표는
`docs/data/concept_graph.md` §2.2 crosswalk.

**계층 경계:** data-pipeline(L1)과 backend(L2)는 *별도 pytest 스위트*(testpaths 분리·별도 설치)
라 서로 import할 수 없다. 따라서 여기서는 backend `EdgeType`을 *import하지 않고* 문자열로
미러한다(`KNOWN_BACKEND_EDGE_TYPES`). backend 쪽 동결은 backend 스위트의
`tests/backend/l1/test_edge_relation_governance.py`가 자기 enum에 대해 수행한다 — 두 미러가
어긋나면 crosswalk 표를 의식적으로 갱신해야 한다(조용한 drift 차단).

**적재 현황:** 현재 어느 적재기도 `prerequisite` 외 관계를 backend `concept_edge`에 적재하지
않는다(약한 관계 N² dense화 방어 — `test_edge_relation_governance.py`). 이 crosswalk는 관계가
*노드화·적재될 때*의 투영 어휘를 미리 못 박는다(어휘 확정 ≠ 적재 개시).
"""

from __future__ import annotations

from typing import Final

from data_pipeline.concept_graph.models import RELATION_TYPES

# backend 런타임 투영이 아직 정의되지 않은 pipeline 관계 표식(어휘는 L1에 존재·투영 미정).
DEFERRED: Final[str] = "deferred"

# pipeline `Relation` value → backend `EdgeType` value(대문자 문자열) 또는 DEFERRED.
# 방향 주의: generalization·specialization은 backend에 단일 `EXTENDS`로 투영된다
#   (backend는 방향을 EXTENDS 한 축으로 흡수 — specialization은 EXTENDS의 역방향 해석).
# application·notation_variant는 backend 런타임 대응이 없어 DEFERRED.
RELATION_TO_BACKEND_EDGE_TYPE: Final[dict[str, str]] = {
    "prerequisite": "PREREQUISITE",
    "generalization": "EXTENDS",
    "specialization": "EXTENDS",
    "contrast": "CONTRASTS",
    "composition": "COMPOSED_OF",
    "application": DEFERRED,
    "notation_variant": DEFERRED,
}

# backend `EdgeType` 값 미러(L2 소스 물리 분리 — import 불가). backend enums.py의 EdgeType과
# backend 거버넌스 테스트가 동일 집합을 각자 freeze한다. crosswalk 표적 검증의 단일 원천.
KNOWN_BACKEND_EDGE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "PREREQUISITE",
        "COMPOSED_OF",
        "ANALOGOUS_TO",
        "EXTENDS",
        "CONTRASTS",
        "TRIGGERS_DISTRACTOR",
    }
)

# traversal에서 배제해야 하는 *약한* backend 관계 — CLAUDE.md "similar_to/related_to를 traversal에
# 쓰지 마라"의 실제 대응물. ANALOGOUS_TO(유사)·TRIGGERS_DISTRACTOR(오개념 유발)를 선수 그래프
# traversal에 넣으면 N² dense화·attention 희석. prerequisite만 traversal 대상(단일 진실).
TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES: Final[frozenset[str]] = frozenset(
    {"ANALOGOUS_TO", "TRIGGERS_DISTRACTOR"}
)

# 어느 관계 어휘에도 등장해선 안 되는 총칭 관계 토큰(관계 타입 폭발 방어 — Part 3·8대 원칙 ③).
# `similar_to`/`related_to`는 의미가 약해 traversal에 쓰면 그래프가 dense화된다(금지 어휘).
FORBIDDEN_RELATION_TOKENS: Final[frozenset[str]] = frozenset({"similar_to", "related_to"})

# backend에 적재되는 유일한 관계(현 범위) — crosswalk에서 PREREQUISITE로 투영되는 것만 실적재.
LOADED_RELATION: Final[str] = "prerequisite"


def backend_edge_type_for(relation: str) -> str:
    """pipeline 관계 문자열 → backend EdgeType 문자열(또는 DEFERRED). 미지 관계면 KeyError.

    crosswalk의 단일 조회 진입점. RELATION_TYPES 밖 값은 등록 누락이므로 시끄럽게 실패한다.
    """
    if relation not in RELATION_TO_BACKEND_EDGE_TYPE:
        raise KeyError(
            f"crosswalk 미등록 관계: {relation!r}. "
            f"pipeline Relation({sorted(RELATION_TYPES)})에 추가 시 crosswalk도 갱신하라."
        )
    return RELATION_TO_BACKEND_EDGE_TYPE[relation]


__all__ = [
    "DEFERRED",
    "FORBIDDEN_RELATION_TOKENS",
    "KNOWN_BACKEND_EDGE_TYPES",
    "LOADED_RELATION",
    "RELATION_TO_BACKEND_EDGE_TYPE",
    "TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES",
    "backend_edge_type_for",
]
