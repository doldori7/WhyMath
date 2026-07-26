"""L2 학습 증거 이벤트 적재기 — `evidence_event` 하이퍼테이블 append 라이터.

PED-01 파일럿 E2E의 evidence write 좌석이다. 학습목표별 유형 달성 증거를 시계열로 적재한다
("정답≠달성"·§ORM docstring). append-only(멱등 upsert 아님·이벤트 로그) 라이터다.

────────────────────────────────────────────────────────────────────────────
B1: 미성년 데이터 — cipher/평문 미접촉 라이터
────────────────────────────────────────────────────────────────────────────
이 라이터는 **이미 암호화된 바이트**(`payload_encrypted`/`payload_nonce`)만 받는다 — cipher도 원문
payload도 보지 않는다(암호화-at-write는 api 헬퍼 층 `encrypt_evidence_payload`가 담당·dialogue_turn
선례). 그래서 L2가 api(L6) 층을 import하지 않는다(역방향 의존 금지). 두 암호 컬럼이 None이면
메타 전용 행이다(미성년 원문 payload 평문 저장 없음).

7계층: L2 학습자 모델의 영속 증거 좌석. sync 엔진은 슬3 `_build_sync_engine` 재사용.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class EvidenceEventStore:
    """`evidence_event` append 라이터(하이퍼테이블·B1 봉투 암호화 바이트 수신).

    `log`는 이벤트 1건을 INSERT한다(`event_id`는 DB autoincrement·`time`은 미지정 시 server now).
    암호 컬럼은 *이미 암호화된 바이트*를 그대로 싣는다(라이터는 cipher/평문 미접촉). sync 엔진은
    슬3 `_build_sync_engine` 재사용.
    """

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def log(
        self,
        *,
        session_id: UUID,
        objective_id: str,
        k_type: str,
        event_type: str,
        meta: dict[str, Any] | None = None,
        payload_encrypted: bytes | None = None,
        payload_nonce: bytes | None = None,
        retention_until: datetime | None = None,
        correct: bool | None = None,
        rt_ms: int | None = None,
        judge_score: int | None = None,
        fidelity_score: int | None = None,
        pack_version: int | None = None,
        occurred_at: datetime | None = None,
    ) -> int:
        """증거 이벤트 1건 INSERT. 반환=1.

        `payload_encrypted`/`payload_nonce`는 `encrypt_evidence_payload`가 낸 바이트를 그대로 싣는다
        (둘 다 None이면 메타 전용). `occurred_at` 미지정 시 `time`은 server now(파티션 키)로 채운다.
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        values: dict[str, Any] = {
            "time": occurred_at if occurred_at is not None else func.now(),
            "session_id": session_id,
            "objective_id": objective_id,
            "k_type": k_type,
            "event_type": event_type,
            "meta": meta,
            "payload_encrypted": payload_encrypted,
            "payload_nonce": payload_nonce,
            "retention_until": retention_until,
            "correct": correct,
            "rt_ms": rt_ms,
            "judge_score": judge_score,
            "fidelity_score": fidelity_score,
            "pack_version": pack_version,
        }
        with self._get_engine().begin() as conn:
            conn.execute(pg_insert(EvidenceEvent).values(**values))
        return 1

    def fetch_by_objective(
        self, objective_id: str
    ) -> list[tuple[bytes | None, bytes | None, dict[str, Any] | None]]:
        """목표별 증거 행의 `(payload_encrypted, payload_nonce, meta)` 목록 — E2E 라운드트립용.

        복호는 호출자(api 헬퍼 `resolve_evidence_payload`)가 cipher로 수행한다
        (라이터는 바이트만 반환).
        """
        from sqlalchemy import select

        stmt = select(
            EvidenceEvent.payload_encrypted,
            EvidenceEvent.payload_nonce,
            EvidenceEvent.meta,
        ).where(EvidenceEvent.objective_id == objective_id)
        with self._get_engine().begin() as conn:
            return [(row[0], row[1], row[2]) for row in conn.execute(stmt)]


__all__ = ["EvidenceEventStore"]
