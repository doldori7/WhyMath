"""EvidenceLink ORM — `to_schema()` JSON-safe 직렬화(열람·이동권 export 의존·hermetic·DB 0).

`privacy/export.py`가 `_row_to_json`→`to_schema().model_dump(mode="json")`로 본인 증거 그래프를
내보낸다. 본 테스트는 그 직렬화가 UUID·날짜·nullable을 JSON 안전하게 변환함을 *세션 없이* 잠근다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from whymath_backend.db.models.evidence_link import EvidenceLink


def test_to_schema_roundtrip_json_safe() -> None:
    sid, stu = uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 6, 19, 9, 0, tzinfo=UTC)
    row = EvidenceLink(
        link_id=7,
        session_id=sid,
        student_id=stu,
        event_id=42,
        misconception_id="distribution-over-power",
        node_id="HS-ALG-001",
        polarity=-1,
        weight=0.5,
        retention_until=date(2027, 3, 1),
        created_at=now,
    )
    payload = row.to_schema().model_dump(mode="json")
    assert payload["link_id"] == 7
    assert payload["student_id"] == str(stu)  # UUID → str
    assert payload["session_id"] == str(sid)
    assert payload["misconception_id"] == "distribution-over-power"
    assert payload["polarity"] == -1
    assert payload["weight"] == 0.5
    assert payload["retention_until"] == "2027-03-01"  # date → ISO
    assert payload["created_at"].startswith("2026-06-19")  # datetime → ISO


def test_to_schema_nullable_fields_none() -> None:
    # 느슨참조·미평가 컬럼은 None으로 안전 직렬화(PII 0·식별자/신호만).
    row = EvidenceLink(
        link_id=1,
        session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        misconception_id="x",
        polarity=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    payload = row.to_schema().model_dump(mode="json")
    assert payload["event_id"] is None
    assert payload["node_id"] is None
    assert payload["weight"] is None
    assert payload["retention_until"] is None
