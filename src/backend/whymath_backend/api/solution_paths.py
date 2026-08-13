"""L5 SolutionPath 단계 *점층 공개* 엔드포인트 (SOL-02 — step_panel의 실단계 공급면).

배경: 장면의 `step_panel` 요소(`l4/learning_scene.py` StepPanelElement)는 `solution_path_id`만
싣는다 — 스키마가 `reveal_policy="deferred"`를 강제해 단계 내용은 장면에 없다. 모바일은 그 id로
본 엔드포인트를 호출해 *학생이 펼친 단계까지의* 내용만 받아 간다.

보안·교수학 설계(왜 새 표면인가):
  - SEC-24가 봉인한 것은 *무인증* 표면의 정답류다 — `GET /v1/problems/{id}/steps`의 공개 투영
    (`PublicProblemStep`)이 `expected_answer`(S4-09 승격 어댑터가 `SolutionStep.content`를 싣는
    좌석·`whs/path_promotion.py`)를 키째 숨기는 이유다.
  - 본 엔드포인트는 ① `ConsentedUser`(인증 + 미성년자 학부모 동의 게이트·`api/_auth.py`)를
    통과한 학생에게만 ② `up_to` 쿼리로 *서버가* 슬라이스를 집행해 펼친 만큼만 내려준다 —
    클라이언트는 미펼침 단계 내용을 메모리에도 갖지 않는다. 답 미루기(deferred)를 스키마
    표기가 아니라 서버가 집행한다(화장품 금지).
  - 조회는 SOL-01의 `l3/solution_path_store`가 담당한다(경로 읽기 단일 표면·재구현 금지).
    본 모듈은 슬라이스·클램프·404 매핑만 한다.

범위: 단일 경로의 단계 점층 공개만. 다중 풀이 비교·갤러리(S4-10)·힌트 콘텐츠(S4-11)·
approach_type 노출은 SOL-02 acceptance ⑦의 범위 밖 그대로다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.db.session import get_session
from whymath_backend.l3.solution_path_store import (
    get_solution_path,
    get_solution_path_steps,
)


class SolutionPathStepItem(BaseModel):
    """점층 공개 단계 1개 — 순서 + 내용만. 오개념·검증 메타(reasoning_type·justification·
    sympy_verified)는 내부 전용이라 여기 두지 않는다(학생 대면 표면 최소화)."""

    model_config = ConfigDict(extra="forbid")

    step_order: int = Field(ge=1, description="단계 순서(1부터).")
    content: str = Field(min_length=1, description="단계 내용(SolutionStep.content의 영속 좌석).")


class SolutionPathStepsResponse(BaseModel):
    """점층 공개 응답 — `steps`는 1..`up_to` 슬라이스, `total`은 서버가 보유한 전체 단계 수.

    클라이언트는 `up_to < total`이면 "다음 단계 펼치기"를 `up_to+1`로 다시 호출해 점층을
    진행한다. `up_to`는 요청값을 `total`로 클램프한 *실제 공개 상한*(total=0인 퇴화 케이스에서
    0이 될 수 있어 ge=0).
    """

    model_config = ConfigDict(extra="forbid")

    steps: list[SolutionPathStepItem]
    total: int = Field(ge=0, description="경로의 실체화 단계 총수(서빙 가능분).")
    up_to: int = Field(ge=0, description="실제로 공개된 상한(요청 up_to를 total로 클램프).")


router = APIRouter(prefix="/v1/solution-paths", tags=["solution-paths"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/{solution_path_id}/steps",
    response_model=SolutionPathStepsResponse,
    summary="검증 풀이 경로 단계 점층 공개(인증 학생·up_to까지)",
)
async def list_solution_path_steps(
    user: ConsentedUser,
    session: SessionDep,
    solution_path_id: str,
    up_to: Annotated[int, Query(ge=1, description="펼칠 단계 상한(1부터·기본 1)")] = 1,
) -> SolutionPathStepsResponse:
    """경로 단계를 1..up_to만 내려준다 — 서버 측 점층 공개(답 미루기 집행).

    경로 미존재 → 404. `up_to`가 총수를 넘으면 총수로 클램프한다(넘침은 에러가 아니라
    전부 공개). 인증은 `ConsentedUser` — 무인증 401·미동의 미성년 403(정답류는 동의된
    학생에게만).
    """
    if await get_solution_path(session, solution_path_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"풀이 경로를 찾을 수 없습니다: {solution_path_id}",
        )
    rows = await get_solution_path_steps(session, solution_path_id)
    total = len(rows)
    clamped = min(up_to, total)
    # expected_answer는 store가 NULL을 SQL에서 제외해 NOT NULL이 보장된다 — 타입 좁힘 겸 방어.
    items = [
        SolutionPathStepItem(step_order=row.step_order, content=row.expected_answer)
        for row in rows[:clamped]
        if row.expected_answer is not None
    ]
    return SolutionPathStepsResponse(steps=items, total=total, up_to=clamped)
