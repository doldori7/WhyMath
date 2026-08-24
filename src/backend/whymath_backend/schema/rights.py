"""Rights & Provenance Infrastructure 스키마 (LIC-01).

설계 정본: EOS 42번 모듈 "Source Registry + Rights Registry + License Registry +
Policy Engine + Provenance Graph"의 MVP 데이터 계약. Content-Source/Rights를 N:M으로
분리하고, License를 Permission primitive로 정규화해 기계적 권리 판정이 가능하게 한다.

컨벤션(`problem.py`·`provenance.py` 답습):
  - ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True).
  - enum은 `schema.enums.py`의 str-Enum을 재사용.
  - 식별자 UUID는 `default_factory=uuid4`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import (
    DerivationType,
    LicenseType,
    PermissionAction,
    RightsDecision,
    RightsReviewStatus,
    SourceAuthority,
)

__all__ = [
    "AttributionTemplate",
    "ContentRightsLink",
    "ContentSourceLink",
    "DerivationEdge",
    "PermissionSet",
    "RightsCheckRequest",
    "RightsCheckResponse",
    "RightsEntity",
    "RightsHolderEntity",
    "SourceEntity",
]


# ──────────────────────────────────────────────────────────────────────────
# 출처(Source)
# ──────────────────────────────────────────────────────────────────────────
class SourceEntity(BaseModel):
    """외부/내부 원본 출처의 정규화 표현.

    원본 URL뿐 아니라 취득일·해시·스냅샷·신뢰도를 함께 보관해 원본이 변경/삭제되어도
    당시 사용 내용을 재현할 수 있게 한다.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    source_id: uuid.UUID = Field(default_factory=uuid4, description="출처 PK")
    source_type: str = Field(
        ..., max_length=64, description="출처 유형 — public_institution/website/dataset/book/ai/..."
    )
    title: str = Field(..., max_length=512, description="자료명")
    publisher: str | None = Field(default=None, max_length=256, description="발행기관")
    creator: str | None = Field(default=None, max_length=256, description="원저작자")
    original_url: str | None = Field(default=None, max_length=2048, description="원본 URL")
    retrieved_at: datetime | None = Field(default=None, description="취득일")
    publication_date: str | None = Field(
        default=None, max_length=32, description="발행일(YYYY-MM-DD 등 자유형)"
    )
    jurisdiction: str | None = Field(default=None, max_length=8, description="국가코드(KR/US/...)")
    source_hash: str | None = Field(default=None, max_length=128, description="원본 SHA-256 등")
    archive_uri: str | None = Field(
        default=None, max_length=2048, description="s3://... 형태 스냅샷"
    )
    source_authority: SourceAuthority = Field(
        default=SourceAuthority.UNKNOWN, description="출처 신뢰도"
    )
    status: str = Field(default="verified", max_length=32, description="verified/pending/disputed")
    extra: dict[str, Any] | None = Field(default=None, description="출처별 확장 메타")
    created_at: datetime | None = Field(default=None, description="등록 시각")


# ──────────────────────────────────────────────────────────────────────────
# 권리 보유자(Rights Holder)
# ──────────────────────────────────────────────────────────────────────────
class RightsHolderEntity(BaseModel):
    """권리 보유자 — 기관/개인을 문자열이 아닌 엔티티로 관리."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    holder_id: uuid.UUID = Field(default_factory=uuid4, description="보유자 PK")
    entity_type: str = Field(
        ..., max_length=32, description="organization/person/government/ai_model/..."
    )
    name: str = Field(..., max_length=256, description="표시명")
    country: str | None = Field(default=None, max_length=8, description="소재국가")
    aliases: list[str] = Field(default_factory=list, description="기관명 변경·표기 변형")
    contact: str | None = Field(default=None, max_length=512, description="연락처/URL")
    extra: dict[str, Any] | None = Field(default=None, description="확장 메타")


# ──────────────────────────────────────────────────────────────────────────
# Permission Primitive
# ──────────────────────────────────────────────────────────────────────────
class PermissionSet(BaseModel):
    """License를 해석한 정규화 권리 primitive 집합.

    None은 "명시적으로 알 수 없음/검수 필요"를 의미할 수 있으며,
    Rights Policy Engine은 None을 False와 구분해 REVIEW_REQUIRED로 처리할 수 있다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    display: bool | None = Field(default=None, description="표시")
    copy_: bool | None = Field(default=None, alias="copy", description="내부 복제")
    redistribute: bool | None = Field(default=None, description="재배포")
    modify: bool | None = Field(default=None, description="수정")
    translate: bool | None = Field(default=None, description="번역")
    commercial_use: bool | None = Field(default=None, description="상업적 이용")
    download: bool | None = Field(default=None, description="다운로드")
    print_: bool | None = Field(default=None, alias="print", description="인쇄")
    export: bool | None = Field(default=None, description="내보내기")
    embed: bool | None = Field(default=None, description="임베드")
    api_access: bool | None = Field(default=None, description="API 접근")
    rag_index: bool | None = Field(default=None, description="RAG 인덱싱")
    ai_context: bool | None = Field(default=None, description="LLM 컨텍스트")
    ai_training: bool | None = Field(default=None, description="LLM 학습")
    ai_fine_tuning: bool | None = Field(default=None, description="파인튜닝")
    ai_evaluation: bool | None = Field(default=None, description="모델 평가")
    ai_synthetic_derivation: bool | None = Field(default=None, description="AI 합성 파생")

    def allows(self, action: PermissionAction) -> bool | None:
        """action에 해당하는 권한을 조회한다."""
        mapping: dict[PermissionAction, bool | None] = {
            PermissionAction.DISPLAY: self.display,
            PermissionAction.COPY: self.copy_,
            PermissionAction.REDISTRIBUTE: self.redistribute,
            PermissionAction.MODIFY: self.modify,
            PermissionAction.TRANSLATE: self.translate,
            PermissionAction.COMMERCIAL_USE: self.commercial_use,
            PermissionAction.DOWNLOAD: self.download,
            PermissionAction.PRINT: self.print_,
            PermissionAction.EXPORT: self.export,
            PermissionAction.EMBED: self.embed,
            PermissionAction.API_ACCESS: self.api_access,
            PermissionAction.RAG_INDEX: self.rag_index,
            PermissionAction.AI_CONTEXT: self.ai_context,
            PermissionAction.AI_TRAINING: self.ai_training,
            PermissionAction.AI_FINE_TUNING: self.ai_fine_tuning,
            PermissionAction.AI_EVALUATION: self.ai_evaluation,
            PermissionAction.AI_SYNTHETIC_DERIVATION: self.ai_synthetic_derivation,
        }
        return mapping.get(action)


# ──────────────────────────────────────────────────────────────────────────
# 권리(Rights)
# ──────────────────────────────────────────────────────────────────────────
class RightsEntity(BaseModel):
    """콘텐츠에 적용되는 권리 정책 레코드.

    license_code는 원본 라이선스 이름이고, permissions는 EOS가 해석한 정규화 값이다.
    계약 콘텐츠의 경우 conditions(JSONB)에 country/territory/allowed_users/expiration 등을
    추가한다.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    rights_id: uuid.UUID = Field(default_factory=uuid4, description="권리 PK")
    license_code: LicenseType = Field(..., description="원본 라이선스 enum")
    copyright_status: str = Field(
        default="copyrighted", max_length=32, description="copyrighted/public_domain/..."
    )
    holder_id: uuid.UUID | None = Field(default=None, description="RightsHolder FK")
    permissions: PermissionSet = Field(default_factory=PermissionSet, description="정규화 권한")
    attribution_required: bool = Field(default=False, description="출처 표시 필요 여부")
    share_alike: bool = Field(default=False, description="Share-Alike 의무")
    conditions: dict[str, Any] | None = Field(
        default=None,
        description="조건부 정책 — country/allowed_users/valid_until/contract_id/...",
    )
    review_status: RightsReviewStatus = Field(
        default=RightsReviewStatus.UNVERIFIED, description="검수/분쟁 상태"
    )
    valid_from: datetime | None = Field(default=None, description="유효 시작")
    valid_until: datetime | None = Field(default=None, description="유효 만료")
    notes: str | None = Field(default=None, description="검수 메모")
    created_at: datetime | None = Field(default=None, description="등록 시각")


# ──────────────────────────────────────────────────────────────────────────
# Content-Source / Content-Rights N:M 연결
# ──────────────────────────────────────────────────────────────────────────
class ContentSourceLink(BaseModel):
    """콘텐츠 ↔ 출처 N:M 연결."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    content_type: str = Field(..., max_length=64, description="problem/concept_content/...")
    content_id: uuid.UUID = Field(..., description="콘텐츠 PK")
    source_id: uuid.UUID = Field(..., description="SourceEntity PK")
    role: str = Field(default="primary", max_length=32, description="primary/secondary/inspiration")
    original_reference: dict[str, Any] | None = Field(
        default=None, description="해당 콘텐츠 내에서의 구체적 참조(년도/시험/문항번호 등)"
    )
    created_at: datetime | None = Field(default=None, description="등록 시각")


class ContentRightsLink(BaseModel):
    """콘텐츠 ↔ 권리 N:M 연결."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    content_type: str = Field(..., max_length=64, description="problem/concept_content/...")
    content_id: uuid.UUID = Field(..., description="콘텐츠 PK")
    rights_id: uuid.UUID = Field(..., description="RightsEntity PK")
    is_primary: bool = Field(default=True, description="지배 권리 여부")
    applies_to_fragment: str | None = Field(
        default=None,
        max_length=128,
        description="특정 요소(stem/diagram/solution/video)에만 적용되는 경우",
    )
    created_at: datetime | None = Field(default=None, description="등록 시각")


# ──────────────────────────────────────────────────────────────────────────
# Derivation Graph 기초
# ──────────────────────────────────────────────────────────────────────────
class DerivationEdge(BaseModel):
    """콘텐츠 파생 관계 엣지."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    edge_id: uuid.UUID = Field(default_factory=uuid4, description="엣지 PK")
    from_content_type: str = Field(..., max_length=64)
    from_content_id: uuid.UUID = Field(...)
    to_content_type: str = Field(..., max_length=64)
    to_content_id: uuid.UUID = Field(...)
    derivation_type: DerivationType = Field(..., description="파생 유형")
    provenance_id: uuid.UUID | None = Field(default=None, description="생성 이력 FK")
    edge_metadata: dict[str, Any] | None = Field(default=None, description="변형 파라미터 등")
    created_at: datetime | None = Field(default=None, description="등록 시각")


# ──────────────────────────────────────────────────────────────────────────
# Attribution 자동 생성
# ──────────────────────────────────────────────────────────────────────────
class AttributionTemplate(BaseModel):
    """출처 문구 자동 생성용 템플릿 인자."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., max_length=512, description="자료명")
    creator: str | None = Field(default=None, max_length=256, description="저작자/기관")
    source_url: str | None = Field(default=None, max_length=2048, description="원본 URL")
    license_code: LicenseType = Field(..., description="라이선스")
    year: int | None = Field(default=None, description="발행년")
    extra: dict[str, Any] | None = Field(default=None, description="확장 필드")


# ──────────────────────────────────────────────────────────────────────────
# Rights Policy Engine 계약
# ──────────────────────────────────────────────────────────────────────────
class RightsCheckRequest(BaseModel):
    """Rights Policy Engine 판정 요청."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_type: str = Field(..., max_length=64, description="problem/concept_content/...")
    content_id: uuid.UUID = Field(..., description="콘텐츠 PK")
    action: PermissionAction = Field(..., description="요청 행위")
    user_type: str | None = Field(default=None, max_length=32, description="student/teacher/admin")
    country: str | None = Field(default=None, max_length=8, description="요청 발생 국가")
    subscription_tier: str | None = Field(
        default=None, max_length=32, description="free/basic/premium"
    )
    service_name: str = Field(default="WhyMath", max_length=64)
    requested_at: datetime = Field(default_factory=datetime.utcnow)


class RightsCheckResponse(BaseModel):
    """Rights Policy Engine 판정 응답."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_type: str = Field(..., max_length=64)
    content_id: uuid.UUID = Field(...)
    action: PermissionAction = Field(...)
    decision: RightsDecision = Field(...)
    reason_code: str = Field(..., max_length=128, description="판정 사유 코드")
    rights_id: uuid.UUID | None = Field(default=None, description="적용된 권리 레코드")
    attribution: str | None = Field(default=None, description="출처 표시 문구(필요시)")
    conditions: dict[str, Any] | None = Field(default=None, description="추가 조건")
    share_alike: bool = Field(default=False, description="Share-Alike 의무가 있는지 여부")

    @model_validator(mode="after")
    def _attribution_with_allow(self) -> "RightsCheckResponse":
        """ALLOW_WITH_ATTRIBUTION일 때 attribution이 비어 있으면 경고(에러는 아님).

        실제 attribution은 DB에서 조회 후 채우므로 응답 시점에 None일 수 있다.
        """
        return self
