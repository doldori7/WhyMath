"""WH-1 학습 증거 저장소 — `evidence_links` 적재·진단 조회·보존 파기(설계 04a §2.3·§3 도구7).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.3(학습 증거 그래프)·§3 도구7
(`log_evidence`). 하네스가 verify/match 신호로 증거를 *적재*(`log_evidence`)하고, 진단·학부모
리포트가 *조회*(`get_evidence_for_misconception`·`net_support`)한다. 보존 기한 경과분은 야간 배치
(`purge_expired`)로 파기한다(삭제권은 `student_id` FK CASCADE가 학생 삭제 시 자동 처리).

배치(L4·hypothesis_store 옆): 증거는 per-student 오개념 가설의 *근거*라 오개념 패키지에 둔다.
`CATALOG_BY_ID`(같은 L4 패키지)로 참조 무결성을 강제하고, `EvidenceLink`(L1 모델)을 import한다
(L4→L1 허용).

저장소 패턴(`hypothesis_store.py`·WH-S 저장소 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*. 트랜잭션 commit은 호출자 관리.
  - **순수 ORM/쿼리빌더만**(원시 SQL 0). `log_evidence`는 BIGSERIAL `link_id`를 호출자가 바로 쓰게
    `flush`+`refresh`(commit은 호출자).

★게이트(참조 무결성·정합): `log_evidence`는 적재 전 ① `misconception_id ∈ CATALOG_BY_ID`(정본
오개념 실재·`validate_distractor_map` 패턴) ② `polarity ∈ {−1,+1}`(DB CHECK 이중)를 강제한다.
위반은 `EvidenceValidationError`. *거짓 증거(미등록 오개념·잘못된 극성)가 진단 그래프에 유입되는
것을 차단*한다(CLAUDE.md 정확성 #1·거짓 낙인 방지).

개인정보(§2.3): 민감 학생 데이터지만 식별자·극성·가중치·날짜만 담아 평문 적정. 삭제권은 모델
FK CASCADE + 본 모듈 `purge_expired`(보존 경과)로 보장. API 노출은 하네스/리포트 계층 몫(후속).

범위 밖(후속): `curate_hypothesis`(증거→가설 세트·감쇠·ε-규칙·하네스)·BKT 초기화·pgvector 삭제까지
단일 트랜잭션 삭제 오케스트레이션·`select_probe`. 본 모듈은 *증거 CRUD + 진단 집계*만 둔다.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.evidence_link import EvidenceLink
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID

__all__ = [
    "EvidenceValidationError",
    "get_evidence_for_misconception",
    "get_evidence_for_student",
    "log_evidence",
    "net_support",
    "purge_expired",
]

_VALID_POLARITY = (-1, 1)


class EvidenceValidationError(ValueError):
    """증거 적재 게이트 위반 — 미등록 오개념(CATALOG_BY_ID 부재) 또는 잘못된 극성."""


async def log_evidence(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    student_id: uuid.UUID,
    misconception_id: str,
    polarity: int,
    event_id: int | None = None,
    node_id: str | None = None,
    weight: float | None = None,
    retention_until: date | None = None,
) -> EvidenceLink:
    """증거 엣지 1개를 적재한다(§3 도구7 — 게이트 통과 후).

    게이트(거짓 증거 차단·CLAUDE.md 정확성 #1):
      ① `misconception_id ∈ CATALOG_BY_ID` — 정본 오개념 실재(미등록이면 거짓 낙인 차단).
      ② `polarity ∈ {−1, +1}` — +1 지지/−1 반박만(DB CHECK 이중 가드).
    위반은 `EvidenceValidationError`. `flush`+`refresh`로 DB-assigned `link_id`를 같은 트랜잭션에서
    가시화(commit은 호출자). `student_id` FK CASCADE가 삭제권을 자동 보장한다.
    """
    if misconception_id not in CATALOG_BY_ID:
        raise EvidenceValidationError(
            f"증거 참조 무결성 위반 — misconception_id {misconception_id!r}이(가) "
            "정본 카탈로그(CATALOG_BY_ID)에 없음."
        )
    if polarity not in _VALID_POLARITY:
        raise EvidenceValidationError(
            f"극성 위반 — polarity={polarity!r}(허용 {_VALID_POLARITY} — +1 지지/−1 반박)."
        )
    link = EvidenceLink(
        session_id=session_id,
        student_id=student_id,
        misconception_id=misconception_id,
        polarity=polarity,
        event_id=event_id,
        node_id=node_id,
        weight=weight,
        retention_until=retention_until,
    )
    session.add(link)
    await session.flush()
    await session.refresh(link)
    return link


async def get_evidence_for_student(
    session: AsyncSession, student_id: uuid.UUID
) -> list[EvidenceLink]:
    """한 학생의 증거 전체를 적재순 조회(감사·삭제권 일괄 로드). student_id 인덱스 prefix."""
    stmt = (
        select(EvidenceLink)
        .where(EvidenceLink.student_id == student_id)
        .order_by(EvidenceLink.created_at, EvidenceLink.link_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_evidence_for_misconception(
    session: AsyncSession, student_id: uuid.UUID, misconception_id: str
) -> list[EvidenceLink]:
    """한 학생의 *한 오개념 가설*을 지지/반박하는 증거를 조회(진단 조인). 복합 인덱스 정확 매칭."""
    stmt = (
        select(EvidenceLink)
        .where(
            EvidenceLink.student_id == student_id,
            EvidenceLink.misconception_id == misconception_id,
        )
        .order_by(EvidenceLink.created_at, EvidenceLink.link_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def net_support(session: AsyncSession, student_id: uuid.UUID, misconception_id: str) -> float:
    """오개념 가설의 *순 지지도* = Σ(polarity × COALESCE(weight, 1.0)) — SQL 진단 신호(§2.3).

    양수면 가설 지지 우세·음수면 반박 우세·0이면 균형/증거 없음. "이 학생의 진짜 원인은 X"라는
    진단이 LLM 추론이 아닌 이 집계로 나온다(학부모 리포트 신뢰 근거). 증거 없으면 0.0.
    """
    stmt = select(
        func.coalesce(
            func.sum(EvidenceLink.polarity * func.coalesce(EvidenceLink.weight, 1.0)),
            0.0,
        )
    ).where(
        EvidenceLink.student_id == student_id,
        EvidenceLink.misconception_id == misconception_id,
    )
    result = await session.execute(stmt)
    return float(result.scalar_one())


async def purge_expired(session: AsyncSession, *, as_of: date) -> int:
    """보존 기한(`retention_until`)이 `as_of` 이전인 증거를 파기한다 — 야간 배치(§2.3 자동 파기).

    `retention_until < as_of`인 레코드만 삭제한다(NULL=무기한은 미삭제). 삭제 행수를 반환한다.
    `idx_evidence_retention`을 탄다. 학생 단위 삭제권은 FK CASCADE가 별도 처리(여기선 보존 만료만).
    트랜잭션 commit은 호출자 관리.
    """
    stmt = (
        delete(EvidenceLink)
        .where(
            EvidenceLink.retention_until.is_not(None),
            EvidenceLink.retention_until < as_of,
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    # DELETE는 CursorResult(rowcount 보유) — Result[Any] 타입 좁히기. -1 드라이버는 0 폴백.
    return cast("CursorResult[Any]", result).rowcount or 0
