"""Subject-neutral 교육과정(curriculum) HTTP API — CUR-10 Framework/Version 실물의 조회 표면.

엔드포인트(prefix `/v1` — 이 파일은 curricula·learning-outcomes 두 리소스를 한 라우터로 묶는다):
  - GET /v1/curricula                       — 프레임워크 목록(framework_id 오름차순, limit/offset).
  - GET /v1/curricula/{framework_id}        — 프레임워크 단건 + 소속 버전 목록(CUR-10 Version).
  - GET /v1/curricula/{framework_id}/nodes  — CurriculumEntry 기반 *개념 노드 뷰*(구조 투영).
  - GET /v1/learning-outcomes/{norm_id}     — 성취기준(학습 성과) 단건(AchievementStandard).

Subject-neutral 원칙(CUR-11 acceptance ②):
  `/math/grade/10/unit/3` 같은 *과목 특화 경로*를 만들지 않는다 — 과목·국가·학년은 경로가 아니라
  **데이터 축**이며 쿼리 필터(`subject`·`country_code` 등)로만 표현한다. 수학 외 과목 확장 시
  경로 구조가 그대로 재사용된다(EOS Curriculum Semantic Backbone ADR Phase 1 항목 5).

세션 결선: `db.session.get_session`을 `Annotated[AsyncSession, Depends(...)]`로 받는다
(concepts.py 선례 — Depends 기본인자(B008) 회피). 전부 읽기 전용이라 commit 없음.

인가 판단(선례 실측 근거 명기 — CUR-11 설계 지침):
  다섯 엔드포인트 모두 GET·무인증이다. 선례 = concepts.py·problems.py의 GET(단건·목록·엣지)
  무인증 유지("공개 카탈로그" — SEC-07 D1이 CUD만 `RequireContentAdmin`으로 봉인하고 GET은
  의도적으로 열어 둠). 여기 노출되는 것은 교육과정 *구조 메타데이터*(프레임워크·버전·개념 노드
  투영·NCIC 공공누리 1유형 성취기준)뿐이며 학생 데이터·PII가 없어 같은 공개 카탈로그 축이다.
  쓰기(POST/PATCH/DELETE)는 이 태스크 범위 밖 — 생기면 RequireContentAdmin 선례를 따라야 한다.

저작권 레일(CLAUDE.md·기존 노출 계약 실측):
  - CurriculumFramework/Version/Entry: 교육과정 코드·단원명·구조 라벨만(사실정보) — 본문류 필드
    자체가 모델에 없다(curriculum_entry.py "법적 메모").
  - AchievementStandard: 성취기준 본문(statement 계열)·해설은 **NCIC 공공누리 제1유형**이라 본문
    노출이 허용되는 예외 출처다(검정교과서·EBS·평가원 본문 금지와 대비 — schema/standard.py
    "법적 메모"·`licensing_safety.md` 가이드 v2.0). 출처 표시 의무는 응답에 포함되는
    `source_url`(required 필드)이 이행한다.

7계층: 이 라우터는 L1 영속 모델(ORM)·schema 계약의 *조회 표면*(L5 api)일 뿐 수학 로직이 없다.
노드 뷰의 깊이 해석(required_depth)도 셀 값을 그대로 투영한다 — read-time 해석 로직은
`l1/curriculum/curriculum_resolve.py`(CurriculumDepthResolver) 소관이며 여기서 재구현하지 않는다.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.curriculum_entry import CurriculumEntry
from whymath_backend.db.models.curriculum_framework import CurriculumFramework
from whymath_backend.db.models.curriculum_version import CurriculumVersion
from whymath_backend.db.session import get_session
from whymath_backend.schema.curriculum_framework import (
    CurriculumFramework as CurriculumFrameworkSchema,
)
from whymath_backend.schema.curriculum_version import (
    CurriculumVersion as CurriculumVersionSchema,
)
from whymath_backend.schema.enums import CurriculumLicense, RequiredDepth
from whymath_backend.schema.standard import (
    AchievementStandard as AchievementStandardSchema,
)

# 두 리소스(curricula·learning-outcomes)를 한 파일·한 라우터로 묶기 위해 prefix는 `/v1`이다
# (파일당 라우터 1개 = app.py 결선 관례 유지 — 리소스별 prefix 대신 경로에 리소스명을 명시).
router = APIRouter(prefix="/v1", tags=["curriculum"])

# get_session 의존성 — Annotated 메타데이터(B008 회피, concepts.py 선례).
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 경로 파라미터 제약 — ORM 컬럼 길이와 일치시켜 초과 입력을 422로 조기 거부한다
# (framework_id=String(64)·norm_id=String(32) — 각 ORM 모듈 실측).
FrameworkIdPath = Annotated[
    str,
    Path(min_length=1, max_length=64, description="프레임워크 식별자 (예: 'KR_NC_2022')"),
]
NormIdPath = Annotated[
    str,
    Path(min_length=1, max_length=32, description="성취기준 norm_id (예: '2022_2수_01_01')"),
]


# ──────────────────────────────────────────────────────────────────────────
# 응답 모델 — 프레임워크 상세(+버전)·개념 노드 뷰
# ──────────────────────────────────────────────────────────────────────────
class CurriculumFrameworkDetail(BaseModel):
    """프레임워크 단건 상세 — 프레임워크 본체 + 소속 버전 목록.

    CUR-10이 신설한 `CurriculumVersion`(temporal curriculum 스냅숏)을 별도 라우트 없이
    상세 응답에 동봉한다 — 프레임워크:버전은 1:N 소유 관계라 상세 조회의 자연스러운 구성이며,
    라우트 표면 최소화(acceptance ①의 5종 밖 신규 경로 발명 금지)와도 정합한다.
    """

    model_config = ConfigDict(extra="forbid")

    framework: CurriculumFrameworkSchema = Field(description="프레임워크 본체")
    versions: list[CurriculumVersionSchema] = Field(
        description="소속 버전 목록 — version_label 오름차순(프레임워크 내 유일·안정 정렬)"
    )


class CurriculumNodeView(BaseModel):
    """CurriculumEntry 기반 *개념 노드 뷰* — 매트릭스 셀의 노드 지향 구조 투영.

    셀(31필드) 전체가 아니라 노드 관점에 필요한 축만 추린다: 식별(entry/concept/국가/과목/
    프레임워크) · 위계(선행/후행 개념) · 매핑(성취기준 코드) · 배치(학년·영역) · 깊이 ·
    상태(존재·신뢰도) · 라이선스 추적(license_id·source_name — 공공누리 출처 표시 축).
    제외 축과 이유: 표기(notation_* — 렌더러 관심사·Concept Purity), 맥락 서술(introduced_context
    — 노드 뷰는 구조만), 교과서 참조(textbook_unit_refs — 별도 매핑 소비처 몫), 감사 필드
    (verified_by·created_at·updated_at). 셀 원본 전체가 필요한 소비처는 후속 태스크에서 별도
    표면을 논의한다 — 이 뷰의 계약을 셀 스키마 진화로부터 절연하는 것이 목적이다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    entry_id: str = Field(description="셀 표면 식별자 (CurriculumEntry PK)")
    concept_id: str = Field(description="개념 식별자 (개념 그래프 키 공간·느슨참조)")
    country_code: str = Field(description="국가 코드 (예: 'KR')")
    subject: str = Field(description="교과 레벨 과목 축 (예: '수학' — 데이터 축, 경로 아님)")
    framework_id: str | None = Field(description="소속 프레임워크 (CUR-10 연결·null=미분류)")
    domain_label: str | None = Field(description="영역 라벨 (예: '수와 연산')")
    sub_domain_label: str | None = Field(description="세부 영역 라벨")
    introduced_grade: int | None = Field(description="도입 학년 (교육과정 구조 정보)")
    grade_band: str | None = Field(description="학년군 라벨")
    required_depth: RequiredDepth | None = Field(
        description="요구 깊이 (awareness/procedural/conceptual/mastery — 셀 값 그대로 투영)"
    )
    cognitive_level: str | None = Field(description="인지 수준 라벨")
    is_present: bool = Field(description="그 나라 교육과정에 개념이 존재하는지")
    confidence: float = Field(description="셀 신뢰도 [0,1]")
    national_standard_codes: list[str] = Field(
        description="매핑된 국가 성취기준 *코드* 목록 (사실정보·본문 아님)"
    )
    prerequisite_concept_ids: list[str] = Field(description="선행 개념 식별자 목록")
    followup_concept_ids: list[str] = Field(description="후행 개념 식별자 목록")
    license_id: CurriculumLicense = Field(description="셀 단위 라이선스 추적 식별자")
    source_name: str = Field(description="출처 명칭 (출처 표시 축)")


def _to_node_view(entry: CurriculumEntry) -> CurriculumNodeView:
    """ORM 셀 → 노드 뷰 투영 (배열 NULL은 빈 목록으로 정규화 — 소비처 분기 제거)."""
    return CurriculumNodeView(
        entry_id=entry.entry_id,
        concept_id=entry.concept_id,
        country_code=entry.country_code,
        subject=entry.subject,
        framework_id=entry.framework_id,
        domain_label=entry.domain_label,
        sub_domain_label=entry.sub_domain_label,
        introduced_grade=entry.introduced_grade,
        grade_band=entry.grade_band,
        required_depth=entry.required_depth,
        cognitive_level=entry.cognitive_level,
        is_present=entry.is_present,
        confidence=float(entry.confidence),
        national_standard_codes=list(entry.national_standard_codes or []),
        prerequisite_concept_ids=list(entry.prerequisite_concept_ids or []),
        followup_concept_ids=list(entry.followup_concept_ids or []),
        license_id=entry.license_id,
        source_name=entry.source_name,
    )


# ──────────────────────────────────────────────────────────────────────────
# GET /v1/curricula — 프레임워크 목록
# ──────────────────────────────────────────────────────────────────────────
@router.get(
    "/curricula",
    response_model=list[CurriculumFrameworkSchema],
    summary="교육과정 프레임워크 목록",
)
async def list_curricula(
    session: SessionDep,
    country: Annotated[
        str | None, Query(min_length=1, max_length=16, description="국가 코드 필터 (예: 'KR')")
    ] = None,
    status_filter: Annotated[
        Literal["draft", "review", "approved", "published", "deprecated", "superseded"] | None,
        Query(alias="status", description="생명주기 상태 필터"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="페이지 크기")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 행 수")] = 0,
) -> list[CurriculumFrameworkSchema]:
    """프레임워크 목록 — `framework_id` 오름차순(PK·동률 없는 전순서), limit/offset.

    국가·상태는 *데이터 축*이라 쿼리 필터다(subject-neutral — 경로에 국가/과목을 넣지 않는다).
    `status`는 예약어 충돌(파이썬 내장 아님·fastapi.status와의 이름 충돌)을 피해 파라미터명은
    `status_filter`, 와이어 이름은 `alias="status"`로 둔다.
    """
    stmt = select(CurriculumFramework)
    if country is not None:
        stmt = stmt.where(CurriculumFramework.country == country)
    if status_filter is not None:
        stmt = stmt.where(CurriculumFramework.status == status_filter)
    stmt = stmt.order_by(CurriculumFramework.framework_id).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


# ──────────────────────────────────────────────────────────────────────────
# GET /v1/curricula/{framework_id} — 프레임워크 단건 + 버전 목록
# ──────────────────────────────────────────────────────────────────────────
@router.get(
    "/curricula/{framework_id}",
    response_model=CurriculumFrameworkDetail,
    summary="교육과정 프레임워크 단건(+버전 목록)",
)
async def read_curriculum(
    framework_id: FrameworkIdPath,
    session: SessionDep,
) -> CurriculumFrameworkDetail:
    """프레임워크 단건 조회 — 없으면 404. 소속 버전(CUR-10 CurriculumVersion)을 동봉한다.

    버전 정렬은 `version_label` 오름차순 — 같은 프레임워크 내 UNIQUE(CUR-10
    `uq_curriculum_version_framework_label`)라 안정 정렬이다.
    """
    orm = await session.get(CurriculumFramework, framework_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"교육과정 프레임워크를 찾을 수 없습니다: {framework_id}",
        )
    stmt = (
        select(CurriculumVersion)
        .where(CurriculumVersion.framework_id == framework_id)
        .order_by(CurriculumVersion.version_label)
    )
    result = await session.execute(stmt)
    versions = [row.to_schema() for row in result.scalars().all()]
    return CurriculumFrameworkDetail(framework=orm.to_schema(), versions=versions)


# ──────────────────────────────────────────────────────────────────────────
# GET /v1/curricula/{framework_id}/nodes — CurriculumEntry 기반 개념 노드 뷰
# ──────────────────────────────────────────────────────────────────────────
@router.get(
    "/curricula/{framework_id}/nodes",
    response_model=list[CurriculumNodeView],
    summary="프레임워크의 개념 노드 뷰 (CurriculumEntry 기반)",
)
async def list_curriculum_nodes(
    framework_id: FrameworkIdPath,
    session: SessionDep,
    subject: Annotated[
        str | None,
        Query(min_length=1, max_length=64, description="교과 레벨 과목 필터 (예: '수학')"),
    ] = None,
    country_code: Annotated[
        str | None, Query(min_length=1, max_length=16, description="국가 코드 필터 (예: 'KR')")
    ] = None,
    present_only: Annotated[
        bool,
        Query(description="true면 is_present=true 셀만 (그 교육과정에 실재하는 개념만)"),
    ] = False,
    limit: Annotated[int, Query(ge=1, le=200, description="페이지 크기")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 행 수")] = 0,
) -> list[CurriculumNodeView]:
    """프레임워크에 연결된 CurriculumEntry 셀들을 *개념 노드 뷰*로 투영 — 프레임워크 없으면 404.

    정렬은 `entry_id`(PK) 오름차순 — 동률 없는 전순서라 페이지네이션이 안정적이다. 과목·국가는
    데이터 축 필터다(subject-neutral). `framework_id`가 NULL인 셀(CUR-10 이전 미분류 잔존)은
    어떤 프레임워크의 노드 뷰에도 나타나지 않는다 — 정직한 미분류이며 조용한 귀속 날조를 하지
    않는다(백필은 CUR-10 마이그레이션·로더 몫).
    """
    if await session.get(CurriculumFramework, framework_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"교육과정 프레임워크를 찾을 수 없습니다: {framework_id}",
        )
    stmt = select(CurriculumEntry).where(CurriculumEntry.framework_id == framework_id)
    if subject is not None:
        stmt = stmt.where(CurriculumEntry.subject == subject)
    if country_code is not None:
        stmt = stmt.where(CurriculumEntry.country_code == country_code)
    if present_only:
        stmt = stmt.where(CurriculumEntry.is_present.is_(True))
    stmt = stmt.order_by(CurriculumEntry.entry_id).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [_to_node_view(row) for row in result.scalars().all()]


# ──────────────────────────────────────────────────────────────────────────
# GET /v1/learning-outcomes/{norm_id} — 성취기준(학습 성과) 단건
# ──────────────────────────────────────────────────────────────────────────
@router.get(
    "/learning-outcomes/{norm_id}",
    response_model=AchievementStandardSchema,
    summary="학습 성과(성취기준) 단건 조회",
)
async def read_learning_outcome(
    norm_id: NormIdPath,
    session: SessionDep,
) -> AchievementStandardSchema:
    """성취기준 단건 조회(norm_id PK) — 없으면 404.

    리소스명이 subject-neutral 어휘 'learning-outcomes'인 이유: 성취기준은 한국 국가 교육과정의
    용어이고, CASE 등 국제 체계에서는 learning outcome/CFItem에 대응한다(EOS ADR §CASE 매핑 —
    CUR-14). 응답은 `schema.AchievementStandard` 전체다 — 본문(statement 계열)·해설은 NCIC
    공공누리 제1유형이라 노출 허용이며(모듈 docstring 저작권 레일), 출처 표시 의무는 응답의
    `source_url` 필드가 이행한다.
    """
    orm = await session.get(AchievementStandard, norm_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"학습 성과(성취기준)를 찾을 수 없습니다: {norm_id}",
        )
    return orm.to_schema()
