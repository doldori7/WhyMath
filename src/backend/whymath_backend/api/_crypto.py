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


__all__ = ["SecretCipher", "build_secret_cipher"]
