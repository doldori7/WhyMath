"""GDPR 삭제 감사(DeletionAudit) Pydantic 스키마 — slice 58 (조회 API 응답).

slice 57이 `deletion_audit`에 적재하는 행의 *읽기* 표현. `GET /v1/me/deletions`가 본인 삭제
이력을 반환할 때 직렬화에 쓴다. 삭제 *메타*만(콘텐츠 없음 — slice 57 설계: 누가·무엇·언제).
ORM(`db/models/audit.py`)과 별도로 세운 검증·API 레이어이며 `to_schema`/`from_schema`가 잇는다
(activity.py·user.py 동일 패턴).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import AuditResourceType


class DeletionAudit(BaseModel):
    """본인 리소스 삭제 감사 1행(읽기) — append-only 기록의 단일 표현."""

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # enum 값 그대로 직렬화(resource_type="learning_session")
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    audit_id: uuid.UUID = Field(default_factory=uuid4, description="감사 PK (UUID)")
    user_id: uuid.UUID | None = Field(
        default=None,
        description="삭제를 수행한 소유자 (plain UUID — FK 아님, 사용자 삭제돼도 잔존)",
    )
    resource_type: AuditResourceType | None = Field(
        default=None,
        description="삭제된 도메인 (learning_session/dialogue/assessment)",
    )
    resource_id: uuid.UUID | None = Field(
        default=None,
        description="삭제된 리소스의 id (해당 도메인 PK)",
    )
    deleted_at: datetime | None = Field(
        default=None,
        description="삭제·감사 기록 시각 (DB server_default now())",
    )
