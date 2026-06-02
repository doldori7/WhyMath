"""디바이스별 고유 HMAC 시크릿 저장소 — OAuth-style 등록 + 검증.

슬라이스 22 — 슬라이스 21의 *공유* HMAC secret 한계 해소(앱 바이너리 추출 시 모든 디바이스
서명 위조 가능). 본 모듈은 *디바이스별 고유 secret*을 서버가 발급·검증한다:

1. **등록**: 클라이언트가 `POST /v1/devices/register` 호출 → 서버가 `device_id`(UUID4)와
   `secret_plain`(URL-safe 32B 토큰) 생성 → `secret_hash`(SHA-256·솔트 없음 — 고엔트로피
   토큰엔 KDF 불필요)만 저장 → `secret_plain`을 *1회만* 응답으로 반환.
2. **저장**: 클라이언트는 secret을 KeyChain/Keystore(iOS/Android) 등 *기기 안전 저장소*에
   보관(앱 파일에 평문 저장 금지). 분실 시 재등록(이전 device_id 폐기).
3. **검증**: 매 요청 `X-Device-Sig = HMAC-SHA256(secret_plain, device_id)` 동봉 →
   서버 `store.verify(device_id, sig)` → 저장된 secret_hash로 `HMAC(secret_plain, device_id)`
   재계산 비교 — 불가(secret_plain은 미저장)... 그러므로 *서명 검증은 다른 방식*:
   서버가 받은 `X-Device-Sig`를 secret_hash와 비교? No — HMAC은 secret이 필요한데 서버엔
   hash만 있음.

**설계 결정(v1)**: secret_hash 대신 *secret_plain을 메모리에만* 보관(`dict[device_id, plain]`,
프로세스 재시작 시 분실 → 재등록). 이는 다음 트레이드오프:
  - 보안: 서버 메모리 dump 시 모든 secret 노출. 운영은 *DB 영속(secret_hash + plain은 응답
    1회만)*이 필요하나 *서명 검증을 KDF 없이* 하려면 KMS·HMAC-key envelope 등 추가 인프라
    필요. 그 인프라는 후속 슬라이스(인메모리는 패턴 정합·`RateLimitBackend` 인메모리/Redis
    선택과 동일).
  - 단순성: v1은 단일 프로세스 인메모리. 분산은 후속(DB-backed + secret_plain envelope).

**위협 모델 명시**: slice 21보다 *나음*(공유 secret 공격면 제거) — 한 디바이스가 노출돼도
다른 디바이스 영향 0. 정식 위협 모델(replay·revocation·rotation)은 후속 슬라이스.
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from hashlib import sha256
from typing import Protocol, runtime_checkable


@runtime_checkable
class DeviceCredentialStore(Protocol):
    """디바이스 자격증명 저장소 경계 — 등록·검증·폐기.

    구현은 인메모리(`InMemoryDeviceStore`) 또는 DB-backed(후속). secret_plain은 등록 응답
    *1회만* 노출 — 저장소는 영구 보관 가능하나 *읽기 외부 노출 없음*.
    """

    def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        """새 device_id + secret_plain 발급. 반환 `(device_id, secret_plain)`. 1회 응답 후
        secret_plain은 다시 노출 불가(클라이언트가 안전 저장)."""
        ...

    def verify(self, device_id: str, signature_hex: str) -> bool:
        """`signature_hex`가 device_id에 대한 유효 서명인지(`HMAC-SHA256(secret, device_id)`).

        device_id 미등록·서명 불일치 시 False. 상수-시간 비교(타이밍 공격 방어).
        """
        ...

    def revoke(self, device_id: str) -> bool:
        """등록 폐기 — 향후 verify는 False. 미존재면 False, 폐기 성공이면 True."""
        ...


class InMemoryDeviceStore:
    """단일 프로세스 인메모리 — 분산/HA·재시작 영속은 DB-backed 후속.

    v1: secret_plain을 *그대로 메모리* 보관(검증에 HMAC 재계산 필요·hash만으론 불가). 보안
    트레이드오프는 모듈 docstring 참조. 매 register는 새 UUID4·URL-safe 32B 토큰 생성.
    """

    def __init__(self) -> None:
        # device_id → (user_id, secret_plain, revoked)
        self._creds: dict[str, tuple[uuid.UUID, str, bool]] = {}

    def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        device_id = str(uuid.uuid4())
        # 32B URL-safe token — ~256-bit entropy(보안 충분·KDF 불필요)
        secret_plain = secrets.token_urlsafe(32)
        self._creds[device_id] = (user_id, secret_plain, False)
        return device_id, secret_plain

    def verify(self, device_id: str, signature_hex: str) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        _user, secret_plain, revoked = cred
        if revoked:
            return False
        expected = hmac.new(
            secret_plain.encode("utf-8"), device_id.encode("utf-8"), sha256
        ).hexdigest()
        return hmac.compare_digest(signature_hex.lower(), expected)

    def revoke(self, device_id: str) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        user, secret_plain, _ = cred
        self._creds[device_id] = (user, secret_plain, True)
        return True

    def reset(self) -> None:
        """테스트 격리용 — 모든 자격증명 초기화."""
        self._creds.clear()


# 모듈 전역 — FastAPI 단일 프로세스 가정. 분산은 DB-backed로 교체(후속).
# `None`이면 store 모드 비활성(slice 21 shared-secret 폴백). 테스트·운영은 `set_store`로 활성.
_DEVICE_STORE: DeviceCredentialStore | None = None


def set_device_store(store: DeviceCredentialStore | None) -> None:
    """전역 store 설정 — None이면 slice 21 폴백."""
    global _DEVICE_STORE
    _DEVICE_STORE = store


def get_device_store() -> DeviceCredentialStore | None:
    """현재 store 반환(미설정 시 None)."""
    return _DEVICE_STORE
