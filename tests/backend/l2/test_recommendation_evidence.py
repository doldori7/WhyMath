"""L2 추천 폐루프 회계 writer — `evidence_event` 기록 좌석 단위테스트 (REC-03·hermetic).

`l2/pedagogy_evidence.py`(PED-03) 테스트 스타일 승계. 관심사:
  - 학생에게 실제로 반환된 추천만 기록(가짜 처치 금지)한다는 계약 — 호출부는 이 모듈이
    아니라 `api/me.py` 쪽에서 지키므로(test_me.py), 여기서는 함수 자체의 순수 기록 동작만.
  - **B1**: 학생 원문·user_id가 들어갈 슬롯이 시그니처에 없고, 암호문 컬럼도 건드리지 않는다.
  - 커밋하지 않는다(호출자 경계 — `pedagogy_evidence` 선례).
  - PED-03 집계(`effectiveness.py`)의 `event_type.in_([...])` 필터와 겹치지 않는 event_type.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

from whymath_backend.l2 import recommendation_evidence
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME as PEDAGOGY_EVENT_TYPE_OUTCOME,
)
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_TREATMENT as PEDAGOGY_EVENT_TYPE_TREATMENT,
)
from whymath_backend.l2.recommendation_evidence import (
    EVENT_TYPE_RECOMMENDATION_TREATMENT,
    META_KEY_APPLIED_WEIGHTS,
    META_KEY_GATE_REASON,
    META_KEY_MODE,
    META_KEY_POOL_SIZE,
    META_KEY_PROBLEM_ID,
    META_KEY_THETA,
    record_recommendation_treatment,
)

_AT = datetime(2026, 8, 3, tzinfo=UTC)


class _FakeSession:
    """`session.add`만 관찰하는 가짜 세션 — commit이 호출되면 즉시 실패한다."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:  # pragma: no cover - 호출되면 테스트 실패
        raise AssertionError("writer가 commit하면 안 된다 — 커밋 경계는 호출자 책임")


class TestRecommendationTreatment:
    async def test_records_problem_theta_pool_size_and_weights_in_meta(self) -> None:
        session = _FakeSession()
        pid = uuid.uuid4()
        row = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=pid,
            theta=0.42,
            pool_size=50,
            applied_weights=True,
            occurred_at=_AT,
        )
        assert session.added == [row]
        assert row.event_type == EVENT_TYPE_RECOMMENDATION_TREATMENT
        assert row.meta is not None
        assert row.meta[META_KEY_PROBLEM_ID] == str(pid)
        assert row.meta[META_KEY_THETA] == 0.42
        assert row.meta[META_KEY_POOL_SIZE] == 50
        assert row.meta[META_KEY_APPLIED_WEIGHTS] is True

    async def test_omits_optional_meta_keys_when_absent(self) -> None:
        """None인 선택 키(mode·gate_reason)는 넣지 않는다 — '없음'과 'null 기록'을 구분."""
        session = _FakeSession()
        row = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=uuid.uuid4(),
            theta=0.0,
            pool_size=10,
            applied_weights=False,
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert META_KEY_MODE not in row.meta
        assert META_KEY_GATE_REASON not in row.meta

    async def test_records_mode_and_gate_reason_when_present(self) -> None:
        session = _FakeSession()
        row = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=uuid.uuid4(),
            theta=1.5,
            pool_size=30,
            applied_weights=False,
            mode="suneung",
            gate_reason="persona_ineligible",
            occurred_at=_AT,
        )
        assert row.meta is not None
        assert row.meta[META_KEY_MODE] == "suneung"
        assert row.meta[META_KEY_GATE_REASON] == "persona_ineligible"

    async def test_session_id_is_fresh_placeholder_each_call(self) -> None:
        """결합 축(session_id)이 아직 없다 — 매 호출마다 새 UUID(재사용 0)."""
        session = _FakeSession()
        row_a = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=uuid.uuid4(),
            theta=0.0,
            pool_size=1,
            applied_weights=False,
            occurred_at=_AT,
        )
        row_b = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=uuid.uuid4(),
            theta=0.0,
            pool_size=1,
            applied_weights=False,
            occurred_at=_AT,
        )
        assert row_a.session_id != row_b.session_id

    def test_event_type_does_not_collide_with_pedagogy_axis(self) -> None:
        """PED-03 집계(effectiveness.py)의 event_type 필터에 걸리지 않아야 오염이 없다."""
        assert EVENT_TYPE_RECOMMENDATION_TREATMENT not in (
            PEDAGOGY_EVENT_TYPE_TREATMENT,
            PEDAGOGY_EVENT_TYPE_OUTCOME,
        )

    def test_event_type_constant_is_frozen(self) -> None:
        expected = "recommendation_render"
        assert recommendation_evidence.EVENT_TYPE_RECOMMENDATION_TREATMENT == expected


class TestB1PlaintextProhibition:
    def test_signature_has_no_free_text_or_user_id_slot(self) -> None:
        """학생 원문·user_id가 들어올 파라미터가 **아예 없다** — 구조적 차단.

        `pedagogy_evidence`와 같은 금지어 집합에 `user_id`를 추가한다 — 이 좌석은
        `evidence_event`에 user_id 컬럼 자체가 없다는 B1 설계(가명화 유지)를
        시그니처 수준에서도 강제한다.
        """
        forbidden = {
            "text",
            "utterance",
            "payload",
            "content",
            "answer",
            "solution",
            "body",
            "user_id",
        }
        params = set(inspect.signature(record_recommendation_treatment).parameters)
        assert not (params & forbidden), f"원문/식별 슬롯 발견: {params & forbidden}"

    async def test_ciphertext_columns_untouched(self) -> None:
        session = _FakeSession()
        row = await record_recommendation_treatment(
            session,  # type: ignore[arg-type]
            problem_id=uuid.uuid4(),
            theta=0.0,
            pool_size=1,
            applied_weights=False,
            occurred_at=_AT,
        )
        assert row.payload_encrypted is None
        assert row.payload_nonce is None
