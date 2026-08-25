"""EOS Audit Event SDK — `audit.emit(...)` 및 헬퍼 (ADMIN-10).

`docs/architecture/90_audit_log.md`가 정본. 모든 중요한 변경은 이 SDK를 통해
`audit_event` 테이블에 append-only로 기록한다.
"""

from __future__ import annotations

from whymath_backend.audit.event_bus import (
    emit,
    emit_ai_event,
    emit_content_event,
    emit_identity_event,
)

__all__ = [
    "emit",
    "emit_ai_event",
    "emit_content_event",
    "emit_identity_event",
]
