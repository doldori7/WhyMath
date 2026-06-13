"""풀이 단계 검증 도구 HTTP 표면 — `POST /v1/verify-step`(stateless).

WH-1 1단계 슬라이스 2(`verify_step` 도구화·§3.1)의 *엔드포인트 좌석*. 학생 풀이의 *한 단계*
(expr_before → expr_after)가 올바른 변형인지 **3상태**(correct/incorrect/unverifiable)로 판정한다.

**경계**:
- *stateless* — DB 무접근·LLM 호출 0·세션 없음(순수 SymPy 결정론 검증 1회).
- 인증 = `ConsentedUser`(미성년 동의 게이트만) — 학생 풀이 단계는 PII 가능(CLAUDE.md). 인증
  게이트만 걸고 *본인 데이터 스코핑/적재는 없다*(stateless).
- **노출 계약**: 응답은 *판정 결과*(state·reason·evidence_weight·step_type)뿐이다. 학생 풀이
  단계가 *입력*으로 들어오나, 정답/본문은 *전혀 누출하지 않는다*(verify_step은 판정만 반환·정답을
  알지도 못함). `reason`은 "동치 아님 — SymPy: ..." 같은 *검증 사유*일 뿐 정답이 아니다.

**정직 스코프**(후속): PRM 점수·step 파싱(솔루션→단계 분해)·coach 파이프라인 결선은 *후속
슬라이스*다. 본 슬라이스는 verify_step *도구 primitive* + 엔드포인트까지다(기존 validator/
match_gate/coach/harness 불변·verify_step은 신규 좌석).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.l3.verify_step import VerifyStepResult, verify_step
from whymath_backend.schema.enums import StepType

router = APIRouter(prefix="/v1", tags=["verify"])


class VerifyStepRequest(BaseModel):
    """`POST /v1/verify-step` 요청 — 풀이 한 단계(변형 전·후 식 + 선택 step_type)."""

    model_config = ConfigDict(extra="forbid")

    expr_before: str = Field(
        max_length=4000,
        description="변형 *전* 식(학생 풀이 한 단계의 좌측). 길이 상한은 남용 방어.",
    )
    expr_after: str = Field(
        max_length=4000,
        description="변형 *후* 식(같은 단계의 우측). before와 동치면 correct.",
    )
    step_type: StepType | None = Field(
        default=None,
        description=(
            "단계 유형(선택). 비대수(조건해석·케이스분류·그래프스케치)면 SymPy 시도 없이 "
            "unverifiable. 계산·검산·미지정이면 심볼릭 동치 검증."
        ),
    )


@router.post(
    "/verify-step",
    response_model=VerifyStepResult,
    summary="풀이 한 단계 3상태 검증(correct/incorrect/unverifiable·stateless)",
)
async def post_verify_step(
    body: VerifyStepRequest,
    user: ConsentedUser,
) -> VerifyStepResult:
    """풀이 한 단계(expr_before → expr_after)가 올바른 변형인지 *3상태*로 판정 — DB 무접근.

    대수 변형은 SymPy 심볼릭 동치로 correct/incorrect를, 비대수 단계(서술형·경우나누기·기하)나
    판정/파싱 불가는 *정직하게* unverifiable로 반환한다(CLAUDE.md "확실하지 않으면 모른다" —
    correct로 위장하지 않음·unverifiable이면 evidence_weight 0.5 할인).

    `user`는 인증 게이트만(stateless라 user 데이터 미사용). 응답은 판정만 — 정답/본문 누출 0.
    """
    _ = user.user_id  # 인증 게이트 통과 확인용(stateless라 user 데이터 미사용).
    return verify_step(body.expr_before, body.expr_after, body.step_type)
