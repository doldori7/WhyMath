"""슬라이스4 evidence 봉투 암호화 테스트 — encrypt/resolve/build (dialogue 선례 미러·2-튜플).

hermetic: 암호 프리미티브만(PG·네트워크 불요).
변별력: 변조 시 InvalidTag·암호행+키없음 시 RuntimeError.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr
from whymath_backend.api._crypto import (
    SecretCipher,
    build_evidence_payload_cipher,
    encrypt_evidence_payload,
    resolve_evidence_payload,
)


@dataclass
class _KeyStub:
    """`build_evidence_payload_cipher`가 읽는 두 속성만 가진 최소 settings 대역."""

    evidence_payload_encryption_key: SecretStr
    evidence_payload_decryption_fallback_keys: SecretStr


def _cipher() -> SecretCipher:
    return SecretCipher(os.urandom(32))


class TestEvidenceRoundTrip:
    def test_encrypt_then_resolve(self) -> None:
        cipher = _cipher()
        payload = '{"utterance": "학생 원문 발화", "step": 2}'
        ct, nonce = encrypt_evidence_payload(cipher, payload)
        assert isinstance(ct, bytes) and isinstance(nonce, bytes)
        assert resolve_evidence_payload(cipher, ct, nonce) == payload

    def test_tamper_raises_invalid_tag(self) -> None:
        cipher = _cipher()
        ct, nonce = encrypt_evidence_payload(cipher, "민감 본문")
        assert ct is not None and nonce is not None
        tampered = bytes([ct[0] ^ 0x01]) + ct[1:]  # 첫 바이트 비트플립
        with pytest.raises(InvalidTag):
            resolve_evidence_payload(cipher, tampered, nonce)

    def test_cipher_none_writes_nothing(self) -> None:
        # B1: cipher 없으면 암호행 미기록(메타 전용) — 평문 저장 없음.
        assert encrypt_evidence_payload(None, "민감 본문") == (None, None)

    def test_payload_none_writes_nothing(self) -> None:
        assert encrypt_evidence_payload(_cipher(), None) == (None, None)

    def test_meta_only_resolves_none(self) -> None:
        assert resolve_evidence_payload(_cipher(), None, None) is None

    def test_encrypted_row_without_key_raises_loud(self) -> None:
        # 암호행인데 cipher 미설정 → 조용한 유실 대신 시끄러운 RuntimeError.
        with pytest.raises(RuntimeError):
            resolve_evidence_payload(None, b"ciphertext", b"nonce12bytes")


class TestBuildEvidenceCipher:
    def test_key_present_builds_cipher(self) -> None:
        key = base64.b64encode(os.urandom(32)).decode()
        stub = _KeyStub(SecretStr(key), SecretStr(""))
        cipher = build_evidence_payload_cipher(stub)
        assert cipher is not None
        # 회전 무중단 — primary로 암호화·복호 왕복.
        ct, nonce = cipher.encrypt("본문")
        assert cipher.decrypt(ct, nonce) == "본문"

    def test_no_key_returns_none(self) -> None:
        stub = _KeyStub(SecretStr(""), SecretStr(""))
        assert build_evidence_payload_cipher(stub) is None
