"""오개념 crosswalk(kebab-id ↔ M-id) 연결 — 백엔드 계약 모델(Pydantic).

오개념 정체성 통합(math_dsl_risk_register.md Q3·Q10-⑥·`math_dsl_remediation_design.md` §1)의
*골격*이다. 두 별개 체계 — L4 런타임 탐지 정본 **kebab-id 30종**(`l4/misconception/catalog.py`)과
콘텐츠 카탈로그 **M-id 839종**(`schema/misconception_catalog.py`) — 을 *FK로 묶지 않고* N:M 매핑
테이블로 잇는다. 학생 데이터(`misconception_hypothesis`·`evidence_links`)는 kebab-id를 그대로
보존하고(rekey 불필요), 조회 시점에 이 crosswalk로 M-id를 read-time 해석한다(crosslink_resolve.py).

`ConceptStandardLink`(개념↔성취기준 N:M·`schema/standard.py`)의 *오개념* 짝이며 ORM/유일키/변환
헬퍼 패턴을 미러한다. 의미 유일키는 `(kebab_id, mis_id, link_type)`이고 `link_id`(UUID)는
ORM 전용이라 이 계약 모델에는 없다.

매핑 정확성 주의(CLAUDE.md 우선순위 #1·#3): 틀린 매핑은 *오도된 학부모/학생 리포트*로 이어지므로
crosswalk 행은 **사람 검수 산출물**이다 — 자동 생성 매핑을 검수 없이 라이브 테이블에 커밋하지 않는다
(`method`·`confidence`로 근거·신뢰도를 남기되 채택은 검수 책임).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 연결 의미(한글 정본) — '직접매핑'(같은 오개념)·'부분매핑'(M-id가 더 좁거나 넓음)·'개념겹침'
# (관련 개념·완전 동일 아님). ConceptStandardLink.link_type Literal 패턴 미러.
CrosslinkType = Literal["직접매핑", "부분매핑", "개념겹침"]

# 후보 근거 방식 — 'manual'(사람 매핑)·'standard_code'(성취기준 코드 일치)·'embedding'(의미 유사).
# 자동(embedding/standard_code)도 *채택은 사람 검수* 전제(자동 커밋 금지).
CrosslinkMethod = Literal["manual", "standard_code", "embedding"]


class MisconceptionCrosslink(BaseModel):
    """오개념 kebab-id ↔ M-id 단일 연결 — 백엔드 계약 모델.

    `kebab_id`는 L4 탐지 카탈로그 id(느슨참조 — `l4/misconception/catalog.py`의 30종),
    `mis_id`는 콘텐츠 카탈로그 PK(실 FK 대상 `misconception_catalog.mis_id`), `link_type`은 연결
    의미, `confidence`는 매핑 신뢰도(0~1), `method`는 후보 근거 방식이다. 의미 유일키는
    `(kebab_id, mis_id, link_type)`(같은 쌍·의미의 중복 금지).
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    kebab_id: str = Field(
        ...,
        description="L4 탐지 카탈로그 id(느슨참조 — 예 'distribution-over-power')",
        max_length=64,
    )
    mis_id: str = Field(
        ...,
        # max_length=32 — DB 컬럼 폭(String(32))과 정합. atom 투영 mis_id('ATOM:'+code)가
        # 실측 최장 18자(348건이 16자 초과)라 구 16은 오버플로(Phase 5 이전 대비 헤드룸 포함).
        description="콘텐츠 카탈로그 M-id(FK 대상 misconception_catalog.mis_id — 예 'M0425')",
        max_length=32,
    )
    link_type: CrosslinkType = Field(
        ...,
        description="연결 의미 — 직접매핑/부분매핑/개념겹침",
    )
    confidence: float | None = Field(
        default=None,
        description="매핑 신뢰도 0~1(검수 보조 — 채택은 사람 책임)",
        ge=0.0,
        le=1.0,
    )
    method: CrosslinkMethod = Field(
        default="manual",
        description="후보 근거 방식 — manual/standard_code/embedding(자동도 채택은 검수 전제)",
    )
    note: str | None = Field(default=None, description="검수 메모(자체 작성)")


__all__ = [
    "CrosslinkMethod",
    "CrosslinkType",
    "MisconceptionCrosslink",
]
