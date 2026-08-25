"""단원 단위 성취수준 등급 커버리지(AchievementLevelUnit) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schema/standard.py`(Pydantic `AchievementLevelUnit`)와 *별도*로 세운 영속 매핑이며
`from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(`models/achievement_standard.py` 동일 패턴).
`achievement_criteria_v1` 코퍼스(CUR-05 회수)의 `achievement_levels_by_unit`(school_level×subject
세트마다 "단원 → 성취수준 등급 라벨 목록") 원소를 담는다.

CUR-07 핵심 설계 결정 — `achievement_standard`에 컬럼을 추가하지 않고 *별도 테이블*을 세운 이유
(`schema/standard.py` 모듈 docstring "CUR-07 확장" §2가 실측 근거를 기록):
  `unit` 문자열(예 '(1) 다항식')은 개별 성취기준(`norm_id`)에 안전하게 귀속시킬 조인 축이 없다.
  ① `AchievementStandard.domain`/`sub_domain`(NCIC 표준 분류 어휘)과 교집합 0(실측: 고등학교
  표준 26개 domain 대조) ② 같은 코퍼스의 `unit_hierarchy` 최상위 번호 매김과도 불일치(예: 같은
  "(1)"이 공통수학에서 "문자와 식"과 "다항식" 둘을 가리킴) ③ "(1) 문항 개발 목록"·"(2) 예시 평가
  문항" 같은 *보고서 절 제목*까지 섞여 있어 순수 단원 분류조차 아니다. 억지로 개별 성취기준에
  이으면 "이 단원의 모든 성취기준이 이 등급 집합을 가진다"는 원본에 없는 주장이 되므로(CLAUDE.md
  "환경 사실의 추론 등재 금지"), **개별 성취기준과의 연결은 이 태스크 범위 밖으로 명시**하고 이
  테이블은 (school_level, subject, unit) 자연키로만 존재한다. FK 없음 — 독립 테이블(additive).

PK 판단: `unit_id`는 UUID 대리키(`server_default gen_random_uuid()` — `concept_standard_link.
link_id`·`defect_report.report_id` 선례). 자연 유일키는 `(school_level, subject, unit)` 복합
UNIQUE — 멱등 upsert(`ON CONFLICT`)는 이 복합키를 충돌 대상으로 쓴다(PK가 아니라도 무방 — schema
쪽에 `unit_id`가 없으므로 `from_schema`가 그 컬럼을 비우고 DB server_default가 채운다).

타입 매핑: `school_level`·`subject`·`unit`(NCIC 코드처럼 닫힌 짧은 라벨이 아니라 코퍼스 원문
그대로의 자유 라벨) → `sa.String`(길이 제한 없음, `AchievementStandard.school_type`/`subject`
선례와 동형 — 닫힌 enum 강제는 파이프라인 책임). `levels` → `ARRAY(sa.Text)` NOT NULL
`server_default '{}'::text[]`(`parent_codes` 동일 패턴). `source_document` → `sa.Text`(nullable).
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.standard import (
    AchievementLevelUnit as SchemaAchievementLevelUnit,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: AchievementLevelUnit (단원 단위 성취수준 등급 커버리지 — FK 없음·독립 테이블)
# ──────────────────────────────────────────────────────────────────────────
class AchievementLevelUnit(Base):
    """단원 단위 성취수준 등급 커버리지 영속 ORM — `unit_id` UUID 대리 PK.

    자연 유일키 `(school_level, subject, unit)` — 같은 코퍼스 재적재 시 멱등 upsert 대상(복합
    UNIQUE). `AchievementStandard`를 포함해 어떤 테이블과도 FK를 걸지 않는다(모듈 docstring —
    unit↔개별 성취기준 연결은 실측 근거 부족으로 이 태스크 범위 밖).
    """

    __tablename__ = "achievement_level_unit"

    # PK = UUID(server_default gen_random_uuid() — concept_standard_link.link_id 선례,
    # schema엔 unit_id가 없어 from_schema가 비우고 DB server_default가 채운다).
    unit_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 코퍼스 출처 KICE 보고서 구분('고등학교'|'초중학교') — achievement_standard.school_type과
    # 다른 어휘(모듈 docstring)이므로 FK·공유 enum 없이 자유 문자열로 둔다.
    school_level: Mapped[str] = mapped_column(sa.String, nullable=False)
    subject: Mapped[str] = mapped_column(sa.String, nullable=False)
    # 단원 라벨(코퍼스 원문 그대로 — 서술 아님, 짧은 헤더 문자열).
    unit: Mapped[str] = mapped_column(sa.String, nullable=False)
    # NOT NULL 배열 — schema default_factory=list. parent_codes와 동일 빈 배열 기본값.
    levels: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    source_document: Mapped[str | None] = mapped_column(sa.Text)

    # ── 제약·인덱스 (자연 유일키 + 과목 단위 조회 경로) ──
    __table_args__ = (
        # 같은 (보고서구분, 과목, 단원) 재적재 시 멱등 upsert 대상.
        sa.UniqueConstraint(
            "school_level",
            "subject",
            "unit",
            name="uq_achievement_level_unit_school_subject_unit",
        ),
        # 과목 단위 조회 경로(예: '고등학교'의 '심화수학Ⅰ' 단원별 등급 목록).
        sa.Index("idx_achievement_level_unit_subject", "school_level", "subject"),
    )

    # ── 변환 헬퍼 (schema↔db seam, achievement_standard.py 패턴) ──────────
    @classmethod
    def from_schema(cls, schema: SchemaAchievementLevelUnit) -> AchievementLevelUnit:
        """검증된 `schema.AchievementLevelUnit` → 영속 ORM(mapper 컬럼키 필터).

        schema엔 `unit_id`가 없으므로(자연 유일키는 (school_level, subject, unit)) 필터가
        unit_id를 비우고 DB server_default(gen_random_uuid())가 채운다.
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaAchievementLevelUnit:
        """영속 ORM → `schema.AchievementLevelUnit`(Pydantic 검증 복원).

        ORM 전용 컬럼 `unit_id`는 schema에 없고(extra="forbid") 들어가면 거부되므로, schema가
        받는 필드만 추려 복원한다(concept_standard_link.to_schema와 동일 사유).
        """
        schema_fields = set(SchemaAchievementLevelUnit.model_fields)
        data = {name: getattr(self, name) for name in schema_fields}
        return SchemaAchievementLevelUnit.model_validate(data)


__all__ = ["AchievementLevelUnit"]
