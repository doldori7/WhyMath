"""L5 상호작용 이벤트 수집 — 학생의 시각화 조작 → AttemptEvent 영속. 슬라이스 96-F/J.

E(웹→Flutter JS 채널)로 흐른 학생 조작 신호를 백엔드에 적재해 L2 행동 분석(능동 탐구·메타인지
신호)의 입력으로 삼는다. 시각화 조작은 전용 `EventType.시각화조작`으로 분류하고(J — `그래프그리기`
답안 작도와 구분), 세부(어떤 조작·파라미터·값·개념 컨텍스트)는 `event_data` JSONB에 담는다 —
기존 `attempt_event` 하이퍼테이블 재사용(7계층: L5만 세션 보유·하위 조합).

경계: 이 엔드포인트는 *수집 게이트*다 — 검증(스키마)·인증(동의)만 하고 그대로 적재한다.
컨텍스트(J): 계산기 임베드는 약점개념 scene 흐름에서만 뜨고 그 흐름엔 problem/attempt가 *없다* →
concept_id/scene_id를 event_data에 싣고 attempt_id/problem_id는 NULL로 둔다(없는 연결 위조 금지).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.db.models.activity import AttemptEvent
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import EventType
from whymath_backend.schema.event_data_contract import build_event_data

router = APIRouter(prefix="/v1/interactions", tags=["activity"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class InteractionEventIn(BaseModel):
    """웹 계산기 조작 이벤트 입력 — E의 `emitInteraction({type, payload, at})`와 정합."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="조작 종류(param_change·param_play·surface_change·surface_range 등)",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="조작 세부(예: {name, value})"
    )
    at: int | None = Field(default=None, description="클라이언트 발생 시각(epoch ms·선택)")
    concept_id: str | None = Field(
        default=None,
        max_length=128,
        description="탐구 중인 개념(약점개념 scene의 concept_id·호스트가 주입·선택)",
    )
    scene_id: str | None = Field(
        default=None,
        max_length=128,
        description="조작이 일어난 학습 장면(scene_id·호스트가 주입·선택)",
    )


@router.post(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="시각화 조작 이벤트 적재 (학습 로그 — L2 행동 분석 입력)",
)
async def post_interaction(
    user: ConsentedUser,
    session: SessionDep,
    body: InteractionEventIn,
) -> None:
    """인증 학생의 시각화 조작 이벤트를 `attempt_event`에 적재한다(시각화조작 활동으로 분류).

    세부는 `event_data`(JSONB)에 담는다: `{interaction, payload, client_at, concept_id, scene_id}`.
    `get_session`은 자동 commit하지 않으므로 핸들러가 명시적으로 commit한다.
    """
    session.add(
        AttemptEvent(
            event_at=datetime.now(timezone.utc),
            user_id=user.user_id,
            event_type=EventType.시각화조작,
            event_data=build_event_data(
                EventType.시각화조작,
                interaction=body.type,
                payload=body.payload,
                client_at=body.at,
                concept_id=body.concept_id,
                scene_id=body.scene_id,
            ),
        )
    )
    await session.commit()
