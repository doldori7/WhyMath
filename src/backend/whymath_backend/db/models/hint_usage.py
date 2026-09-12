"""HintUsage 영속 ORM(`hint_usage`) — 힌트 횟수·레벨·열람시간 1급 데이터화 (EOS-45).

설계 정본: `docs/architecture/32_learning_history.md` §4(HintUsage). `problem_attempt.
used_hint`(불리언)는 "썼다/안 썼다"만 남겨 무힌트 20초 정답과 힌트 3회 4분 정답의 숙련도
해석이 구분되지 않는다 — 이 테이블이 힌트 사용 각 건(레벨·시각·열람시간)을 영속한다.
**used_hint 병행 유지**(대체 아님): 기존 소비자(`l2/learning_metrics_rollup`의
`daily_hint_reliance_rate`)는 불변이고, 이 테이블은 더 정밀한 파생(hint_rate·최대 레벨)의
원천이다. 검증 Pydantic 정본은 `schema/hint_usage.py` — 본 모듈은 *영속 스키마*만 둔다
(EOS-32 `answer_submission.py` 관례 그대로).

**과거분 백필 불가(정직)**: 과거 힌트 이력은 `attempt_event`의 `힌트제공`(hint_level 있음)·
`힌트요청`(레벨 없음) 이벤트로 *부분* 존재하나, hint_id·view_duration_ms가 없고 "AI 공급
(supply)" 이벤트와 "학생 열람(usage)" 기록은 의미가 다르다 — 이벤트를 usage 행으로 승격하면
절반을 날조하게 된다. 수집은 배포 시점부터(이관 전략 = 32_learning_history §4·EOS-32 동형).

영속 매핑 결정(근거 병기 — EOS-32 관례 재사용):
  - `hint_usage_id` UUID PK `gen_random_uuid()`.
  - `(attempt_id, user_id)` **NOT NULL 복합 FK → problem_attempt(attempt_id, user_id)
    ON DELETE CASCADE** — EOS-32 PR #902 P1에서 확정된 소유 정합 원칙을 처음부터 적용:
    단독 attempt FK면 "A의 attempt + B의 user_id" 조합이 통과해 user_id 선별 export/erasure에
    타인 힌트 이력이 섞인다. 참조 대상 UNIQUE `uq_problem_attempt_attempt_user`는 EOS-32
    마이그레이션(8f0b8e906362)이 이미 만들었으므로 **재사용**한다(중복 생성 금지).
  - `user_id` UUID **NOT NULL FK user_profile.user_id**(복합 FK와 별도 — 계정 실재 강제·
    privacy 3종 균일 경로. NO ACTION — 삭제권은 앱레벨 `_ERASURE_PLAN` 자식 우선 명시 삭제).
  - `hint_id` TEXT nullable **느슨참조** — 힌트 정본 테이블 부재 실측(FK 날조 금지·schema
    docstring 상세). 폭 제약은 schema(max_length=200)가 강제·DB는 TEXT 좌석.
  - `hint_level` INTEGER NOT NULL — 폐쇄 1~4의 강제는 schema(ge/le·정본은
    l4.hint_deferral.HintLevel)·DB는 값만 담는다(`answer_submission.response_type` 동형).
  - `requested_at` TIMESTAMPTZ NOT NULL `server_default now()` — 보존 파기(`_RETENTION_PLAN`)
    축(NOT NULL이라 NULL-미파기 잔존 없음)·attempt 내 자연 순서.
  - `view_duration_ms` INTEGER **nullable** — 클라 계측의 종료 신호(이탈·강제 종료·백그라운드)
    부재 케이스가 구조적으로 존재해 미확정=NULL(0 날조 금지 — schema docstring 상세).
  - 순번 UNIQUE 없음 — 힌트 열람은 프로토콜 순번이 아니라 시각(`requested_at`) 순서다
    (answer_submission.sequence_no와 의도적 차이·중복 열람도 각각 사실).

인덱스: `(user_id, requested_at DESC)` — privacy 경로·학생 단위 최근순(`idx_answer_submission_
user` 동형). `(attempt_id)` — attempt 단위 hint_rate·최대 레벨 파생 조회(answer_submission은
UNIQUE 선두 컬럼이 겸했으나 여기는 UNIQUE가 없어 별도 인덱스).

개인정보 메모(CLAUDE.md·`activity.py` 방침): 힌트 사용 이력은 *미성년 학습 행동 데이터*다 —
암호화·동의는 저장·동의 계층 책임(ORM은 컬럼만·가짜 CHECK 없음). privacy 3종 배선은
acceptance가 강제·`test_erasure_plan_completeness`가 동결한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.hint_usage import HintUsage as SchemaHintUsage


class HintUsage(Base):
    """힌트 사용 영속 ORM — `hint_usage`(학생이 힌트 1개를 연 사건 1행·requested_at 순서).

    한 행 = attempt(`attempt_id`) 안에서 학생(`user_id`)이 hint_level 수준의 힌트를 연 기록.
    `l2` 파생(hint_rate·최대 레벨)의 원천이며 소비 로직은 이 모듈 범위 밖(저장소만 세운다 —
    배선 확장은 후속·`tests/backend/l2/test_hint_rate_mastery_input.py`가 가용성만 증명).
    """

    __tablename__ = "hint_usage"

    # ===== 기본 식별 =====
    hint_usage_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # attempt 참조는 (attempt_id, user_id) 복합 FK(__table_args__ — EOS-32 소유 정합 관례).
    attempt_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    # pseudonymous user_id 직접 보유 — privacy 3종 배선의 균일 경로. user_profile FK는 복합
    # FK와 별도 유지(계정 실재 강제).
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id"), nullable=False
    )

    # ===== 힌트 식별·수준 =====
    # 느슨참조 — 힌트 정본 테이블 부재 실측(FK 날조 금지·모듈 docstring).
    hint_id: Mapped[str | None] = mapped_column(sa.Text)
    # 폐쇄 1~4 강제는 schema(정본 l4.hint_deferral.HintLevel) — DB는 값만 담는다.
    hint_level: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # ===== 시간·계측 =====
    requested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    # NULL = 미측정(종료 신호 부재 — 0 날조 금지·schema docstring).
    view_duration_ms: Mapped[int | None] = mapped_column(sa.Integer)

    # ── 제약·인덱스 ──
    __table_args__ = (
        # EOS-32 소유 정합 관례 — "A의 attempt + B의 user_id" 조합을 DB가 거부. 참조 대상
        # UNIQUE(uq_problem_attempt_attempt_user)는 EOS-32가 이미 생성(재사용·중복 생성 금지).
        # attempt 삭제(GDPR) 시 자식 힌트 이력 동반 제거(CASCADE)도 이 복합 FK가 담당.
        sa.ForeignKeyConstraint(
            ["attempt_id", "user_id"],
            ["problem_attempt.attempt_id", "problem_attempt.user_id"],
            name="fk_hint_usage_attempt_owner",
            ondelete="CASCADE",
        ),
        sa.Index("idx_hint_usage_user", "user_id", sa.desc("requested_at")),
        sa.Index("idx_hint_usage_attempt", "attempt_id"),
    )

    # ── 변환 헬퍼 (schema↔db seam, answer_submission.py 패턴) ────────────
    @classmethod
    def from_schema(cls, schema: SchemaHintUsage) -> HintUsage:
        """검증된 `schema.HintUsage` → 영속 ORM(mapper 컬럼키 필터).

        `requested_at=None`(schema 기본 — DB가 채움)은 kwargs에서 *제외*한다 — 명시적 None
        할당은 NULL INSERT가 되어 NOT NULL 위반이고, 속성 미설정이어야 `server_default now()`
        가 적용된다(EOS-32 `submitted_at` 동형).
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        if kwargs.get("requested_at") is None:
            kwargs.pop("requested_at", None)  # server_default now() 적용(명시 NULL 금지)
        return cls(**kwargs)

    def to_schema(self) -> SchemaHintUsage:
        """영속 ORM → `schema.HintUsage`(Pydantic 검증 복원 — hint_level 1~4 재검증)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaHintUsage.model_validate(data)


__all__ = ["HintUsage"]
