"""MisconceptionHypothesisRecord ORM — `to_schema()` JSON-safe 직렬화(열람권 export·hermetic·DB 0).

`privacy/export.py`가 본인 오개념 가설 레코드를 `to_schema().model_dump(mode="json")`로 내보낸다.
Numeric(3,2)→float·UUID·datetime·nullable user_id의 JSON 안전 변환을 *세션 없이* 잠근다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from whymath_backend.db.models.misconception_hypothesis import MisconceptionHypothesisRecord


def test_to_schema_roundtrip_json_safe() -> None:
    rid, uid = uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 6, 19, 9, 0, tzinfo=UTC)
    row = MisconceptionHypothesisRecord(
        id=rid,
        user_id=uid,
        misconception_id="sine-distributes-over-sum",
        confidence=Decimal("0.75"),  # Numeric(3,2)가 DB서 반환하는 Decimal → float 강제 확인
        turns_since_evidence=2,
        evidence_count=3,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    payload = row.to_schema().model_dump(mode="json")
    assert payload["id"] == str(rid)  # UUID → str
    assert payload["user_id"] == str(uid)
    assert payload["misconception_id"] == "sine-distributes-over-sum"
    assert payload["confidence"] == 0.75  # Decimal → float (JSON number)
    assert payload["turns_since_evidence"] == 2
    assert payload["evidence_count"] == 3
    assert payload["is_active"] is True
    assert payload["created_at"].startswith("2026-06-19")


def test_to_schema_nullable_user_id_none() -> None:
    row = MisconceptionHypothesisRecord(
        id=uuid.uuid4(),
        misconception_id="x",
        confidence=Decimal("0.50"),
        turns_since_evidence=0,
        evidence_count=1,
        is_active=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    payload = row.to_schema().model_dump(mode="json")
    assert payload["user_id"] is None
    assert payload["is_active"] is False
