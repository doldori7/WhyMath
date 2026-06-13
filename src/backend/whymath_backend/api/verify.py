"""풀이 단계 검증 도구 HTTP 표면 — `POST /v1/verify-step`·`POST /v1/verify-solution`(stateless).

WH-1 1단계(`verify_step` 도구화·§3.1)의 *엔드포인트 좌석*.
- `/v1/verify-step`: 학생 풀이의 *한 단계*(expr_before → expr_after)가 올바른 변형인지
  **3상태**(correct/incorrect/unverifiable)로 판정한다.
- `/v1/verify-solution`: *이미 분해된* 단계 시퀀스(표현식 리스트)에 verify_step을 *연쇄 적용*해
  집계한다(상태별 카운트·`unverified_ratio`·첫 incorrect 위치·§3.1 연쇄 검증). 텍스트→단계
  분해는 L5(OCR·공간정보) 책임이라 여기 밖이다 — 호출자가 *이미 분해된* steps를 보낸다.

**경계**:
- *stateless* — DB 무접근·LLM 호출 0·세션 없음(순수 SymPy 결정론 검증).
- 인증 = `ConsentedUser`(미성년 동의 게이트만) — 학생 풀이 단계는 PII 가능(CLAUDE.md). 인증
  게이트만 걸고 *본인 데이터 스코핑/적재는 없다*(stateless).
- **노출 계약**: 응답은 *판정 결과*(state·reason·evidence_weight·step_type·카운트·비율)뿐이다.
  학생 풀이 단계가 *입력*으로 들어오나, 정답/본문은 *전혀 누출하지 않는다*(verify_step은 판정만
  반환·정답을 알지도 못함). `reason`은 "동치 아님 — SymPy: ..." 같은 *검증 사유*일 뿐 정답이 아니다.

**정직 스코프**(후속): PRM 점수·텍스트→단계 분해(L5 책임)·coach 파이프라인 결선·단원별 verify
커버리지 ≥70% 게이팅은 *후속 슬라이스*다. 본 슬라이스는 verify_step·verify_solution *도구
primitive* + 엔드포인트까지다(기존 validator/match_gate/coach/harness·`validate_response` 불변·
verify_solution은 신규 좌석).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.l3.verify_solution import (
    SolutionVerificationResult,
    verify_solution,
)
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


class VerifySolutionRequest(BaseModel):
    """`POST /v1/verify-solution` 요청 — *이미 분해된* 단계 시퀀스(+ 전이별 선택 step_types).

    `steps`는 호출자가 *이미 분해한* 표현식 리스트다 — 자유 텍스트→단계 분해는 L5(OCR·공간정보)
    책임이라 여기 밖이다(방정식 풀이와 변형 체인을 혼동한 *거짓 incorrect* 위험·정확성 #1).
    인접 전이 steps[i]→steps[i+1]마다 verify_step이 걸리며, `step_types`를 주면 길이가 전이
    개수(`len(steps)-1`)와 같아야 한다(전이당 하나·불일치 시 422).
    """

    model_config = ConfigDict(extra="forbid")

    steps: list[str] = Field(
        max_length=200,
        description="이미 분해된 풀이 단계 표현식 리스트(순서대로). 인접 전이를 연쇄 검증한다.",
    )
    step_types: list[StepType | None] | None = Field(
        default=None,
        description=(
            "전이별 단계 유형(선택). 주면 길이 = 전이 개수(len(steps)-1)여야 한다(전이당 하나). "
            "비대수(조건해석·케이스분류·그래프스케치)면 그 전이는 SymPy 시도 없이 unverifiable."
        ),
    )


@router.post(
    "/verify-solution",
    response_model=SolutionVerificationResult,
    summary="풀이 단계 시퀀스 연쇄 검증 집계(카운트·unverified_ratio·첫 오류·stateless)",
)
async def post_verify_solution(
    body: VerifySolutionRequest,
    user: ConsentedUser,
) -> SolutionVerificationResult:
    """이미 분해된 단계 시퀀스에 verify_step을 *연쇄 적용*해 집계 — DB 무접근(§3.1).

    인접 전이(steps[i]→steps[i+1])마다 verify_step을 걸어 상태별 카운트·`unverified_ratio`
    (검증 불가 비율)·첫 incorrect 전이 인덱스를 모은다. 판정은 전적으로 verify_step 소관이라
    (재구현 아님) 그 보수성(거짓 incorrect 회피·판정 불가→unverifiable)을 그대로 상속한다.

    엣지: steps 길이 <2면 전이 0개 → 빈 결과(에러 아님). step_types 길이가 전이 개수와 다르면
    verify_solution이 ValueError를 던지므로 *422*로 변환해 호출자에게 명확히 알린다(조용한 패딩
    금지·정확성 #1 — FastAPI는 본문 ValueError를 자동 422로 바꾸지 않으니 명시 처리).

    `user`는 인증 게이트만(stateless라 user 데이터 미사용). 응답은 검증 집계만 — 정답/본문 누출 0.
    """
    _ = user.user_id  # 인증 게이트 통과 확인용(stateless라 user 데이터 미사용).
    try:
        return verify_solution(body.steps, body.step_types)
    except ValueError as exc:
        # step_types 길이 규약 위반 — 입력 오류이므로 422(스택트레이스·500 노출 금지).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
