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

raw `user_id`는 여전히 담지 않는다. `evidence_event`에는 그 컬럼이 아예 없고, 처치↔결과는
`session_id` 축으로 묶인다(가명화 유지 — 집계는 학생 개인이 아니라 세션·전략 단위로 이뤄진다).
SEC-24(원 SEC-16)이 처치 행 `meta`에 추가한 것은 *키드 해시 바인딩*(`META_KEY_USER_BINDING`)뿐이다 —
서버 시크릿 없이는 역산 불가한 HMAC이라 가명화가 유지되고, 집계는 이 키를 읽지 않으며,
용도는 오직 outcome 기입 전 소유권 대조다.

7계층: L2 학습자 데이터의 영속 기록. 판정·정책은 L4(`l4/pedagogy/adaptive`)가 이 행을 *읽어서*
한다(역방향 의존 0). 커밋 경계는 호출자 책임 — `mastery_tracking._stage_attempt_mastery` 선례대로
`session.add`만 하고 commit하지 않는다.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings
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
# SEC-24(원 SEC-16): 처치 행에 저장되는 세션↔사용자 키드 해시 바인딩. 집계(effectiveness)는 이 키를
# *읽지 않는다* — 용도는 outcome 기입 전 소유권 대조뿐이다(가명화 유지·역산 불가 HMAC).
META_KEY_USER_BINDING: str = "user_binding"

# HMAC 도메인 프리픽스 — jwt_secret_key를 다른 용도(토큰 서명)와 공유하므로 입력 도메인을
# 분리해 교차 용도 위조를 차단한다(버전 접미사 v1 — 스킴 교체 시 구분).
_BINDING_DOMAIN = "whymath-study-session-binding-v1"


class SessionOwnershipError(Exception):
    """outcome 기입 세션 소유권 검증 실패 — 처치 행 부재·바인딩 부재·바인딩 불일치.

    세 사유를 *구분하지 않는다* — 구분해 주면 "그 session_id가 존재하는가"를 알려주는
    존재 오라클이 된다(SEC-24(원 SEC-16) 오라클 차단).
    """


class DuplicateOutcomeError(Exception):
    """같은 (objective, session)에 outcome이 이미 존재 — 중복 기입(자기 가중 게이밍) 거부."""


def session_user_binding(session_id: uuid.UUID, user_id: uuid.UUID, *, settings: Settings) -> str:
    """세션↔사용자 바인딩 키드 해시(HMAC-SHA256 hexdigest·64자) — SEC-24(원 SEC-16) 소유권 대조 축.

    키 선택 근거(`jwt_secret_key`):
      ① jwt_secret은 인증이 서는 배포에서 *항상 구성되는* 시크릿이라, 새 env 축(미설정 시
         fail-open/closed 분기)을 만들지 않는다.
      ② 도메인 프리픽스(`_BINDING_DOMAIN`)로 토큰 서명과 용도를 분리한다 — 같은 키라도
         입력 도메인이 달라 교차 위조가 성립하지 않는다.
      ③ 키 로테이션 시 인플라이트 학습 세션의 outcome 기입이 403이 되지만, 같은 로테이션이
         액세스 토큰 자체를 무효화하므로 클라는 어차피 재인증·재학습 경로다(수용).
      ④ *유염 키드 해시*라 `evidence_event` 가명화(raw user_id 미저장)와 양립한다 —
         `privacy/audit.hash_client_ip`(sha256(salt+ip)·역산 불가 목표)와 동일 계열.
    """
    key = settings.jwt_secret_key.get_secret_value().encode()
    msg = f"{_BINDING_DOMAIN}:{session_id}:{user_id}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _now() -> datetime:
    """기록 시각(UTC aware) — 파티션 키 `time`. 테스트가 패치할 수 있게 함수로 뺀다."""
    return datetime.now(UTC)


async def record_pedagogy_treatment(
    session: AsyncSession,
    *,
    objective_id: str,
    k_type: str,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
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

    SEC-24(원 SEC-16): `meta`에 세션↔사용자 키드 해시 바인딩(`META_KEY_USER_BINDING`)을
    함께 남긴다 — `/outcome` 소유권 대조의 앵커다. raw `user_id`가 아니라 HMAC
    해시라 가명화가 유지된다.
    """
    meta: dict[str, Any] = {
        META_KEY_STRATEGY: strategy,
        META_KEY_CONTENT_SOURCE: content_source,
        META_KEY_USER_BINDING: session_user_binding(session_id, user_id, settings=settings),
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
    user_id: uuid.UUID,
    settings: Settings,
    correct: bool,
    rt_ms: int | None = None,
    pack_version: int | None = None,
    occurred_at: datetime | None = None,
) -> EvidenceEvent:
    """처치 이후의 시도 결과 1건을 검증 후 stage한다(commit 0).

    `session_id`가 처치 행과 같아야 집계가 (전략 → 결과)로 이을 수 있다. `meta`는 두지 않는다 —
    결과 신호는 전용 컬럼(`correct`·`rt_ms`)이 이미 있고, 원문은 담지 않는다(B1).

    SEC-24(원 SEC-16): stage 전에 소유권·중복을 검증한다. **이 함수가 outcome의 유일한
    writer**이므로 검증을 여기(안쪽)에 두어야 우회가 구조적으로 불가하다
    (PED-06 "정본화 ≠ 집행" 교훈 — 계약을 API 층에만 두면 새 호출자가 생길 때
    조용히 뚫린다). 검증 실패 시:
      - `SessionOwnershipError` — 처치 부재·바인딩 부재·바인딩 불일치(사유 미구분).
      - `DuplicateOutcomeError` — 같은 (objective, session)에 outcome 기존재.
    기존 "세션이 안 맞으면 행은 남되 집계 제외" 규약을 "기입 거부"로 승격했다 — 고아 outcome
    자체가 오염 벡터다(무제한 적재로 저장소·집계 스캔을 오염시킨다).
    """
    binding = session_user_binding(session_id, user_id, settings=settings)
    # ① 처치 행 조회 — *같은 objective*의 처치만 인정한다(다른 objective의 session_id를 도용한
    # 목표 교차 위조도 이 where 절이 함께 차단한다). earliest(order_by time asc) 기준은
    # `aggregate_effectiveness`의 "가장 이른 처치" 규약과 동형 — 검증과 집계가 같은 행을 본다.
    treatment = (
        (
            await session.execute(
                select(EvidenceEvent)
                .where(
                    EvidenceEvent.objective_id == objective_id,
                    EvidenceEvent.session_id == session_id,
                    EvidenceEvent.event_type == EVENT_TYPE_TREATMENT,
                )
                .order_by(EvidenceEvent.time.asc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if treatment is None:
        raise SessionOwnershipError
    # ② 바인딩 대조 — 바인딩 키가 없는 구(舊) 처치 행도 fail-closed로 거부한다(프로덕션 클라
    # 0(MOB-13 미배선)이라 인플라이트 구 세션 없음). compare_digest = 타이밍 안전 비교.
    stored = (treatment.meta or {}).get(META_KEY_USER_BINDING)
    if not isinstance(stored, str) or not hmac.compare_digest(stored, binding):
        raise SessionOwnershipError
    # ③ 중복 검사 — 같은 (objective, session)의 outcome 기존재 시 거부(자기 가중 게이밍 차단).
    # 정직 표기: SELECT-then-INSERT라 동시 요청 경합 창이 남는다 — 완전 차단은 하이퍼테이블
    # 부분 유니크 인덱스(마이그레이션 별건)이고, *대량* 오염 벡터는 이 검사로 닫힌다.
    duplicate = (
        (
            await session.execute(
                select(EvidenceEvent)
                .where(
                    EvidenceEvent.objective_id == objective_id,
                    EvidenceEvent.session_id == session_id,
                    EvidenceEvent.event_type == EVENT_TYPE_OUTCOME,
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if duplicate is not None:
        raise DuplicateOutcomeError

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
    "META_KEY_USER_BINDING",
    "DuplicateOutcomeError",
    "SessionOwnershipError",
    "record_pedagogy_outcome",
    "record_pedagogy_treatment",
    "session_user_binding",
]
