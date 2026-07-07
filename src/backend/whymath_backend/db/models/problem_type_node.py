"""문제유형 노드 *PG 프로젝션* ORM — problem_type_id 키 안전 메타 (리치 Part 2 Phase 3).

`skill_node`·`atom_node`·`concept_node`(메타 프로젝션 슬)의 *문제유형 그래프* 짝이다. data-pipeline
`problem_type_graph`가 자체작성 `problem_types.jsonl`을 `graph.json`(문제유형 노드)으로 정형화했고,
이 테이블이 그 *안전 메타*를 problem_type_id 키로 영속 투영한다 — 검색 enrichment·필터·(후속) 문제
분류·추천 백킹. upsert로 멱등 적재한다(`ON CONFLICT(problem_type_id) DO UPDATE`).

────────────────────────────────────────────────────────────────────────────
skill_node와의 차이 (왜 native enum이 없는가 — D1)
────────────────────────────────────────────────────────────────────────────
cognitive-action 축은 이미 `BehaviorArea`(Phase 2a)다. 문제유형은 중복 archetype enum을 두지 않고
*exercise하는 스킬*(`behavior_skills`·skill_graph_v1 참조)로 "무슨 사고를 요구하는가"를 표현한다.
따라서 이 테이블은 **native PG enum이 없다**(전량 TEXT/TEXT[]/BOOL·skill_node의 `behavior_area_enum`
같은 enum 미소유·마이그레이션이 enum 미생성). 표면(SignaturePattern) 컬럼도 없다(≠surface 불변식).

법적(CLAUDE.md 우선순위 #2): 문제유형 택소노미는 **전량 자체작성**(cognitive-action 추상)이라
redaction 무관 — 평가원 기출 *문항 본문*을 담지 않는다. 수록 필드는 전부 안전 메타·자체 라벨이다.
유형 연결은 참조 키(`behavior_skills`)만 — 별도 엣지 테이블·prerequisite DAG 없음(신규 엣지 타입 0).

인덱스: PK `problem_type_id`로 충분하되, `family`(문제유형 family 그룹핑)는 필터·집계에서 자주 거는
축이라 보조 인덱스를 둔다.

7계층: L1 데이터 기반의 *영속 프로젝션*(검색 서빙 백킹). 표시·필터·(후속) 분류·추천 메타를 보관할
뿐, 소비(L2/L4·문제 생성 태깅)는 이 좌석을 쓰되 여기서 구현하지 않는다. schema/ 상응 Pydantic 표면은
없다(`skill_node`·`atom_node`·`concept_node` 선례).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base

# 문제유형 메타 검수 상태 기본값 — v1 택소노미는 자체작성이나 검수 전이라 정직하게 'ai_estimated'
# (skill_node·atom_node 동형·검수 승격 시 'reviewed'로 갱신·plain text). 게이팅이 이 리터럴과 비교.
PROBLEM_TYPE_REVIEW_STATUS_DEFAULT: str = "ai_estimated"


class ProblemTypeNode(Base):
    """문제유형 메타 PG 프로젝션 — problem_type_id 키 안전 표시·필터 메타(검색 enrichment 백킹).

    한 행 = 한 문제유형 노드의 안전 메타(name_ko·family·behavior_skills·mastery_estimable·연결
    성취기준 코드). PK(problem_type_id=`ptype.<slug>`)로 멱등 upsert 적재한다. 본문·표면·오개념·
    프롬프트 슬롯은 두지 않는다(순수 cognitive-action 택소노미·skill_node·atom_node 동형).
    """

    __tablename__ = "problem_type_node"

    # PK = problem_type_id(`ptype.<slug>`·의미론 id·upsert 충돌 키). skill/concept/atom과 분리.
    problem_type_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 한국어 표시명(graph.json `name_ko`·필수). 검색 enrichment 핵심 표시 필드.
    name_ko: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 문제유형 family(그룹·graph.json `family`·필수). 필터·집계 축.
    family: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # exercise하는 skill_id 목록(graph.json `behavior_skills`·≥1개·skill_graph_v1 참조·본문 아님).
    # cognitive-action 표현의 참조 키(신규 엣지 타입 0·junction 아님·standard_codes 선례 동형).
    behavior_skills: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 독립추정 게이트(graph.json `mastery_estimable`·기본 true). NOT NULL·server_default.
    mastery_estimable: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    # 문제유형 설명(graph.json `description`·nullable·자체작성 짧은 설명·표시 가능 안전 필드).
    description: Mapped[str | None] = mapped_column(sa.Text)
    # 연결 NCIC 성취기준 *코드* 목록(graph.json `standard_codes`·기본 빈 배열·코드는 사실정보).
    standard_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 검수 게이팅 — v1 자체작성이나 검수 전이라 기본 'ai_estimated'(skill_node 동형·NOT NULL).
    review_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(skill_node·atom_node 동형).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # family(문제유형 family 그룹) 보조 인덱스(검색·추천·집계).
        sa.Index("ix_problem_type_node_family", "family"),
    )


__all__ = ["ProblemTypeNode", "PROBLEM_TYPE_REVIEW_STATUS_DEFAULT"]
