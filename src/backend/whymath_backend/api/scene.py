"""L5 학습 장면 오케스트레이션 서비스 — 진단(L2) → Concept 로드(L1) → 장면 생성(L4). S5a.

7계층: L5(api)만 DB 세션을 보유하고 하위 계층을 *조합*한다(`api/visualization.py` 선례·역의존
회피). 진단된 개념(`ConceptDiagnosis`)으로 Concept(L1)를 로드하고, 숙달도를 수준 라벨(L4
`mastery_to_level`)로 바꿔 `generate_learning_scene`(L4·S3)에 위임한다 — Concept의
`recommended_visual_styles`·`cognitive_type`가 결정론 골격에 반영된다.

범위(S5a): 단일 진단 → 학습 장면 서비스 + HTTP 엔드포인트(약점 선택은 `compute_concept_diagnoses`가
weakest-first 정렬 → 호출자가 [0]을 넘김). `learner_context.active_hypothesis_ids`는 WH-1 가설
store(`get_active_hypotheses`)에서 학생의 *활성 오개념 가설*을 조회해 채운다 — `scene_generation`이
이를 ∩ 카탈로그로 *적응형 오개념 프로브*로 만든다(RS2 거짓 낙인 차단·근거 있는 가설만). 가설이
없으면(신규 학생 등) 빈 목록이라 프로브 0(정직한 경계 유지). 레이트리밋은 visualization 버킷
재사용(장면 생성 = 내부 시각화 spec LLM 1회).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._l3_state import get_cache, get_provider, get_trace
from whymath_backend.api._rate_limit import RateLimitedVisualization
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.session import get_session
from whymath_backend.l1.concept_visualization import get_visualizability
from whymath_backend.l2.concept_diagnosis import (
    ConceptDiagnosis,
    compute_concept_diagnoses,
)
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.l4.learning_scene import LearningScene, SceneLearnerContext
from whymath_backend.l4.lthc import mastery_to_level
from whymath_backend.l4.misconception.evidence_store import net_support_by_misconception
from whymath_backend.l4.misconception.hypothesis_store import get_active_hypotheses
from whymath_backend.l4.scene_generation import generate_learning_scene


async def scene_for_concept_diagnosis(
    diagnosis: ConceptDiagnosis,
    session: AsyncSession,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    student_subscription: str = "free",
    student_id: uuid.UUID | None = None,
) -> LearningScene | None:
    """진단된 개념 → Concept 로드 → 맞춤 학습 장면 생성. Concept 미존재면 None.

    L5 오케스트레이션(`visualize_for_concept_diagnosis` 미러): concept_id로 Concept(L1)를
    로드하고, 숙달도(bkt_mastery, 없으면 irt_mastery_proxy)를 `mastery_to_level`(L4)로 수준 라벨화해
    `generate_learning_scene`(L4)에 위임한다. 생성기가 시각화 spec을 라우터 경유로 채운다.

    검증 실패(`InvalidVisualizationSpecError`)는 *전파*된다(생성기→호출자·슬93 동일). Concept가 DB에
    없으면(orphan id) None을 돌려준다(장면 스킵·예외 아님).

    **오개념 프로브 적응**: `student_id`가 주어지면 WH-1 가설 store(`get_active_hypotheses`·L4)에서
    그 학생의 *활성 오개념 가설*을 조회해 id와 *누적 신뢰도 맵*을 넘긴다 — `scene_generation`이
    이를 ∩ 카탈로그로 *적응형 프로브*로 만들고, 신뢰도로 개입 패턴을 다양화한다(doc 결정트리·>0.8
    반례·≥0.5 거꾸로·<0.5 보류). 근거 있는 가설만(RS2 거짓 낙인 차단). `student_id`가 None이면
    (익명·맥락 없음) 조회 생략·빈 목록(프로브 0·기존 동작).

    **렌더 시점 증거 재확인**(evidence_links 연동): `net_support_by_misconception`으로 학생의
    증거 그래프를 단일 쿼리 집계해, 순지지도가 *음수*(반박 우세)인 활성 가설은 프로브에서 *제외*한다
    — `curate_hypothesis`가 턴 시점에 쓰는 net_support<0 archived 규약과 동형이되, 직전 턴 이후
    누적된 신규 증거까지 렌더 시점에 반영해 *반박된 오개념을 학생에게 들이밀지 않는다*(낙인 회피).
    증거 없는 가설(키 부재→0.0)은 유지(과도 억제 회피).

    Args:
        diagnosis: 개념 진단(`compute_concept_diagnoses`의 원소·약점 먼저 정렬됨).
        session: DB 세션(Concept 로드·가설 store 조회용·L5가 보유).
        provider/cache/trace: L3 `pipeline.generate` DI(라우터 경유 생성·캐시·관측).
        student_subscription: 클라우드 승급 가드용 구독 등급(기본 free).
        student_id: 가설 store 조회용 학생 id(None이면 프로브 적응 생략).

    Returns:
        검증된 `LearningScene`, Concept 미존재면 None.
    """
    concept_orm = await session.get(Concept, diagnosis.concept_id)
    if concept_orm is None:
        return None
    # 시각화 가능성 4분류(Part 5)를 시각화 계층 Overlay에서 조회(노드 비내장·ADR 계층분리).
    visualizability = await get_visualizability(session, concept_orm.code)
    mastery = (
        diagnosis.bkt_mastery if diagnosis.bkt_mastery is not None else diagnosis.irt_mastery_proxy
    )
    level = mastery_to_level(mastery) if mastery is not None else "초보"
    # WH-1 활성 가설 → 적응형 오개념 프로브(student_id 있을 때만 조회·근거 있는 가설만).
    # 신뢰도 맵도 함께 넘겨 개입 패턴을 가설별로 다양화한다(scene_generation 결정트리).
    # 렌더 시점 *증거 재확인*: evidence_links 순지지도가 음수(반박 우세)인 가설은 프로브를
    # 억제한다(RS2 거짓 낙인 차단·curate net_support<0 archived 규약 동형·턴 후 신규 증거 반영).
    active_hypothesis_ids: list[str] = []
    active_hypothesis_confidences: dict[str, float] | None = None
    if student_id is not None:
        hypotheses = await get_active_hypotheses(session, student_id)
        net_support_map = await net_support_by_misconception(session, student_id)
        corroborated = [
            h for h in hypotheses if net_support_map.get(h.misconception_id, 0.0) >= 0.0
        ]
        active_hypothesis_ids = [h.misconception_id for h in corroborated]
        active_hypothesis_confidences = {h.misconception_id: h.confidence for h in corroborated}
    learner_context = SceneLearnerContext(
        mastery_level=mastery,
        theta=diagnosis.irt_theta,
        active_hypothesis_ids=active_hypothesis_ids,
        active_hypothesis_confidences=active_hypothesis_confidences,
    )
    req = RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription=student_subscription,
        # sync 강제: 생성기의 parse 게이트가 텍스트를 *즉시* 필요로 함(visualization.py 선례).
        sync=True,
    )
    return await generate_learning_scene(
        concept_orm.to_schema(),
        level,
        req,
        provider=provider,
        cache=cache,
        trace=trace,
        learner_context=learner_context,
        visualizability=visualizability,
    )


# ──────────────────────────────────────────────────────────────────────────
# HTTP 엔드포인트 (L5) — 약점 개념 학습 장면 (S5a)
# ──────────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/v1/scenes", tags=["scene"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/weak-concept",
    response_model=LearningScene,
    summary="내 약점 개념 맞춤 학습 장면 생성 (L2 진단 → L4 장면)",
    dependencies=[RateLimitedVisualization],
)
async def post_weak_concept_scene(
    user: ConsentedUser,
    session: SessionDep,
    request: Request,
) -> LearningScene:
    """인증 학생의 *가장 약한 개념*을 진단(L2)해 맞춤 학습 장면(L4)을 생성한다.

    흐름: `compute_concept_diagnoses`(약점 먼저 정렬) → 최약점 → `scene_for_concept_diagnosis`
    (Concept 로드·수준 라벨·WH-1 활성 가설 조회→적응형 오개념 프로브·장면 생성·라우터 경유).
    provider/cache/trace는 app.state에서 꺼낸다. 에러: 진단 없음/Concept 없음=404·장면 검증
    실패=422·LLM 큐 불가=503. 레이트리밋은 visualization 버킷 재사용(장면 생성 = 내부 시각화
    spec LLM 1회).
    """
    diagnoses = await compute_concept_diagnoses(session, user.user_id)
    if not diagnoses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진단할 개념이 없습니다(채점 이력 부족).",
        )
    try:
        scene = await scene_for_concept_diagnosis(
            diagnoses[0],
            session,
            provider=get_provider(request),
            cache=get_cache(request),
            trace=get_trace(request),
            student_id=user.user_id,
        )
    except InvalidVisualizationSpecError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"학습 장면 생성 실패(검증 미통과): {exc}",
        ) from exc
    except QualityQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="학습 장면 생성 LLM을 현재 사용할 수 없습니다(잠시 후 재시도).",
        ) from exc
    if scene is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="개념 데이터를 찾을 수 없습니다.",
        )
    return scene
