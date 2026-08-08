"""user_profile dead tenancy billing columns drop — ADMIN-02

죽은 컬럼 4종 제거: `school_id`(FK 없는 고아 컬럼, operations_platform_gap_review.md §3
D2·account_security_gap_review.md:421 §4-⑧이 부재를 이미 자인)·`subscription_tier`·
`subscription_started_at`·`subscription_renewed_at`(결제 시스템 부재로 소비처 0 —
concept.embedding_id drop(f1a2b3c4d5e7)·Phase 1b 4컬럼 청산(f0a1b2c3d4e5) 선례 동형).
소비처 재확인: `grep -rn` 전체 백엔드 소스에서 4컬럼 모두 model/schema 정의 외 참조 0건
(2026-08-08 실측).

**prod 실측 안전장치**(ADMIN-02 acceptance ①): 이 저장소가 라이브 prod DB에 접속할 수
없는 개발 환경에서 작성됐다 — 4컬럼이 실제로 전량 NULL인지 사전 확인이 불가능했다.
"비어있으면 드롭, 아니면 드롭 대신 미사용 자인 주석+동결 테스트로 범위 재조정"이라는
조건부 지시를 만족시키기 위해, 그 조건을 이 마이그레이션 `upgrade()` 자체에 실행 시점
가드로 내장한다 — 실제 prod에 `alembic upgrade`를 적용하는 순간에 4컬럼 중 하나라도
비어있지 않은 행이 있으면 드롭 대신 즉시 예외를 던지고 트랜잭션을 롤백한다(추측이 아니라
실행 시점 실측으로 조건을 확정 — CLAUDE.md "검증 없는 실행 안내 금지"·"환경 사실의 추론
등재 금지"의 마이그레이션 레벨 적용).

Revision ID: d8559726a87a
Revises: 090d254a5d43
Create Date: 2026-08-08 22:42:23.368130
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8559726a87a"
down_revision: str | None = "090d254a5d43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TARGET_COLUMNS: tuple[str, ...] = (
    "school_id",
    "subscription_tier",
    "subscription_started_at",
    "subscription_renewed_at",
)


def upgrade() -> None:
    # 실행 시점 안전 가드 — 4컬럼 중 하나라도 비어있지 않은 행이 있으면 드롭 전면 중단
    # (사전 prod 실측이 불가능했던 개발 환경 제약을 실행 시점 자기검증으로 대체).
    bind = op.get_bind()
    nonnull_count = bind.execute(
        sa.text(
            "SELECT count(*) FROM user_profile WHERE "
            "school_id IS NOT NULL OR subscription_tier IS NOT NULL OR "
            "subscription_started_at IS NOT NULL OR subscription_renewed_at IS NOT NULL"
        )
    ).scalar()
    if nonnull_count:
        raise RuntimeError(
            f"user_profile.{{{', '.join(_TARGET_COLUMNS)}}} 중 비어있지 않은 행이 "
            f"{nonnull_count}건 존재 — 드롭 중단(ADMIN-02 acceptance ① 안전장치). 데이터가 "
            "실제로 쓰이고 있다면 드롭 대신 미사용 자인 주석+동결 테스트로 범위를 재조정할 "
            "것(Kiki 확인 필요) — 이 마이그레이션을 그대로 재실행하지 말 것."
        )

    op.drop_column("user_profile", "school_id")
    op.drop_column("user_profile", "subscription_tier")
    op.drop_column("user_profile", "subscription_started_at")
    op.drop_column("user_profile", "subscription_renewed_at")
    # subscription_tier_enum은 이 컬럼 전용 native ENUM(다른 컬럼 참조 0건, 2026-08-08 실측)
    # — 컬럼 드롭 후 고아 타입으로 남지 않도록 함께 제거. checkfirst로 멱등.
    postgresql.ENUM(name="subscription_tier_enum").drop(bind, checkfirst=True)


def downgrade() -> None:
    # 왕복 안전 — nullable 컬럼으로 복원(값은 upgrade 가드가 통과했을 때만 전량 NULL이었으므로
    # 데이터 손실 0). ENUM 타입은 add_column이 미존재 시 자동 생성(create_table 원본 동작 미러).
    op.add_column(
        "user_profile",
        sa.Column(
            "subscription_tier",
            sa.Enum("free", "basic", "premium", name="subscription_tier_enum"),
            nullable=True,
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_profile",
        sa.Column("subscription_renewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("user_profile", sa.Column("school_id", sa.Uuid(), nullable=True))
