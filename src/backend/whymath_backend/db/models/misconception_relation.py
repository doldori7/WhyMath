"""오개념 전용 관계셋(caused_by·variant_of) ORM 모델 — 개념그래프와 물리적으로 격리된 저장소.

설계 정본: `docs/architecture/04e_misconception_remediation_design.md` §2(특히 §2-3 "격리
스키마 설계"). 04c §6 Level2("오개념 간 관계 그래프가 없다")가 요구한 갭을 좁히되, §2-1·§2-2가
재검토해 **실제로 비어 있는 축 2종만** 채택한다:

  - `caused_by` — 오개념 A가 오개념 B를 유발(예: "분수개념 부족" → "통분 오류").
  - `variant_of` — 같은 오개념의 다른 표현형(surface expression).

**채택 안 함**(재론하지 않는다):
  - `misconception_of`(오개념→개념 방향) — 이미 `Concept.misconception_codes` +
    `concept_src_id` *느슨참조*로 해결된 축이다(`edge_design_part3_review.md` "채택 안 함"
    결정). 이 테이블은 그 축을 다루지 않는다 — 개념 테이블 FK는 0개다.
  - `repaired_by` — `l4/misconception/intervene.py`의 confidence 결정트리와 이중 진실원천이
    되므로 제외한다(04e §2-2).

이 모듈은 **저장소(storage)만** 세운다 — traversal 엔진·조회 API·소비 로직은 신설하지 않는다
(04e §2-3 "reactive-candidate-expansion용 미래 작업" — 지금은 짓지 않는다).

`misconception_crosslink.py`(오개념 kebab-id ↔ M-id N:M) 선례를 미러하되 핵심 차이는 **복합 PK**
다 — 서로게이트 PK(`link_id`) 없이 `(from_mis_id, relation_type, to_mis_id)` 자체가 식별자다
(`db/models/problem.py::ProblemRelation` — 동일 테이블을 가리키는 두 FK + 복합 PK 구조의
정확한 선례. `ProblemRelation`은 자기참조 금지 검증기를 schema에 두지만, 이 모델은 04e §2-3이
명시한 "순환 무해(순회 안 함)" 판단을 그대로 따라 자기참조 금지 검증을 넣지 않는다).

PK·FK 판단:
  - `from_mis_id`·`to_mis_id`(둘 다 `sa.String(32)`·**실 FK** → `misconception_catalog.mis_id`·
    CASCADE) — misconception_catalog.mis_id와 동일 폭(atom 투영 mis_id 최장 18자 실측·
    마이그레이션 a5b6c7d8e9f0 선례 그대로). M-id 삭제 시 그 관계도 함께 삭제(연결은 M-id에
    종속 — crosslink.mis_id CASCADE 선례와 동형).
  - `relation_type`(`sa.String(16)`) — 닫힌 2종 어휘(`caused_by`/`variant_of`)는 DB CHECK가
    아니라 **schema Literal·`to_schema` 재검증**이 강제한다(crosslink.link_type 선례 — "닫힌
    어휘는 schema 몫, DB는 값만 담는다"). 오타(`repaired_by`·`misconception_of` 등)는 schema
    검증에서 거부된다.
  - 개념 테이블 FK: **0개**(Storage 레벨 불변식 — 04c Level1과 동형). traversal 진입 차단은
    `test_misconception_seven_stage_manifest.py`(FK 부재 확인)와 소스 스캔 동결 테스트
    (`concept_edge` 순회 함수가 이 테이블명을 참조하지 않음)가 이중으로 지킨다.

DAG 강제 없음(04e §2-3 근거 그대로 인용): `caused_by`·`variant_of` 둘 다 순회 알고리즘에 태우지
않고 단건 조회만 하므로, 순환이 존재해도 무해하다 — `prerequisite`(concept_edge)처럼 DAG를
강제할 필요가 없다.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.misconception_relation import (
    MisconceptionRelation as SchemaMisconceptionRelation,
)


class MisconceptionRelation(Base):
    """오개념 ↔ 오개념 관계 영속 ORM — 복합 PK `(from_mis_id, relation_type, to_mis_id)`.

    개념 그래프(`concept_edge`)와 물리적으로 격리된 신규 테이블(04e §2-3). 양쪽 FK 모두
    `misconception_catalog.mis_id`만 가리키며, 개념 테이블 FK는 0개다. traversal 엔진에
    태우지 않는 단건 조회 전용 저장소 — 이 모듈 자체는 조회 함수를 두지 않는다.
    """

    __tablename__ = "misconception_relation"

    # 유발 방향(caused_by) — A(from)가 B(to)를 유발. CASCADE — from 쪽 M-id 삭제 시 관계도 삭제.
    from_mis_id: Mapped[str] = mapped_column(
        sa.String(32),
        sa.ForeignKey("misconception_catalog.mis_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # 닫힌 2종 어휘(caused_by/variant_of) — schema Literal·to_schema 재검증이 강제(DB는 값만 담음).
    relation_type: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    # 피유발/변형형 대상(to). CASCADE — to 쪽 M-id 삭제 시 관계도 삭제.
    to_mis_id: Mapped[str] = mapped_column(
        sa.String(32),
        sa.ForeignKey("misconception_catalog.mis_id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        # 정방향(from) 조회는 PK 선두 컬럼이라 이미 인덱싱됨 — 역방향(to) 조회만 별도 인덱스
        # 필요(crosslink의 양방향 인덱스 선례와 동형).
        sa.Index("idx_misconception_relation_to", "to_mis_id"),
    )

    # ── 변환 헬퍼 (schema↔db seam, misconception_crosslink.py 패턴) ──────────
    @classmethod
    def from_schema(cls, schema: SchemaMisconceptionRelation) -> MisconceptionRelation:
        """검증된 `schema.MisconceptionRelation` → 영속 ORM(mapper 컬럼키 필터).

        복합 PK뿐이라(서로게이트 PK 없음) schema 필드와 ORM 컬럼키가 그대로 일치한다.
        """
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaMisconceptionRelation:
        """영속 ORM → `schema.MisconceptionRelation`(Pydantic 검증 복원 — relation_type 재검증)."""
        schema_fields = set(SchemaMisconceptionRelation.model_fields)
        data = {name: getattr(self, name) for name in schema_fields}
        return SchemaMisconceptionRelation.model_validate(data)


__all__ = ["MisconceptionRelation"]
