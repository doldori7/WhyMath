"""디바이스 secret 봉투 암호화 단위테스트 — AES-256-GCM (slice 72, hermetic).

프리미티브(`SecretCipher`)와 팩토리(`build_secret_cipher`)를 격리 검증한다 — round-trip·
nonce 유일성·변조 탐지(GCM 인증)·잘못된 키/길이·키 미설정 비활성.
"""

from __future__ import annotations

import base64
import os

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr

from whymath_backend.api._crypto import SecretCipher, build_secret_cipher
from whymath_backend.config import Settings

_KEY = os.urandom(32)
_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings(enc_key_b64: str = "") -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        device_secret_encryption_key=SecretStr(enc_key_b64),
    )


class TestSecretCipher:
    def test_round_trip(self) -> None:
        """encrypt → decrypt가 원본 평문 복원."""
        cipher = SecretCipher(_KEY)
        ct, nonce = cipher.encrypt("s3cr3t-token-xyz")
        assert cipher.decrypt(ct, nonce) == "s3cr3t-token-xyz"

    def test_round_trip_non_ascii(self) -> None:
        """비-ASCII(한글·이모지)도 utf-8 round-trip."""
        cipher = SecretCipher(_KEY)
        secret = "비밀토큰🔐áé"
        ct, nonce = cipher.encrypt(secret)
        assert cipher.decrypt(ct, nonce) == secret

    def test_nonce_unique_per_encrypt(self) -> None:
        """같은 평문도 매 encrypt가 새 nonce·다른 ciphertext(결정론 노출 차단)."""
        cipher = SecretCipher(_KEY)
        ct1, n1 = cipher.encrypt("same")
        ct2, n2 = cipher.encrypt("same")
        assert n1 != n2
        assert ct1 != ct2
        # 그래도 둘 다 같은 평문으로 복호
        assert cipher.decrypt(ct1, n1) == cipher.decrypt(ct2, n2) == "same"

    def test_tamper_detected(self) -> None:
        """ciphertext 1바이트 변조 → 복호가 InvalidTag(조용한 비트플립 차단)."""
        cipher = SecretCipher(_KEY)
        ct, nonce = cipher.encrypt("token")
        tampered = bytes([ct[0] ^ 0x01]) + ct[1:]
        with pytest.raises(InvalidTag):
            cipher.decrypt(tampered, nonce)

    def test_wrong_key_fails(self) -> None:
        """다른 키로는 복호 불가(InvalidTag) — DB dump만으로 복호 불가의 근거."""
        ct, nonce = SecretCipher(_KEY).encrypt("token")
        with pytest.raises(InvalidTag):
            SecretCipher(os.urandom(32)).decrypt(ct, nonce)

    def test_wrong_nonce_fails(self) -> None:
        """nonce 불일치 → 복호 실패."""
        cipher = SecretCipher(_KEY)
        ct, _nonce = cipher.encrypt("token")
        with pytest.raises(InvalidTag):
            cipher.decrypt(ct, os.urandom(12))

    def test_invalid_key_length_rejected(self) -> None:
        """32바이트 아닌 키는 ValueError(부팅 fail-fast 근거)."""
        with pytest.raises(ValueError, match="32바이트"):
            SecretCipher(os.urandom(16))


class TestBuildSecretCipher:
    def test_none_when_key_unset(self) -> None:
        """키 미설정(빈 문자열)이면 None — 암호화 비활성(평문 폴백)."""
        assert build_secret_cipher(_settings("")) is None

    def test_cipher_when_key_set(self) -> None:
        """base64 32바이트 키 설정 시 SecretCipher 반환·round-trip 동작."""
        key_b64 = base64.b64encode(os.urandom(32)).decode()
        cipher = build_secret_cipher(_settings(key_b64))
        assert cipher is not None
        ct, nonce = cipher.encrypt("token")
        assert cipher.decrypt(ct, nonce) == "token"

    def test_invalid_length_key_raises(self) -> None:
        """base64 디코딩 후 길이가 32가 아니면 ValueError(설정 오류 fail-fast)."""
        bad_b64 = base64.b64encode(os.urandom(16)).decode()
        with pytest.raises(ValueError, match="32바이트"):
            build_secret_cipher(_settings(bad_b64))
