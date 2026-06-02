"""디바이스별 고유 HMAC 시크릿 저장소 — OAuth-style 등록 + 검증 + DB-backed 영속.

슬라이스 22(인메모리) → 슬라이스 23(DB-backed 영속·HA). 디바이스 자격증명을 PostgreSQL에
저장해 ① 프로세스 재시작 후에도 등록 보존(클라이언트 재등록 불필요) ② 다중 워커/HA 시
모든 워커가 동일 store 공유(인메모리는 워커별 상태가 갈라짐) ③ 운영 가시성(DB 쿼리로 등록
현황·폐기 이력·user_id별 매핑 확인 가능)을 확보한다.

세 구현체:
1. `InMemoryDeviceStore` — 단일 프로세스 dev·테스트용(슬라이스 22 그대로, async 시그너처로 전환).
2. `PgDeviceStore` — *운영 표준*. SQLAlchemy `async_sessionmaker`로 매 호출마다 짧은 세션을
   열고 닫는다(store 자체는 stateless·sessionmaker만 보유). FastAPI 라이프스팬에서
   `set_device_store(PgDeviceStore(get_sessionmaker()))`로 활성.

**async 전환 이유**(슬라이스 22 → 23): PG 접근이 async(asyncio·SQLAlchemy AsyncSession)라
Protocol 메서드를 모두 `async`로 통일했다. 호출처(라우터·`_client_device_id`)는 이미 async
컨텍스트(FastAPI) — `await store.method(...)` 한 줄 추가뿐. 인메모리도 `async def`로 맞춰
Protocol 일관성을 유지한다(인메모리 동작은 즉시 반환이라 비용 0).

**secret_plain 저장 방식 — v1 평문**(InMemory와 동일 트레이드오프):
  - **검증에 원본 필요**: `HMAC(secret_plain, device_id)` 재계산이 verify의 핵심이라 KDF
    (bcrypt/argon2)로 hash만 저장하면 검증 불가. KDF는 *one-way*라 HMAC 키로 못 쓴다.
  - **v1 절충**: secret_plain을 평문으로 DB에 저장. DB 접근 권한 가진 자(DBA·DB dump)는
    모든 secret 노출 가능. 후속(KMS envelope): secret_plain을 master key로 AES-GCM 암호화해
    `secret_encrypted bytea + nonce bytea` 저장 → verify 시 복호화 후 HMAC. KMS·rotation
    인프라 필요(`RateLimitBackend` 인메모리→Redis와 같은 점진 진보 모델).
  - **위협 모델 정합**: slice 22 인메모리는 메모리 dump 노출, slice 23 PG는 DB dump 노출. 둘
    다 *내부 침입자* 위협이고 *공격면은 같다*(KDF로 둘 다 안 됨, KMS envelope만 다음 단계).
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol, runtime_checkable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@runtime_checkable
class DeviceCredentialStore(Protocol):
    """디바이스 자격증명 저장소 경계 — 등록·검증·폐기(모두 async).

    구현체: `InMemoryDeviceStore`(dev/테스트), `PgDeviceStore`(운영 표준). secret_plain은
    *register 응답*에서만 외부 노출되고 그 외엔 저장소 내부에만 존재한다(서명 검증 위해
    필요 — 모듈 docstring 참조).
    """

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        """새 device_id + secret_plain 발급. 반환 `(device_id, secret_plain)`.
        secret_plain은 *이 응답에서만* 노출(클라이언트가 안전 저장 책임)."""
        ...

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        """`signature_hex`가 device_id에 대한 유효 서명인지(`HMAC-SHA256(secret, device_id)`).

        device_id 미등록·서명 불일치·폐기 시 False. 상수-시간 비교(타이밍 공격 방어).
        """
        ...

    async def revoke(self, device_id: str) -> bool:
        """등록 폐기 — 향후 verify는 False. 미존재면 False, 폐기 성공이면 True. idempotent."""
        ...


def _compute_signature(secret_plain: str, device_id: str) -> str:
    """`HMAC-SHA256(secret_plain, device_id)`의 hex digest(64자 lowercase)."""
    return hmac.new(secret_plain.encode("utf-8"), device_id.encode("utf-8"), sha256).hexdigest()


class InMemoryDeviceStore:
    """단일 프로세스 인메모리 — dev·테스트용. 운영은 `PgDeviceStore`(영속·HA).

    매 register는 새 UUID4 device_id + URL-safe 32B 토큰(secret_plain) 생성·내부 dict 보관.
    프로세스 재시작 시 모든 등록 분실(클라이언트는 재등록 필요).
    """

    def __init__(self) -> None:
        # device_id → (user_id, secret_plain, revoked)
        self._creds: dict[str, tuple[uuid.UUID, str, bool]] = {}

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        device_id = str(uuid.uuid4())
        # 32B URL-safe token — ~256-bit entropy(보안 충분·KDF 불필요)
        secret_plain = secrets.token_urlsafe(32)
        self._creds[device_id] = (user_id, secret_plain, False)
        return device_id, secret_plain

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        _user, secret_plain, revoked = cred
        if revoked:
            return False
        expected = _compute_signature(secret_plain, device_id)
        return hmac.compare_digest(signature_hex.lower(), expected)

    async def revoke(self, device_id: str) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        user, secret_plain, _ = cred
        self._creds[device_id] = (user, secret_plain, True)
        return True

    def reset(self) -> None:
        """테스트 격리용 — 모든 자격증명 초기화(sync — 호출자가 await 안 함)."""
        self._creds.clear()


class PgDeviceStore:
    """PostgreSQL-backed 영속 store — 운영 표준(슬라이스 23).

    `async_sessionmaker`를 받아 *자체* 짧은 세션을 매 호출마다 연다(close 자동). 호출자(라우터
    · `_client_device_id`)가 자기 세션을 store에 주입하지 않아도 되므로 FastAPI dep 체인
    단순화(slice 22 인메모리와 동일한 외부 시그너처).

    트랜잭션: register는 INSERT + commit(실패 시 자동 rollback·SQLAlchemy 컨텍스트매니저).
    verify는 read-only(commit 불필요). revoke는 UPDATE WHERE device_id + commit.

    **HA·다중 워커**: 모든 워커가 같은 PG를 가리키므로 한 워커에서 등록 → 다른 워커에서 verify
    가능. 인메모리(워커별 상태 분리)의 한계 해소.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        # 지연 import — 순환 import 방지(models가 schema를 import, 본 모듈은 models를 import)
        from whymath_backend.db.models.device import DeviceCredential

        device_id = str(uuid.uuid4())
        secret_plain = secrets.token_urlsafe(32)
        async with self._sessionmaker() as session:
            session.add(
                DeviceCredential(
                    device_id=device_id,
                    user_id=user_id,
                    secret_plain=secret_plain,
                    revoked=False,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        return device_id, secret_plain

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            row: DeviceCredential | None = await session.get(DeviceCredential, device_id)
            if row is None or row.revoked:
                return False
            expected = _compute_signature(row.secret_plain, device_id)
        return hmac.compare_digest(signature_hex.lower(), expected)

    async def revoke(self, device_id: str) -> bool:
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            stmt = (
                update(DeviceCredential)
                .where(DeviceCredential.device_id == device_id)
                .values(revoked=True, revoked_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            # CursorResult.rowcount는 Result 베이스에 노출 안 됨 — DML 결과 한정 속성
            rowcount = getattr(result, "rowcount", 0) or 0
            return bool(rowcount > 0)


# 모듈 전역 — FastAPI 단일 프로세스/다중 워커 가정. `None`이면 store 모드 비활성
# (slice 21 shared-secret 폴백). 운영 lifespan은 `set_device_store(PgDeviceStore(...))`로 활성.
_DEVICE_STORE: DeviceCredentialStore | None = None


def set_device_store(store: DeviceCredentialStore | None) -> None:
    """전역 store 설정 — None이면 slice 21 폴백."""
    global _DEVICE_STORE
    _DEVICE_STORE = store


def get_device_store() -> DeviceCredentialStore | None:
    """현재 store 반환(미설정 시 None)."""
    return _DEVICE_STORE
