"""학생 요청 라우팅 신호의 기본값 — 흩어진 리터럴을 단일 좌석으로 통합(OPS-18).

배경(OPS-18 "클라우드 승급 사슬 학생 도달 0"): 학생 대면 호출부 6곳
(`api/visualization.py`·`api/scene.py`·`l4/misconception/judge_seam.py` 2곳·
`l3/cross_verify.py`·`l3/equivalent/{llm_generator,rephrase}.py`)이 각자
`student_subscription="free"`를 파라미터 기본값·인라인 리터럴로 하드코딩해 왔고, `budget_krw`는
어느 곳도 명시하지 않아 `RoutingRequest`의 필드 기본값(0.0)에 암묵적으로 의존했다.
`router.Router._decide_cost_tier`의 규칙1(`budget_krw<=0`)·규칙2(`student_subscription=="free"`)
가 *둘 다* 무조건 충족되므로, 이 여섯 곳을 거치는 어떤 요청도 구조적으로 LOCAL을 벗어날 수
없다 — 라우터가 판단해서가 아니라 호출부에 애초에 다른 값을 실어 보낼 배선이 없어서다.

이 모듈은 *그 하드코딩을 없애지 않는다* — 결제 도입 결정(§5-①, `subscription_tier`/
`budget_krw` DB 읽기) 전까지는 여전히 오늘과 똑같은 값을 반환한다(회귀 0). 다만 여섯 곳이
각자 들고 있던 리터럴을 이 자리 하나로 모아, 실제 배선이 들어올 때 여섯 곳이 아니라
`default_student_escalation_signals()` 내부 하나만 고치면 되게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StudentEscalationDefaults", "default_student_escalation_signals"]


@dataclass(frozen=True, slots=True)
class StudentEscalationDefaults:
    """학생 요청의 현재 기본 라우팅 신호(구독·예산) — `RoutingRequest` 생성 시 주입되는 값.

    두 필드는 `RoutingRequest.student_subscription`/`budget_krw`와 이름·의미가 1:1 대응한다.
    """

    student_subscription: str = "free"
    budget_krw: float = 0.0


def default_student_escalation_signals() -> StudentEscalationDefaults:
    """학생 요청 기본 라우팅 신호 — 오늘은 구독=free·예산=0(결제 미배선).

    반환값은 여섯 호출부가 지금까지 하드코딩해 온 값과 *바이트 동일*하다(순수 리터럴 이동·
    동작 변경 없음). 실 `subscription_tier`/`budget_krw` DB 읽기·결제 연동은 이 함수의
    *내부만* 바뀌면 된다 — 호출부를 다시 찾아다닐 필요가 없다(OPS-18 acceptance①).
    """
    return StudentEscalationDefaults()
