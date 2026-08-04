"""학생 결함 신고 HTTP 표면 — RPT-01(`docs/architecture/service_operations_gap_review.md` §3 D1).

엔드포인트(prefix `/v1/reports`):
  - POST /v1/reports/defects — 결함 신고 1건 접수(append-only). 201.

**무인증**(`ConsentedUser` 등 인증 의존성 없음) — `DefectReport`는 `user_id`를 저장하지 않으므로
(RPT-01 설계 핵심) 인증을 강제할 이유가 없다. 남용 방어는 저장 기반 방어를 신설하지 않고 기존
`api/_rate_limit.py`(SEC-08 선례)의 IP 단위 한도(`RateLimitedIpDefectReport`, 전용 카테고리)로
건다.

요청 바디는 `category`(폐쇄 6종)·`problem_id`(선택, plain UUID)만 받는다 — `report_id`·
`reported_at`은 서버가 생성(클라이언트가 지정 불가, `DefectReportCreate`가 그 두 필드를
스키마에서 아예 제외해 구조적으로 차단한다).

append-only — 이 라우터는 PATCH/PUT/DELETE를 노출하지 않는다(`tests/backend/api/
test_reports.py`의 `TestAppendOnly`가 회귀 동결).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._rate_limit import RateLimitedIpDefectReport
from whymath_backend.db.models.audit import DefectReport
from whymath_backend.db.session import get_session
from whymath_backend.schema.audit import DefectReport as DefectReportSchema
from whymath_backend.schema.enums import DefectCategory

router = APIRouter(prefix="/v1/reports", tags=["reports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class DefectReportCreate(BaseModel):
    """결함 신고 요청 바디 — 카테고리 + 대상 문항 참조만(자유서술 0).

    `report_id`·`reported_at`은 여기 없다(서버 전용 생성 필드) — 클라이언트가 신고 시각·PK를
    지정할 수 없게 스키마 레벨에서 차단한다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    category: DefectCategory = Field(description="결함 카테고리(폐쇄 6종 — 자유서술 없음)")
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="신고 대상 문항 id(선택 — plain UUID). 문항 무관 신고(UI문제 등)는 생략.",
    )


@router.post(
    "/defects",
    status_code=status.HTTP_201_CREATED,
    response_model=DefectReportSchema,
    summary="학생 결함 신고 접수 (append-only, 무인증)",
    dependencies=[RateLimitedIpDefectReport],
)
async def create_defect_report(
    body: DefectReportCreate,
    session: SessionDep,
) -> DefectReportSchema:
    """결함 신고 1행 적재 — `user_id` 미저장(RPT-01 설계). 항상 201(재시도 안전한 append-only).

    `report_id`는 DB `gen_random_uuid()`가, `reported_at`은 DB `now()`가 채운다 — 클라이언트
    입력에서 유래하지 않는다(schema 자체에 그 필드가 없어 구조적으로 차단). ORM은 `api/me.py`
    `_delete_owned_resource`의 `DeletionAudit(...)` 직접 생성 패턴을 그대로 따른다(감사 행
    생성은 schema 왕복 없이 필요한 컬럼만 채워 DB server_default에 나머지를 맡긴다).
    """
    orm = DefectReport(category=body.category, problem_id=body.problem_id)
    session.add(orm)
    await session.commit()
    await session.refresh(orm)
    return orm.to_schema()
