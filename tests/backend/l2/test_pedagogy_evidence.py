"""L2 교수법 증거 writer — `evidence_event` 기록 좌석 단위테스트 (PED-03·SEC-24(원 SEC-16)·hermetic).

`evidence_event`의 최초 writer다. 관심사:
  - 처치/결과 두 이벤트 유형이 각각 올바른 컬럼을 채운다(처치는 결과 컬럼을 비운다).
  - **B1**: 학생 원문이 들어갈 슬롯이 시그니처에 없고, 암호문 컬럼도 건드리지 않는다.
  - 커밋하지 않는다(호출자 경계 — `mastery_tracking` 선례).
  - **SEC-24(원 SEC-16)**(`docs/reviews/functional_security_audit_2026-08-08.md` M2): 처치 행 meta의 키드
    해시 바인딩(`META_KEY_USER_BINDING`)과, 유일 outcome writer 안쪽의 소유권·중복 검증
    (`SessionOwnershipError`·`DuplicateOutcomeError`) — 결함주입으로 거부 경로를 직접 때린다.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr

from whymath_backend.config import Settings
from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.l2 import pedagogy_evidence
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_CONCEPT_CODE,
    META_KEY_CONTENT_SOURCE,
    META_KEY_GATE_REASON,
    META_KEY_STRATEGY,
    META_KEY_USER_BINDING,
    DuplicateOutcomeError,
    SessionOwnershipError,
    record_pedagogy_outcome,
    record_pedagogy_treatment,
    session_user_binding,
)

_AT = datetime(2026, 7, 26, tzinfo=UTC)
_UID = uuid.uuid4()


def _settings(secret: str = "unit-test-secret-0123456789abcdef") -> Settings:
    """바인딩 HMAC 키(jwt_secret)만 채운 테스트 설정."""
    return Settings(jwt_secret_key=SecretStr(secret))


class _Scalars:
    """`.scalars().first()` 표면 — `tests/backend/api/test_study.py`의 `_Scalars` 관례."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _FakeSession:
    """`session.add` 관찰 + execute 큐(outcome 검증 SELECT용) — commit이 호출되면 즉시 실패.

    outcome writer는 (처치 select → 중복 select) 순서로 execute를 2회 부른다(처치가 없으면
    1회에서 예외로 끊긴다). `queue()`로 그 순서대로 결과 행 목록을 주입한다.
    """

    def __init__(self, *execute_results: list[Any]) -> None:
        self.added: list[Any] = []
        self._execute_results: list[list[Any]] = list(execute_results)

    def queue(self, *execute_results: list[Any]) -> None:
        """execute 결과를 뒤에 추가 주입 — 처치 행을 만든 *뒤* 그 행을 큐에 넣을 때 쓴다."""
        self._execute_results.extend(execute_results)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._execute_results.pop(0))

    async def commit(self) -> None:  # pragma: no cover - 호출되면 테스트 실패
        raise AssertionError("writer가 commit하면 안 된다 — 커밋 경계는 호출자 책임")


def _treatment_row(
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
    objective_id: str = "OBJ.1",
    with_binding: bool = True,
) -> EvidenceEvent:
    """정당(또는 바인딩 없는 구형) 처치 행 픽스처 — outcome 소유권 검증의 대조 대상."""
    meta: dict[str, Any] = {
        META_KEY_STRATEGY: "SOCRATIC",
        META_KEY_CONTENT_SOURCE: "dsl_render",
    }
    if with_binding:
        meta[META_KEY_USER_BINDING] = session_user_binding(session_id, user_id, settings=settings)
    return EvidenceEvent(
        time=_AT,
        session_id=session_id,
        objective_id=objective_id,
        k_type="CONCEPT",
        event_type=EVENT_TYPE_TREATMENT,
        meta=meta,
    )


class TestTreatment:
    async def test_records_strategy_and_source_in_meta(self) -> None:
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
            user_id=_UID,
            settings=_settings(),
            strategy="SOCRATIC",
            content_source="dsl_render",
            concept_code="math.algebra.linear",
            occurred_at=_AT,
        )
        assert session.added == [row]
        assert row.event_type == EVENT_TYPE_TREATMENT
        assert row.meta is not None
        assert row.meta[META_KEY_STRATEGY] == "SOCRATIC"
        assert row.meta[META_KEY_CONTENT_SOURCE] == "dsl_render"
        assert row.meta[META_KEY_CONCEPT_CODE] == "math.algebra.linear"

    async def test_records_user_binding_hexdigest_in_meta(self) -> None:
        """SEC-24(원 SEC-16) — 처치 행 meta에 (session ↔ user) 키드 해시 바인딩이 올바른 값으로 실린다."""
        session = _FakeSession()
        settings = _settings()
        sid = uuid.UUID(int=7)
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            user_id=_UID,
            settings=settings,
            strategy="SOCRATIC",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert row.meta[META_KEY_USER_BINDING] == session_user_binding(sid, _UID, settings=settings)

    async def test_leaves_outcome_columns_empty(self) -> None:
        """처치 시점에는 결과가 아직 없다 — 비워 두는 것이 정직하다."""
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
            user_id=_UID,
            settings=_settings(),
            strategy="DIRECT",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        assert row.correct is None
        assert row.rt_ms is None

    async def test_omits_optional_meta_keys_when_absent(self) -> None:
        """None인 선택 키는 넣지 않는다 — "없음"과 "null로 기록됨"을 구분 가능하게."""
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
            user_id=_UID,
            settings=_settings(),
            strategy="DIRECT",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert META_KEY_CONCEPT_CODE not in row.meta
        assert META_KEY_GATE_REASON not in row.meta

    async def test_records_gate_demotion_reason(self) -> None:
        """게이트 강등 시 사유 코드가 남고, `strategy`는 **강등 결과**(학생이 본 것)다."""
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
            user_id=_UID,
            settings=_settings(),
            strategy="SOCRATIC",
            content_source="dsl_render",
            gate_reason_code="hint_not_escalated",
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert row.meta[META_KEY_GATE_REASON] == "hint_not_escalated"
        assert row.meta[META_KEY_STRATEGY] == "SOCRATIC"


class TestSessionUserBinding:
    """SEC-24(원 SEC-16) 바인딩 함수 — 순수·결정론·입력 민감(세 축 전부 변별)·hex 형태."""

    def test_deterministic(self) -> None:
        settings = _settings()
        sid = uuid.UUID(int=1)
        assert session_user_binding(sid, _UID, settings=settings) == session_user_binding(
            sid, _UID, settings=settings
        )

    def test_differs_by_user(self) -> None:
        settings = _settings()
        sid = uuid.UUID(int=1)
        assert session_user_binding(sid, uuid.UUID(int=2), settings=settings) != (
            session_user_binding(sid, uuid.UUID(int=3), settings=settings)
        )

    def test_differs_by_session(self) -> None:
        settings = _settings()
        assert session_user_binding(uuid.UUID(int=2), _UID, settings=settings) != (
            session_user_binding(uuid.UUID(int=3), _UID, settings=settings)
        )

    def test_differs_by_secret(self) -> None:
        """시크릿이 다르면 다르다 — 키 없이 재현 불가한 *키드* 해시임을 변별."""
        sid = uuid.UUID(int=1)
        assert session_user_binding(sid, _UID, settings=_settings("secret-a-0123456789")) != (
            session_user_binding(sid, _UID, settings=_settings("secret-b-0123456789"))
        )

    def test_is_64_hex_chars(self) -> None:
        digest = session_user_binding(uuid.UUID(int=1), _UID, settings=_settings())
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")


class TestOutcome:
    async def test_records_correct_and_rt(self) -> None:
        settings = _settings()
        sid = uuid.UUID(int=1)
        treatment = _treatment_row(session_id=sid, user_id=_UID, settings=settings)
        session = _FakeSession([treatment], [])  # 처치 select → 정당 행, 중복 select → 없음
        row = await record_pedagogy_outcome(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            user_id=_UID,
            settings=settings,
            correct=True,
            rt_ms=3200,
            occurred_at=_AT,
        )
        assert row.event_type == EVENT_TYPE_OUTCOME
        assert row.correct is True
        assert row.rt_ms == 3200
        assert row.meta is None  # 결과는 전용 컬럼이 있어 meta 불요

    async def test_shares_session_id_with_treatment(self) -> None:
        """같은 session_id로 묶여야 집계가 (전략→결과)로 이을 수 있다."""
        settings = _settings()
        session = _FakeSession()
        sid = uuid.uuid4()
        await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            user_id=_UID,
            settings=settings,
            strategy="ANALOGY",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        # outcome 검증 SELECT가 방금 stage된 처치 행을 되읽는 상황을 큐로 재현한다.
        session.queue([session.added[0]], [])
        await record_pedagogy_outcome(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            user_id=_UID,
            settings=settings,
            correct=False,
            occurred_at=_AT,
        )
        assert {r.session_id for r in session.added} == {sid}


class TestOutcomeOwnership:
    """SEC-24(원 SEC-16) 결함주입 — 위조·도용·구형·중복 기입이 행을 남기지 못하고 거부되는지."""

    async def test_forged_session_id_without_treatment_is_rejected(self) -> None:
        """① 처치 행 없음(위조 session_id) → SessionOwnershipError·stage 0."""
        session = _FakeSession([])  # 처치 select → 빈 결과
        with pytest.raises(SessionOwnershipError):
            await record_pedagogy_outcome(
                session,  # type: ignore[arg-type]
                objective_id="OBJ.1",
                k_type="CONCEPT",
                session_id=uuid.uuid4(),
                user_id=_UID,
                settings=_settings(),
                correct=True,
                occurred_at=_AT,
            )
        assert session.added == []  # 거부 = 행 자체가 남지 않는다(고아 outcome 오염 벡터 차단)

    async def test_other_students_session_is_rejected(self) -> None:
        """② 학생 B에게 발급된 세션에 학생 A가 outcome 기입 → SessionOwnershipError."""
        settings = _settings()
        sid = uuid.uuid4()
        student_b = uuid.uuid4()
        treatment = _treatment_row(session_id=sid, user_id=student_b, settings=settings)
        session = _FakeSession([treatment])
        with pytest.raises(SessionOwnershipError):
            await record_pedagogy_outcome(
                session,  # type: ignore[arg-type]
                objective_id="OBJ.1",
                k_type="CONCEPT",
                session_id=sid,
                user_id=_UID,  # 학생 A
                settings=settings,
                correct=True,
                occurred_at=_AT,
            )
        assert session.added == []

    async def test_legacy_treatment_without_binding_is_rejected(self) -> None:
        """③ 바인딩 키 없는 구(舊) 처치 행 → fail-closed 거부(프로덕션 클라 0 — MOB-13 미배선)."""
        settings = _settings()
        sid = uuid.uuid4()
        treatment = _treatment_row(
            session_id=sid, user_id=_UID, settings=settings, with_binding=False
        )
        session = _FakeSession([treatment])
        with pytest.raises(SessionOwnershipError):
            await record_pedagogy_outcome(
                session,  # type: ignore[arg-type]
                objective_id="OBJ.1",
                k_type="CONCEPT",
                session_id=sid,
                user_id=_UID,
                settings=settings,
                correct=True,
                occurred_at=_AT,
            )
        assert session.added == []

    async def test_legitimate_owner_is_staged_without_binding_on_outcome_row(self) -> None:
        """④ 정당 소유자 → stage되고, 바인딩은 *처치 행 전용*(outcome 행 meta에 없음)."""
        settings = _settings()
        sid = uuid.uuid4()
        treatment = _treatment_row(session_id=sid, user_id=_UID, settings=settings)
        session = _FakeSession([treatment], [])
        row = await record_pedagogy_outcome(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            user_id=_UID,
            settings=settings,
            correct=True,
            occurred_at=_AT,
        )
        assert session.added == [row]
        assert row.meta is None  # 바인딩(키드 해시)은 처치 행 전용 — outcome 행에는 없다

    async def test_duplicate_outcome_is_rejected(self) -> None:
        """⑤ 같은 (objective, session)에 outcome 기존재 → DuplicateOutcomeError(게이밍 거부)."""
        settings = _settings()
        sid = uuid.uuid4()
        treatment = _treatment_row(session_id=sid, user_id=_UID, settings=settings)
        existing_outcome = EvidenceEvent(
            time=_AT,
            session_id=sid,
            objective_id="OBJ.1",
            k_type="CONCEPT",
            event_type=EVENT_TYPE_OUTCOME,
            correct=True,
        )
        session = _FakeSession([treatment], [existing_outcome])
        with pytest.raises(DuplicateOutcomeError):
            await record_pedagogy_outcome(
                session,  # type: ignore[arg-type]
                objective_id="OBJ.1",
                k_type="CONCEPT",
                session_id=sid,
                user_id=_UID,
                settings=settings,
                correct=False,
                occurred_at=_AT,
            )
        assert session.added == []

    async def test_ownership_rejections_share_one_exception_type(self) -> None:
        """⑥ ①~③의 거부가 전부 *같은 타입* — 사유 미구분(세션 존재 오라클 차단)."""
        settings = _settings()
        sid = uuid.uuid4()
        raised: list[BaseException] = []
        scenarios: list[_FakeSession] = [
            _FakeSession([]),  # ① 처치 없음
            _FakeSession(  # ② 타인 소유
                [_treatment_row(session_id=sid, user_id=uuid.uuid4(), settings=settings)]
            ),
            _FakeSession(  # ③ 바인딩 없음
                [
                    _treatment_row(
                        session_id=sid, user_id=_UID, settings=settings, with_binding=False
                    )
                ]
            ),
        ]
        for session in scenarios:
            with pytest.raises(SessionOwnershipError) as excinfo:
                await record_pedagogy_outcome(
                    session,  # type: ignore[arg-type]
                    objective_id="OBJ.1",
                    k_type="CONCEPT",
                    session_id=sid,
                    user_id=_UID,
                    settings=settings,
                    correct=True,
                    occurred_at=_AT,
                )
            raised.append(excinfo.value)
        assert {type(exc) for exc in raised} == {SessionOwnershipError}


class TestB1PlaintextProhibition:
    def test_signatures_have_no_free_text_slot(self) -> None:
        """학생 원문이 들어올 파라미터가 **아예 없다** — 구조적 차단.

        `text`/`utterance`/`payload` 류 슬롯이 생기면 평문 저장 경로가 열린다. 시그니처 수준에서
        막아 두면 실수로도 흘릴 수 없다. SEC-24(원 SEC-16)이 추가한 `user_id`(UUID)·`settings`(Settings)는
        원문 텍스트 슬롯이 아니라 위반이 아니다(검사 취지 = 자유 텍스트 유입 차단).
        """
        forbidden = {"text", "utterance", "payload", "content", "answer", "solution", "body"}
        for fn in (record_pedagogy_treatment, record_pedagogy_outcome):
            params = set(inspect.signature(fn).parameters)
            assert not (params & forbidden), f"{fn.__name__}에 원문 슬롯: {params & forbidden}"

    async def test_ciphertext_columns_untouched(self) -> None:
        """암호문 컬럼도 건드리지 않는다 — 암호화해서 담을 원문 자체가 없다."""
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
            user_id=_UID,
            settings=_settings(),
            strategy="DIRECT",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        assert row.payload_encrypted is None
        assert row.payload_nonce is None

    def test_event_type_constants_are_frozen(self) -> None:
        """집계가 같은 상수를 import하므로 문자열이 두 곳에서 표류하면 조인이 조용히 깨진다."""
        assert pedagogy_evidence.EVENT_TYPE_TREATMENT == "pedagogy_render"
        assert pedagogy_evidence.EVENT_TYPE_OUTCOME == "pedagogy_outcome"
