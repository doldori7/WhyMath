"""권장 시각화 양식 Overlay — 개념 code → 권장 시각화 양식 배열 (슬라이스 88·ARCH-14 ③).

개념의 *권장 시각화 양식*(단위원·수형도·수직선 등 — 개념을 가장 잘 드러내는 교수학적 표현
형식)은 개념 정체성이 아니라 **시각화 계층**의 투영 정보다 — ADR
`docs/architecture/concept_node_layering_decision.md` §1("visualization 계층 = 노드 비내장")·
`CurriculumEntry` Overlay 선례(rev f3a4b5c6d7e8이 `subject`를 노드에서 제거)·
`concept_visualization`(시각화 *가능성*) Overlay 선례를 따른다. 과거엔
`concept.recommended_visual_styles` 컬럼(슬88)으로 노드에 내장했으나 ARCH-14 ③(Concept Purity
마지막 부채 청산)로 이 Overlay 테이블로 외부화한다 — 노드는 순수 개념 의미만 남긴다.

키·조인: **PK = `code`**(backend `concept.code`·`concept_content.code`·`concept_visualization.code`
와 동일 키 공간). **FK는 두지 않는다**(loose ref·`concept_visualization` 선례) — 적재 순서·재적재
독립성. 한 행의 *존재*가 "양식 태깅됨"을 뜻하고, 행이 없으면 미태깅(리졸버가 `[]` 반환)이다.

`concept_visualization`(시각화 *가능성* 4분류 — 그려야 하는가·어느 인지 수준까지)과는 **다른 축**
이다: 이 Overlay는 양식(*무엇을* 그릴 것인가 — 단위원·수형도·수직선 등)을 담는다. 두 축은 별도
테이블로 분리한다(같은 축이 아니므로 한 테이블에 얹지 않음).

7계층: L1 데이터 기반의 *영속 Overlay*. 보관·조회 백킹이며 시각화 힌트 소비는 L3/L4가 한다
(역방향 의존 없음). native ENUM `visualization_style_enum`은 슬88 마이그레이션 `b5c6d7e8f9a0`이
*이미 소유*하므로 본 테이블은 그 타입을 **재사용**한다(중복 CREATE TYPE 금지·`_pg_enum`은
마이그레이션에서 create_type=False로 참조).
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum
from whymath_backend.schema.enums import VisualizationStyle


class ConceptVisualStyle(Base):
    """권장 시각화 양식 Overlay — code 키 개념의 권장 시각화 양식 배열(슬88 통제 어휘).

    한 행 = 한 개념의 권장 양식 태깅. PK(`code`)로 멱등 upsert(`ON CONFLICT(code) DO UPDATE`).
    `recommended_styles`는 NOT NULL — 행이 존재하면 양식 태깅이 확정된 것이고, 미태깅 개념은
    *행 부재*로 표현한다(별도 nullable 값 불요·리졸버가 `[]`로 폴백). `concept_visualization`
    (시각화 *가능성*·그려야 하는가)과는 **다른 축**(양식='무엇을' 그릴 것인가).
    """

    __tablename__ = "concept_visual_style"

    # PK = 개념 code(concept.code·concept_visualization.code와 동일 키 공간·loose ref·FK 없음).
    code: Mapped[str] = mapped_column(primary_key=True)
    # 권장 시각화 양식 배열(단위원·수형도 등). NOT NULL — 행 존재=태깅됨(미태깅은 행 부재).
    # native ENUM `visualization_style_enum`은 슬88 마이그레이션(b5c6d7e8f9a0)이 소유 — 재사용한다
    # (`_pg_enum`은 마이그레이션에서 create_type=False로 참조·중복 생성 금지).
    recommended_styles: Mapped[list[VisualizationStyle]] = mapped_column(
        ARRAY(_pg_enum(VisualizationStyle, "visualization_style_enum")),
        nullable=False,
    )
