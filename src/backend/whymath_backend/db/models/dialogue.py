"""도메인5 Socratic 대화(Dialogue) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schemas/v1.0/schema_v1.0.md` §7.1(`dialogue`·`dialogue_turn` DDL 2테이블)·§7.1
인덱스. 이 ORM은 `schema/dialogue.py`(Pydantic, 검증·API)와 *별도*로 세운 영속 매핑이며
`from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(배치1 `problem.py`·`user.py` 동일 패턴).

타입 매핑(DDL → ORM, problem.py/user.py 선례 그대로):
  - `UUID PRIMARY KEY` → `server_default gen_random_uuid()`(배치1 UUID PK 선례).
  - `UUID REFERENCES`(nullable FK) → `uuid.UUID|None` + FK(예: user_id→user_profile,
    attempt_id→problem_attempt, problem_id→problem, dialogue_id→dialogue).
  - `UUID`(REFERENCES 없음) → `uuid.UUID|None`(*FK 아님* — `targeted_concept_id`는 §7.1 DDL에
    REFERENCES 절이 없는 느슨참조. activity.target_concept_id 선례와 동형).
  - `INTEGER NOT NULL`(turn_order) → required `int`(schema가 NOT NULL을 required로 둔 선례,
    problem.py ProblemStep.step_order와 동형).
  - `resolution_enum`/`turn_role_enum`/`content_type_enum`/`socratic_strategy_enum`/
    `student_intent_enum` → `_pg_enum(...)`(신규 PG 타입).
  - `DECIMAL(p,s)` → `Mapped[float|None] = mapped_column(sa.Numeric(p, s))`(estimated_cost_usd
    DECIMAL(8,4)·auto_quality_score·student_understanding_signal).
  - `BOOLEAN DEFAULT FALSE`(flagged_for_review) → `nullable=False, server_default sa.false()`
    (problem.py boolean default 선례; schema도 `bool = False`).
  - `VARCHAR(n)`(model_used) → `sa.String(n)`; `TEXT`(content) → `sa.Text`.
  - `JSONB`(image_analysis) → `JSONB`.
  - 제약·인덱스(§7.1 UNIQUE + CREATE INDEX) → `__table_args__`.

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`activity.py` 방침과 동일):
  `dialogue_turn`의 `content`(대화 본문)·`image_uri`(손글씨 이미지 URI)·`image_analysis`
  (Qwen3-VL 분석)는 *미성년 채팅·손글씨 데이터*다. 평문 저장 금지·동의 없는 학습 사용 금지는
  *저장·동의 계층*(암호화·미들웨어·검수) 책임이며, ORM에는 컬럼만 두고 가짜 CHECK를 만들지
  않는다(schema.dialogue 모듈 docstring·problem.py 방침과 동형 — 문서화만).
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
from whymath_backend.schema.dialogue import Dialogue as SchemaDialogue
from whymath_backend.schema.dialogue import DialogueTurn as SchemaDialogueTurn
from whymath_backend.schema.enums import (
    ContentType,
    Resolution,
    SocraticStrategy,
    StudentIntent,
    TurnRole,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: Dialogue (§7.1 dialogue — 한 문제 풀이 중의 대화 세션)
# ──────────────────────────────────────────────────────────────────────────
class Dialogue(Base):
    """Socratic 대화 세션 영속 ORM — §7.1 `dialogue`(한 문제 풀이 중 학생↔AI 대화 1단위).

    PK `dialogue_id`만 있고 나머지는 nullable/기본값(DDL 그대로). FK 3개:
    `user_id`→user_profile·`attempt_id`→problem_attempt·`problem_id`→problem. `resolution`으로
    학생이 스스로 풀었는지·유도로 풀었는지·결국 풀이를 봤는지·포기했는지를 가른다(특성 #96
    콴다 대비 차별 핵심 지표).
    """

    __tablename__ = "dialogue"

    # ===== 기본 식별 =====
    dialogue_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id")
    )
    # slice 56: attempt가 cascade 삭제돼도 dialogue 자체는 보존 — 링크만 끊음(SET NULL).
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("problem_attempt.attempt_id", ondelete="SET NULL")
    )
    problem_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("problem.problem_id")
    )

    # ===== 시간 =====
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    # ===== 대화 결과 =====
    resolution: Mapped[Resolution | None] = mapped_column(_pg_enum(Resolution, "resolution_enum"))
    # S3-32: 서버검증(verify_final_answer) + Polya REVIEW 게이트 완료 시각. NULL=미완료·
    # api/coach.py의 멱등 가드(schema.dialogue.py 필드 docstring 참조).
    server_verified_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True)
    )

    # ===== 턴 카운트 =====
    total_turns: Mapped[int | None] = mapped_column(sa.Integer)
    student_turns: Mapped[int | None] = mapped_column(sa.Integer)
    assistant_turns: Mapped[int | None] = mapped_column(sa.Integer)

    # ===== LLM 사용량 =====
    model_used: Mapped[str | None] = mapped_column(sa.String(50))
    total_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(sa.Numeric(8, 4))

    # ===== 품질 평가 =====
    student_rating: Mapped[int | None] = mapped_column(sa.Integer)
    auto_quality_score: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))
    flagged_for_review: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )

    # ── 인덱스 (§7.1 CREATE INDEX — started_at DESC) ──
    __table_args__ = (
        sa.Index("idx_dialogue_user", "user_id", sa.desc("started_at")),
        sa.Index("idx_dialogue_problem", "problem_id"),
    )

    # ── 변환 헬퍼 (schema↔db seam, problem.py 패턴) ──────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaDialogue) -> Dialogue:
        """검증된 `schema.Dialogue` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaDialogue:
        """영속 ORM → `schema.Dialogue`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaDialogue.model_validate(data)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: DialogueTurn (§7.1 dialogue_turn — 학생↔AI 한 번의 교환)
# ──────────────────────────────────────────────────────────────────────────
class DialogueTurn(Base):
    """대화 턴 영속 ORM — §7.1 `dialogue_turn`(학생↔AI 한 번의 교환, 특성 #8/#18/#21).

    PK `turn_id`, `dialogue_id`→dialogue FK. `turn_order`는 `INTEGER NOT NULL`이라 required
    (problem.py ProblemStep.step_order 선례). `UNIQUE(dialogue_id, turn_order)` — 한 대화 안에서
    turn_order 유일(DDL 제약). `targeted_concept_id`는 §7.1 DDL에 REFERENCES가 없어 *FK 아님*
    (느슨참조).

    개인정보 메모(모듈 docstring 참조): `content`·`image_uri`·`image_analysis`는 *미성년 채팅·
    손글씨 데이터*다. 저장·동의 계층 책임이라 ORM에는 컬럼만 두고 가짜 CHECK를 만들지 않는다.
    """

    __tablename__ = "dialogue_turn"

    # ===== 기본 식별 =====
    turn_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # slice 56: 대화 삭제(GDPR) 시 자식 turn 함께 제거 — ON DELETE CASCADE.
    dialogue_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("dialogue.dialogue_id", ondelete="CASCADE")
    )
    # INTEGER NOT NULL → required(UNIQUE(dialogue_id, turn_order) 구성요소).
    turn_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    spoken_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    # ===== 내용 (content는 *미성년 채팅 데이터*) =====
    role: Mapped[TurnRole | None] = mapped_column(_pg_enum(TurnRole, "turn_role_enum"))
    # 감사상환 #2: 봉투 암호화(AES-256-GCM) 시 평문 대신 content_encrypted+content_nonce에
    # 저장하므로 content는 암호화 행에서 NULL(원래부터 nullable). 기존/암호화 비활성 행은 평문
    # 유지(dual-read 폴백). CLAUDE.md 절대 금기 '미성년 채팅 평문 저장 금지'의 저장계층 시행.
    content: Mapped[str | None] = mapped_column(sa.Text)
    # 감사상환 #2: 대화 본문 at-rest 봉투 암호화 — 마스터 키(DB 밖·env)로 암호화된 본문 +
    # 96-bit nonce. 둘 다 NULL이면 평문(content) 행. 키가 DB에 없어 dump 단독 복호 불가.
    # device.secret_encrypted/secret_nonce 선례 미러. schema round-trip 제외(_NON_SCHEMA_COLUMNS).
    content_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    content_nonce: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    content_type: Mapped[ContentType | None] = mapped_column(
        _pg_enum(ContentType, "content_type_enum")
    )

    # ===== AI 응답 메타데이터 (특성 #8/#18/#21) =====
    socratic_strategy: Mapped[SocraticStrategy | None] = mapped_column(
        _pg_enum(SocraticStrategy, "socratic_strategy_enum")
    )
    targeted_step: Mapped[int | None] = mapped_column(sa.Integer)
    # REFERENCES 없음 → FK 아님(느슨참조).
    targeted_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)

    # ===== 학생 응답 분석 =====
    student_intent: Mapped[StudentIntent | None] = mapped_column(
        _pg_enum(StudentIntent, "student_intent_enum")
    )
    student_understanding_signal: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))

    # ===== 멀티모달 (*미성년 풀이 데이터*) =====
    # SEC-01: 손글씨 이미지 URI·Qwen3-VL 분석은 **미성년 풀이 전사가 가능한** 데이터인데
    # 암호화 경로가 아예 없었다(평문 Text/JSONB). content와 같은 봉투 암호화(AES-256-GCM)를
    # 붙인다 — 암호화 행에서는 평문 컬럼이 NULL이고 `*_encrypted`+`*_nonce`에 저장된다
    # (dual-read 폴백: 기존/암호화 비활성 행은 평문 유지). 키는 **content와 동일**
    # (`dialogue_content_encryption_key`) — 같은 테이블·같은 요청·같은 데이터 주체라 키를
    # 쪼개도 폭발 반경이 실질적으로 줄지 않는 반면, 키가 하나 늘면 "미설정→평문 폴백" 함정이
    # 하나 더 생긴다(Kiki 결정).
    image_uri: Mapped[str | None] = mapped_column(sa.Text)
    image_uri_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    image_uri_nonce: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    # JSONB는 그대로 암호화할 수 없어 **결정론 JSON 직렬화 후** 바이트를 암호화한다
    # (`sort_keys=True`·`ensure_ascii=False`). 복호는 역직렬화해 dict로 되돌린다.
    #
    # SEC-04: `none_as_null=True` 필수 — 기본값(False)이면 Python `None`이 **SQL NULL이 아니라
    # JSONB 스칼라 `null`** 로 저장된다. 그러면 "분석 없음"인 행이 `image_analysis IS NOT NULL`을
    # 만족해 *평문 데이터가 있는 행*으로 오계수된다: ①배포 실측 쿼리가 "암호화 안 됨" 거짓경보를
    # 내고 ②백필 WHERE가 그 행들을 대상으로 잡아 LIMIT 창을 채우면 **진짜 평문 행이 굶어죽는다**
    # (2026-07-28 실 PG 재현: JSONB null 5행+평문 1행·batch_size=3에서 CLI가 "0행 처리"를
    # 완료로 보고하고 평문 1행이 미암호화 잔존). 값 없음은 SQL NULL이어야 한다.
    image_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    image_analysis_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    image_analysis_nonce: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)

    # ── 제약·인덱스 (§7.1 UNIQUE + CREATE INDEX) ──
    __table_args__ = (
        sa.UniqueConstraint("dialogue_id", "turn_order"),
        sa.Index("idx_turn_dialogue", "dialogue_id", "turn_order"),
    )

    # 감사상환 #2: schema round-trip에서 제외하는 봉투 암호화 컬럼(schema는 extra="forbid"라
    # 이 키가 model_validate에 들어가면 실패). 복호는 handler/헬퍼 층이 담당하고(순수 seam에
    # cipher 미주입), schema.content엔 복호된 평문을 별도 설정한다. ciphertext는 API·export에
    # 절대 노출하지 않는다(schema 밖 유지).
    # SEC-01: 이미지 봉투 컬럼도 같은 이유로 schema 밖에 둔다(ciphertext는 API·export 미노출).
    _NON_SCHEMA_COLUMNS = frozenset(
        {
            "content_encrypted",
            "content_nonce",
            "image_uri_encrypted",
            "image_uri_nonce",
            "image_analysis_encrypted",
            "image_analysis_nonce",
        }
    )

    @classmethod
    def from_schema(cls, schema: SchemaDialogueTurn) -> DialogueTurn:
        """검증된 `schema.DialogueTurn` → 영속 ORM(schema↔db seam).

        암호화 컬럼(content_encrypted/content_nonce)은 schema에 없어 여기서 설정되지 않는다 —
        handler/헬퍼 층(`_build_dialogue_turn`)이 content를 암호화해 채운다(순수 seam).
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaDialogueTurn:
        """영속 ORM → `schema.DialogueTurn`(Pydantic 검증 복원).

        봉투 암호화 컬럼은 `_NON_SCHEMA_COLUMNS`로 제외(schema extra="forbid"·ciphertext 비노출).
        암호화 행은 content가 NULL이므로 handler/헬퍼 층이 복호값을 schema.content에 덮어쓴다.
        """
        mapped_keys = {
            col.key
            for col in sa.inspect(type(self)).mapper.column_attrs
            if col.key not in self._NON_SCHEMA_COLUMNS
        }
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaDialogueTurn.model_validate(data)


__all__ = ["Dialogue", "DialogueTurn"]
