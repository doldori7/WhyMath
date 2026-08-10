"""L5 시각화 오케스트레이션 서비스 — 진단(L2) → Concept 로드(L1) → 명세 생성(L3). 슬라이스 95.

7계층: L5(api)만 DB 세션을 보유하고 하위 계층을 *조합*한다(L2→L3 역의존 회피 — L5가 중간
다리, `00_overview.md` 경계 원칙·`api/me._compute_concept_diagnosis` 선례). 이 서비스는 진단된
개념(`ConceptDiagnosis`)으로 Concept(L1)를 로드하고, 숙달도를 수준 라벨(L4 `mastery_to_level`)로
바꿔 `visualization_spec_for_concept`(L3·슬94)에 위임한다 — Concept의 `recommended_visual_styles`
(슬88)가 프롬프트 힌트로 자동 반영된다.

범위(슬라이스 95): 단일 진단 → 시각화 서비스 함수(약점 선택은 `compute_concept_diagnoses`가
weakest-first 정렬 → 호출자가 [0]을 넘김). HTTP 엔드포인트 + provider/cache/trace의 FastAPI DI
배선은 후속(L5 프런트 착수 시).

PED-16(2026-08-10): `api/scene.py`와의 서빙 오케스트레이션 미러(~40행 — 개념 로드→Overlay 조회→
숙달도 라벨화→생성용 RoutingRequest 조립)는 공유 헬퍼(`api/_concept_orchestration.py`)로 해소했다.
`/v1/visualizations/*` 3라우트(본 파일의 `/weak-concept`·`/spec` POST·GET)의 by-design 미배선
상태(클라 호출자 0으로 이미 등재된 *별개 축*의 기존 결정)는 이 리팩터로 바뀌지 않는다 — 라우트
삭제도 신규 클라 배선도 하지 않았다(회귀 확인: 엔드포인트 시그니처·경로·응답 모델 무변경).
"""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._concept_orchestration import (
    STUDENT_ESCALATION_DEFAULTS as _STUDENT_ESCALATION_DEFAULTS,
)
from whymath_backend.api._concept_orchestration import (
    generate_routing_request,
    load_concept_with_overlays,
    mastery_level_for_diagnosis,
)
from whymath_backend.api._l3_state import get_cache, get_provider, get_trace
from whymath_backend.api._rate_limit import RateLimitedVisualization
from whymath_backend.db.session import get_session
from whymath_backend.l2.concept_diagnosis import (
    ConceptDiagnosis,
    compute_concept_diagnoses,
)
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.visualization import (
    InvalidVisualizationSpecError,
    visualization_spec_for_concept,
)
from whymath_backend.l4.visualization_policy import is_visualizable
from whymath_backend.schema.enums import VisualizationType
from whymath_backend.schema.visualization import Visualization, VisualizationShareLink


async def visualize_for_concept_diagnosis(
    diagnosis: ConceptDiagnosis,
    session: AsyncSession,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    student_subscription: str = _STUDENT_ESCALATION_DEFAULTS.student_subscription,
) -> Visualization | None:
    """진단된 개념 → Concept 로드 → 맞춤 시각화 명세 생성. Concept 미존재면 None.

    L5 오케스트레이션: `diagnosis.concept_id`로 Concept(L1)를 로드하고, 숙달도(bkt_mastery,
    없으면 irt_mastery_proxy)를 `mastery_to_level`(L4)로 수준 라벨화해
    `visualization_spec_for_concept`(L3)에 위임한다. Concept의 `recommended_visual_styles`
    (슬88)가 프롬프트 힌트로 자동 반영된다. 호출자는 `compute_concept_diagnoses`(weakest-first)로
    약점 개념을 골라 넘긴다.

    검증 실패(`InvalidVisualizationSpecError`)는 *전파*된다(관측이 아닌 산출물·슬93과 동일).
    None을 돌려주는 두 경우(시각화 스킵·예외 아님): ① Concept가 DB에 없음(orphan id) ② 개념의
    시각화 가능성 4분류가 *추상·불가*라 자동 시각화를 보류(플레이북 Part 5 게이트·05b) — 억지
    그림 대신 다른 접근이 교수학적으로 옳다(CLAUDE.md 교수학 정확성).

    Args:
        diagnosis: 개념 진단(`compute_concept_diagnoses`의 원소·약점 먼저 정렬됨).
        session: DB 세션(Concept 로드용·L5가 보유).
        provider/cache/trace: L3 `pipeline.generate` DI(라우터 경유·캐시·관측).
        student_subscription: 클라우드 승급 가드용 구독 등급(기본값은
            `escalation_defaults.default_student_escalation_signals()` 단일 좌석, 오늘은 free).

    Returns:
        검증된 `Visualization`, Concept 미존재 또는 시각화 보류(추상·불가) 시 None.
    """
    # 공유 오케스트레이션 헬퍼(PED-16④, `api/_concept_orchestration.py`) — Concept 로드 + 권장
    # 시각화 양식(슬88)·시각화 가능성(Part 5) Overlay 조회를 `scene.py`와 함께 쓴다.
    ctx = await load_concept_with_overlays(session, diagnosis.concept_id)
    if ctx.concept_orm is None:
        return None
    concept_schema = ctx.concept_orm.to_schema().model_copy(
        update={"recommended_visual_styles": ctx.recommended_visual_styles}
    )
    # 시각화 가능성 게이트(Part 5·05b) — 추상·불가 개념은 억지 시각화를 하지 않는다
    # (`visualization.py` 전용 — `scene.py`는 이 게이트를 두지 않는다).
    if not is_visualizable(ctx.visualizability):
        return None
    _mastery, level = mastery_level_for_diagnosis(diagnosis)
    req = generate_routing_request(student_subscription)
    return await visualization_spec_for_concept(
        concept_schema,
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
        # None = 개념 데이터 부재(orphan) 또는 시각화 가능성이 추상·불가라 자동 시각화 보류
        # (플레이북 Part 5 게이트·05b) — 둘 다 "시각화 산출물 없음"이라 404로 정직히 반환한다.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이 개념은 시각화 대상이 아니거나(추상·불가) 개념 데이터가 없습니다.",
        )
    return viz


# ──────────────────────────────────────────────────────────────────────────
# HTTP 엔드포인트 (L5) — Graph2dSpec 명세 라운드트립 (slice 96-B)
# ──────────────────────────────────────────────────────────────────────────
# 코어가 spec을 *중앙 검증*하고, 클라(웹·Flutter)가 이미 쓰는 ?spec=<base64(JSON)> 공유 파라미터를
# 생성/파싱한다(표현≠의미·슬89). LLM 호출 0(순수 검증/인코딩)이라 레이트리미터는 적용하지 않는다.


def _encode_spec(spec: dict[str, Any]) -> str:
    """spec dict → 표준 base64(compact JSON). 웹 atob·Flutter encodeGraph2dSpecParam 호환."""
    return base64.b64encode(
        json.dumps(spec, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode()


def _decode_spec(param: str) -> dict[str, Any]:
    """base64(JSON) → spec dict. 잘못된 base64·JSON·비-객체는 ValueError(호출부 422 매핑)."""
    raw = base64.b64decode(param, validate=True)  # binascii.Error(⊂ValueError)
    data = json.loads(raw)  # JSONDecodeError(⊂ValueError)
    if not isinstance(data, dict):
        raise ValueError("spec은 JSON 객체여야 합니다.")
    return data


@router.post(
    "/spec",
    response_model=VisualizationShareLink,
    summary="시각화 명세 검증 + 공유 링크 파라미터 생성 (Graph2dSpec 라운드트립)",
)
async def post_visualization_spec(
    user: ConsentedUser, visualization: Visualization
) -> VisualizationShareLink:
    """`Visualization`을 코어 계약으로 검증하고 웹 계산기용 `?spec=` 공유 파라미터를 생성한다.

    body의 `spec`은 `Visualization._validate_typed_spec`로 type별 자동 검증되어 위반 시 422다.
    `spec_param`은 표준 base64(JSON(spec))로 웹 계산기(`?spec=`)·Flutter가 그대로 소비한다.
    (웹 계산기는 interactive_graph_2d만 렌더 — 다른 type도 검증·인코딩은 동일하게 지원.)
    """
    spec_param = _encode_spec(visualization.spec)
    return VisualizationShareLink(
        visualization=visualization,
        spec_param=spec_param,
        share_query=f"?spec={spec_param}",
    )


@router.get(
    "/spec",
    response_model=Visualization,
    summary="공유 파라미터(?spec=base64) → 검증된 시각화 명세로 디코드",
)
async def get_visualization_spec(
    user: ConsentedUser,
    spec: Annotated[str, Query(description="base64(JSON(Graph2dSpec)) — 웹 ?spec= 파라미터")],
) -> Visualization:
    """`?spec=<base64>`를 디코드·검증해 정본 `Visualization`(interactive_graph_2d)을 돌려준다.

    웹 `?spec=`는 Graph2dSpec dict만 싣는 정방향 어댑터 규약과 대칭이므로 type을 2d로 가정한다.
    base64/JSON 파손·spec 검증 위반은 422다.
    """
    try:
        spec_dict = _decode_spec(spec)
        return Visualization(type=VisualizationType.interactive_graph_2d, spec=spec_dict)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"올바른 Graph2dSpec 명세가 아닙니다: {exc}",
        ) from exc
