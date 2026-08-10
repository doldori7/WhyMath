"""problem_attempt.selected_choice_index — 학생이 고른 객관식 보기 인덱스 (ASM-06)

학생이 실제로 고른 객관식 보기의 0-기반 인덱스를 적재해 `Problem.distractor_map`과
대조하면 어느 오개념이 이 오답을 유발했는지 역추적할 수 있다
(`l4.misconception.distractor_link.resolve_misconception_from_choice`). 지금까지
`student_answer`는 자유텍스트뿐이라 "몇 번 보기를 골랐는가" 자체가 채점 레이어에 없었다
(선행 조사 결론 — NLP-02 shadow 채점은 수치/기호식 검산 오프라인 배치이지 선택 인덱스를
포착하지 않는다).

- **additive·nullable**: 기존 행은 전부 NULL(자유응답형·구버전 클라 등)로 남는다. 데이터
  백필 대상 없음(`a3b4c5d6e7f8_problem_irt_difficulty_b` 선례 동형 — nullable 컬럼 추가만).
- `ge=0` 구조 검증은 `schema.activity.ProblemAttempt`(Pydantic) 책임 — DB CHECK는 두지
  않는다(`problem.py`/`activity.py` ORM 모듈 docstring의 "가짜 CHECK 금지" 방침과 정합).

마이그레이션 ID는 sliding-window hex 스킴을 따른다(임의 id는 alembic CycleDetected 유발 —
MEMORY 2026-07-03 실측). down_revision = 실제 head `7ef2b5a8e69e`(2026-08-10 착수 시점
`alembic heads` 실측 확인). 생성 전 `alembic/versions/*.py` 전량 grep으로 기존 75개
revision id와 무충돌 확인.

Revision ID: 0afd40ce1867
Revises: 7ef2b5a8e69e
Create Date: 2026-08-10 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0afd40ce1867"
down_revision: str | None = "7ef2b5a8e69e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """`problem_attempt.selected_choice_index` 추가(nullable INTEGER·기존 행 무영향)."""
    op.add_column(
        "problem_attempt",
        sa.Column("selected_choice_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """컬럼 제거 — 선택 인덱스 기록만 소실(원본 attempt·student_answer·채점 결과는 무영향)."""
    op.drop_column("problem_attempt", "selected_choice_index")
