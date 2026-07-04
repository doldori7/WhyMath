"""스킬 노드 *PG 프로젝션* ORM — skill_id 키 안전 메타 (리치 Part 2 Phase 2a).

`concept_node`·`atom_node`(메타 프로젝션 슬)의 *스킬 그래프* 짝이다. data-pipeline
`skill_graph`가 자체작성 `skills.jsonl`을 `graph.json`(스킬 노드)으로 정형화했고, 이 테이블이 그
*안전 메타*를 skill_id 키로 영속 투영한다 — 검색 enrichment·필터·(Phase 2b) skill mastery 조인
백킹. upsert로 멱등 적재한다(`ON CONFLICT(skill_id) DO UPDATE`).

────────────────────────────────────────────────────────────────────────────
concept_node·atom_node와의 차이 (왜 신규 테이블인가 — 재키잉 아닌 additive)
────────────────────────────────────────────────────────────────────────────
스킬은 개념(무엇)과 직교하는 *행동*(어떻게) 축이다. 키·의미가 달라 기존 프로젝션을 재키잉하지
않고 신규 테이블을 둔다(concept_node·atom_node를 건드리지 않음·검색·임베딩 무영향·additive).
  - **키**: `skill_id`(`skill.<slug>`·의미론 id) — concept/atom code 공간과 분리.
  - **축**: `behavior_area`(6종 폐쇄 **PG native enum** `behavior_area_enum`) — atom_node가 인지축을
    plain TEXT 자유 라벨로 둔 것과 달리, 행동영역은 폐쇄 6종이라 native enum으로 정합을 강제한다.

법적(CLAUDE.md 우선순위 #2): 스킬 택소노미는 **전량 자체작성**이라 redaction 무관(성취기준·교과서
본문 미포함). 수록 필드는 전부 안전 메타·자체 라벨이다. 스킬 연결은 참조 키
(`prerequisite_skill_ids`)만 — 별도 엣지 테이블 없음(신규 엣지 타입 0·anti-explosion).

인덱스: PK `skill_id`로 충분하되, `behavior_area`(행동영역 필터)·`family`(Skill Family 그룹핑)는
검색·추천에서 자주 거는 필터라 보조 인덱스를 둔다.

7계층: L1 데이터 기반의 *영속 프로젝션*(검색 서빙 백킹). 표시·필터·(2b) mastery 조인 메타를 보관할
뿐, 소비(L2 mastery·L4 결선)는 이 좌석을 쓰되 여기서 구현하지 않는다. schema/ 상응 Pydantic 표면은
없다(`concept_node`·`atom_node` 선례).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum
from whymath_backend.schema.enums import BehaviorArea

# 스킬 메타 검수 상태 기본값 — v1 택소노미는 자체작성이나 전문 검수 전이라 정직하게 'ai_estimated'
# (atom_node 동형·검수 승격 시 'reviewed'로 갱신 가능·plain text). 게이팅이 이 리터럴과 비교.
SKILL_REVIEW_STATUS_DEFAULT: str = "ai_estimated"


class SkillNode(Base):
    """스킬 메타 PG 프로젝션 — skill_id 키 안전 표시·필터 메타(검색 enrichment·2b mastery 백킹).

    한 행 = 한 스킬 노드의 안전 메타(name_ko·behavior_area·family·mastery_estimable·선수 참조·
    연결 성취기준 코드). PK(skill_id=`skill.<slug>`)로 멱등 upsert 적재한다. 본문·오개념·프롬프트
    슬롯은 두지 않는다(순수 스킬 택소노미·concept_node·atom_node 동형).
    """

    __tablename__ = "skill_node"

    # PK = skill_id(`skill.<slug>`·의미론 id·upsert 충돌 키). concept/atom code 공간과 분리.
    skill_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 한국어 표시명(graph.json `name_ko`·필수). 검색 enrichment 핵심 표시 필드.
    name_ko: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 행동영역(6종 폐쇄 축·PG native enum). 필터·(2b) mastery 집계 축. NOT NULL.
    behavior_area: Mapped[BehaviorArea] = mapped_column(
        _pg_enum(BehaviorArea, "behavior_area_enum"), nullable=False
    )
    # Skill Family(연속체 그룹·graph.json `family`·필수). 관련 스킬 묶음 필터.
    family: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # mastery 독립추정 게이트(graph.json `mastery_estimable`·기본 true). NOT NULL·server_default.
    mastery_estimable: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    # 스킬 설명(graph.json `description`·nullable·자체작성 짧은 설명·표시 가능 안전 필드).
    description: Mapped[str | None] = mapped_column(sa.Text)
    # 선수 스킬 skill_id 목록(graph.json `prerequisite_skill_ids`·참조 키·기본 빈 배열·엣지 타입 0).
    prerequisite_skill_ids: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 연결 NCIC 성취기준 *코드* 목록(graph.json `standard_codes`·기본 빈 배열·코드는 사실정보).
    standard_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 검수 게이팅 — v1 자체작성이나 검수 전이라 기본 'ai_estimated'(정직 표기). plain text·NOT NULL.
    review_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(concept_node·atom_node 동형).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # behavior_area(행동영역 필터)·family(Skill Family 그룹) 보조 인덱스(검색·추천·집계).
        sa.Index("ix_skill_node_behavior_area", "behavior_area"),
        sa.Index("ix_skill_node_family", "family"),
    )


__all__ = ["SkillNode", "SKILL_REVIEW_STATUS_DEFAULT"]
