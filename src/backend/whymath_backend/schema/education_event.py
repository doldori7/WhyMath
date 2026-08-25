"""Canonical Education Event envelope — EOS 204 Education Event System.

이 모듈은 `docs/architecture/204_education_event_system.md` §4 Canonical Education
Event Envelope을 Pydantic 모델로 구현한다. 모든 EOS 교육 이벤트는 이 봉투를 사용하며,
외부 표준(xAPI/Caliper/CloudEvents)은 `events/adapters`에서 변환한다.

설계 원칙:
- payload는 event_type별 계약(`event_data_contract.py` 패턴)으로 검증.
- PII 필드는 봉투 레벨에서 거부 — payload allowlist가 별도로 동작.
- occurred_at / recorded_at 분리 — 오프라인/모바일 이벤트 대응.
- trace 필드로 causation chain 표현.
- privacy 메타데이터는 registry 조회 + SDK 자동 부착.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.event_taxonomy import (
    EducationEventType,
    EventActorType,
    EventPrivacyClassification,
)


class Actor(BaseModel):
    """Event 행위자."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    actor_type: EventActorType = Field(..., description="행위자 유형")
    actor_id: str | None = Field(default=None, description="행위자 식별자(pseudonymized)")


class Session(BaseModel):
    """이벤트가 속한 세션."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    session_id: str | None = Field(default=None, description="API/장치 세션 식별자")
    learning_session_id: str | None = Field(default=None, description="학습 세션 식별자")


class Object(BaseModel):
    """Event object (행위 대상)."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    entity_type: str = Field(..., description="대상 유형(예: problem, concept, hint)")
    entity_id: str = Field(..., description="안정적 ID reference")
    entity_version: str | None = Field(default=None, description="version_id (EOS-44)")


class PedagogyContext(BaseModel):
    """교수학적 맥락."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    strategy_id: str | None = Field(default=None, description="교수전략 ID")
    strategy_version: str | None = Field(default=None, description="교수전략 버전")
    intervention_reason: str | None = Field(
        default=None, description="개입 사유(예: misconception_detected)"
    )
    explanation_mode: str | None = Field(
        default=None, description="socratic | polya | direct | ..."
    )


class EducationContext(BaseModel):
    """이벤트 교육적 맥락."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    subject_id: str | None = Field(default=None, description="과목 ID")
    curriculum_id: str | None = Field(default=None, description="교육과정 ID")
    grade: str | None = Field(default=None, description="학년/학년군")
    unit_id: str | None = Field(default=None, description="단원 ID")
    objective_id: str | None = Field(default=None, description="학습목표 ID")
    concept_ids: list[str] = Field(default_factory=list, description="관련 개념 ID 목록")
    skill_ids: list[str] = Field(default_factory=list, description="관련 스킬 ID 목록")
    misconception_ids: list[str] = Field(default_factory=list, description="관련 오개념 ID 목록")
    pedagogy: PedagogyContext | None = Field(default=None, description="교수학적 맥락")


class Source(BaseModel):
    """이벤트 생산처."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    service: str = Field(..., description="생산 서비스(예: problem-service, coach-service)")
    client: str | None = Field(default=None, description="클라이언트(예: student-web, flutter)")


class Trace(BaseModel):
    """이벤트 추적 및 인과관계."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    trace_id: str | None = Field(default=None, description="전체 흐름 식별자")
    correlation_id: str | None = Field(default=None, description="관련 사건 그룹")
    causation_id: str | None = Field(default=None, description="직접 원인 이벤트 ID")
    parent_event_id: str | None = Field(default=None, description="상위 이벤트 ID")


class Privacy(BaseModel):
    """이벤트 프라이버시 메타데이터."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    classification: EventPrivacyClassification = Field(..., description="PII 등급")
    contains_pii: bool = Field(default=False, description="PII 포함 여부")
    consent_scope: str | None = Field(default=None, description="동의 범위(예: learning_analytics)")
    retention_policy_id: str | None = Field(default=None, description="보존 정책 ID")
    ai_training_allowed: bool | None = Field(default=None, description="AI 학습 사용 허용 여부")


class EducationEvent(BaseModel):
    """EOS Canonical Education Event 봉투.

    모든 EOS 교육 이벤트는 이 봉투를 사용한다. payload는 event_type별 계약으로
    추가 검증된다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    event_id: str = Field(..., description="이벤트 식별자(UUIDv7 권장)")
    event_type: EducationEventType = Field(..., description="이벤트 유형")
    event_version: str = Field(default="1.0", description="이벤트 의미 버전")

    occurred_at: datetime = Field(..., description="도메인 사건 발생 시각(timezone-aware)")
    recorded_at: datetime = Field(..., description="서버 수신/기록 시각(timezone-aware)")
    processed_at: datetime | None = Field(default=None, description="처리 완료 시각(선택)")

    actor: Actor = Field(..., description="행위자")
    session: Session = Field(default_factory=Session, description="세션")
    object: Object = Field(..., description="행위 대상")

    context: EducationContext = Field(default_factory=EducationContext, description="교육적 맥락")
    payload: dict[str, Any] = Field(default_factory=dict, description="event_type별 payload")

    source: Source = Field(..., description="생산처")
    trace: Trace = Field(default_factory=Trace, description="추적/인과관계")

    privacy: Privacy = Field(..., description="프라이버시 메타데이터")

    schema_version: str = Field(default="education-event@1.0", description="봉투 계약 버전")

    @model_validator(mode="after")
    def _validate_timestamps(self) -> EducationEvent:
        if self.occurred_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ValueError("occurred_at과 recorded_at은 timezone-aware datetime이어야 합니다")
        if self.recorded_at < self.occurred_at:
            raise ValueError("recorded_at은 occurred_at보다 빠를 수 없습니다")
        if self.processed_at is not None:
            if self.processed_at.tzinfo is None:
                raise ValueError("processed_at은 timezone-aware datetime이어야 합니다")
            if self.processed_at < self.recorded_at:
                raise ValueError("processed_at은 recorded_at보다 빠를 수 없습니다")
        return self


class EducationEventEnvelope(BaseModel):
    """외부 전송용 envelope — EducationEvent + 메타데이터.

    EducationEvent 자체가 봉투이므로 초기에는 EducationEvent를 그대로 직렬화한다.
    향후 암호화/압축/서명 메타데이터를 추가할 때 사용.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    event: EducationEvent = Field(..., description="Canonical Education Event")
    metadata: dict[str, Any] = Field(default_factory=dict, description="전송 메타데이터(선택)")
