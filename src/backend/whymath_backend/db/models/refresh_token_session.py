"""refresh_token_session 테이블 — 리프레시 토큰 서버측 취소(allowlist)·OAuth-a3b 백킹 행.

a3의 stateless 리프레시 토큰엔 만료 전 개별 취소 수단이 없었다(빈자리). a3b는 발급된 리프레시
토큰마다 *세션 행*을 두어(allowlist), `/v1/auth/refresh`가 매 갱신에서 행의 존재·미취소를
확인하고, `/v1/auth/logout`이 행을 `revoked=true`로 만들어(denylist) 즉시 무효화한다. 행의 PK는
리프레시 토큰의 `jti` 클레임이라, 토큰을 디코드해 곧장 PK lookup 한다.

설계(`device.py` DeviceCredential 동형 — 서버 내부 크리덴셜 테이블):
- **PK = token_session_id(UUID) = 리프레시 토큰 jti**: 발급 시 앱이 `uuid.uuid4()`로 만들어
  토큰 클레임과 행 PK에 동시에 박는다(resolve_user의 user_id 앱 생성과 동형). server_default에
  의존하지 않는 건 발급 코드가 *발급 전에* jti 값을 알아야 하기 때문.
- **user_id FK → user_profile.user_id (NOT NULL)**: 사용자별 세션 일괄취소(a3c)·소유 검증.
  CASCADE 미적용 — 사용자 삭제 시 정리는 상위 lifecycle 몫(device.py 방침).
- **expires_at**: 리프레시 토큰 만료(발급 시 `now + jwt_refresh_expire_minutes`). *프루닝·감사*
  용도이고 실제 만료 게이트는 JWT `exp`(decode가 강제). 약간의 시각 오차는 무해.
- **revoked / revoked_at**: 로그아웃·관리 취소 플래그(device.py revoked 동형). `/refresh`는
  revoked=true면 거부. revoke는 멱등.
- **회전(rotation)·재사용 탐지는 a3c. 세션 목록 조회·전체/단건 로그아웃은 SEC-10(D4)**: 본
  테이블이 그 기반(인덱스 포함) — 신규 테이블 0.
- **platform(SEC-10)**: `GET /v1/auth/sessions`가 "낯선 기기 인지" 용도로만 노출하는 좁은 요약
  (`"iOS"`/`"Android"`/`"Web"`/`NULL`). IP·User-Agent *원문*은 이 테이블에도, 다른 어떤 테이블
  에도 저장하지 않는다(최소 수집 — `account_security_gap_review.md` D4). `api/auth.py`의
  `_summarize_platform`이 로그인·리프레시 시점 `User-Agent` 헤더에서 도출한다. nullable —
  이 컬럼 도입 이전 발급 세션은 값이 없다(소급 채움 없음).

Pydantic `schema/` 상응물 없음(서버 내부 테이블 — device.py 방침).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class RefreshTokenSession(Base):
    """리프레시 토큰 세션(allowlist) 행 — 발급된 리프레시 토큰 1개당 1행(PK=jti).

    `/v1/auth/refresh`는 토큰 jti로 이 행을 PK lookup 해 *존재·미취소*를 확인하고(allowlist),
    `/v1/auth/logout`은 `revoked=true`로 만들어 즉시 무효화한다(denylist). 만료 게이트 자체는
    JWT `exp`이고, expires_at은 프루닝·감사용.
    """

    __tablename__ = "refresh_token_session"

    # PK = 리프레시 토큰 jti(앱이 uuid4로 발급 — 토큰 클레임과 동시에 박음·server_default 없음).
    token_session_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    # user_profile.user_id FK — 사용자별 일괄취소(a3c)·소유 검증. CASCADE 미적용(device.py 방침).
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id"), nullable=False
    )
    # 발급 시각 — 운영/감사. server_default now()(misconception_hypothesis 선례).
    issued_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    # 리프레시 토큰 만료(발급 시 앱이 now + jwt_refresh_expire_minutes로 설정) — 프루닝·감사용.
    # 실제 만료 거부는 JWT exp(decode_refresh_token)가 강제.
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    # 취소 플래그 — /refresh는 revoked=true면 거부. /logout이 채운다. revoke는 멱등.
    revoked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    # 취소 시각 — 미취소는 NULL.
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # 플랫폼 요약(SEC-10) — "iOS"/"Android"/"Web"/NULL. IP·UA 원문은 저장하지 않는다(최소 수집).
    platform: Mapped[str | None] = mapped_column(sa.String(32))

    # 사용자별 세션 조회·일괄취소(a3c) 접근 경로(device.idx_device_credential_user 동형).
    __table_args__ = (
        sa.Index(
            "idx_refresh_token_session_user",
            "user_id",
            sa.desc("issued_at"),
        ),
    )


__all__ = ["RefreshTokenSession"]
