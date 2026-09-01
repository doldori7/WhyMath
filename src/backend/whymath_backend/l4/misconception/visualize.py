"""오개념 진단 → 맞춤 교정 시각화 명세 (L4→L3 배선). 슬라이스 93.

L4는 *무엇을·언제* 시각화할지 결정하고, 실제 생성·검증은 L3 `generate_visualization_spec`
(라우터 경유·검증 게이트)에 위임한다 — 7계층 L4→L3 정방향(`step_shadow`가 동일하게 L3를
직접 호출하는 선례).

게이트(임계 일관): `select_intervention`이 *개입을 확정*(반례·거꾸로 사고)한 경우에만
시각화를 만든다 — 진단 보류(confidence<0.5·None)면 시각화도 만들지 않는다(intervene
결정트리와 *동일 임계*·라벨링/과개입 회피). 생성된 시각화는 소크라테스 발화를 *대체하지
않고 보완*한다(직접 교정 금지 원칙 유지).

메모: `InterventionPattern.VISUALIZATION`(패턴3) enum은 존재하나 `select_intervention`
결정트리는 신뢰도로 반례/거꾸로/보류만 고르므로 *패턴 게이트는 무효* — 대신 '확정 진단 시
보완 시각화' 게이트를 쓴다. (패턴3 편입은 pedagogy-designer 후속.)
"""

from __future__ import annotations

from whymath_backend.l3.data_grade_defaults import SELF_AUTHORED_CORPUS
from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.visualization import generate_visualization_spec
from whymath_backend.l4.misconception.intervene import select_intervention
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.schema.visualization import Visualization


def _concept_for_misconception(m: Misconception) -> str:
    """오개념 → 교정 시각화용 개념 문자열(L3 프롬프트 입력).

    학생이 잘못 가정한 `canonical_statement`를 명시해, 그 가정이 왜 틀리는지 드러내는
    *교정* 시각화를 L3가 만들도록 안내한다(예: '(a+b)²=a²+b²' → 넓이 모델로 교차항 노출).
    """
    return (
        f"{m.domain} 영역의 오개념 '{m.name_kr}' 교정 — "
        f"학생이 '{m.canonical_statement}'를 항상 참이라 잘못 가정한다. "
        "이 가정이 왜 틀리는지 드러내는 시각화."
    )


async def visualize_misconception(
    match: MisconceptionMatch,
    level: str,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    student_subscription: str = "free",
) -> Visualization | None:
    """진단된 오개념에 *맞춤 교정 시각화 명세*를 생성(L3 위임). 진단 보류면 None.

    `select_intervention`이 개입을 확정(보류 아님)한 경우에만 시각화를 만든다 — intervene
    결정트리와 동일 임계로 일관(confidence<0.5는 시각화도 보류). 생성·검증은 L3
    `generate_visualization_spec`에 위임하며, 검증 실패(`InvalidVisualizationSpecError`)는
    *전파*된다 — 이 시각화는 관측이 아니라 산출물이므로 삼키지 않는다(호출자는 실패 시
    소크라테스 발화만으로 진행할 수 있다·step_shadow의 fire-and-forget과 대비).

    Args:
        match: 오개념 진단 결과(`diagnose`의 원소).
        level: 학생 수준 문자열(예: "고1"·"초보") — 호출자(L5)가 UserProfile·숙련도에서 구성.
        provider/cache/trace: L3 `pipeline.generate` DI(라우터 경유·캐시·관측).
        student_subscription: 클라우드 승급 가드용 구독 등급(기본 free).

    Returns:
        확정 진단이면 검증된 `Visualization`, 보류면 None.
    """
    if select_intervention(match) is None:
        return None  # 진단 보류 → 시각화도 보류(임계 일관·과개입 회피)
    req = RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription=student_subscription,
        # 등급: 프롬프트에 실리는 것은 오개념 카탈로그의 개념 라벨과 학생 *수준 라벨*
        # ("고1"·"초보")뿐이다 — 학생 원문·풀이는 넘기지 않는다(`visualize`는 match와
        # level만 받는다). 자체 저작이라 반출 가능(EOS-59).
        data_licenses=SELF_AUTHORED_CORPUS,
    )
    return await generate_visualization_spec(
        _concept_for_misconception(match.misconception),
        level,
        req,
        provider=provider,
        cache=cache,
        trace=trace,
    )
