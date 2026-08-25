"""교육과정 프레임워크 버전(CurriculumVersion) Pydantic 계약 모델.

설계 정본: `docs/architecture/eos_curriculum_semantic_backbone_adr.md` Phase 1.
`CurriculumFramework` 아래에 여러 버전(개정·일부 개정·역사적 스냅숏)을 둬서
EOS가 temporal curriculum을 보존할 수 있게 한다.

ID 체계:
  `version_id`는 UUID PK. `framework_id`는 느슨참조 FK(Pydantic에서는 str, ORM에서 FK).
  하나의 framework는 여러 version을 가진다.

타입 매핑(ORM과 동형):
  - `version_id` → required `UUID` (PK).
  - `framework_id` → required `str` (FK).
  - `version_label` → required `str` (예: '2022_REV_01').
  - `effective_from`·`effective_to` → `date | None`.
  - `status` → Literal with default `"published"`.
  - `source_id` → `str | None` (TIER 0 원문 source 식별자; source 1급 테이블은 CUR-14/후속).
  - `created_at`·`updated_at` → required `datetime`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CurriculumVersion(BaseModel):
    """교육과정 프레임워크의 단일 버전.

    `version_label`은 사람이 읽는 라벨(예: '2022_REV_01', '2015 개정')이고,
    `version_id`는 UUID 기반 불변 식별자다. 동일 framework 내에서 version_label은
    의미상 유일해야 하지만, 백엔드 계약은 단일 모델이므로 DB UNIQUE 제약으로 보장한다.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    version_id: UUID = Field(..., description="버전 PK — UUID")
    framework_id: str = Field(
        ...,
        description="소속 프레임워크 식별자 (CurriculumFramework.framework_id)",
    )
    version_label: str = Field(
        ...,
        description="사람이 읽는 버전 라벨 (예: '2022_REV_01', '2015 개정')",
    )

    effective_from: date | None = Field(
        default=None,
        description="버전 시행 시작일 — DATE 타입(날짜만)",
    )
    effective_to: date | None = Field(
        default=None,
        description="버전 폐기/종료 예정일 (선택)",
    )
    status: Literal[
        "draft",
        "review",
        "approved",
        "published",
        "deprecated",
        "superseded",
    ] = Field(default="published", description="버전 생명주기 상태")

    source_id: str | None = Field(
        default=None,
        description="TIER 0 공식 원문 source 식별자 (source 1급 테이블은 후속 태스크)",
    )

    created_at: datetime = Field(..., description="레코드 생성 시각")
    updated_at: datetime = Field(..., description="레코드 최종 수정 시각")


__all__ = ["CurriculumVersion"]
