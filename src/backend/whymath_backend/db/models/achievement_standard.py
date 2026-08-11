"""성취기준(AchievementStandard) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schema/standard.py`(Pydantic, 검증·API 계약)와 *별도*로 세운 영속 매핑이며
`from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(`models/concept.py`·`models/curriculum_entry.py`
동일 패턴 — SQLModel 미사용). 이 슬라이스(P1-2)는 성취기준의 ORM·계약·마이그레이션만 세우고,
jsonl 코퍼스 로더는 후속 슬라이스 몫이다(코퍼스 포맷 확정 전까지 보류).

PK 판단(이 모듈의 핵심 결정):
  `norm_id`(교육과정 간 유일 식별자)가 PK다. `official_code`(고시 원문코드)는 교육과정 간
  *비유일*(예: 2022·2015에 동일 `[12미적01-01]` 동시 존재 가능)이라 **PK가 아니고
  NON-unique 컬럼**이며, `(curriculum_revision, official_code)`가 유일성을 갖는다
  (`UniqueConstraint`로 강제). norm_id는 UUID가 아닌 의미 문자열이라 `gen_random_uuid()`
  server_default가 없다(curriculum_entry.entry_id가 str PK라 server_default 없는 것과 동형 —
  값은 schema/로더가 채운다).

타입 매핑(schema → ORM, concept.py·curriculum_entry.py 선례 그대로):
  - `norm_id`(PK) → `sa.String(32)`(NORM_ID_PATTERN 최대 길이 여유 — 의미 문자열).
  - `official_code`(NON-unique) → `sa.String(32)`(고시 원문코드 — 의미 문자열).
  - `curriculum_revision` → `sa.String(16)`('2022 개정'·'2015 개정').
  - `grade_band`·`school_type`·`subject`·`domain`(required) → `sa.String, NOT NULL`.
  - `sub_domain`(선택) → `sa.String`(nullable).
  - `statement`(본문, required) → `sa.Text, NOT NULL`(자유 서술 — 길이 무제한).
  - `commentary`·`big_idea`(선택) → `sa.Text`(nullable).
  - `effective_from`(시행일) → `sa.Date`(TIMESTAMPTZ 아님 — 날짜만, curriculum_entry 선례).
  - `parent_codes`(선수 코드 배열, NOT NULL 의미) → `ARRAY(sa.Text), server_default '{}'::text[]`
    (concept_node.standard_codes·concept_fusion.concept_ids NOT NULL 배열 선례 — schema가
    default_factory=list라 항상 list를 넘기지만 DB도 빈 배열 기본값을 둔다).
  - `source_url`(required) → `sa.Text, NOT NULL`(URL — 길이 여유).
  - `source_document`(선택) → `sa.Text`(nullable).

법적 메모(공공누리 제1유형): 성취기준 본문(`statement`)·해설(`commentary`)은 NCIC 공공누리
제1유형 자료라 본문 보유가 *허용*된다(검정교과서·EBS·평가원 본문 금지와 대비 —
`licensing_safety.md` 가이드 v2.0). 출처 표시 의무는 수집기·노출 계층이 동봉한다.

CUR-07 확장(additive): `evaluation_criteria_codes`(평가준거 코드, `ARRAY(sa.Text)` NOT NULL
`server_default '{}'::text[]` — `parent_codes`와 동일 배열 패턴) 컬럼을 추가한다.
`achievement_criteria_v1` 코퍼스의 `standard_criteria_coverage`(official_code 단위 1:N)를 실측
근거로 `(curriculum_revision, official_code)` 대조 매칭한 값을 로더(`l1/standards/
criteria_loader.py`)가 채운다 — 기존 행은 server_default가 빈 배열을 채우므로 무충돌(additive).
같은 코퍼스의 `achievement_levels_by_unit`(unit 문자열 단위)은 이 테이블에 컬럼을 추가하지
*않는다* — `schema/standard.py` 모듈 docstring "CUR-07 확장" §2가 그 판단 근거를 기록한다
(별도 테이블 `AchievementLevelUnit`, `db/models/achievement_level_unit.py`).
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.standard import (
    AchievementStandard as SchemaAchievementStandard,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: AchievementStandard (성취기준 — norm_id PK·official_code 비유일)
# ──────────────────────────────────────────────────────────────────────────
class AchievementStandard(Base):
    """성취기준 영속 ORM — `norm_id` PK(교육과정 간 유일), `official_code` NON-unique.

    교육과정 간 유일성은 `(curriculum_revision, official_code)` 복합 UNIQUE로 강제한다
    (모듈 docstring PK 판단). 형식 검증(norm_id/official_code 정규식)·cross-dataset 정합은
    *데이터 파이프라인 책임*이며 ORM에는 컬럼만 둔다(curriculum_entry.py 방침과 동형 —
    가짜 CHECK 없음).
    """

    __tablename__ = "achievement_standard"

    # ===== 식별 — norm_id(PK, 의미 문자열·UUID 아님) + 비유일 official_code =====
    # norm_id는 UUID가 아니라 의미 문자열이라 gen_random_uuid() server_default 없음(로더가 채움).
    norm_id: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    # official_code는 교육과정 간 *비유일* — UNIQUE 아님(NON-unique). 유일성은 복합 UNIQUE로.
    official_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    curriculum_revision: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    # ===== 분류 (NCIC subject/domain은 str — 닫힌 enum 강제는 파이프라인 책임) =====
    grade_band: Mapped[str] = mapped_column(sa.String, nullable=False)
    school_type: Mapped[str] = mapped_column(sa.String, nullable=False)
    subject: Mapped[str] = mapped_column(sa.String, nullable=False)
    domain: Mapped[str] = mapped_column(sa.String, nullable=False)
    sub_domain: Mapped[str | None] = mapped_column(sa.String)

    # ===== 본문·해설 (공공누리 1유형 — 본문 보유 허용) =====
    statement: Mapped[str] = mapped_column(sa.Text, nullable=False)
    commentary: Mapped[str | None] = mapped_column(sa.Text)
    big_idea: Mapped[str | None] = mapped_column(sa.Text)

    # ===== 시점·위계·출처 =====
    # DATE — 날짜만(TIMESTAMPTZ 아님, curriculum_entry.effective_from 선례).
    effective_from: Mapped[date | None] = mapped_column(sa.Date)
    # NOT NULL 배열 — schema default_factory=list. concept_node.standard_codes 선례대로 빈 배열.
    parent_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    source_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_document: Mapped[str | None] = mapped_column(sa.Text)

    # ===== 평가준거 코드 커버리지 (CUR-07 — additive, achievement_criteria_v1 매칭 결과) =====
    # official_code 1건 : 평가준거 코드 다건 — parent_codes와 동일 NOT NULL 배열 패턴(빈 배열 기본).
    evaluation_criteria_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )

    # ── 제약·인덱스 (복합 UNIQUE + 조회 경로 인덱스) ──
    __table_args__ = (
        # 교육과정 간 유일성 — official_code 단독은 비유일이므로 개정과 함께 유일(모듈 docstring).
        sa.UniqueConstraint(
            "curriculum_revision",
            "official_code",
            name="uq_achievement_standard_revision_official_code",
        ),
        # official_code로 성취기준을 찾는 경로(개정 미지정 광역 조회).
        sa.Index("idx_achievement_standard_official_code", "official_code"),
        # 개정 × 영역 필터(예: '2022 개정'의 '도형과 측정' 성취기준 목록).
        sa.Index("idx_achievement_standard_revision_domain", "curriculum_revision", "domain"),
    )

    # ── 변환 헬퍼 (schema↔db seam, concept.py 패턴) ──────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaAchievementStandard) -> AchievementStandard:
        """검증된 `schema.AchievementStandard` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaAchievementStandard:
        """영속 ORM → `schema.AchievementStandard`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaAchievementStandard.model_validate(data)


__all__ = ["AchievementStandard"]
