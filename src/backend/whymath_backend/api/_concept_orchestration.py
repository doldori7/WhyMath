"""`api/scene.py`↔`api/visualization.py` 공유 오케스트레이션 헬퍼 — 서빙 미러 해소(PED-16④).

두 파일이 "개념 로드(L1)→시각화 가능성/권장 스타일 Overlay 조회(L1)→숙달도 라벨화(L4)→생성용
RoutingRequest(L3) 조립" ~40행을 그대로 미러하고 있었다(각 파일 docstring이 스스로 "미러"라
불렀다 — `dsl_integration_gap_review.md` §2-①). 이 모듈로 그 공통분만 뽑아 두 사본이 조용히
갈라지는 위험을 원천 소멸시킨다.

**공유하지 않는 것**(과잉 추상화 회피 — 두 파일이 실제로 100% 동일하게 수행하는 부분만 뽑는다):
  - `behavior_areas`(행동영역) 조회·WH-1 활성 가설 오개념 프로브 — `scene.py` 전용.
  - `is_visualizable` 게이트(추상·불가 개념은 시각화 스킵) — `visualization.py` 전용.
  - 각 엔드포인트의 HTTP 에러 매핑(404/422/503) — 라우터 계층 관심사라 각 파일에 남긴다.

`/v1/visualizations/*` 3라우트의 by-design 미배선 상태(클라 호출자 0으로 이미 등재된 별개 축의
기존 결정)는 이 리팩터로 바뀌지 않는다 — 오케스트레이션 중복 제거와 라우트 배선 상태는 서로
독립이다(회귀 확인: 두 파일의 기존 라우터 등록·엔드포인트 시그니처 무변경).

7계층: L5(api) 내부 헬퍼 — 두 호출자와 동일하게 L1(Concept·Overlay)·L3(RoutingRequest)·L4
(`mastery_to_level`)를 *조합*만 한다(L5가 하위 계층을 조합하는 기존 경계 원칙 그대로 — L4/L5
역의존은 만들지 않는다).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept import Concept
from whymath_backend.l1.concept_visual_style import get_recommended_visual_styles
from whymath_backend.l1.concept_visualization import get_visualizability
from whymath_backend.l2.concept_diagnosis import ConceptDiagnosis
from whymath_backend.l3.data_grade_defaults import SELF_AUTHORED_CORPUS
from whymath_backend.l3.escalation_defaults import default_student_escalation_signals
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l4.lthc import mastery_to_level
from whymath_backend.schema.enums import VisualizationStyle

# 학생 요청 라우팅 신호 기본값 — 6개 호출부 공용 단일 좌석(OPS-18). scene.py·visualization.py가
# 이제 이 모듈 하나에서 가져온다(이전엔 두 파일이 각자 `default_student_escalation_signals()`를
# 호출해 동일 인스턴스를 별도로 만들었다 — 값 자체는 불변이라 회귀는 없었으나 좌석을 하나로 모은다).
STUDENT_ESCALATION_DEFAULTS = default_student_escalation_signals()


@dataclass(frozen=True, slots=True)
class ConceptOverlayContext:
    """Concept(L1) + Overlay(시각화 가능성·권장 스타일) 로드 결과.

    `concept_orm=None`이면 orphan id(DB에 Concept 없음) — 호출자가 즉시 None/404로 처리한다
    (예외 아님·두 파일의 기존 동작과 동일).
    """

    concept_orm: Concept | None
    visualizability: Any = None
    recommended_visual_styles: list[VisualizationStyle] | None = None


async def load_concept_with_overlays(
    session: AsyncSession, concept_id: Any
) -> ConceptOverlayContext:
    """Concept(L1) 로드 + 시각화 가능성·권장 시각화 양식 Overlay(L1) 조회.

    권장 시각화 양식(슬88)·시각화 가능성 4분류(Part 5)는 ARCH-14 ③으로 *노드 비내장* —
    전용 Overlay(`concept_visual_style`·`concept_visualization`)에서 code 키로 조회한다(행
    부재→각각 빈 목록/미태깅값·기존 동작 그대로).
    """
    concept_orm = await session.get(Concept, concept_id)
    if concept_orm is None:
        return ConceptOverlayContext(concept_orm=None)
    visualizability = await get_visualizability(session, concept_orm.code)
    styles = await get_recommended_visual_styles(session, concept_orm.code)
    return ConceptOverlayContext(
        concept_orm=concept_orm,
        visualizability=visualizability,
        recommended_visual_styles=styles,
    )


def mastery_level_for_diagnosis(diagnosis: ConceptDiagnosis) -> tuple[float | None, str]:
    """진단의 숙달도(bkt_mastery 우선·없으면 irt_mastery_proxy)를 L4 수준 라벨로 변환.

    두 값 다 없으면(신규 학생 등) 정직한 기본 라벨 "초보"를 쓴다(두 파일의 기존 동작 그대로).
    """
    mastery = (
        diagnosis.bkt_mastery if diagnosis.bkt_mastery is not None else diagnosis.irt_mastery_proxy
    )
    level = mastery_to_level(mastery) if mastery is not None else "초보"
    return mastery, level


def generate_routing_request(student_subscription: str) -> RoutingRequest:
    """L3 생성용 RoutingRequest 조립 — scene/visualization 공용 생성 프로필.

    `sync=True` 강제 — 두 생성기(`generate_learning_scene`·`visualization_spec_for_concept`) 모두
    parse 게이트가 텍스트를 *즉시* 필요로 하므로 QUALITY 비동기(빈 text·job_id)로 가면 안 된다.
    """
    return RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription=student_subscription,
        budget_krw=STUDENT_ESCALATION_DEFAULTS.budget_krw,  # 단일 좌석 값(OPS-18·회귀 0)
        sync=True,
        # 등급: 생성 프롬프트에 실리는 자료는 L1 Concept(자체 개념 그래프)과 숙달도 *라벨*
        # 뿐이다 — 학생 원문·제3자 저작물 없음. 자체 저작이라 반출 가능(EOS-59).
        data_licenses=SELF_AUTHORED_CORPUS,
    )


__all__ = [
    "STUDENT_ESCALATION_DEFAULTS",
    "ConceptOverlayContext",
    "generate_routing_request",
    "load_concept_with_overlays",
    "mastery_level_for_diagnosis",
]
