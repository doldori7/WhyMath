"""L2 교수법 증거 기록 — 처치(treatment)·결과(outcome)를 `evidence_event`에 남긴다 (PED-03).

`evidence_event` 테이블의 **최초 writer**다. 테이블·마이그레이션은 소단원 DSL 슬라이스가 이미 세워
뒀으나(`db/models/evidence_event.py`) 지금까지 쓰는 코드가 없어 항상 빈 테이블이었다.

────────────────────────────────────────────────────────────────────────────
왜 필요한가 — 처치 기록 없이는 효과 측정이 성립하지 않는다
────────────────────────────────────────────────────────────────────────────
04d §3(Adaptive Pedagogy Engine)은 "누구에게 어떤 교수법이 효과적인가"를 데이터로 답하겠다고
선언한다. 그런데 **결과만 있고 무엇을 보여줬는지 모르면 비교군이 없다** — 정답률이 올랐어도 그것이
SOCRATIC 덕인지 DIRECT 덕인지 구분할 방법이 없다.

2026-07 실측: 결과 축(풀이→BKT `record_problem_attempt_mastery`)은 `/v1/me`에 배선돼 살아 있으나,
처치 축(`decide()`가 고른 전략)은 **어디에도 기록되지 않았다**(`supply()`의 API 소비자 0건). 이
좌석이 그 공백을 닫는다.

**가짜 처치 금지**: 이 좌석은 "학생에게 실제로 렌더된 전략"만 기록한다. 고르기만 하고 화면에
적용하지 않은 전략을 처치로 남기면 유효해 보이지만 틀린 측정이 되어 아무것도 안 하느니 못하다.
따라서 호출자는 렌더 결과(`SupplyResult`)를 손에 쥔 뒤에만 이 좌석을 부른다.

────────────────────────────────────────────────────────────────────────────
B1: 미성년 원문 발화 평문 저장 금지 (CLAUDE.md 절대 금기)
────────────────────────────────────────────────────────────────────────────
`meta`(JSONB)에는 **비민감 메타만** 넣는다 — 전략명·공급 경로·개념 code·게이트 사유코드. 학생
발화·풀이 원문은 이 좌석에 *들어오지도 않는다*(시그니처에 슬롯 부재 = 구조적 차단).
`payload_encrypted`/`payload_nonce`는 **쓰지 않는다** — 암호화해서 담을 원문 자체가 없다.

`user_id`도 담지 않는다. `evidence_event`에는 그 컬럼이 아예 없고, 처치↔결과는 `session_id` 축으로
묶인다(가명화 유지 — 집계는 학생 개인이 아니라 세션·전략 단위로 이뤄진다).

7계층: L2 학습자 데이터의 영속 기록. 판정·정책은 L4(`l4/pedagogy/adaptive`)가 이 행을 *읽어서*
한다(역방향 의존 0). 커밋 경계는 호출자 책임 — `mastery_tracking._stage_attempt_mastery` 선례대로
`session.add`만 하고 commit하지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.evidence_event import EvidenceEvent

# 이벤트 유형 — `evidence_event.event_type`은 enum이 아니라 TEXT(팩이 정의)이므로 이 두 리터럴을
# 모듈 상수로 동결한다. 집계(`l4/pedagogy/adaptive/effectiveness.py`)가 같은 상수를 import해서
# 쓰므로 문자열이 두 곳에서 따로 표류하지 않는다.
EVENT_TYPE_TREATMENT: str = "pedagogy_render"
"""처치 — 이 세션에서 학생에게 *실제로 렌더된* 교수법 전략."""

EVENT_TYPE_OUTCOME: str = "pedagogy_outcome"
"""결과 — 그 처치 이후의 시도 결과(정답 여부·소요 시간)."""

# `meta` JSONB 키 — 비민감 메타만(B1). 집계가 전략을 되읽는 키라 상수로 동결한다.
META_KEY_STRATEGY: str = "pedagogy_strategy"
META_KEY_CONTENT_SOURCE: str = "content_source"
META_KEY_CONCEPT_CODE: str = "concept_code"
META_KEY_GATE_REASON: str = "gate_reason_code"


def _now() -> datetime:
    """기록 시각(UTC aware) — 파티션 키 `time`. 테스트가 패치할 수 있게 함수로 뺀다."""
    return datetime.now(UTC)


async def record_pedagogy_treatment(
    session: AsyncSession,
    *,
    objective_id: str,
    k_type: str,
    session_id: uuid.UUID,
    strategy: str,
    content_source: str,
    concept_code: str | None = None,
    gate_reason_code: str | None = None,
    pack_version: int | None = None,
    occurred_at: datetime | None = None,
) -> EvidenceEvent:
    """학생에게 렌더된 교수법 전략 1건을 `evidence_event`에 stage한다(commit 0).

    `correct`·`rt_ms`는 **비운다** — 처치 시점에는 결과가 아직 없다. 결과는
    `record_pedagogy_outcome`이 같은 `session_id`로 별도 행을 남기고, 집계가 둘을 조인한다.

    `gate_reason_code`가 채워져 있으면 게이트가 요청 전략을 강등했다는 뜻이다 — 그 경우에도
    **실제 렌더된 전략**(강등 결과)을 `strategy`로 기록한다(학생이 본 것이 처치다).
    """
    meta: dict[str, Any] = {
        META_KEY_STRATEGY: strategy,
        META_KEY_CONTENT_SOURCE: content_source,
    }
    # None인 선택 키는 아예 넣지 않는다 — "없음"과 "null로 기록됨"을 구분 가능하게.
    if concept_code is not None:
        meta[META_KEY_CONCEPT_CODE] = concept_code
    if gate_reason_code is not None:
        meta[META_KEY_GATE_REASON] = gate_reason_code

    row = EvidenceEvent(
        time=occurred_at if occurred_at is not None else _now(),
        session_id=session_id,
        objective_id=objective_id,
        k_type=k_type,
        pack_version=pack_version,
        event_type=EVENT_TYPE_TREATMENT,
        meta=meta,
    )
    session.add(row)
    return row


async def record_pedagogy_outcome(
    session: AsyncSession,
    *,
    objective_id: str,
    k_type: str,
    session_id: uuid.UUID,
    correct: bool,
    rt_ms: int | None = None,
    pack_version: int | None = None,
    occurred_at: datetime | None = None,
) -> EvidenceEvent:
    """처치 이후의 시도 결과 1건을 stage한다(commit 0).

    `session_id`가 처치 행과 같아야 집계가 (전략 → 결과)로 이을 수 있다. `meta`는 두지 않는다 —
    결과 신호는 전용 컬럼(`correct`·`rt_ms`)이 이미 있고, 원문은 담지 않는다(B1).
    """
    row = EvidenceEvent(
        time=occurred_at if occurred_at is not None else _now(),
        session_id=session_id,
        objective_id=objective_id,
        k_type=k_type,
        pack_version=pack_version,
        event_type=EVENT_TYPE_OUTCOME,
        correct=correct,
        rt_ms=rt_ms,
    )
    session.add(row)
    return row


__all__ = [
    "EVENT_TYPE_OUTCOME",
    "EVENT_TYPE_TREATMENT",
    "META_KEY_CONCEPT_CODE",
    "META_KEY_CONTENT_SOURCE",
    "META_KEY_GATE_REASON",
    "META_KEY_STRATEGY",
    "record_pedagogy_outcome",
    "record_pedagogy_treatment",
]
