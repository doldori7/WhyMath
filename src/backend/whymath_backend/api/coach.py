"""L4 교수학 코치 HTTP 표면 — `POST /v1/coach`.

학생 발화·Polya 상태(+옵션 숙달도)를 받아 *통합 결정*을 반환한다. L4 슬라이스 1-5의 모든
결정 함수를 한 발화로 묶는 엔드포인트:
- `PolyaCoach.decide()` — 단계 전이·prompt 조립·socratic_category·hint_level·reveals
- `diagnose()` — 오개념 후보 top-K
- `select_intervention()` — top-1 신뢰도 0.5+ 시 개입 결정
- `adapt_lthc()` — 숙달도 제공 시 진입점·확장·비계 조정

**경계**:
- *stateless* — state는 클라이언트가 보내고 받는다(세션 영속·`dialogue` DB 쓰기는 후속).
- *LLM 호출 0* — `PolyaCoach.coach()`(LLM seam 사용)는 별도 슬라이스(라이브 키 필요).
- 인증 = `ConsentedUser`(미성년 동의 게이트 통과) — 학생 발화는 PII 가능(CLAUDE.md).
- 응답에 `system`/`prompt` 본문이 노출되므로 *학생 발화를 그대로 에코하지 않음*(에코 시
  필터·검증 없이 표면화될 위험).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.l4 import (
    LthcAdaptation,
    MasteryLevel,
    PedagogyDecision,
    PolyaCoach,
    PolyaState,
    adapt_lthc,
)
from whymath_backend.l4.misconception import (
    InterventionDecision,
    MisconceptionMatch,
    diagnose,
    select_intervention,
)

router = APIRouter(prefix="/v1", tags=["coach"])

_coach = PolyaCoach()  # 상태 비저장 — 단일 인스턴스 재사용


class CoachRequest(BaseModel):
    """`/v1/coach` 요청 본문 — 학생 발화·현재 상태·옵션 숙달도."""

    model_config = ConfigDict(extra="forbid")

    student_input: str = Field(
        min_length=0,
        max_length=4000,
        description="학생 발화(자연어). 빈 문자열 허용(첫 진입). 길이 상한은 남용·비용 방어.",
    )
    polya_state: PolyaState = Field(
        default_factory=PolyaState,
        description="세션의 현재 Polya 상태. 기본값=UNDERSTAND 진입.",
    )
    mastery_level: MasteryLevel | None = Field(
        default=None,
        description="학생 숙달도 라벨(있을 때만 LTHC 조정안 반환).",
    )


class CoachResponse(BaseModel):
    """`/v1/coach` 응답 — 통합 교수학 결정.

    `decision`은 *반드시* 채워지고(`PolyaCoach.decide()`는 항상 결정 반환), 나머지는 조건부.
    """

    model_config = ConfigDict(extra="forbid")

    decision: PedagogyDecision = Field(
        description="Polya 단계 전이·프롬프트·hint_level·socratic_category 등 핵심 결정.",
    )
    misconceptions: list[MisconceptionMatch] = Field(
        default_factory=list,
        description="오개념 후보 top-3(없으면 빈 리스트). confidence 내림차순.",
    )
    intervention: InterventionDecision | None = Field(
        default=None,
        description=(
            "top-1 misconception이 신뢰도 0.5+면 개입 결정(반례 유도/거꾸로 사고)."
            " 미만이면 None — 진단 보류(라벨링 회피)."
        ),
    )
    lthc: LthcAdaptation | None = Field(
        default=None,
        description="요청에 `mastery_level`이 있을 때만 LTHC 조정안. 없으면 None.",
    )


@router.post(
    "/coach",
    response_model=CoachResponse,
    summary="L4 교수학 통합 결정",
)
async def coach_decide(
    body: CoachRequest,
    user: ConsentedUser,
) -> CoachResponse:
    """학생 발화 → Polya 결정 + 오개념 진단 + LTHC 조정안을 *한 번에* 반환.

    `user`는 사용자 식별·인가 게이트일 뿐, 본 슬라이스는 데이터를 *영속화하지 않는다*
    (stateless — 세션 적재는 후속 슬라이스 `/v1/coach/sessions` 시).
    """
    _ = user.user_id  # 인증 게이트 통과 확인용(slice 6 stateless라 user 데이터 미사용)

    decision = _coach.decide(body.student_input, body.polya_state)
    matches = diagnose(body.student_input)
    intervention = select_intervention(matches[0]) if matches else None
    lthc = (
        adapt_lthc(body.polya_state.current_stage, body.mastery_level)
        if body.mastery_level is not None
        else None
    )

    return CoachResponse(
        decision=decision,
        misconceptions=matches,
        intervention=intervention,
        lthc=lthc,
    )
