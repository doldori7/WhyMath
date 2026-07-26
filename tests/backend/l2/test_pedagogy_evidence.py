"""L2 교수법 증거 writer — `evidence_event` 기록 좌석 단위테스트 (PED-03·hermetic).

`evidence_event`의 최초 writer다. 관심사:
  - 처치/결과 두 이벤트 유형이 각각 올바른 컬럼을 채운다(처치는 결과 컬럼을 비운다).
  - **B1**: 학생 원문이 들어갈 슬롯이 시그니처에 없고, 암호문 컬럼도 건드리지 않는다.
  - 커밋하지 않는다(호출자 경계 — `mastery_tracking` 선례).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

from whymath_backend.l2 import pedagogy_evidence
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_CONCEPT_CODE,
    META_KEY_CONTENT_SOURCE,
    META_KEY_GATE_REASON,
    META_KEY_STRATEGY,
    record_pedagogy_outcome,
    record_pedagogy_treatment,
)

_AT = datetime(2026, 7, 26, tzinfo=UTC)


class _FakeSession:
    """`session.add`만 관찰하는 가짜 세션 — commit이 호출되면 즉시 실패한다."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:  # pragma: no cover - 호출되면 테스트 실패
        raise AssertionError("writer가 commit하면 안 된다 — 커밋 경계는 호출자 책임")


class TestTreatment:
    async def test_records_strategy_and_source_in_meta(self) -> None:
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
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

    async def test_leaves_outcome_columns_empty(self) -> None:
        """처치 시점에는 결과가 아직 없다 — 비워 두는 것이 정직하다."""
        session = _FakeSession()
        row = await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
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
            strategy="SOCRATIC",
            content_source="dsl_render",
            gate_reason_code="hint_not_escalated",
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert row.meta[META_KEY_GATE_REASON] == "hint_not_escalated"
        assert row.meta[META_KEY_STRATEGY] == "SOCRATIC"


class TestOutcome:
    async def test_records_correct_and_rt(self) -> None:
        session = _FakeSession()
        row = await record_pedagogy_outcome(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=uuid.UUID(int=1),
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
        session = _FakeSession()
        sid = uuid.uuid4()
        await record_pedagogy_treatment(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            strategy="ANALOGY",
            content_source="dsl_render",
            occurred_at=_AT,
        )
        await record_pedagogy_outcome(
            session,  # type: ignore[arg-type]
            objective_id="OBJ.1",
            k_type="CONCEPT",
            session_id=sid,
            correct=False,
            occurred_at=_AT,
        )
        assert {r.session_id for r in session.added} == {sid}


class TestB1PlaintextProhibition:
    def test_signatures_have_no_free_text_slot(self) -> None:
        """학생 원문이 들어올 파라미터가 **아예 없다** — 구조적 차단.

        `text`/`utterance`/`payload` 류 슬롯이 생기면 평문 저장 경로가 열린다. 시그니처 수준에서
        막아 두면 실수로도 흘릴 수 없다.
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
