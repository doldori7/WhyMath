"""JWT 액세스 토큰 발급·검증(순수, FastAPI 무관) — L5 인증 집행 계층.

`UserProfile`엔 credential 필드가 없어 토큰은 `sub=user_id`만 담는 *집행 토큰*이다. 실제 로그인
(카카오/네이버 OAuth, 후속)이 `create_access_token`을 호출해 발급하는 게 설계이고, 지금은 발급
seam과 검증만 둔다. 시크릿(`Settings.jwt_secret_key`)이 비면 명확한 RuntimeError(빈 시크릿으로
서명/검증하는 사고 방지 — CLAUDE.md 보안). 토큰 자체 오류(만료·서명 불일치·sub 누락)는 jose
`JWTError`로 표면화하고, FastAPI 의존성(`api/_auth.py`)이 401로 변환한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from whymath_backend.config import Settings

_MISCONFIG = "JWT 시크릿 미설정 — WHYMATH_JWT_SECRET_KEY 환경변수가 필요합니다"


def create_access_token(
    user_id: uuid.UUID | str,
    *,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """user_id를 sub로 하는 서명된 액세스 토큰 발급. 시크릿 미설정 시 RuntimeError(발급 불가)."""
    if not settings.jwt_configured:
        raise RuntimeError(f"{_MISCONFIG}(토큰 발급 불가).")
    now = datetime.now(tz=timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded: str = jwt.encode(
        claims,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return encoded


def decode_access_token(token: str, *, settings: Settings) -> str:
    """토큰을 검증하고 sub(user_id 문자열)를 반환. 만료·서명 불일치·sub 누락 시 jose JWTError.

    시크릿 미설정은 RuntimeError(서버 구성 오류 — 토큰 문제와 구분, 401 아닌 500).
    """
    if not settings.jwt_configured:
        raise RuntimeError(f"{_MISCONFIG}(토큰 검증 불가).")
    claims = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
    subject = claims.get("sub")
    if not subject:
        raise JWTError("토큰에 sub(user_id) 클레임이 없습니다.")
    return str(subject)
