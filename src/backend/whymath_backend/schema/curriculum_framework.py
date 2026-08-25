"""교육과정 프레임워크(CurriculumFramework) Pydantic 계약 모델.

설계 정본: `docs/architecture/eos_curriculum_semantic_backbone_adr.md` Phase 1.
WhyMath Concept 원본 트리 위에 쌓는 Curriculum Overlay의 최상위 그룹이다.

ID 체계:
  `framework_id`는 의미 문자열 PK로, CASE 1.1의 `CFDocument`/`CaseCFI` 개념과 대응한다.
  권장 prefix: `CURR-xxxxxxxx` 또는 체계 축약(`KR_NC_2022`, `CCSS-MATH`, `IB-DP-MATH` 등).
  안정성을 위해 재사용 가능한 문자열 식별자를 사용; UUID는 `CurriculumVersion.version_id`에 둔다.

타입 매핑(ORM과 동형):
  - `framework_id` → required `str` (PK).
  - `authority`·`country`·`title` → required `str`.
  - `description` → `str | None`.
  - `effective_from`·`effective_to` → `date | None`.
  - `status` → Literal with default `"published"`.
  - `created_at`·`updated_at` → required `datetime`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CurriculumFramework(BaseModel):
    """교육과정 프레임워크 — 국가/기관/학교 단위 교육과정의 버킷.

    `country`는 ISO 3166-1 alpha-2(예: 'KR')를 권장하지만, 체계에 따라 'INT'(국제) 등의
    의사 코드도 허용한다. enum 강제는 하지 않음 — EOS는 다중 교육과정 매핑을 지원하며
    새로운 국가/기관 체계가 계속 추가될 수 있다(ADR §7).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    framework_id: str = Field(
        ...,
        description="프레임워크 PK — 의미 문자열 식별자 (예: 'KR_NC_2022', 'CCSS-MATH')",
    )
    authority: str = Field(
        ...,
        description=(
            "프레임워크를 발행한 기관 "
            "(예: '한국 교육부', 'Common Core State Standards Initiative')"
        ),
    )
    country: str = Field(
        ...,
        description="프레임워크가 적용되는 국가/법정 체계 코드 (예: 'KR', 'US')",
    )
    title: str = Field(..., description="프레임워크 공식 명칭")
    description: str | None = Field(default=None, description="프레임워크에 대한 부연 설명")

    effective_from: date | None = Field(
        default=None,
        description="프레임워크 시행 시작일 — DATE 타입(날짜만)",
    )
    effective_to: date | None = Field(
        default=None,
        description="프레임워크 폐기/종료 예정일 (선택)",
    )
    status: Literal[
        "draft",
        "review",
        "approved",
        "published",
        "deprecated",
        "superseded",
    ] = Field(default="published", description="프레임워크 생명주기 상태")

    created_at: datetime = Field(..., description="레코드 생성 시각")
    updated_at: datetime = Field(..., description="레코드 최종 수정 시각")


__all__ = ["CurriculumFramework"]
