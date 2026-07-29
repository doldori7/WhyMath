"""JWT 토큰 헬퍼 단위테스트 — create/decode 왕복·만료·서명·미설정."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from jose import JWTError, jwt
from pydantic import SecretStr
from whymath_backend.config import Settings
from whymath_backend.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)

_SECRET = "test-secret-key-0123456789abcdef"


def _settings(secret: str = _SECRET) -> Settings:
    """테스트 Settings — jwt_secret_key를 명시 주입(init 인자가 env보다 우선)."""
    return Settings(jwt_secret_key=SecretStr(secret))


def test_create_decode_roundtrip() -> None:
    settings = _settings()
    user_id = uuid.uuid4()
    token = create_access_token(user_id, settings=settings)
    assert decode_access_token(token, settings=settings) == str(user_id)


def test_expired_token_raises_jwterror() -> None:
    settings = _settings()
    token = create_access_token(
        uuid.uuid4(), settings=settings, expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(JWTError):
        decode_access_token(token, settings=settings)


def test_wrong_secret_raises_jwterror() -> None:
    token = create_access_token(uuid.uuid4(), settings=_settings("secret-aaaaaaaaaaaaaaaa"))
    with pytest.raises(JWTError):
        decode_access_token(token, settings=_settings("secret-bbbbbbbbbbbbbbbb"))


def test_tampered_token_raises_jwterror() -> None:
    settings = _settings()
    token = create_access_token(uuid.uuid4(), settings=settings)
    with pytest.raises(JWTError):
        decode_access_token(token + "x", settings=settings)


def test_token_without_sub_raises_jwterror() -> None:
    """sub 클레임이 없는 토큰은 JWTError(검증 실패)."""
    settings = _settings()
    token = jwt.encode(
        {"foo": "bar"},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(JWTError):
        decode_access_token(token, settings=settings)


def test_missing_secret_raises_runtimeerror() -> None:
    """빈 시크릿(미설정)은 발급·검증 모두 RuntimeError(서버 구성 오류)."""
    settings = Settings(jwt_secret_key=SecretStr(""))
    with pytest.raises(RuntimeError):
        create_access_token(uuid.uuid4(), settings=settings)
    with pytest.raises(RuntimeError):
        decode_access_token("any-token", settings=settings)


def test_refresh_create_decode_roundtrip() -> None:
    settings = _settings()
    user_id = uuid.uuid4()
    jti = uuid.uuid4()
    token = create_refresh_token(user_id, settings=settings, jti=jti)
    claims = decode_refresh_token(token, settings=settings)
    assert claims.subject == str(user_id)
    assert claims.jti == str(jti)


def test_refresh_expired_raises_jwterror() -> None:
    settings = _settings()
    token = create_refresh_token(
        uuid.uuid4(), settings=settings, jti=uuid.uuid4(), expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(JWTError):
        decode_refresh_token(token, settings=settings)


def test_access_token_rejected_as_refresh() -> None:
    """typ=access 토큰을 리프레시로 디코드하면 JWTError(용도 오용 차단)."""
    settings = _settings()
    token = create_access_token(uuid.uuid4(), settings=settings)
    with pytest.raises(JWTError):
        decode_refresh_token(token, settings=settings)


def test_refresh_token_rejected_as_access() -> None:
    """typ=refresh 토큰을 액세스로 디코드하면 JWTError(용도 오용 차단)."""
    settings = _settings()
    token = create_refresh_token(uuid.uuid4(), settings=settings, jti=uuid.uuid4())
    with pytest.raises(JWTError):
        decode_access_token(token, settings=settings)


def test_refresh_token_without_jti_raises_jwterror() -> None:
    """jti 클레임 없는 리프레시 토큰은 JWTError(서버측 취소 추적 불가·a3b 계약)."""
    settings = _settings()
    token = jwt.encode(
        {"sub": "u-123", "typ": "refresh"},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(JWTError):
        decode_refresh_token(token, settings=settings)


def test_legacy_access_token_without_typ_still_decodes() -> None:
    """후방호환: typ 클레임 없는 기존 액세스 토큰도 decode_access_token이 받아준다."""
    settings = _settings()
    token = jwt.encode(
        {"sub": "u-123"},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(token, settings=settings) == "u-123"


def test_refresh_missing_secret_raises_runtimeerror() -> None:
    """빈 시크릿(미설정)은 리프레시 발급·검증 모두 RuntimeError(서버 구성 오류)."""
    settings = Settings(jwt_secret_key=SecretStr(""))
    with pytest.raises(RuntimeError):
        create_refresh_token(uuid.uuid4(), settings=settings, jti=uuid.uuid4())
    with pytest.raises(RuntimeError):
        decode_refresh_token("any-token", settings=settings)
