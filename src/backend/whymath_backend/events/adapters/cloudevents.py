"""CloudEvents 1.0 Adapter.

EOS Canonical Education Event → CloudEvents envelope 변환.
CloudEvents는 infrastructure envelope 참고 모델로 사용한다.
"""

from __future__ import annotations

import json
from typing import Any

from whymath_backend.schema.education_event import EducationEvent


def to_cloudevents(event: EducationEvent) -> dict[str, Any]:
    """EducationEvent를 CloudEvents 1.0 JSON 형식으로 변환."""
    # payload와 context는 JSON serializable해야 함.
    data = event.model_dump(mode="json", by_alias=False)
    return {
        "specversion": "1.0",
        "type": f"whymath.eos.{event.event_type}",
        "source": f"whymath.io/{event.source.service}",
        "id": event.event_id,
        "time": event.occurred_at.isoformat(),
        "datacontenttype": "application/json",
        "data": data,
    }


def to_cloudevents_bytes(event: EducationEvent) -> bytes:
    """CloudEvents envelope을 UTF-8 JSON bytes로 직렬화."""
    return json.dumps(to_cloudevents(event), ensure_ascii=False).encode("utf-8")
