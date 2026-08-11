"""SolutionPath 영속 ORM(`solution_paths`) — 풀이 경로 헤더 테이블 신설 (S4-09·D1).

설계 정본: `schemas/v1.1/solution_path.schema.yaml`(storage: "PostgreSQL 16 (solution_paths)")·
`docs/architecture/solution_module_gap_review.md` §3 D1. 검증 Pydantic 정본은
`l3/solution_path.py`(SolutionPath/SolutionStep/Justification) — 본 모듈은 *영속 스키마*만 둔다.

테이블 분할(테이블 증식 최소화 — D1 좌석 설계 그대로):
  - **헤더**(본 테이블): 경로 식별·approach_type·concept_sequence·검수/군집 메타.
  - **단계**: 기존 `problem_step`(`db/models/problem.py`)에 additive 컬럼(`solution_path_id` FK·
    `concept_node_id`·`reasoning_type`·`justification`·`common_errors`·`sympy_verified`)으로
    영속한다 — 단계 전용 테이블을 *신설하지 않는다*.

영속 매핑 결정(근거 병기):
  - `solution_path_id` TEXT PK — yaml `type: string`(UUID 강제 아님). 승격 어댑터가
    `sp-{verified_solutions.id}` 결정론 ID를 부여해 멱등 재실행을 자연 지원한다.
  - `problem_id` UUID **FK problem.problem_id** — yaml invariant "problem_id가 실재하는
    Problem"의 DB 강제(참조 실재는 적재 시점 책임 — l3 Pydantic 경계). `verified_solutions`의
    느슨참조(WH-S 오프라인 독립)와 달리, 본 테이블은 *서빙 표면*(steps API·learning_scene)의
    원천이라 코퍼스 정합을 FK로 강제한다(`problem_step.problem_id` 기존 FK 관례 동형).
  - `approach_type` TEXT NOT NULL — PG enum을 *만들지 않는다*(Enum 좌석 신설은 S4-10 몫 —
    `l3/solution_path.py` ApproachType Literal이 폐쇄 6종을 강제·DB는 TEXT 좌석만).
  - `concept_sequence` JSONB NOT NULL server_default '[]' — 개념 노드 ID 순서열(list[str]).
    `none_as_null=True`(SEC-06 전수 거버넌스 — Python None을 JSON null로 저장 금지).
  - `verified_by_human` BOOL NOT NULL server_default false — 사람 검수 통과 여부(환각 방어 ④).
    기본 false: 승격 직후는 항상 미검수(AI 자기승인 금지).
  - `equivalence_cluster_id` TEXT nullable — 동치 *후보* 군집(확정 동치 아님 — 정직 경계).
    군집 판정·부여는 S4-12(D4) 몫이라 지금은 좌석만.
  - `created_at` TIMESTAMPTZ NOT NULL server_default now().
  - `embedding` 컬럼 **없음** — S4-12에서 판정(acceptance 명시·임베딩 네임스페이스 거버넌스).

인덱스: `(problem_id)` — steps API·learning_scene 결선·승격 어댑터가 전부 문제 단위로
조회한다(`idx_verified_solutions_problem_grade` 접근 패턴 동형).

개인정보 메모(CLAUDE.md): 시스템이 생성·승격한 콘텐츠이며 학생 PII가 아니다(`verified_solutions`
동일 방침 — 동의·암호화 대상 아님).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class SolutionPath(Base):
    """풀이 경로 헤더 영속 ORM — `solution_paths`(단계는 `problem_step` additive 컬럼).

    한 행은 *한 풀이 경로*: 문제 `problem_id`에 대한 approach_type 1개·개념 시퀀스·검수 상태.
    한 문제에 여러 행(다중 접근)이 올 수 있다(problem_id UNIQUE 없음 — N:1). 검증된
    `l3.solution_path.SolutionPath`(Pydantic)와의 매핑은 승격 어댑터(`whs/path_promotion.py`)가
    수행한다 — db가 l3를 import하지 않는다(계층 위생·순환 회피).
    """

    __tablename__ = "solution_paths"

    # ===== 식별 =====
    solution_path_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 실재하는 문제만 참조(FK) — 서빙 표면 원천의 코퍼스 정합 강제(모듈 docstring 근거).
    problem_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("problem.problem_id"), nullable=False
    )

    # ===== 풀이 유형·골격 =====
    # 폐쇄 6종 강제는 l3 Pydantic(Literal) — DB는 TEXT 좌석만(PG enum 신설 안 함·S4-10 재론).
    approach_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 개념 노드 ID 순서열(골격) — 매칭 확정분만(매칭 실패 스텝 제외·날조 금지).
    concept_sequence: Mapped[list[str]] = mapped_column(
        JSONB(none_as_null=True), nullable=False, server_default=sa.text("'[]'::jsonb")
    )

    # ===== 검수·군집 메타 =====
    # 승격 직후 항상 false(AI 자기승인 금지) — 사람 검수 통과 시에만 true.
    verified_by_human: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    # 동치 *후보* 군집(확정 동치 아님) — 부여는 S4-12(D4) 몫, 지금은 좌석만.
    equivalence_cluster_id: Mapped[str | None] = mapped_column(sa.Text)

    # ===== 운영 메타 =====
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    # ── 인덱스 (문제 단위 조회 — steps API·learning_scene 결선·승격 멱등 확인) ──
    __table_args__ = (sa.Index("idx_solution_paths_problem", "problem_id"),)


__all__ = ["SolutionPath"]
