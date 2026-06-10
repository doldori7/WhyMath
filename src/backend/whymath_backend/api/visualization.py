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

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept import Concept
from whymath_backend.l2.concept_diagnosis import ConceptDiagnosis
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.visualization import visualization_spec_for_concept
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
    )
    return await visualization_spec_for_concept(
        concept_orm.to_schema(),
        level,
        req,
        provider=provider,
        cache=cache,
        trace=trace,
    )
