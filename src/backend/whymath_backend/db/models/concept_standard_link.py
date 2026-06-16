"""개념↔성취기준 링크(ConceptStandardLink) ORM 모델 (SQLAlchemy 2.0 영속 레이어).

설계 정본: `schema/standard.py`(Pydantic, 검증·API 계약)와 *별도*로 세운 영속 매핑이며
`from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(`models/concept.py` 동일 패턴). 개념 그래프(L1)의
개념과 성취기준(`achievement_standard`) 사이를 잇는 N:M 연결 레이어다.

PK·참조 판단(이 모듈의 핵심 결정):
  - `link_id`(UUID PK·server_default `gen_random_uuid()`) — concept.py의 UUID PK 선례 그대로.
    Pydantic `ConceptStandardLink`엔 `link_id`가 없어(연결의 의미키는 (concept_code, norm_id,
    link_type)) `from_schema`는 link_id를 비우고 DB server_default가 채운다. `to_schema`는
    schema 필드만 추려 복원한다(아래 변환 헬퍼 주석).
  - `concept_code`(`sa.String(64)`·NOT NULL) — 개념 식별자 *느슨참조*. 현재 'UC.*', 후속
    'ELEM-GEO-*'(백엔드 Concept.code가 String(64)인 것과 동일 어휘·길이). **FK 아님** —
    개념 식별자 공간이 (UC 키·후속 개념코드로) 진화 중이라 DB FK로 묶지 않는다
    (curriculum_entry.national_standard_codes가 cross-dataset 느슨참조라 FK 아닌 것과 동형).
  - `norm_id`(`sa.String(32)`·NOT NULL·**REAL FK** → `achievement_standard.norm_id`,
    `ondelete="CASCADE"`) — 성취기준이 삭제되면 그 링크도 함께 삭제(연결은 성취기준에 종속).

`link_type`(연결 의미·한글 정본 '직접'/'재매핑'/'준용') 저장 방식 판단:
  `sa.String(8)`로 둔다(PG native enum 미생성). 닫힌 어휘 강제는 Pydantic `Literal`(schema)이
  API 경계에서 하고 `to_schema` 복원이 재검증하므로, DB는 `concept_node.review_status`(소규모
  상태값을 plain `Text`로 둔 선례)처럼 값만 담는다. concept_edge의 `edge_type_enum`은 *개념→개념
  그래프 어휘*(6종·여러 도메인이 SQL 필터에 쓰는 정본)라 PG enum이 정당했던 것과 대비된다 —
  link_type은 연결 메타의 보조 라벨이라 enum 타입 오브젝트를 새로 만들 표면 비용이 과하다.
  ("재매핑"은 한글 3자라 VARCHAR(8)에 여유.)
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.standard import (
    ConceptStandardLink as SchemaConceptStandardLink,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ConceptStandardLink (개념 ↔ 성취기준 N:M 연결)
# ──────────────────────────────────────────────────────────────────────────
class ConceptStandardLink(Base):
    """개념 ↔ 성취기준 연결 영속 ORM — `link_id` UUID PK, `norm_id` 실 FK.

    의미 유일키 `(concept_code, norm_id, link_type)` — 같은 개념·성취기준 쌍에 같은 의미의
    중복 링크를 막는다(복합 UNIQUE). `concept_code`는 느슨참조(FK 아님), `norm_id`는 실 FK
    (achievement_standard, CASCADE). `link_type`은 한글 정본 값을 그대로 담는다(모듈 docstring).
    """

    __tablename__ = "concept_standard_link"

    # PK = UUID(server_default gen_random_uuid() — concept.py UUID PK 선례, schema엔 link_id 없음).
    link_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 개념 식별자 느슨참조 — FK 아님(개념 식별자 공간 진화 중, Concept.code와 동일 String(64)).
    concept_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # 성취기준 실 FK — 성취기준 삭제 시 링크도 함께 삭제(연결은 성취기준에 종속).
    norm_id: Mapped[str] = mapped_column(
        sa.String(32),
        sa.ForeignKey("achievement_standard.norm_id", ondelete="CASCADE"),
        nullable=False,
    )
    # 연결 의미('직접'/'재매핑'/'준용') — 닫힌 어휘 강제는 schema Literal·to_schema 재검증 몫.
    link_type: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(sa.Text)

    # ── 제약·인덱스 (의미 유일키 + 양방향 조회 경로) ──
    __table_args__ = (
        # 같은 (개념, 성취기준, 의미) 쌍의 중복 링크 금지.
        sa.UniqueConstraint(
            "concept_code",
            "norm_id",
            "link_type",
            name="uq_concept_standard_link_concept_norm_type",
        ),
        # 성취기준 → 연결된 개념 조회(FK 역방향).
        sa.Index("idx_concept_standard_link_norm", "norm_id"),
        # 개념 → 연결된 성취기준 조회.
        sa.Index("idx_concept_standard_link_concept", "concept_code"),
    )

    # ── 변환 헬퍼 (schema↔db seam, concept.py 패턴) ──────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaConceptStandardLink) -> ConceptStandardLink:
        """검증된 `schema.ConceptStandardLink` → 영속 ORM(mapper 컬럼키 필터).

        schema엔 `link_id`가 없으므로(의미키는 (concept_code, norm_id, link_type)) 필터가
        link_id를 비우고 DB server_default(gen_random_uuid())가 채운다.
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaConceptStandardLink:
        """영속 ORM → `schema.ConceptStandardLink`(Pydantic 검증 복원).

        ORM 전용 컬럼 `link_id`는 schema에 없고(extra="forbid") 들어가면 거부되므로, schema가
        받는 필드만 추려 복원한다(curriculum_entry 등은 필드집합이 같아 단순 추출이었으나, 여기선
        link_id가 ORM 전용이라 schema 필드 교집합이 필요하다).
        """
        schema_fields = set(SchemaConceptStandardLink.model_fields)
        data = {name: getattr(self, name) for name in schema_fields}
        return SchemaConceptStandardLink.model_validate(data)


__all__ = ["ConceptStandardLink"]
