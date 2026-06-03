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
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NamedTuple, Protocol, cast, runtime_checkable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DeviceInfo(NamedTuple):
    """본인 디바이스 목록 응답의 *내부* 표현 — store→라우터 seam.

    Pydantic 응답 schema는 `api/devices.py`가 별도 정의(레이어 분리: store는 *데이터 표면*,
    라우터는 *HTTP 표면*). secret_plain·user_id는 노출 안 함(보안·PII 표면 최소화).

    slice 32: `last_used_at` 추가 — 마지막 verify 성공 시각(없으면 None=한 번도 미사용).
    `CachedDeviceStore` 경유 시 cache miss에서만 갱신(정밀도 ≈ cache TTL).

    slice 37: `revoked` + `revoked_at` 추가 — `include_revoked=True` 모드에서 *본인 폐기 이력*
    노출용. 본인 데이터라 user_id PII 우려 없음. 폐기 시각으로 UI가 "3일 전 폐기됨" 등 표시.
    """

    device_id: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None


class _CredRecord(NamedTuple):
    """InMemoryDeviceStore 내부 행 — 슬라이스 32에서 last_used_at 추가하며 NamedTuple로
    리팩터(이전 4-tuple 인덱싱 → 이름 접근). `_replace`로 불변 업데이트 가능.

    slice 37: `revoked_at` 추가 — Pg ORM과 parity(slice 23). revoke/cleanup_stale은
    `datetime.now(UTC)` 채움·미폐기는 None.
    """

    user_id: uuid.UUID
    secret_plain: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


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

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        """등록 폐기 — *본인 소유 디바이스만*. 미존재·타인 소유면 False(idempotent + 정보 비누설).

        타인 device 폐기 시도 시 False 반환 — 404와 동일 응답(존재 여부를 노출하지 않음·
        device_id 열거 공격 방어). slice 24 추가: `owner_id` 인자(인증된 사용자의 user_id).
        """
        ...

    async def list_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        """본인 소유 device 목록 — 최신 등록순(`created_at` DESC).

        slice 29 추가·기본 *활성*(미폐기) device만. slice 37: `include_revoked=True`면 폐기
        이력 포함. slice 38: `limit/offset` 페이지네이션 — `include_revoked=True` 시 폐기
        이력이 폭증할 수 있어 *페이지 단위* 응답. 라우터가 limit 상한 검증(`device_list_
        max_limit`)·여기선 신뢰. 빈 리스트는 *해당 페이지에 결과 없음*(클라이언트가 stop).
        """
        ...

    async def count_for_user(self, owner_id: uuid.UUID, *, include_revoked: bool = False) -> int:
        """slice 39: 본인 소유 device *총 개수* — UI "Page X of Y"·"총 N개" 표시용.

        라우터에서 `?include_total=true` 옵션 시만 호출(추가 COUNT 쿼리 비용 회피). list_for_
        user와 *같은 필터 조건*(owner_id 스코프·include_revoked 필터) — pagination invariant.
        """
        ...

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        """slice 33: N일 이상 미사용 활성 device 자동 폐기 → 폐기된 device_id 목록 반환.

        조건: `revoked=False` AND `(last_used_at < now - N일) OR (last_used_at IS NULL AND
        created_at < now - N일)` — 한 번도 verify 안 된 device는 created_at 기준(등록만 하고
        방치된 device 차단). 정상 사용자 무영향(매월 1회 이상 verify는 보장). cron/Celery beat
        에서 일일 호출 권장. revoke와 같은 효과(verify 거부)이나 `owner_id` 검증 없음(*시스템
        호출*·관리자 권한 의미).

        slice 34: ① 반환을 `int` → `list[str]`로 확장 — 호출자가 *어느* device가 폐기됐는지
        식별 가능 → CachedDeviceStore가 정확한 키들만 일괄 invalidate(슬라이스 26 invariant
        강화). ② `dry_run=True`(기본 False)면 *상태 변경 0*·식별만 → 운영자가 "어느 device가
        폐기될지" 미리 보기(preview). 건수는 `len(result)`로 그대로 얻음.
        """
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
        # slice 32: 내부 행을 `_CredRecord` NamedTuple로 리팩터(이전 4-tuple).
        self._creds: dict[str, _CredRecord] = {}

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        device_id = str(uuid.uuid4())
        # 32B URL-safe token — ~256-bit entropy(보안 충분·KDF 불필요)
        secret_plain = secrets.token_urlsafe(32)
        self._creds[device_id] = _CredRecord(
            user_id=user_id,
            secret_plain=secret_plain,
            revoked=False,
            created_at=datetime.now(UTC),
            last_used_at=None,
            revoked_at=None,
        )
        return device_id, secret_plain

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        if cred.revoked:
            return False
        expected = _compute_signature(cred.secret_plain, device_id)
        if not hmac.compare_digest(signature_hex.lower(), expected):
            return False
        # slice 32: last_used_at 갱신(성공 경로만)
        self._creds[device_id] = cred._replace(last_used_at=datetime.now(UTC))
        return True

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        cred = self._creds.get(device_id)
        if cred is None:
            return False
        # slice 24: 본인 소유 검증 — 타인 device면 False(404 등가·정보 비누설)
        if cred.user_id != owner_id:
            return False
        # slice 37: revoked_at 채움 — Pg ORM parity
        self._creds[device_id] = cred._replace(revoked=True, revoked_at=datetime.now(UTC))
        return True

    async def list_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        # slice 29: 본인 소유 device — created_at DESC 정렬
        # slice 32: last_used_at 함께 노출
        # slice 37: include_revoked=True면 폐기 이력 포함·revoked/revoked_at 노출
        # slice 38: limit/offset 페이지네이션
        items = [
            DeviceInfo(
                device_id=d,
                created_at=c.created_at,
                last_used_at=c.last_used_at,
                revoked=c.revoked,
                revoked_at=c.revoked_at,
            )
            for d, c in self._creds.items()
            if c.user_id == owner_id and (include_revoked or not c.revoked)
        ]
        items.sort(key=lambda info: info.created_at, reverse=True)
        return items[offset : offset + limit]

    async def count_for_user(self, owner_id: uuid.UUID, *, include_revoked: bool = False) -> int:
        # slice 39: list_for_user와 같은 필터·페이지네이션 적용 *전* 총 개수
        return sum(
            1
            for c in self._creds.values()
            if c.user_id == owner_id and (include_revoked or not c.revoked)
        )

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        # slice 33+34: N일 이상 미사용 활성 device 식별 + 옵션 폐기. dry_run이면 식별만.
        threshold = datetime.now(UTC) - timedelta(days=max_age_days)
        affected: list[str] = []
        now = datetime.now(UTC)
        for device_id, cred in list(self._creds.items()):
            if cred.revoked:
                continue
            # 한 번도 verify 안 됐으면 등록 시각 기준 — 등록만 하고 방치된 device 차단
            last_active = cred.last_used_at or cred.created_at
            if last_active < threshold:
                affected.append(device_id)
                if not dry_run:
                    # slice 37: revoked_at 채움(Pg ORM parity·slice 33의 누락 수정)
                    self._creds[device_id] = cred._replace(revoked=True, revoked_at=now)
        return affected

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
            if not hmac.compare_digest(signature_hex.lower(), expected):
                return False
            # slice 32: last_used_at 갱신(verify 성공 경로만). CachedDeviceStore의 cache
            # miss 경로에서만 진입 — cache hit은 inner 우회라 last_used_at은 *대략* 신선.
            row.last_used_at = datetime.now(UTC)
            await session.commit()
        return True

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            # slice 24: WHERE에 user_id 추가 — 타인 device는 0행 매치 → False(404 등가)
            stmt = (
                update(DeviceCredential)
                .where(
                    DeviceCredential.device_id == device_id,
                    DeviceCredential.user_id == owner_id,
                )
                .values(revoked=True, revoked_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            # CursorResult.rowcount는 Result 베이스에 노출 안 됨 — DML 결과 한정 속성
            rowcount = getattr(result, "rowcount", 0) or 0
            return bool(rowcount > 0)

    async def list_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        # slice 29: SELECT WHERE user_id=X AND revoked=false ORDER BY created_at DESC.
        # slice 32: last_used_at 함께 SELECT.
        # slice 37: include_revoked=True면 revoked 필터 제거·revoked/revoked_at 컬럼 추가
        # slice 38: limit/offset 페이지네이션 — 서버측(SQL LIMIT/OFFSET, network 절감)
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            stmt = select(
                DeviceCredential.device_id,
                DeviceCredential.created_at,
                DeviceCredential.last_used_at,
                DeviceCredential.revoked,
                DeviceCredential.revoked_at,
            ).where(DeviceCredential.user_id == owner_id)
            if not include_revoked:
                stmt = stmt.where(DeviceCredential.revoked.is_(False))
            stmt = stmt.order_by(DeviceCredential.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [
                DeviceInfo(
                    device_id=row[0],
                    created_at=row[1],
                    last_used_at=row[2],
                    revoked=row[3],
                    revoked_at=row[4],
                )
                for row in result.all()
            ]

    async def count_for_user(self, owner_id: uuid.UUID, *, include_revoked: bool = False) -> int:
        # slice 39: SELECT COUNT(*) WHERE user_id=X [AND revoked=False] — 같은 필터.
        from sqlalchemy import func

        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            stmt = (
                select(func.count())
                .select_from(DeviceCredential)
                .where(DeviceCredential.user_id == owner_id)
            )
            if not include_revoked:
                stmt = stmt.where(DeviceCredential.revoked.is_(False))
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        # slice 33+34: SELECT 활성 candidates → Python 필터 → 옵션 UPDATE 반복.
        # dry_run=True면 SELECT만(상태 변경 0)·preview용.
        from whymath_backend.db.models.device import DeviceCredential

        threshold = datetime.now(UTC) - timedelta(days=max_age_days)
        async with self._sessionmaker() as session:
            sel = select(
                DeviceCredential.device_id,
                DeviceCredential.last_used_at,
                DeviceCredential.created_at,
            ).where(DeviceCredential.revoked.is_(False))
            result = await session.execute(sel)
            stale_ids = [
                row[0]
                for row in result.all()
                # last_used_at 우선·없으면 created_at(한 번도 verify 안 됨)
                if (row[1] or row[2]) < threshold
            ]
            if dry_run:
                return stale_ids
            now = datetime.now(UTC)
            for device_id in stale_ids:
                upd = (
                    update(DeviceCredential)
                    .where(DeviceCredential.device_id == device_id)
                    .values(revoked=True, revoked_at=now)
                )
                await session.execute(upd)
            await session.commit()
        return stale_ids


# 모듈 전역 — FastAPI 단일 프로세스/다중 워커 가정. `None`이면 store 모드 비활성
# (slice 21 shared-secret 폴백). 운영 lifespan은 `set_device_store(PgDeviceStore(...))`로 활성.
_DEVICE_STORE: DeviceCredentialStore | None = None


# ──────────────────────────────────────────────────────────────────────────
# 슬라이스 26 — verify 결과 Redis 캐시(데코레이터)
#
# 슬라이스 23 한계 ③(매 verify가 PG 라운드트립 → connection pool 부담) 해소. *유효한*
# (device_id, sig) 페어를 짧은 TTL로 캐시 → 정상 트래픽의 verify는 DB 0 라운드트립.
# 실패(미등록·잘못된 sig)는 캐시 안 함 — 공격자의 캐시 poison 시도는 inner.verify로 차단.
# revoke는 즉시 `DEL`로 invalidate — TTL 자연 만료 + 명시 DEL 이중 보장(stale window 최소).
# ──────────────────────────────────────────────────────────────────────────


_VERIFY_CACHE_KEY_PREFIX = "device_verify:"
_COUNT_CACHE_KEY_PREFIX = "device_count:"  # slice 40: count_for_user 결과 캐시


@runtime_checkable
class _CacheClient(Protocol):
    """디바이스 verify 캐시용 좁은 Redis 인터페이스 — GET/SETEX/DEL/PING(slice 30 health)."""

    async def get(self, key: str) -> Any:
        """캐시 GET — 없으면 None. bytes/str 모두 호환(decode_responses 설정 무관)."""
        ...

    async def setex(self, key: str, seconds: int, value: str) -> Any:
        """SETEX — TTL 동봉 SET(원자적·TTL 만료 시 자동 제거)."""
        ...

    async def delete(self, *keys: str) -> Any:
        """키 삭제(가변 키)."""
        ...

    async def ping(self) -> Any:
        """연결 도달성 확인 — startup health check(slice 30) 전용."""
        ...


class CachedDeviceStore:
    """`DeviceCredentialStore` 데코레이터 — verify 결과를 Redis로 캐시.

    슬라이스 26 — slice 23의 `PgDeviceStore`는 매 verify가 PK SELECT 라운드트립. 정상
    트래픽(매 요청 `X-Device-Sig` 검증)은 *반복되는 동일 쿼리* → 캐시 효과 큼. 본 데코레이터는
    *모든* `DeviceCredentialStore` 구현을 감쌀 수 있다(InMemory 감싸기는 무의미하나 무해).

    캐시 의미:
      - **key**: `device_verify:{device_id}` — 한 디바이스당 1개(정당 서명은 결정론적·HMAC).
      - **value**: 마지막 성공한 *유효 서명*의 hex(lowercase) 문자열.
      - **TTL**: 짧게(권장 60s) — revoke 후 stale 기간을 제한.
      - **성공만 캐시**: 실패(미등록·잘못된 sig)는 SETEX 안 함 → 공격자의 잘못된 sig가 캐시 자리
        차지 못 함(매 시도 DB 라운드트립). 정상 클라이언트의 정당 sig만 캐시·재요청은 0 RTT.

    invalidation: `revoke(True)` 즉시 `DEL device_verify:{X}` → stale 즉시 0. DEL 실패에도 TTL
    자연 만료로 stale window는 TTL 이내(이중 안전망).

    캐시 클라이언트 보안: 캐시엔 *서명*만 저장(secret_plain·user_id·만료 정보 등 *추가 PII 0*).
    Redis dump가 노출돼도 *그 디바이스의 정당 서명*만 알려지나, 그 서명은 어차피 매 요청에 평문
    노출(`X-Device-Sig` 헤더)이라 *새 노출면 0*.
    """

    def __init__(
        self,
        inner: DeviceCredentialStore,
        cache: _CacheClient,
        ttl_seconds: int = 60,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        result = await self._inner.register(user_id)
        # slice 40: count 캐시 invalidate(active·all 두 키) — 새 device가 count에 반영
        await self._cache.delete(
            f"{_COUNT_CACHE_KEY_PREFIX}{user_id}:active",
            f"{_COUNT_CACHE_KEY_PREFIX}{user_id}:all",
        )
        return result

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        # 1) 캐시 GET — hit + 일치면 DB 라운드트립 0
        cache_key = _VERIFY_CACHE_KEY_PREFIX + device_id
        cached = await self._cache.get(cache_key)
        if cached is not None:
            cached_str = cached.decode("utf-8") if isinstance(cached, bytes) else cached
            # 상수시간 비교 — 캐시 hit 경로도 타이밍 공격 방어
            if hmac.compare_digest(cached_str, signature_hex.lower()):
                return True
        # 2) 캐시 미스/불일치 → inner(DB) 위임
        result = await self._inner.verify(device_id, signature_hex)
        # 3) 성공만 캐시 — 실패는 매번 DB(공격자의 poison 시도 차단)
        if result:
            await self._cache.setex(cache_key, self._ttl, signature_hex.lower())
        return result

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        # revoke 성공 시 즉시 캐시 invalidate — stale window 최소화
        result = await self._inner.revoke(device_id, owner_id)
        if result:
            # slice 26: verify 캐시 DEL + slice 40: count 캐시 두 키 모두 DEL(폐기로 active 감소)
            await self._cache.delete(
                _VERIFY_CACHE_KEY_PREFIX + device_id,
                f"{_COUNT_CACHE_KEY_PREFIX}{owner_id}:active",
                f"{_COUNT_CACHE_KEY_PREFIX}{owner_id}:all",
            )
        return result

    async def list_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        # 목록 조회는 캐시 안 함 — 등록/폐기 직후 신선도 우선(빈도 낮은 관리 표면).
        # slice 37: include_revoked·slice 38: limit/offset 그대로 inner에 전달
        return await self._inner.list_for_user(
            owner_id, include_revoked=include_revoked, limit=limit, offset=offset
        )

    async def count_for_user(self, owner_id: uuid.UUID, *, include_revoked: bool = False) -> int:
        # slice 40: count 결과 캐시 — register/revoke가 즉시 invalidate하므로 stale 위험 ≈ 0
        # (cleanup_stale은 시스템 호출·TTL 자연 만료로 회복). 키 접미사 active/all로
        # include_revoked 분기 분리(서로 다른 값).
        suffix = "all" if include_revoked else "active"
        cache_key = f"{_COUNT_CACHE_KEY_PREFIX}{owner_id}:{suffix}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            cached_str = cached.decode("utf-8") if isinstance(cached, bytes) else cached
            return int(cached_str)
        result = await self._inner.count_for_user(owner_id, include_revoked=include_revoked)
        await self._cache.setex(cache_key, self._ttl, str(result))
        return result

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        # slice 34: inner가 폐기 device_id 목록을 반환하므로 *정확히* 그 키들만 캐시 invalidate.
        # slice 33의 "TTL 자연 만료" 트레이드오프 해소 — stale 기간 즉시 0(DEL 성공 가정).
        # dry_run=True면 inner도 상태 변경 0·캐시도 건드리지 않음.
        affected = await self._inner.cleanup_stale(max_age_days, dry_run=dry_run)
        if not dry_run and affected:
            await self._cache.delete(*[_VERIFY_CACHE_KEY_PREFIX + d for d in affected])
        return affected


def set_device_store(store: DeviceCredentialStore | None) -> None:
    """전역 store 설정 — None이면 slice 21 폴백."""
    global _DEVICE_STORE
    _DEVICE_STORE = store


def get_device_store() -> DeviceCredentialStore | None:
    """현재 store 반환(미설정 시 None)."""
    return _DEVICE_STORE


# ──────────────────────────────────────────────────────────────────────────
# 슬라이스 27 — lifespan 결선(Settings.device_store_mode 기반 자동 활성)
#
# 운영자는 `WHYMATH_DEVICE_STORE_MODE=pg_cached` 한 줄로 store 활성 — 라우터/lifespan에
# `set_device_store` 코드 작성 불필요. 모드 3종(none/pg/pg_cached) × cleanup 책임(Redis
# 클라이언트 닫기) 일관 처리.
# ──────────────────────────────────────────────────────────────────────────


def build_device_store_from_settings(
    settings: Any,
) -> tuple[DeviceCredentialStore | None, Callable[[], Awaitable[None]]]:
    """`Settings.device_store_mode`에 맞춰 store + async cleanup 반환.

    반환 `(store, cleanup_fn)`:
      - `none` 모드 → `(None, noop)`. slice 21 공유 secret 폴백 동작.
      - `pg` 모드 → `(PgDeviceStore, noop)`. PG sessionmaker는 지연 엔진 생성·dispose는
        lifespan의 기존 `dispose_engine`이 책임(별도 cleanup 불필요).
      - `pg_cached` 모드 → `(CachedDeviceStore(PgDeviceStore, Redis), redis.aclose)`. Redis
        클라이언트는 본 함수가 생성 → cleanup_fn이 닫는다.

    호출자(lifespan)는 startup에 `set_device_store(store)` + shutdown에 `await cleanup_fn()`
    + `set_device_store(None)`. 본 함수는 *순수*(set_device_store는 호출자 책임).

    `settings: Any` — `whymath_backend.config.Settings` 순환 import 회피(typing-only 명시).
    """
    from whymath_backend.db.session import get_sessionmaker

    mode = settings.device_store_mode

    async def _noop() -> None:
        return None

    if mode == "none":
        return None, _noop

    sm = get_sessionmaker(settings)
    pg_store: DeviceCredentialStore = PgDeviceStore(sm)

    if mode == "pg":
        return pg_store, _noop

    # mode == "pg_cached" — Redis 클라이언트 생성·CachedDeviceStore 래핑
    redis_client = _build_redis_for_cache(settings)
    cached = CachedDeviceStore(
        pg_store, redis_client, ttl_seconds=settings.device_verify_cache_ttl_seconds
    )

    async def _close_redis() -> None:
        # redis.asyncio.Redis.aclose() — 연결 풀 반납(라이브 통합 테스트가 검증)
        close = getattr(redis_client, "aclose", None)
        if close is not None:
            await close()

    return cached, _close_redis


def _build_redis_for_cache(settings: Any) -> _CacheClient:  # pragma: no cover
    """기본 redis.asyncio 클라이언트 — 지연 import(라이브러리 없는 환경 보호).

    Redis 라이브러리·연결 의존성은 라이브 통합 테스트(@integration·실 Redis 데몬)에서
    검증한다 — hermetic 테스트는 모드를 `pg`/`none`으로 두거나 가짜 클라이언트 주입한다.
    """
    try:
        from redis.asyncio import Redis
    except ImportError as exc:
        raise RuntimeError(
            "redis Python 클라이언트가 설치되지 않았습니다. "
            "`pip install redis[hiredis]` 후 다시 시도하세요."
        ) from exc
    return cast(_CacheClient, Redis.from_url(settings.redis_url, decode_responses=True))


# ──────────────────────────────────────────────────────────────────────────
# 슬라이스 30 — startup health check (PG/Redis 도달성)
#
# 슬라이스 27의 한계 ①(Redis 연결은 lazy·미도달 시 첫 요청에서야 오류) 해소. 부팅 시 store가
# 의존하는 PG/Redis ping → 미도달 시 RuntimeError로 *fail-fast*(uvicorn이 startup 거부 →
# 좀비 인스턴스 방지). `device_store_mode == "none"`이면 검증 0(slice 21 폴백 동작).
# ──────────────────────────────────────────────────────────────────────────


async def _retry_with_timeout(
    operation: Callable[[], Awaitable[Any]],
    *,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    jitter: bool = False,
) -> None:
    """slice 35: operation을 timeout 안에서 실행·실패 시 exponential backoff 재시도.

    각 시도는 독립 `asyncio.timeout`. 실패(TimeoutError/Exception 무관) 시 `backoff *
    2^attempt`초 대기 후 재시도. 모든 시도 실패하면 *마지막 예외*를 raise(호출자가 timeout vs
    기타 구분). 첫 시도 성공이면 backoff 0(정상 인프라 무영향).

    slice 36: `jitter=True`면 AWS-style *full jitter* — `uniform(0, base * 2^attempt)`.
    k8s 다수 pod 동시 재시작 시 thundering herd 차단(인프라 회복 직후 동시 폭주 방어).
    """
    import asyncio
    import random

    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            async with asyncio.timeout(timeout_seconds):
                await operation()
            return  # 성공
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                base = backoff_seconds * (2**attempt)
                # slice 36: jitter면 [0, base) 균등 분포·아니면 deterministic base
                delay = random.uniform(0, base) if jitter else base
                await asyncio.sleep(delay)
    # 모든 재시도 소진 — 마지막 예외 raise
    assert last_exc is not None  # unreachable(max_retries >= 1)
    raise last_exc


async def ping_device_store_health(settings: Any) -> None:
    """startup에 store 의존성(PG·Redis) 도달성 검증 — 실패 시 RuntimeError로 fail-fast.

    `pg`/`pg_cached` 모드면 PG ping(SELECT 1). `pg_cached`면 추가로 Redis ping. 메시지에
    어느 구성요소가 실패했는지·폴백 가능한 모드를 명시(운영 진단성).

    슬라이스 31: 각 ping에 `asyncio.timeout(settings.device_store_health_check_timeout_seconds)`
    적용 — 인프라 응답 지연 시 startup 무한 대기 방지.

    슬라이스 35: 각 ping에 `max_retries`회 재시도(exponential backoff) — 일시적 인프라 깜빡
    임(네트워크 일순 단절·DB 재시작 직후) 흡수. 정상 인프라엔 1회 통과(backoff 0).
    """
    from sqlalchemy import text

    from whymath_backend.db.session import get_sessionmaker

    mode = settings.device_store_mode
    if mode == "none":
        return

    timeout = settings.device_store_health_check_timeout_seconds
    max_retries = settings.device_store_health_check_max_retries
    backoff = settings.device_store_health_check_retry_backoff_seconds
    jitter = settings.device_store_health_check_retry_jitter

    # PG 도달성
    async def _pg_ping() -> None:
        sm = get_sessionmaker(settings)
        async with sm() as session:
            await session.execute(text("SELECT 1"))

    try:
        await _retry_with_timeout(
            _pg_ping,
            timeout_seconds=timeout,
            max_retries=max_retries,
            backoff_seconds=backoff,
            jitter=jitter,
        )
    except TimeoutError as exc:
        raise RuntimeError(
            f"device_store_mode={mode}이나 PostgreSQL ping이 {timeout}s 내 응답 없음"
            f"(재시도 {max_retries}회). 인프라 장애 의심 — `WHYMATH_DATABASE_URL`·"
            "네트워크 확인 또는 `WHYMATH_DEVICE_STORE_HEALTH_CHECK_TIMEOUT_SECONDS` 상향."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"device_store_mode={mode}이나 PostgreSQL 미도달(재시도 {max_retries}회): "
            f"{exc}. `WHYMATH_DATABASE_URL` 확인 또는 `WHYMATH_DEVICE_STORE_MODE=none`로 폴백."
        ) from exc

    # Redis 도달성(`pg_cached`만)
    if mode == "pg_cached":
        client = _build_redis_for_cache(settings)
        try:
            await _retry_with_timeout(
                client.ping,
                timeout_seconds=timeout,
                max_retries=max_retries,
                backoff_seconds=backoff,
                jitter=jitter,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"device_store_mode=pg_cached이나 Redis ping이 {timeout}s 내 응답 없음"
                f"(재시도 {max_retries}회). 인프라 장애 의심 — `WHYMATH_REDIS_URL`·"
                "네트워크 확인 또는 `WHYMATH_DEVICE_STORE_HEALTH_CHECK_TIMEOUT_SECONDS` 상향."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"device_store_mode=pg_cached이나 Redis 미도달(재시도 {max_retries}회): "
                f"{exc}. `WHYMATH_REDIS_URL` 확인 또는 `WHYMATH_DEVICE_STORE_MODE=pg`로 폴백."
            ) from exc
        finally:
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()
