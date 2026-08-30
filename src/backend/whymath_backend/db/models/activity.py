"""도메인4 학습 활동(Activity) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schemas/v1.0/schema_v1.0.md` §6.1(`learning_session`·`problem_attempt`·
`attempt_event` DDL 3테이블)·§6.1 인덱스. 이 ORM은 `schema/activity.py`(Pydantic, 검증·API)와
*별도*로 세운 영속 매핑이며 `from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(배치1
`problem.py`·`user.py` 동일 패턴 — SQLModel 미사용).

타입 매핑(DDL → ORM, problem.py/user.py 선례 그대로):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`(배치1 모든 UUID PK 선례).
  - `UUID REFERENCES`(nullable FK) → `uuid.UUID|None` + FK(예: user_id→user_profile,
    session_id→learning_session, problem_id→problem).
  - `UUID`(REFERENCES 없음) → `uuid.UUID|None`(*FK 아님* — DDL에 REFERENCES 절이 없는
    `target_concept_id`·`stuck_at_concept_id`. concept_fusion.concept_ids가 배열이라 FK가
    아니었던 것과 달리, 여기선 *DDL이 REFERENCES를 명시하지 않은* 느슨참조다).
  - `BIGSERIAL`(시계열 PK) → `mapped_column(sa.BigInteger, primary_key=True,
    autoincrement=True)` — DB가 INSERT 시 할당하는 정수 PK(UUID PK와 달리 gen_random_uuid
    server_default를 두지 않는다). `attempt_event.event_id`에서만 사용.
  - `TIMESTAMPTZ NOT NULL`(복합 PK 구성요소) → required `datetime` + `primary_key=True`
    (예: attempt_event.event_at — `user.py` UserPersonaHistory.detected_at 선례).
  - `session_type_enum`/`attempt_mode_enum`/`event_type_enum` → `_pg_enum(...)`(신규 PG 타입).
  - `device_enum`(device_used) → `_pg_enum(Device, "device_enum")` — *배치1 user.py가 이미
    정의한 PG 타입을 동일 name으로 공유*한다(중복 정의 X, 메타데이터상 같은 타입). 공유 enum의
    create_type 처리는 마이그레이션(메인) 몫.
  - `DECIMAL(p,s)` → `Mapped[float|None] = mapped_column(sa.Numeric(p, s))`(focus/engagement).
  - `BOOLEAN`(기본값 없음) → `bool|None`(미응답=NULL 구분 — `user.py` 선례; is_correct·
    used_socratic 등).
  - `JSONB`(자유형) → `JSONB`(ocr_result·event_data); schema가 default_factory=list인 JSONB
    배열(step_times) → problem.py conditions_parsed처럼 `nullable=False, server_default
    "'[]'::jsonb"`.
  - `VARCHAR(n)`(enum 아님) → `sa.String(n)`(network_type).
  - 인덱스(§6.1 CREATE INDEX) → `__table_args__`; 부분 인덱스(idx_attempt_stuck WHERE
    stuck_at_concept_id IS NOT NULL) → `postgresql_where=sa.text(...)`.

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`concept.py` 방침과 동일):
  `problem_attempt`의 `student_answer`·`handwriting_uri`·`ocr_result`는 *미성년 학생 풀이
  데이터*다. 평문 저장 금지·동의 없는 학습 사용 금지는 *저장·동의 계층*(암호화·미들웨어·
  검수) 책임이며, ORM에는 컬럼만 두고 가짜 CHECK를 만들지 않는다(schema.activity 모듈
  docstring·problem.py 본문 미보유 불변식 방침과 동형 — 문서화만).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum
from whymath_backend.schema.activity import AttemptEvent as SchemaAttemptEvent
from whymath_backend.schema.activity import LearningSession as SchemaLearningSession
from whymath_backend.schema.activity import ProblemAttempt as SchemaProblemAttempt
from whymath_backend.schema.enums import (
    AttemptMode,
    Device,
    EventType,
    SessionType,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: LearningSession (§6.1 learning_session — 앱 진입~종료 한 단위)
# ──────────────────────────────────────────────────────────────────────────
class LearningSession(Base):
    """학습 세션 영속 ORM — §6.1 `learning_session`(앱 진입~종료 한 단위).

    PK `session_id`만 있고 나머지는 nullable/기본값(DDL 그대로). `user_id`→user_profile FK.
    `target_concept_id`는 §6.1 DDL에 `REFERENCES`가 없어 *FK가 아니다*(느슨참조 — schema
    docstring 정합). `device_used`는 배치1 user.py가 정의한 `device_enum` PG 타입을 공유한다.
    """

    __tablename__ = "learning_session"

    # ===== 기본 식별 =====
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id")
    )

    # ===== 시간 =====
    started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== 세션 유형·목표 =====
    session_type: Mapped[SessionType | None] = mapped_column(
        _pg_enum(SessionType, "session_type_enum")
    )
    # REFERENCES 없음 → FK 아님(느슨참조).
    target_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 진행 카운트 =====
    problems_attempted: Mapped[int | None] = mapped_column(sa.Integer)
    problems_completed: Mapped[int | None] = mapped_column(sa.Integer)
    problems_correct: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== 세션 품질 신호 =====
    focus_score: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))
    engagement_score: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))

    # ===== 환경 (device_used는 배치1 device_enum 공유) =====
    device_used: Mapped[Device | None] = mapped_column(_pg_enum(Device, "device_enum"))
    # VARCHAR(20) — enum 아닌 자유 문자열(schema network_type 선례).
    network_type: Mapped[str | None] = mapped_column(sa.String(20))

    # ── 인덱스 (§6.1 CREATE INDEX — started_at DESC) ──
    __table_args__ = (sa.Index("idx_session_user", "user_id", sa.desc("started_at")),)

    # ── 변환 헬퍼 (schema↔db seam, problem.py 패턴) ──────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaLearningSession) -> LearningSession:
        """검증된 `schema.LearningSession` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaLearningSession:
        """영속 ORM → `schema.LearningSession`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaLearningSession.model_validate(data)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ProblemAttempt (§6.1 problem_attempt — 한 문제 풀이 1단위, 특성 #96)
# ──────────────────────────────────────────────────────────────────────────
class ProblemAttempt(Base):
    """문항 풀이 시도 영속 ORM — §6.1 `problem_attempt`(특성 #2/#39/#42/#95/#96).

    PK `attempt_id`만 있고 나머지는 nullable/기본값(DDL 그대로). FK 3개:
    `user_id`→user_profile·`session_id`→learning_session·`problem_id`→problem. 단,
    `stuck_at_concept_id`는 §6.1 DDL에 `REFERENCES`가 없어 *FK가 아니다*(느슨참조).

    개인정보 메모(모듈 docstring 참조): `student_answer`·`handwriting_uri`·`ocr_result`는
    *미성년 풀이 데이터*다. 저장·동의 계층 책임이라 ORM에는 컬럼만 두고 가짜 CHECK를 만들지
    않는다(schema.activity 방침과 동형 — 문서화만).
    """

    __tablename__ = "problem_attempt"

    # ===== 기본 식별 =====
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id")
    )
    # slice 56: 세션 삭제(GDPR) 시 자식 attempt 함께 제거 — ON DELETE CASCADE.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("learning_session.session_id", ondelete="CASCADE")
    )
    problem_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("problem.problem_id")
    )

    # ===== 시간 =====
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== 결과 (기본값 없는 BOOLEAN → 미채점=NULL) =====
    is_correct: Mapped[bool | None] = mapped_column(sa.Boolean)
    # *미성년 풀이 데이터* — 평문 저장 금지는 저장계층 책임(모듈 docstring).
    student_answer: Mapped[str | None] = mapped_column(sa.Text)
    confidence_self_reported: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))

    # ===== 풀이 방식 (특성 #96) =====
    attempt_mode: Mapped[AttemptMode | None] = mapped_column(
        _pg_enum(AttemptMode, "attempt_mode_enum")
    )
    used_socratic: Mapped[bool | None] = mapped_column(sa.Boolean)
    used_hint: Mapped[bool | None] = mapped_column(sa.Boolean)
    used_solution_view: Mapped[bool | None] = mapped_column(sa.Boolean)

    # ===== 풀이 이미지/PDF (특성 #95) — *미성년 풀이 데이터* =====
    handwriting_uri: Mapped[str | None] = mapped_column(sa.Text)
    ocr_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))

    # ===== 막힌 지점 분석 =====
    stuck_at_step: Mapped[int | None] = mapped_column(sa.Integer)
    # REFERENCES 없음 → FK 아님(느슨참조).
    stuck_at_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 시간 관리 =====
    time_vs_expected: Mapped[float | None] = mapped_column(sa.Numeric(4, 2))

    # ===== 풀이 단계별 시간 (특성 #42) — schema default_factory=list → NOT NULL JSONB =====
    step_times: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB(none_as_null=True), nullable=False, server_default=sa.text("'[]'::jsonb")
    )

    # ===== 운영 메타 =====
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    # ── 인덱스 (§6.1 CREATE INDEX — idx_attempt_stuck은 부분 인덱스) ──
    __table_args__ = (
        sa.Index("idx_attempt_user", "user_id", sa.desc("started_at")),
        sa.Index("idx_attempt_problem", "problem_id"),
        sa.Index(
            "idx_attempt_stuck",
            "stuck_at_concept_id",
            postgresql_where=sa.text("stuck_at_concept_id IS NOT NULL"),
        ),
        # EOS-32(PR #902 P1): answer_submission의 복합 FK (attempt_id, user_id) 참조 대상.
        # attempt_id가 PK라 이 UNIQUE는 논리적으로 중복이지만, PG는 복합 FK가 가리키는 컬럼
        # 조합에 유일성 보장(UNIQUE/PK)을 요구한다 — 참조 대상 좌석용 표준 패턴(값 제약 추가
        # 효과는 0·기존 행 무영향).
        sa.UniqueConstraint("attempt_id", "user_id", name="uq_problem_attempt_attempt_user"),
    )

    @classmethod
    def from_schema(cls, schema: SchemaProblemAttempt) -> ProblemAttempt:
        """검증된 `schema.ProblemAttempt` → 영속 ORM(schema↔db seam)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaProblemAttempt:
        """영속 ORM → `schema.ProblemAttempt`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaProblemAttempt.model_validate(data)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: AttemptEvent (§6.1 attempt_event — 실시간 단계 이벤트)
# ──────────────────────────────────────────────────────────────────────────
class AttemptEvent(Base):
    """학생 풀이 단계 이벤트 영속 ORM — §6.1 `attempt_event`(실시간 분석용 시계열).

    복합 PK `(event_id, event_at)` — DDL 제약. `event_id`는 `BIGSERIAL`이라 DB가 INSERT 시
    할당하는 정수 PK(autoincrement; UUID PK와 달리 gen_random_uuid server_default 없음).
    `event_at`은 `TIMESTAMPTZ NOT NULL`이라 required(복합 PK 구성요소).

    `attempt_id`·`user_id`·`problem_id`는 §6.1 DDL에 `REFERENCES`가 없어 *FK가 아니다*
    (hypertable 느슨참조 — schema docstring 정합). 운영 시 이 테이블은 TimescaleDB
    hypertable로 변환되나(`event_at` 1일 청크), *그 변환은 마이그레이션 레벨*이라 ORM에서는
    일반 테이블로 둔다(hypertable 관련 코드를 ORM에 넣지 않는다).
    """

    __tablename__ = "attempt_event"

    # ===== 복합 PK (event_id, event_at) =====
    # BIGSERIAL → BigInteger autoincrement PK(DB-assigned, gen_random_uuid 없음).
    event_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    event_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)

    # ===== FK 아님 (REFERENCES 없음 — hypertable 느슨참조) =====
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)
    problem_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 이벤트 내용 =====
    event_type: Mapped[EventType | None] = mapped_column(_pg_enum(EventType, "event_type_enum"))
    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))

    @classmethod
    def from_schema(cls, schema: SchemaAttemptEvent) -> AttemptEvent:
        """검증된 `schema.AttemptEvent` → 영속 ORM(schema↔db seam).

        `event_id`는 BIGSERIAL(DB-assigned)이라 schema에서 None일 수 있다 — 그 경우 생성자에
        넘기지 않으면 ORM 인스턴스 속성은 None이고, INSERT 시 DB가 채운다(autoincrement).
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaAttemptEvent:
        """영속 ORM → `schema.AttemptEvent`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaAttemptEvent.model_validate(data)


__all__ = ["LearningSession", "ProblemAttempt", "AttemptEvent"]
