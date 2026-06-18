"""개인정보(privacy) 인프라 — 삭제권 등 횡단 데이터 보호 오케스트레이션.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.3(R11). L1~L7 어디에도 속하지 않는
*횡단 인프라*다(여러 계층 모델을 가로질러 사용자 데이터를 다룬다). 첫 좌석은 삭제권 오케스트레이션
(`erasure.erase_user`) — 한 사용자의 모든 학생-연결 데이터를 단일 트랜잭션으로 영구 삭제한다.
"""

from __future__ import annotations

from whymath_backend.privacy.erasure import ErasureReport, erase_user

__all__ = ["ErasureReport", "erase_user"]
