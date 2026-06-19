"""개인정보 열람·이동권 — 인증된 *본인*의 학습/진단 데이터를 구조화 JSON으로 모아 반환.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.3 개인정보 설계 원칙(R11). 삭제권
(`erasure.erase_user`·#242)·보존 파기(`retention`·#253/#254)의 *짝*인 **열람·이동권**(GDPR
data access·portability)이다. 삭제권이 이미 *어떤 테이블이 사용자 PII인지* 열거(`_ERASURE_PLAN`)
하므로, 그 인벤토리의 *학습/진단 subset*을 **읽기**로 재사용해 본인 데이터를 한데 모은다.

범위(첫 증분·plan-driven 확장): `_EXPORT_PLAN`의 5종(학습 세션·시도·진단·개념 숙달 이력·능력
스냅샷) + `user_profile` 단건. **보안 항목 영구 제외**: `device_credential`·`refresh_token_session`
(로그인 토큰·기기 자격 — export 시 노출은 보안 위험이고 "개인 학습 데이터"가 아니다). 대화·시계열
지표·오개념 가설·증거·동의/트랙/페르소나 이력·외부 store 실조회·비동기 job은 후속 — 미포함을
*조용히 넘기지 않고* `not_included`로 정직히 드러낸다(날조 0·완전성 정직).

외부 store(ClickHouse 행동 로그·S3 객체·Redis 캐시)는 RDB 밖이라 이 export(PostgreSQL)에 *포함되지
않는다* — `external_export_pending`으로 *구조화*해 ops가 가시화한다(#252 `external_erasure_targets`
미러·정보 누출 방지로 student-facing 응답엔 인프라 store명/locator 미노출·ops 로그만).

저장소 패턴: `AsyncSession` 주입·**읽기 전용**(commit 0·flush 0·`select`만·원시 SQL 0). per-user
본인 데이터라 HTTP 노출이 맞다("전역 집계는 ops CLI" 제약은 *전역*에만 — 이건 본인 1명).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.base import Base
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.db.models.user import UserProfile

__all__ = [
    "ExternalDataLocation",
    "UserDataExport",
    "export_user_data",
    "external_export_pending",
]

# export 계획 — (모델, user 컬럼명, 응답 카테고리 키). `_ERASURE_PLAN`(erasure.py)의 *학습/진단
# subset*이다. 보안 토큰(device_credential·refresh_token_session)·시계열·대화 등은 제외(보안·범위·
# 후속). 모든 모델은 `to_schema()`를 보유한다(JSON-safe 직렬화).
_EXPORT_PLAN: tuple[tuple[type[Base], str, str], ...] = (
    (LearningSession, "user_id", "learning_sessions"),
    (ProblemAttempt, "user_id", "problem_attempts"),
    (Assessment, "user_id", "assessments"),
    (ConceptMasteryHistory, "user_id", "concept_mastery_history"),
    (AbilitySnapshot, "user_id", "ability_snapshots"),
)

# 이 export에 *포함되지 않은* 범위 — student-facing 사용자 친화 설명(인프라 store명·키 미노출).
# 부분 export임을 정직히 알린다(GDPR 완전성·날조 0). 외부 store 상세는 ops 로그(아래 함수)로만.
_NOT_INCLUDED: tuple[str, ...] = (
    "대화 이력(개별 메시지 포함)은 이 내보내기에 미포함 — 후속 확장 예정.",
    "학습 시계열 지표(일별·행동)·세부 시도 이벤트는 미포함 — 후속 확장 예정.",
    "오개념 가설·진단 증거·동의 이력·트랙/페르소나 이력은 미포함 — 후속 확장 예정.",
    "행동 로그·업로드 이미지·세션 캐시 등 외부 시스템 보관 데이터는 미포함(별도 시스템).",
    "보안 항목(로그인 토큰·기기 자격)은 보안상 내보내지 않는다.",
)


class ExternalDataLocation(BaseModel):
    """RDB *밖* store에 남은 본인 데이터 — 이 export(PG)에 *포함되지 않음*. ops용 구조화. 불변.

    `export_user_data`는 PostgreSQL만 읽는다. 외부 store(ClickHouse 행동 로그·S3/MinIO 객체·Redis
    캐시)는 RDB 밖·별도 클라이언트라 이 export에 *포함되지 않는다*. 이 모델은 그 미포함을 *조용히
    넘기지 않고*(날조 0·GDPR 범위 정직) ops가 인지·후속 export할 체크리스트로 *구조화*한다.
    `locator`는 *정확한 키 문법을 단정하지 않는다* — 키/프리픽스 규약은 인프라 정의라 user_id 연관
    대상만 서술한다(없는 사실 날조 금지). 정보 누출 방지로 student-facing 응답엔 싣지 않는다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    store: str = Field(description="외부 store 식별자(clickhouse·s3·redis).")
    data: str = Field(description="그 store가 보유한 사용자 데이터 설명(한국어).")
    locator: str = Field(description="대상(user_id 연관·키 규약은 인프라 정의·단정 아님).")


def external_export_pending(user_id: uuid.UUID) -> tuple[ExternalDataLocation, ...]:
    """이 사용자에 대해 외부 store에 남아 *이 export에 포함되지 않은* 데이터 목록(per-user·구조화).

    `export_user_data`의 PostgreSQL 읽기 *밖*에 있는 store들을 명시한다 — export 범위를 정직히
    드러내(GDPR·날조 0) ops/후속 오케스트레이터가 인지·집행하게 한다. 순수 함수(외부 호출 0)·
    locator는 *키 문법을 단정하지 않고* user_id 연관 대상만 서술한다(인프라 키 규약 날조 금지).
    """
    uid = str(user_id)
    return (
        ExternalDataLocation(
            store="clickhouse",
            data="학습 행동 로그(이벤트 스트림·분석)",
            locator=f"student_id_hash(user_id={uid}) 연관 이벤트 행 — 해시 매핑은 적재 규약 따름",
        ),
        ExternalDataLocation(
            store="s3",
            data="업로드 이미지·렌더 객체(손글씨 풀이·시각화)",
            locator=f"user_id={uid} 연관 업로드/렌더 객체(프리픽스 규약은 인프라 정의)",
        ),
        ExternalDataLocation(
            store="redis",
            data="세션·핫 캐시(작업메모리·레이트리밋)",
            locator=f"user_id={uid} 연관 세션·캐시 키(TTL 만료가 기본)",
        ),
    )


class UserDataExport(BaseModel):
    """열람·이동권 export 결과 — 본인 학습/진단 데이터 + 미포함 범위 고지(정직). 불변(frozen).

    `data`는 카테고리(`_EXPORT_PLAN` 키)→행 리스트(각 행은 `to_schema().model_dump(mode="json")`).
    `not_included`는 *이 export에 빠진 범위*를 사용자 친화로 알린다(부분 export 정직·완전성). 외부
    store 상세(인프라 store명·locator)는 *싣지 않는다*(정보 누출 방지·ops 로그로만).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: uuid.UUID = Field(description="데이터 주체(인증된 본인).")
    exported_at: datetime = Field(description="export 생성 시각(UTC).")
    user_profile: dict[str, Any] | None = Field(
        default=None, description="계정 프로필 단건(없으면 None)."
    )
    data: dict[str, list[dict[str, Any]]] = Field(
        description="카테고리→행 리스트(학습/진단 데이터·JSON-safe)."
    )
    not_included: tuple[str, ...] = Field(
        description="이 export에 미포함된 범위 고지(부분 export 정직·완전성)."
    )


def _row_to_json(row: Any) -> dict[str, Any]:
    """ORM 행 → JSON-safe dict(`to_schema().model_dump(mode="json")`). `_EXPORT_PLAN` 모델 전제.

    `to_schema()`가 Pydantic 스키마로 검증 복원하므로 enum·UUID·datetime이 JSON 안전하게 직렬화된다.
    """
    return cast("dict[str, Any]", row.to_schema().model_dump(mode="json"))


async def export_user_data(session: AsyncSession, *, user_id: uuid.UUID) -> UserDataExport:
    """본인의 학습/진단 데이터를 `_EXPORT_PLAN`대로 모아 구조화 export로 반환한다(읽기 전용).

    각 테이블을 `select(...).where(user컬럼 == user_id)`로 조회(PK 정렬·결정적)하고
    `to_schema().model_dump(mode="json")`로 직렬화한다. `user_profile`은 단건. **commit/flush 0**
    (읽기 전용·저장소 패턴). 외부 store는 포함하지 않고 `external_export_pending`(ops)로 별도 고지.
    멱등·부작용 0 — 같은 user는 같은 데이터(시각만 갱신).
    """
    data: dict[str, list[dict[str, Any]]] = {}
    for model, column, category in _EXPORT_PLAN:
        result = await session.execute(
            select(model)
            .where(getattr(model, column) == user_id)
            .order_by(*model.__mapper__.primary_key)
        )
        data[category] = [_row_to_json(row) for row in result.scalars().all()]

    profile_result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile_row = profile_result.scalars().first()
    user_profile = _row_to_json(profile_row) if profile_row is not None else None

    return UserDataExport(
        user_id=user_id,
        exported_at=datetime.now(UTC),
        user_profile=user_profile,
        data=data,
        not_included=_NOT_INCLUDED,
    )
