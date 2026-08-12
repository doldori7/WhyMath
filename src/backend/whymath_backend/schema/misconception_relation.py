"""오개념 ↔ 오개념 관계(`caused_by`·`variant_of`) — 백엔드 계약 모델(Pydantic).

`MisconceptionCrosslink`(오개념 kebab-id ↔ M-id N:M·`schema/misconception_crosslink.py`)의
*축이 다른* 짝이다 — crosslink는 두 체계(kebab-id/M-id) 사이를 잇고, 이 모델은 **오개념끼리의**
관계(M-id ↔ M-id)만 다룬다. 설계 정본: `docs/architecture/04e_misconception_remediation_design.md`
§2. 개념(concept) 방향 확장은 이미 다른 메커니즘(`concept_src_id` 느슨참조)이 해결했으므로 이
모델의 범위 밖이다(§2-1·§2-2 재확인 — 재론하지 않는다).

닫힌 어휘는 crosslink `link_type`(Literal) 선례를 그대로 따른다 — DB 컬럼은 `String`이고, 이
Pydantic Literal이 `caused_by`/`variant_of` 외 값을 거부하는 유일한 강제 지점이다(오타 →
`ValidationError`). PK는 서로게이트가 아니라 `(from_mis_id, relation_type, to_mis_id)` 자체이므로
이 모델에는 `link_id` 같은 ORM 전용 필드가 없다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 폐쇄 2종 — 04e §2-2가 4종 후보 중 재검토해 채택한 것만 남긴 결과. misconception_of(개념 방향·
# 이미 concept_src_id로 해결)·repaired_by(intervene.py 결정트리와 이중 진실원천 위험)는 의도적
# 제외다(§2-2 표 — 재론하지 않는다).
MisconceptionRelationType = Literal["caused_by", "variant_of"]


class MisconceptionRelation(BaseModel):
    """오개념 M-id ↔ M-id 단일 관계 — 백엔드 계약 모델.

    `from_mis_id`가 `to_mis_id`에 대해 `relation_type`으로 관계를 맺는다(`caused_by`면
    from이 to를 유발, `variant_of`면 from이 to의 다른 표현형). 의미 유일키이자 DB 복합 PK가
    `(from_mis_id, relation_type, to_mis_id)`다.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    from_mis_id: str = Field(
        ...,
        # max_length=32 — DB 컬럼 폭(String(32))·misconception_catalog.mis_id와 정합
        # (atom 투영 mis_id 'ATOM:'+code 최장 18자 실측 — misconception_crosslink.mis_id 선례).
        description="관계의 출발점 M-id(FK 대상 misconception_catalog.mis_id — 예 'M0425')",
        max_length=32,
    )
    relation_type: MisconceptionRelationType = Field(
        ...,
        description="관계 의미 — caused_by(유발)/variant_of(같은 오개념의 다른 표현형)",
    )
    to_mis_id: str = Field(
        ...,
        description="관계의 도착점 M-id(FK 대상 misconception_catalog.mis_id — 예 'M0431')",
        max_length=32,
    )


__all__ = [
    "MisconceptionRelation",
    "MisconceptionRelationType",
]
