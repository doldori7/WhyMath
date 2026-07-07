"""개인정보 삭제권(R11) — 한 사용자의 *모든* 학생-연결 데이터 단일 트랜잭션 영구 삭제.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.3 개인정보 설계 원칙(R11) — "삭제권
행사 시: student_id 기준 evidence_links → … 연쇄 삭제, BKT 상태 초기화, pgvector 임베딩 삭제까지
**한 트랜잭션 단위로**". 본 모듈은 그 *오케스트레이션 좌석*이다. 미성년자의 인지·행동 정밀
프로파일(가설·증거·BKT·θ·대화·행동 로그)을 하나의 원자적 삭제로 지운다(부분 삭제 0).

왜 앱레벨 명시 삭제인가(정직):
  레포 FK 실태(2026-06-17 전수 조사) — 학생-연결 17개 테이블 중 `evidence_links`만 user_profile
  FK `ON DELETE CASCADE`다. 나머지는 ① user_id FK가 **NO ACTION**(user_profile 삭제를 *차단*)
  이거나 ② **느슨참조**(FK 0·hypertable — user 삭제 시 *고아 잔존*)다. 따라서 user_profile 한
  행을 지우는 것만으론 삭제권이 충족되지 않는다 — 자식·고아를 *명시 삭제*해야 한다. FK 전부에
  CASCADE를 거는 대안은 대규모 마이그레이션 + 전역 삭제 의미 변경(오삭제 시 연쇄 위험)이라
  배제하고, **명시·감사 가능·마이그레이션 0**인 앱레벨 오케스트레이션을 택한다(`_ERASURE_PLAN`).

삭제 순서(FK 의존 안전·단일 트랜잭션):
  1. `dialogue`(→ `dialogue_turn` DB CASCADE) → 2. `problem_attempt` → 3. `learning_session`
  (자식 attempt는 위에서 선삭제) → 4~ 나머지 user_id/student_id 테이블(서로 의존 없음·user_profile
  만 참조) → 마지막에 `user_profile`. 같은 트랜잭션이라 어느 단계 실패도 전부 롤백(부분 삭제 0).

감사(GDPR 증빙·slice 57 동형): user_profile 삭제 *전* `DeletionAudit` 1행 적재
  (`resource_type="user_profile"`·user_id·콘텐츠 미저장). `deletion_audit`는 user FK가 없어
  사용자 삭제 후에도 *잔존*한다(compliance 로그 독립성·audit.py 설계).

저장소 패턴: `AsyncSession` 주입·**commit은 호출자**(엔드포인트 트랜잭션과 합류·flush만). 순수
ORM/쿼리빌더만(`delete(Model).where(...)` — 원시 SQL 0·CLAUDE.md). `dialogue_turn`은 user 컬럼이
없어 `dialogue` CASCADE로 제거(보고에는 cascade로 표기).

외부 store(ClickHouse 행동 로그·S3 객체·Redis 세션)는 RDB 밖이라 이 단일 트랜잭션에 못 넣는다 —
삭제를 *조용히 누락하지 않고* `external_erasure_targets`로 *구조화*해
`ErasureReport.pending_external`에 담는다(GDPR 범위 정직·날조 0·ops 후속 체크리스트). 실제 외부
삭제 *집행*은 후속.

범위 밖(후속): 삭제권 *요청* API 엔드포인트(인증·본인 확인·법정대리인 동의 흐름)·보존 기한 배치
(`evidence_store.purge_expired`는 retention 전용·여기는 user 단위)·외부 store 삭제 *집행*
(ClickHouse·S3·Redis 클라이언트 — 현재는 `pending_external` 매니페스트로 명시만).
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.base import Base
from whymath_backend.db.models.activity import AttemptEvent, LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
    SkillMasteryHistory,
)
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.device import DeviceCredential
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.evidence_link import EvidenceLink
from whymath_backend.db.models.misconception_hypothesis import MisconceptionHypothesisRecord
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.timeseries import DailyLearningMetrics, UserBehaviorMetrics
from whymath_backend.db.models.user import (
    UserPersonaHistory,
    UserProfile,
    UserStateSnapshot,
    UserTrackHistory,
)
from whymath_backend.schema.enums import AuditResourceType

__all__ = [
    "ErasureReport",
    "ExternalErasureTarget",
    "erase_user",
    "external_erasure_targets",
]

# 삭제 계획 — (모델, user 컬럼명) child→parent 순서(FK 의존 안전). user_profile·dialogue_turn
# 제외: user_profile은 마지막에 명시 삭제, dialogue_turn은 dialogue CASCADE로 자동 제거.
#   · dialogue 먼저(→ dialogue_turn cascade) · problem_attempt 먼저(learning_session보다).
#   · 나머지는 user_profile만 참조(상호 의존 0)라 순서 무관.
_ERASURE_PLAN: tuple[tuple[type[Base], str], ...] = (
    (Dialogue, "user_id"),  # → dialogue_turn DB CASCADE
    (ProblemAttempt, "user_id"),  # learning_session보다 먼저(session→attempt CASCADE 역순 방지)
    (LearningSession, "user_id"),
    (AttemptEvent, "user_id"),  # 느슨참조·hypertable(고아 방지)
    (Assessment, "user_id"),
    (ConceptMasteryHistory, "user_id"),  # BKT 숙달·느슨참조·hypertable
    (SkillMasteryHistory, "user_id"),  # 스킬 숙달·느슨참조·hypertable
    (AbilitySnapshot, "user_id"),  # IRT θ·느슨참조
    (DailyLearningMetrics, "user_id"),  # 느슨참조·hypertable
    (UserBehaviorMetrics, "user_id"),  # 느슨참조·hypertable
    (MisconceptionHypothesisRecord, "user_id"),  # 활성 오개념 가설
    (EvidenceLink, "student_id"),  # 증거 그래프(user CASCADE이나 명시 삭제로 보고 일관)
    (DeviceCredential, "user_id"),
    (RefreshTokenSession, "user_id"),
    (ParentalConsent, "user_id"),
    (UserTrackHistory, "user_id"),
    (UserPersonaHistory, "user_id"),
    (UserStateSnapshot, "user_id"),
)


class ExternalErasureTarget(BaseModel):
    """`erase_user`가 *직접 삭제하지 않는* 외부 store의 사용자 데이터 — 별도 ops 삭제 대상. 불변.

    `erase_user`는 PostgreSQL(`_ERASURE_PLAN`)만 단일 트랜잭션으로 지운다. 외부 store(ClickHouse
    행동 로그·S3/MinIO 객체·Redis 세션)는 RDB 밖·별도 클라이언트/비동기 인프라라 그 트랜잭션에
    *포함되지 않는다*. 이 모델은 그 누락을 *조용히 넘기지 않고*(날조 0·GDPR 삭제 범위 정직) ops가
    집행할 체크리스트로 *구조화*한다. `locator`는 *정확한 키 문법을 단정하지 않는다* — 키/프리픽스
    규약은 인프라 정의라 user_id 연관 대상을 서술만 한다(없는 사실 날조 금지).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    store: str = Field(description="외부 store 식별자(clickhouse·s3·redis).")
    data: str = Field(description="그 store가 보유한 사용자 데이터 설명(한국어).")
    locator: str = Field(description="삭제 대상(user_id 연관·키 규약은 인프라 정의·단정 아님).")
    reason: str = Field(description="`erase_user` 단일 TX에 *포함되지 않는* 이유.")


def external_erasure_targets(user_id: uuid.UUID) -> tuple[ExternalErasureTarget, ...]:
    """이 사용자에 대해 외부 store에 남아 *별도 삭제가 필요한* 데이터 목록(per-user·구조화).

    `erase_user`의 PostgreSQL 단일 트랜잭션 *밖*에 있는 store들을 명시한다 — 삭제 범위를 정직히
    드러내(GDPR·날조 0) ops/후속 오케스트레이터가 집행하게 한다. 순수 함수(외부 호출 0)·locator는
    *키 문법을 단정하지 않고* user_id 연관 대상만 서술한다(인프라 키 규약 날조 금지).
    """
    uid = str(user_id)
    return (
        ExternalErasureTarget(
            store="clickhouse",
            data="학습 행동 로그(이벤트 스트림·분석)",
            locator=f"student_id_hash(user_id={uid}) 연관 이벤트 행 — 해시 매핑은 적재 규약 따름",
            reason="별도 분석 store·비동기 배치 삭제(RDB 트랜잭션 밖) — 단일 TX 불포함.",
        ),
        ExternalErasureTarget(
            store="s3",
            data="업로드 이미지·렌더 객체(손글씨 풀이·시각화)",
            locator=f"user_id={uid} 연관 업로드/렌더 객체(프리픽스 규약은 인프라 정의)",
            reason="객체 저장소(S3/MinIO)는 RDB 밖·SDK 삭제 — 단일 TX 불포함.",
        ),
        ExternalErasureTarget(
            store="redis",
            data="세션·핫 캐시(작업메모리·레이트리밋)",
            locator=f"user_id={uid} 연관 세션·캐시 키(TTL 만료가 기본·즉시 무효화는 별도)",
            reason="캐시는 RDB 밖·별도 클라이언트 무효화 — 단일 TX 불포함.",
        ),
    )


class ErasureReport(BaseModel):
    """삭제권 실행 결과 — 사용자 + 테이블별 삭제 행수(감사·검증·엔드포인트 응답). 불변(frozen).

    `deleted_counts`는 명시 삭제한 테이블별 행수다(`dialogue_turn`은 DB CASCADE라 비가시·미포함).
    `user_profile_deleted`는 최종 user_profile 삭제 여부(존재했으면 1·이미 없으면 0).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: uuid.UUID = Field(description="삭제 대상 사용자 id.")
    deleted_counts: dict[str, int] = Field(
        description="명시 삭제한 테이블(tablename)별 행수(dialogue_turn은 CASCADE라 미포함)."
    )
    user_profile_deleted: int = Field(
        ge=0, description="user_profile 삭제 행수(1=존재했음·0=이미 없음)."
    )
    total_rows_deleted: int = Field(ge=0, description="명시 삭제 총 행수(user_profile 포함).")
    pending_external: tuple[ExternalErasureTarget, ...] = Field(
        default=(),
        description=(
            "이 트랜잭션이 *삭제하지 않은* 외부 store 대상(ClickHouse·S3·Redis). RDB 밖이라 "
            "단일 TX에 못 넣어 *별도 ops 삭제*가 필요하다 — 누락을 조용히 넘기지 않고(날조 0·GDPR "
            "범위 정직) 후속 집행 체크리스트로 남긴다. 정보 누출 방지로 응답엔 미노출(ops만)."
        ),
    )


async def erase_user(session: AsyncSession, *, user_id: uuid.UUID) -> ErasureReport:
    """사용자의 *모든* 학생-연결 데이터를 단일 트랜잭션으로 영구 삭제(개인정보 삭제권·R11).

    `_ERASURE_PLAN` 순서로 각 테이블을 `delete(...).where(user컬럼 == user_id)`로 지우고(자식→부모),
    `DeletionAudit` 1행을 적재한 뒤(GDPR 증빙·콘텐츠 미저장) 마지막에 `user_profile`을 삭제한다.
    `dialogue_turn`은 `dialogue` 삭제에 DB CASCADE로 함께 제거된다(user 컬럼 없음). **commit은
    호출자**(flush로 같은 트랜잭션 가시화) — 어느 단계 실패도 전부 롤백돼 *부분 삭제가 없다*.

    멱등성: 이미 없는 사용자면 모든 삭제가 0행이고 `user_profile_deleted=0`(에러 없이 무해 종료).
    감사 행은 user_profile이 실재했든 아니든 적재된다(삭제 *시도* 증빙). 순수 ORM/쿼리빌더만.
    """
    counts: dict[str, int] = {}
    for model, column in _ERASURE_PLAN:
        result = await session.execute(delete(model).where(getattr(model, column) == user_id))
        counts[model.__tablename__] = cast("CursorResult[Any]", result).rowcount or 0

    # GDPR 삭제 증빙 — user_profile 삭제 *전* 적재(user FK 없어 사용자 삭제 후에도 잔존·콘텐츠 0).
    session.add(
        DeletionAudit(
            user_id=user_id,
            resource_type=AuditResourceType.user_profile.value,
            resource_id=user_id,
        )
    )

    profile_result = await session.execute(
        delete(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile_deleted = cast("CursorResult[Any]", profile_result).rowcount or 0

    await session.flush()  # 같은 트랜잭션 가시화(commit은 호출자).

    return ErasureReport(
        user_id=user_id,
        deleted_counts=counts,
        user_profile_deleted=profile_deleted,
        total_rows_deleted=sum(counts.values()) + profile_deleted,
        # RDB 밖 store는 이 TX가 못 지운다 — 누락을 구조화해 후속 ops 삭제 체크리스트로 남긴다.
        pending_external=external_erasure_targets(user_id),
    )
