"""개인정보(privacy) 인프라 — 삭제권 등 횡단 데이터 보호 오케스트레이션.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.3(R11). L1~L7 어디에도 속하지 않는
*횡단 인프라*다(여러 계층 모델을 가로질러 사용자 데이터를 다룬다). 첫 좌석은 삭제권 오케스트레이션
(`erasure.erase_user`) — 한 사용자의 모든 학생-연결 데이터를 단일 트랜잭션으로 영구 삭제한다.
SEC-09(`audit.py`)는 개인정보 감사 3종(반출·동의변경·관리자접근) writer + IP 해싱을 더한다.
"""

from __future__ import annotations

from whymath_backend.privacy.audit import (
    hash_client_ip,
    record_admin_access_audit,
    record_consent_change_audit,
    record_export_audit,
)
from whymath_backend.privacy.erasure import ErasureReport, erase_user
from whymath_backend.privacy.export import (
    ExternalDataLocation,
    UserDataExport,
    export_user_data,
    external_export_pending,
)

__all__ = [
    "ErasureReport",
    "ExternalDataLocation",
    "UserDataExport",
    "erase_user",
    "export_user_data",
    "external_export_pending",
    "hash_client_ip",
    "record_admin_access_audit",
    "record_consent_change_audit",
    "record_export_audit",
]
