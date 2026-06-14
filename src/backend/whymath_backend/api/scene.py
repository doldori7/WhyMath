"""L5 학습 장면 오케스트레이션 서비스 — 진단(L2) → Concept 로드(L1) → 장면 생성(L4). S5a.

7계층: L5(api)만 DB 세션을 보유하고 하위 계층을 *조합*한다(`api/visualization.py` 선례·역의존
회피). 진단된 개념(`ConceptDiagnosis`)으로 Concept(L1)를 로드하고, 숙달도를 수준 라벨(L4
`mastery_to_level`)로 바꿔 `generate_learning_scene`(L4·S3)에 위임한다 — Concept의
`recommended_visual_styles`·`cognitive_type`가 결정론 골격에 반영된다.

범위(S5a): 단일 진단 → 학습 장면 서비스 + HTTP 엔드포인트(약점 선택은 `compute_concept_diagnoses`가
weakest-first 정렬 → 호출자가 [0]을 넘김). ★`learner_context.active_hypothesis_ids`는 빈 목록 —
WH-1 가설 store 조회 기반 오개념 프로브 적응은 후속이라 여기선 프로브가 생성되지 않는다(정직한
경계). 레이트리밋은 visualization 버킷 재사용(장면 생성 = 내부 시각화 spec LLM 1회).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._l3_state import get_cache, get_provider, get_trace
from whymath_backend.api._rate_limit import RateLimitedVisualization
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.session import get_session
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
from whymath_backend.l4.scene_generation import generate_learning_scene


async def scene_for_concept_diagnosis(
    diagnosis: ConceptDiagnosis,
    session: AsyncSession,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    student_subscription: str = "free",
) -> LearningScene | None:
    """진단된 개념 → Concept 로드 → 맞춤 학습 장면 생성. Concept 미존재면 None.

    L5 오케스트레이션(`visualize_for_concept_diagnosis` 미러): concept_id로 Concept(L1)를
    로드하고, 숙달도(bkt_mastery, 없으면 irt_mastery_proxy)를 `mastery_to_level`(L4)로 수준 라벨화해
    `generate_learning_scene`(L4)에 위임한다. 생성기가 시각화 spec을 라우터 경유로 채운다.

    검증 실패(`InvalidVisualizationSpecError`)는 *전파*된다(생성기→호출자·슬93 동일). Concept가 DB에
    없으면(orphan id) None을 돌려준다(장면 스킵·예외 아님).

    ★`learner_context`는 진단 스냅샷(mastery·theta)만 담는다 — `active_hypothesis_ids`는 빈 목록
    (WH-1 가설 store 조회 기반 오개념 프로브 적응은 후속·여기선 프로브 미생성).

    Args:
        diagnosis: 개념 진단(`compute_concept_diagnoses`의 원소·약점 먼저 정렬됨).
        session: DB 세션(Concept 로드용·L5가 보유).
        provider/cache/trace: L3 `pipeline.generate` DI(라우터 경유 생성·캐시·관측).
        student_subscription: 클라우드 승급 가드용 구독 등급(기본 free).

    Returns:
        검증된 `LearningScene`, Concept 미존재면 None.
    """
    concept_orm = await session.get(Concept, diagnosis.concept_id)
    if concept_orm is None:
        return None
    mastery = (
        diagnosis.bkt_mastery if diagnosis.bkt_mastery is not None else diagnosis.irt_mastery_proxy
    )
    level = mastery_to_level(mastery) if mastery is not None else "초보"
    learner_context = SceneLearnerContext(
        mastery_level=mastery,
        theta=diagnosis.irt_theta,
        active_hypothesis_ids=[],
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
    (Concept 로드·수준 라벨·장면 생성·라우터 경유). provider/cache/trace는 app.state에서
    꺼낸다. 에러: 진단 없음/Concept 없음=404·장면 검증 실패=422·LLM 큐 불가=503. 레이트리밋은
    visualization 버킷 재사용(장면 생성 = 내부 시각화 spec LLM 1회).
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
