"""분석 이벤트 envelope — 생산 이벤트의 멱등성·시간·PII 경계 단일 계약.

`AttemptEvent.event_id`는 DB가 할당하는 내부 BIGSERIAL이며 모바일 재전송을 식별할 수 없다.
이 모델의 `event_uuid`는 producer가 생성하는 멱등키이고, DB 영속화(DP-03)가 완료되기 전에는
producer 경계의 계약으로만 사용한다.

`event_data_contract`는 이벤트별 payload의 정본이다. 이 모듈은 그 정본을 재사용하면서,
분석 이벤트에는 학생 원문·이미지·URL query·정밀 좌표·영구 기기 식별자를 싣지 못하도록
추가로 차단한다.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import EventType
from whymath_backend.schema.event_data_contract import EVENT_DATA_CONTRACT, build_event_data

__all__ = [
    "AnalyticsEventEnvelope",
    "AnalyticsEventSource",
    "build_analytics_event_envelope",
]


class AnalyticsEventSource(str, Enum):
    """이벤트를 만든 신뢰 경계. source별 재전송/세션 정책이 다르다."""

    BACKEND = "backend"
    MOBILE = "mobile"


# 정확한 payload 필드명 또는 이름만으로 민감성이 확정되는 키다. 값은 검사·저장하지 않는다.
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "chat",
        "chat_text",
        "message",
        "student_answer",
        "answer_text",
        "solution",
        "solution_latex",
        "latex",
        "image",
        "image_url",
        "handwriting",
        "ocr_result",
        "url_query",
        "query_string",
        "x_coordinate",
        "y_coordinate",
        "coordinate",
        "device_id",
        "advertising_id",
        "installation_id",
    }
)


def _find_forbidden_payload_key(value: Any) -> str | None:
    """중첩 payload까지 키 이름만 검사해 원문/식별자 유입을 경계에서 막는다."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and key.strip().lower() in _FORBIDDEN_PAYLOAD_KEYS:
                return key
            found = _find_forbidden_payload_key(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_forbidden_payload_key(nested)
            if found is not None:
                return found
    return None


class AnalyticsEventEnvelope(BaseModel):
    """분석 생산 이벤트의 공통 봉투.

    - `occurred_at`: 클라이언트/도메인에서 사건이 일어난 시각
    - `received_at`: API가 서버에서 수신한 시각
    - `event_uuid`: 재전송 중복 제거를 위한 producer 생성 키 (DP-03에서 unique 영속화)
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_uuid: UUID = Field(description="producer가 생성한 재전송 멱등키")
    schema_version: Literal[1] = Field(default=1, description="봉투 계약 버전")
    occurred_at: datetime = Field(description="도메인 사건 발생 시각")
    received_at: datetime = Field(description="서버 수신 시각")
    source: AnalyticsEventSource = Field(description="생산 신뢰 경계")
    session_id: UUID | None = Field(default=None, description="비식별 학습 세션 식별자")
    correlation_id: UUID | None = Field(default=None, description="한 요청/흐름을 잇는 식별자")
    event_type: EventType = Field(description="기존 EventType 정본 값")
    payload: dict[str, Any] = Field(description="event_data_contract로 검증되는 타입별 payload")

    @model_validator(mode="after")
    def _validate_envelope(self) -> AnalyticsEventEnvelope:
        if self.occurred_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("occurred_at과 received_at은 timezone-aware datetime이어야 합니다")
        if self.received_at < self.occurred_at:
            raise ValueError("received_at은 occurred_at보다 빠를 수 없습니다")
        if self.source == AnalyticsEventSource.MOBILE and self.session_id is None:
            raise ValueError("mobile 이벤트에는 session_id가 필요합니다")

        forbidden_key = _find_forbidden_payload_key(self.payload)
        if forbidden_key is not None:
            raise ValueError(f"분석 payload 금지 키: {forbidden_key}")

        event_type = EventType(self.event_type)
        if event_type not in EVENT_DATA_CONTRACT:
            raise ValueError(f"{event_type.value}는 생산 payload allowlist가 없는 휴면 EventType입니다")
        try:
            normalized = build_event_data(event_type, **self.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"payload allowlist 위반: {exc}") from exc
        self.payload = normalized
        return self


def build_analytics_event_envelope(**kwargs: Any) -> AnalyticsEventEnvelope:
    """producer가 분석 envelope 검증을 우회하지 않도록 제공하는 단일 생성 seam."""

    return AnalyticsEventEnvelope(**kwargs)
