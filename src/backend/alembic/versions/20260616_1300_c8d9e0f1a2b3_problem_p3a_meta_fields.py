"""problem P3a 메타 필드 — question_format 4→10·bloom_level/scoring_type enum·8 컬럼 추가

P3a — `Problem`에 *부가 메타* 8필드 + 신규 enum 2종 + `QuestionFormat` 4→10 확장을 모두
*가산적(additive)*으로 더한다. 기존 50필드 Problem·난이도 5축·signature_patterns·persona_fit·
저작권 source_type 게이트는 *불변*이고, 기존 PG enum 라벨도 보존한다(기존 행 하위호환). 신규
컬럼은 전부 nullable이라 기존 행·구성은 무손상이다(BREAKING-free).

변경 3블록:
  ① question_format_enum ADD VALUE ×6 — 10유형 체계의 신규 라벨(객관식진단·빈칸형·짝짓기형·
     그래프형·수행형·재수전용형). 기존 4종(객관식·단답형·합답형·서술형) 라벨은 보존. 직전
     event_type/edge_type 확장 마이그레이션과 *동형*(ADD VALUE만·테이블 변경 0·데이터 무손상).
     PG 16은 트랜잭션 내 ADD VALUE를 허용한다 — *같은 트랜잭션에서 그 값을 사용(DML)만 하지
     않으면* 안전한데, 이 마이그레이션은 라벨 추가만 하고 그 값으로 INSERT/UPDATE하지 않으므로
     안전하다(`event_type_verify_result`·`edge_type_triggers_distractor` 선례 그대로). `IF NOT
     EXISTS`로 재실행 멱등.
  ② CREATE TYPE bloom_level_enum(6종·영어)·scoring_type_enum(5종·한글) — add_column은
     create_table과 달리 enum 타입을 자동 생성하지 않으므로 명시 생성한다(`postgresql.ENUM(
     ...).create(checkfirst=True)` — `concept_recommended_visual_styles` 선례).
  ③ ADD COLUMN ×8(전부 nullable) — bloom_level·scoring_type·domain·subunit·irt_a·
     discrimination_D·session_position·feedback_id. UUID PK·기존 행 무손상(점진 채움).

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  - 8 컬럼 drop → 신규 enum 2종(bloom_level_enum·scoring_type_enum) drop(`checkfirst` 멱등·본
    마이그레이션이 소유). question_format_enum의 ADD VALUE는 *되돌리지 않는다* — PostgreSQL은
    enum 값 제거를 지원하지 않고(타입 재생성·컬럼 캐스팅 필요), 관례대로 no-op이다(event_type/
    edge_type 확장 선례 동형·데이터 무손상). 추가된 6 라벨은 downgrade 후에도 남지만, 컬럼이
    question_format_enum을 계속 쓰므로(타입 자체는 initial_problem_domain 소유) 무해하다.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-16 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py QuestionFormat 신규 6종과 *정확히 일치*해야 한다(기존 4종은 ADD 안 함).
# 마이그레이션은 결정적이어야 하므로 ORM enum을 import하지 않고 정본 값을 박는다
# (initial_problem_domain의 인라인 라벨 선례).
_QUESTION_FORMAT_NEW: tuple[str, ...] = (
    "객관식진단",
    "빈칸형",
    "짝짓기형",
    "그래프형",
    "수행형",
    "재수전용형",
)

# schema/enums.py BloomLevel(6종·영어)·ScoringType(5종·한글)와 *정확히 일치*해야 한다.
_BLOOM_LEVELS: tuple[str, ...] = (
    "REMEMBER",
    "UNDERSTAND",
    "APPLY",
    "ANALYZE",
    "EVALUATE",
    "CREATE",
)
_SCORING_TYPES: tuple[str, ...] = (
    "정오답",
    "진단",
    "부분점수",
    "시간",
    "루브릭",
)


def upgrade() -> None:
    # ── ① question_format_enum ADD VALUE ×6(멱등) — 기존 4종 라벨 보존·테이블 변경 0. ──
    #    PG 16: 트랜잭션 내 ADD VALUE 허용(같은 트랜잭션에서 그 값을 *사용*만 안 하면 안전 —
    #    이 마이그레이션은 라벨 추가만 하므로 안전). event_type/edge_type 확장 선례 동형.
    for _label in _QUESTION_FORMAT_NEW:
        op.execute(f"ALTER TYPE question_format_enum ADD VALUE IF NOT EXISTS '{_label}'")

    # ── ② 신규 native ENUM 타입 생성(add_column이 자동 생성 안 하므로 명시·checkfirst 멱등). ──
    postgresql.ENUM(*_BLOOM_LEVELS, name="bloom_level_enum").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(*_SCORING_TYPES, name="scoring_type_enum").create(
        op.get_bind(), checkfirst=True
    )

    # ── ③ ADD COLUMN ×8(전부 nullable — 기존 행 무손상·점진 채움). ──
    # 과목·단원 보강.
    op.add_column("problem", sa.Column("domain", sa.String(length=64), nullable=True))
    op.add_column("problem", sa.Column("subunit", sa.String(length=128), nullable=True))
    # 문항 형식 보강(신규 enum 컬럼 — create_type=False로 ②에서 만든 타입 재사용).
    op.add_column(
        "problem",
        sa.Column(
            "bloom_level",
            postgresql.ENUM(*_BLOOM_LEVELS, name="bloom_level_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "problem",
        sa.Column(
            "scoring_type",
            postgresql.ENUM(*_SCORING_TYPES, name="scoring_type_enum", create_type=False),
            nullable=True,
        ),
    )
    # IRT/변별 보강(2PL a·고전 변별도 D — Float).
    op.add_column("problem", sa.Column("irt_a", sa.Float(), nullable=True))
    op.add_column("problem", sa.Column("discrimination_D", sa.Float(), nullable=True))
    # 세션·피드백 메타.
    op.add_column("problem", sa.Column("session_position", sa.Integer(), nullable=True))
    op.add_column("problem", sa.Column("feedback_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    # ── ③ 8 컬럼 drop(추가 역순). ──
    op.drop_column("problem", "feedback_id")
    op.drop_column("problem", "session_position")
    op.drop_column("problem", "discrimination_D")
    op.drop_column("problem", "irt_a")
    op.drop_column("problem", "scoring_type")
    op.drop_column("problem", "bloom_level")
    op.drop_column("problem", "subunit")
    op.drop_column("problem", "domain")

    # ── ② 본 마이그레이션이 만든 신규 ENUM 타입 정리(checkfirst 멱등 — 컬럼 drop 후 안전). ──
    postgresql.ENUM(name="scoring_type_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="bloom_level_enum").drop(op.get_bind(), checkfirst=True)

    # ── ① question_format_enum ADD VALUE는 되돌리지 않는다(PG enum 값 제거 미지원·관례 no-op). ──
    #    event_type/edge_type 확장 선례 동형. 추가된 6 라벨은 남지만 타입은 initial_problem_domain
    #    소유라 무해(데이터 무손상).
