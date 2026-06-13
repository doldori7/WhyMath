"""WH-S 풀이 경로 트리 노드(`solution_nodes`) ORM 모델 — SQLAlchemy 2.0 영속 레이어.

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.1(풀이 경로 트리 — Solution Tree)·
§9 S1(솔버 루프: 도구 8종 + 풀이 트리 + MCTS-lite). 본 모듈은 그 S1 슬라이스 중 *풀이 트리
상태 계층*만 영속한다 — 솔버 루프·MCTS·도구 8종 본체는 후속(모듈 끝 "범위 밖" 참조).

§2.1 정의:
  - 노드 = 풀이 상태(현재까지의 변형·중간 결과), 엣지 = 풀이 행동(전략 적용 1스텝).
  - MCTS 방식 확장: 방문 횟수(`visits`)·과정 보상 추정치(`prm_score`)·verify 결과
    (`verify_status`)를 노드에 저장.
  - PostgreSQL: `solution_nodes(problem_id, parent_id, state_repr, action, prm_score,
    verify_status, visits)`.

영속 매핑 컨벤션(배치1 `problem.py`·`concept.py`·`activity.py` 선례 답습):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`(모든 UUID PK 선례).
  - self-FK(`parent_id REFERENCES solution_nodes`) → `sa.ForeignKey("solution_nodes.id",
    ondelete="CASCADE")`. 부모 노드를 지우면 자식 가지 전체가 함께 제거된다(트리 정합 —
    고아 노드 방지). 트리 루트는 `parent_id=None`(nullable).
  - `JSONB`(state_repr) → 풀이 상태의 구조화 표현(자유형 — 변형 식·중간 결과 등). §2.1이
    "state_repr"로만 명시해 구체 스키마를 두지 않으므로 JSONB 자유형으로 둔다(솔버 루프가
    내용 계약을 정한다 — 후속).
  - `verify_status` → `NodeVerifyStatus` `_pg_enum`(아래 — 신규 PG 타입 `node_verify_status_enum`).
  - `visits` → `Integer NOT NULL server_default 0`(MCTS 미방문 노드는 0).
  - `created_at`/`updated_at` → `server_default now()`·`updated_at`은 `onupdate=now()`
    (운영 메타 — activity.py created_at 선례 + UPDATE 시 갱신).

느슨 결합 — *problems 테이블에 FK를 강제하지 않는다*:
  WH-S는 학생 세션에 직접 개입하지 않는 *독립 오프라인 서브시스템*(§7.5·`whs/__init__` 방침)
  이다. 풀이 트리는 임의 문제(자체 코퍼스·외부 평가셋·합성 문제)에 대해 돌 수 있고, 그 문제가
  반드시 운영 `problem` 테이블에 적재돼 있어야 하는 것은 아니다. 따라서 `problem_id`는 *FK가
  아닌 단순 인덱스 UUID*(느슨참조)다 — activity.py의 `target_concept_id`·`attempt_event` FK
  부재 컬럼과 동형. 이로써 WH-S 배치가 운영 스키마에 강결합되지 않는다.

개인정보 메모(CLAUDE.md 절대 금기 대조): `solution_nodes`는 *시스템 솔버의 내부 탐색 상태*이며
학생 풀이 데이터가 아니다(미성년 PII·동의 대상 아님 — `problem_attempt`와 대비). 따라서
암호화·redaction 불요(평문 JSONB 저장이 적정). 학생 경로 미개입(§7.5)이라 API 노출도 0.

범위 밖(후속 — §9 S1+): 솔버 루프(LLM 정책 모델 구동·Ollama·Phaiakes9)·MCTS-lite 탐색·도구
8종(parse_problem·apply_strategy 등)·다른 저장소(§2.2 Verified Lemma Store·§2.3 Dead-End
Log·§2.4 Verified Solution Bank)·PRM 구축·Tier3(Lean4)·시드 모델 실행. 본 모듈은 *풀이 트리
스키마*만 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum


class NodeVerifyStatus(str, Enum):
    """풀이 트리 노드의 검증 상태 — §3 등급 + 미검증 초기상태(MCTS 노드 생애주기).

    `whs/verdict.WhsGrade`(verified/unverified/failed)와 *의미 정합*하되, 트리 노드는 생성
    직후 아직 검증 전이므로 **pending**(초기상태)을 더한다. 즉 MCTS가 노드를 확장하면 처음엔
    `pending`, verify 도구(§3 도구 5 `verify`)를 거쳐 verified/unverified/failed로 전이한다.

    멤버:
      - `PENDING`("pending"): 검증 전 초기상태(확장 직후·미평가). verdict 등급엔 없는 노드 전용.
      - `VERIFIED`("verified"): 검증 통과(§4 Tier1 pass + 전 단계 Tier2 correct 의미 정합).
      - `UNVERIFIED`("unverified"): 판정 불가 격리(§3·R-S2 — 학습 데이터 배제 대상).
      - `FAILED`("failed"): 검증 실패(답 fail 또는 틀린 과정).

    값=멤버명(소문자)이라 `_pg_enum`의 values_callable로 PG enum 라벨이 값과 일치한다
    (Curriculum 같은 멤버명≠값 케이스 아님 — 단순 매핑).
    """

    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class SolutionNode(Base):
    """WH-S 풀이 경로 트리 노드 영속 ORM — §2.1 `solution_nodes`.

    한 노드는 *풀이 상태*(`state_repr`)이고, 부모 노드로부터 적용한 *행동*(`action`, 전략 1스텝)
    으로 도달한다. self-FK `parent_id`로 트리를 이루며 루트는 `parent_id=None`. MCTS 신호
    (`visits`·`prm_score`·`verify_status`)를 노드에 적재한다.

    `problem_id`는 *FK가 아닌 느슨참조*다(모듈 docstring — WH-S 오프라인 독립성). `parent_id`만
    self-FK(`ondelete="CASCADE"` — 부모 삭제 시 가지 전체 제거).
    """

    __tablename__ = "solution_nodes"

    # ===== 기본 식별 =====
    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성·모듈 docstring). 인덱스만.
    problem_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    # self-FK — 트리 부모(루트는 None). 부모 삭제 시 자식 가지 함께 제거(CASCADE).
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("solution_nodes.id", ondelete="CASCADE")
    )

    # ===== 풀이 상태·행동 (§2.1 노드=상태·엣지=행동) =====
    # 현재까지의 풀이 상태(변형·중간 결과)의 구조화 표현 — 자유형 JSONB(솔버 루프가 계약 정의).
    state_repr: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # 이 노드에 도달하려고 부모에서 적용한 전략 1스텝(치환·케이스 분할 등). 루트는 None.
    action: Mapped[str | None] = mapped_column(sa.Text)

    # ===== MCTS 신호 =====
    # 과정 보상 추정치(PRM) — 미평가 시 None(verify·PRM 후속에서 채움).
    prm_score: Mapped[float | None] = mapped_column(sa.Float)
    # 검증 상태 — 확장 직후 pending, verify 후 verified/unverified/failed로 전이.
    verify_status: Mapped[NodeVerifyStatus] = mapped_column(
        _pg_enum(NodeVerifyStatus, "node_verify_status_enum"),
        nullable=False,
        server_default=NodeVerifyStatus.PENDING.value,
    )
    # MCTS 방문 횟수 — 미방문 노드 0(server_default).
    visits: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))

    # ===== 운영 메타 =====
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    # ── 인덱스 (§2.1 접근 패턴 — problem별 루트 조회·parent별 자식 조회) ──
    __table_args__ = (
        sa.Index("idx_solution_nodes_problem", "problem_id"),
        sa.Index("idx_solution_nodes_parent", "parent_id"),
    )


__all__ = ["NodeVerifyStatus", "SolutionNode"]
