"""디바이스 secret at-rest 봉투(envelope) 암호화 — AES-256-GCM (slice 72).

`PgDeviceStore`는 v1에서 `secret_plain`을 평문 저장한다 — verify가 `HMAC(secret, device_id)`
재계산에 *원본*을 써야 해서 KDF(one-way)로는 검증이 불가하기 때문(`_device_store.py` 모듈
docstring). 그 결과 DB dump·DBA 접근 시 모든 device secret이 노출되는 게 위협 모델이다.

봉투 암호화는 secret을 *마스터 키*(DB 밖·env/Settings)로 AES-GCM 암호화해 저장한다 → DB dump
*단독*으로는 복호 불가(마스터 키가 DB에 없으므로). verify는 복호 후 HMAC 재계산.

설계:
  - **AES-256-GCM**(AEAD): 기밀성 + *무결성*. ciphertext 변조 시 복호가 `InvalidTag`로 실패
    (조용한 비트플립 차단). 96-bit nonce를 매 암호화 새로 생성(GCM 권장·키 재사용 한계 내).
  - **키 = 32바이트**(AES-256). Settings `device_secret_encryption_key`(base64)에서 주입.
  - **봉투만 구현**: 진짜 KMS(키 회전·HSM·per-secret DEK)는 후속. 본 모듈은 단일 마스터 키
    봉투를 제공하고 키 *출처*만 추상화(`build_secret_cipher`).

이 슬라이스(72)는 *프리미티브*만 — `PgDeviceStore` 결선(컬럼·register 암호화·verify 복호화)은
후속 슬라이스. 보안 코드는 프리미티브를 격리해 먼저 철저히 검증한다.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_BYTES = 32  # AES-256
_NONCE_BYTES = 12  # 96-bit — GCM 표준 권장 nonce 길이


class SecretCipher:
    """AES-256-GCM 봉투 암호화기 — `encrypt`/`decrypt` (nonce는 매 암호화 새로 생성).

    키는 32바이트(AES-256). 같은 인스턴스를 재사용해도 매 `encrypt`가 새 nonce를 뽑으므로
    동일 평문도 매번 다른 ciphertext가 된다(결정론 노출 차단).
    """

    def __init__(self, key: bytes) -> None:
        if len(key) != _KEY_BYTES:
            raise ValueError(
                f"AES-256 마스터 키는 {_KEY_BYTES}바이트여야 합니다(받음: {len(key)}바이트). "
                "base64 디코딩 후 길이를 확인하세요."
            )
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """평문 → `(ciphertext, nonce)`. ciphertext는 GCM 인증 태그를 포함(변조 탐지)."""
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return ciphertext, nonce

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> str:
        """`(ciphertext, nonce)` → 평문. 변조·잘못된 키/nonce면 `InvalidTag` raise(조용한 실패 X).

        GCM 인증 태그가 ciphertext에 포함돼 무결성 검증 — 비트플립·키 불일치를 예외로 노출한다.
        """
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")


def build_secret_cipher(settings: Any) -> SecretCipher | None:
    """`Settings.device_secret_encryption_key`에서 `SecretCipher` 생성 — 미설정이면 None.

    None은 *암호화 비활성*(평문 폴백·기존 동작) 신호다(호출자가 분기). 키는 base64 인코딩
    32바이트. 잘못된 길이면 `SecretCipher.__init__`이 `ValueError`(부팅 시 fail-fast 가능).

    `settings: Any` — `whymath_backend.config.Settings` 순환 import 회피(typing-only 명시).
    """
    raw = settings.device_secret_encryption_key.get_secret_value()
    if not raw:
        return None
    key = base64.b64decode(raw)
    return SecretCipher(key)


def encrypt_secret_for_storage(
    cipher: SecretCipher | None, secret_plain: str
) -> tuple[str | None, bytes | None, bytes | None]:
    """slice 73: register용 — `(secret_plain, secret_encrypted, nonce)` 저장 3-튜플 결정.

    cipher 있으면 `(None, ciphertext, nonce)`(평문 컬럼 비우고 암호화 저장), 없으면
    `(secret_plain, None, None)`(평문 폴백·기존 동작). 셋 중 *정확히 한 표현*만 채워진다.
    """
    if cipher is None:
        return secret_plain, None, None
    ciphertext, nonce = cipher.encrypt(secret_plain)
    return None, ciphertext, nonce


def resolve_stored_secret(
    cipher: SecretCipher | None,
    secret_plain: str | None,
    secret_encrypted: bytes | None,
    nonce: bytes | None,
) -> str:
    """slice 73: verify용 — 저장 표현에서 HMAC용 평문 secret 복원.

    암호화 행(secret_encrypted+nonce)이면 복호, 평문 행이면 그대로 반환. *암호화 행인데
    cipher 미설정*이면 `RuntimeError`(조용한 401 lockout 대신 *시끄러운* 500 — 운영자가 키
    유실/미설정을 즉시 인지). 둘 다 없으면 데이터 무결성 오류(RuntimeError).
    """
    if secret_encrypted is not None and nonce is not None:
        if cipher is None:
            raise RuntimeError(
                "암호화된 device secret이나 복호 키가 미설정입니다 — "
                "`WHYMATH_DEVICE_SECRET_ENCRYPTION_KEY`를 확인하세요(키 유실 시 복호 불가)."
            )
        return cipher.decrypt(secret_encrypted, nonce)
    if secret_plain is not None:
        return secret_plain
    raise RuntimeError(
        "device 자격증명 행에 secret_plain·secret_encrypted가 모두 없습니다(데이터 무결성 오류)."
    )


__all__ = [
    "SecretCipher",
    "build_secret_cipher",
    "encrypt_secret_for_storage",
    "resolve_stored_secret",
]
