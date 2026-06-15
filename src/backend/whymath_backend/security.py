"""JWT 액세스·리프레시 토큰 발급·검증(순수, FastAPI 무관) — L5 인증 집행 계층.

`UserProfile`엔 credential 필드가 없어 토큰은 `sub=user_id`만 담는 *집행 토큰*이다. 실제 로그인
(카카오/네이버 OAuth)이 `create_access_token`·`create_refresh_token`을 호출해 발급한다. 두 토큰은
`typ` 클레임("access"·"refresh")으로 용도를 구분한다 — 리프레시를 액세스로(또는 그 반대로)
오용하면 `JWTError`. **후방호환**: `typ` 없는 기존 액세스 토큰은 액세스로 받는다(기발급 무효화
방지). 시크릿(`Settings.jwt_secret_key`)이 비면 명확한 RuntimeError(빈 시크릿으로 서명/검증하는
사고 방지 — CLAUDE.md 보안). 토큰 자체 오류(만료·서명 불일치·sub 누락·typ 불일치)는 jose
`JWTError`로 표면화하고, FastAPI 의존성(`api/_auth.py`·`api/auth.py`)이 401로 변환한다.

★리프레시는 **stateless 서명 토큰**(storage 없음) — 만료 전엔 서버측 개별 취소가 불가하다. 회전
(rotation)·denylist·세션 목록 같은 서버측 취소는 후속(DB 백킹). 단 `/refresh`는 사용자 존재를
확인해 *삭제된 사용자*의 갱신은 거부한다(`api/auth.py`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from whymath_backend.config import Settings

_MISCONFIG = "JWT 시크릿 미설정 — WHYMATH_JWT_SECRET_KEY 환경변수가 필요합니다"

# 토큰 용도 구분 클레임(typ) — 액세스/리프레시 오용 방지. 후방호환: typ 없는 토큰은 액세스로 간주.
_TYPE_CLAIM = "typ"
_ACCESS_TYPE = "access"
_REFRESH_TYPE = "refresh"


def _encode_token(
    user_id: uuid.UUID | str,
    *,
    settings: Settings,
    token_type: str,
    default_minutes: int,
    expires_delta: timedelta | None,
) -> str:
    """user_id를 sub로, token_type을 typ로 담는 서명 토큰 발급. 시크릿 미설정 시 RuntimeError."""
    if not settings.jwt_configured:
        raise RuntimeError(f"{_MISCONFIG}(토큰 발급 불가).")
    now = datetime.now(tz=timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=default_minutes))
    claims = {
        "sub": str(user_id),
        _TYPE_CLAIM: token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded: str = jwt.encode(
        claims,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return encoded


def _decode_token(token: str, *, settings: Settings, expected_type: str) -> str:
    """토큰 검증 후 sub 반환. 만료·서명·sub 누락·typ 불일치 시 JWTError, 미설정 시 RuntimeError.

    typ 검증은 후방호환: `expected_type==refresh`면 typ가 정확히 "refresh"여야 하고(액세스/typ
    없는 토큰을 리프레시로 못 씀), `expected_type==access`면 typ가 "refresh"만 거부한다(typ 없는
    기존 액세스 토큰은 허용).
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
    token_type = claims.get(_TYPE_CLAIM)
    if expected_type == _REFRESH_TYPE:
        if token_type != _REFRESH_TYPE:
            raise JWTError("리프레시 토큰이 아닙니다(typ 불일치).")
    elif token_type == _REFRESH_TYPE:
        raise JWTError("리프레시 토큰은 액세스 토큰으로 사용할 수 없습니다(typ 불일치).")
    return str(subject)


def create_access_token(
    user_id: uuid.UUID | str,
    *,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """user_id를 sub로 하는 서명된 액세스 토큰(typ=access) 발급. 시크릿 미설정 시 RuntimeError."""
    return _encode_token(
        user_id,
        settings=settings,
        token_type=_ACCESS_TYPE,
        default_minutes=settings.jwt_expire_minutes,
        expires_delta=expires_delta,
    )


def create_refresh_token(
    user_id: uuid.UUID | str,
    *,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """user_id를 sub로 하는 서명된 리프레시 토큰(typ=refresh) 발급. 시크릿 미설정 시 RuntimeError.

    긴 TTL(`jwt_refresh_expire_minutes`·기본 30일)로 `/v1/auth/refresh`에서 새 액세스 토큰과
    교환한다. stateless(storage 없음) — 만료 전 서버측 취소는 불가(후속 회전·denylist).
    """
    return _encode_token(
        user_id,
        settings=settings,
        token_type=_REFRESH_TYPE,
        default_minutes=settings.jwt_refresh_expire_minutes,
        expires_delta=expires_delta,
    )


def decode_access_token(token: str, *, settings: Settings) -> str:
    """액세스 토큰 검증 후 sub(user_id) 반환. 만료·서명·sub 누락·리프레시 토큰 시 JWTError.

    시크릿 미설정은 RuntimeError(서버 구성 오류 — 토큰 문제와 구분, 401 아닌 500).
    """
    return _decode_token(token, settings=settings, expected_type=_ACCESS_TYPE)


def decode_refresh_token(token: str, *, settings: Settings) -> str:
    """리프레시 토큰 검증 후 sub(user_id) 반환. 만료·서명·sub 누락·액세스 토큰 시 JWTError.

    시크릿 미설정은 RuntimeError(서버 구성 오류, 401 아닌 500).
    """
    return _decode_token(token, settings=settings, expected_type=_REFRESH_TYPE)
