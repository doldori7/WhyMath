"""시각화 가능성 Overlay — 개념 code → 시각화 4분류(직접/동적/추상/불가) 매핑 (플레이북 Part 5).

개념의 *시각화 가능성*(그려야 하는가·어느 인지 수준까지)은 개념 정체성이 아니라 **시각화 계층**의
판별 정보다 — ADR `docs/architecture/concept_node_layering_decision.md` §1("visualization 계층 =
노드 비내장")·`CurriculumEntry` Overlay 선례(rev f3a4b5c6d7e8이 `subject`를 노드에서 제거)를
따른다. 노드에 내장하지 않고 이 Overlay가 단일 진실이 되며, L4 시각화 게이트
(`l4/visualization_policy.py`·`scene_generation.py`)가 이 값을 조회해 추상·불가 개념의 억지
시각화를 막는다.

키·조인: **PK = `code`**(backend `concept.code`·`concept_content.code` 선례와 동일 키 공간). **FK는
두지 않는다**(loose ref·`concept_content` 선례) — 적재 순서·재적재 독립성. 한 행의 *존재*가
"분류됨"을 뜻하고, 행이 없으면 미태깅(기존 시각화 동작 유지·하위호환)이다.

7계층: L1 데이터 기반의 *영속 Overlay*. 보관·조회 백킹이며 시각화 판별 정책은 L4가 소비한다
(역방향 의존 없음). native ENUM `visualizability_enum`은 본 테이블 마이그레이션이 소유한다.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.db.models._orm_enum import _pg_enum
from whymath_backend.schema.enums import Visualizability


class ConceptVisualization(Base):
    """시각화 가능성 Overlay — code 키 개념의 시각화 4분류(직접/동적/추상/불가).

    한 행 = 한 개념의 시각화 가능성 판별. PK(`code`)로 멱등 upsert(`ON CONFLICT(code) DO UPDATE`).
    `visualizability`는 NOT NULL — 행이 존재하면 분류가 확정된 것이고, 미분류 개념은 *행 부재*로
    표현한다(별도 nullable 값 불요). recommended_visual_styles(양식)·VisualizationType(렌더
    기술)과는 **다른 축**(그려야 하는가·어느 인지 수준까지).
    """

    __tablename__ = "concept_visualization"

    # PK = 개념 code(backend concept.code·concept_content.code와 동일 키 공간·loose ref·FK 없음).
    code: Mapped[str] = mapped_column(primary_key=True)
    # 시각화 4분류(직접/동적/추상/불가). NOT NULL — 행 존재=분류됨(미분류는 행 부재).
    # native ENUM `visualizability_enum`은 본 테이블 마이그레이션이 소유(생성·drop).
    visualizability: Mapped[Visualizability] = mapped_column(
        _pg_enum(Visualizability, "visualizability_enum"),
        nullable=False,
    )
