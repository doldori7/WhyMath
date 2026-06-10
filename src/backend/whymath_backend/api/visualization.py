"""L5 시각화 오케스트레이션 서비스 — 진단(L2) → Concept 로드(L1) → 명세 생성(L3). 슬라이스 95.

7계층: L5(api)만 DB 세션을 보유하고 하위 계층을 *조합*한다(L2→L3 역의존 회피 — L5가 중간
다리, `00_overview.md` 경계 원칙·`api/me._compute_concept_diagnosis` 선례). 이 서비스는 진단된
개념(`ConceptDiagnosis`)으로 Concept(L1)를 로드하고, 숙달도를 수준 라벨(L4 `mastery_to_level`)로
바꿔 `visualization_spec_for_concept`(L3·슬94)에 위임한다 — Concept의 `recommended_visual_styles`
(슬88)가 프롬프트 힌트로 자동 반영된다.

범위(슬라이스 95): 단일 진단 → 시각화 서비스 함수(약점 선택은 `compute_concept_diagnoses`가
weakest-first 정렬 → 호출자가 [0]을 넘김). HTTP 엔드포인트 + provider/cache/trace의 FastAPI DI
배선은 후속(L5 프런트 착수 시).
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
from whymath_backend.l3.visualization import (
    InvalidVisualizationSpecError,
    visualization_spec_for_concept,
)
from whymath_backend.l4.lthc import mastery_to_level
from whymath_backend.schema.visualization import Visualization


async def visualize_for_concept_diagnosis(
    diagnosis: ConceptDiagnosis,
    session: AsyncSession,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    student_subscription: str = "free",
) -> Visualization | None:
    """진단된 개념 → Concept 로드 → 맞춤 시각화 명세 생성. Concept 미존재면 None.

    L5 오케스트레이션: `diagnosis.concept_id`로 Concept(L1)를 로드하고, 숙달도(bkt_mastery,
    없으면 irt_mastery_proxy)를 `mastery_to_level`(L4)로 수준 라벨화해
    `visualization_spec_for_concept`(L3)에 위임한다. Concept의 `recommended_visual_styles`
    (슬88)가 프롬프트 힌트로 자동 반영된다. 호출자는 `compute_concept_diagnoses`(weakest-first)로
    약점 개념을 골라 넘긴다.

    검증 실패(`InvalidVisualizationSpecError`)는 *전파*된다(관측이 아닌 산출물·슬93과 동일).
    Concept가 DB에 없으면(orphan id) None을 돌려준다(시각화 스킵·예외 아님).

    Args:
        diagnosis: 개념 진단(`compute_concept_diagnoses`의 원소·약점 먼저 정렬됨).
        session: DB 세션(Concept 로드용·L5가 보유).
        provider/cache/trace: L3 `pipeline.generate` DI(라우터 경유·캐시·관측).
        student_subscription: 클라우드 승급 가드용 구독 등급(기본 free).

    Returns:
        검증된 `Visualization`, Concept 미존재면 None.
    """
    concept_orm = await session.get(Concept, diagnosis.concept_id)
    if concept_orm is None:
        return None
    mastery = (
        diagnosis.bkt_mastery if diagnosis.bkt_mastery is not None else diagnosis.irt_mastery_proxy
    )
    level = mastery_to_level(mastery) if mastery is not None else "초보"
    req = RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription=student_subscription,
        # sync 강제(슬97): parse_visualization_spec 게이트가 텍스트를 *즉시* 필요로 하므로
        # QUALITY 비동기(빈 text·job_id)로 가면 안 된다 — sync=True면 라우터가 async 미선택.
        sync=True,
    )
    return await visualization_spec_for_concept(
        concept_orm.to_schema(),
        level,
        req,
        provider=provider,
        cache=cache,
        trace=trace,
    )


# ──────────────────────────────────────────────────────────────────────────
# HTTP 엔드포인트 (L5) — 약점 개념 시각화 (slice 96)
# ──────────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/v1/visualizations", tags=["visualization"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/weak-concept",
    response_model=Visualization,
    summary="내 약점 개념 맞춤 시각화 생성 (L2 진단 → L3 시각화)",
    dependencies=[RateLimitedVisualization],
)
async def post_weak_concept_visualization(
    user: ConsentedUser,
    session: SessionDep,
    request: Request,
) -> Visualization:
    """인증 학생의 *가장 약한 개념*을 진단(L2)해 맞춤 시각화 명세(L3)를 생성한다.

    흐름: `compute_concept_diagnoses`(약점 먼저 정렬) → 최약점 → `visualize_for_concept_diagnosis`
    (Concept 로드·L4 수준·L3 생성·라우터 경유). provider/cache/trace는 app.state(`_l3_state`)에서
    꺼낸다. 에러: 진단 없음/Concept 없음=404·명세 검증 실패=422·LLM 큐 불가=503.
    """
    diagnoses = await compute_concept_diagnoses(session, user.user_id)
    if not diagnoses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진단할 개념이 없습니다(채점 이력 부족).",
        )
    try:
        viz = await visualize_for_concept_diagnosis(
            diagnoses[0],
            session,
            provider=get_provider(request),
            cache=get_cache(request),
            trace=get_trace(request),
        )
    except InvalidVisualizationSpecError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"시각화 명세 생성 실패(검증 미통과): {exc}",
        ) from exc
    except QualityQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="시각화 생성 LLM을 현재 사용할 수 없습니다(잠시 후 재시도).",
        ) from exc
    if viz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="개념 데이터를 찾을 수 없습니다.",
        )
    return viz
