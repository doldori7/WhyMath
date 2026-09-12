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
import itertools
import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, NamedTuple, Protocol, cast, runtime_checkable

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whymath_backend.api._crypto import (
    SupportsEnvelope,
    encrypt_secret_for_storage,
    require_device_secret_cipher,
    resolve_stored_secret,
)
from whymath_backend.api._degradation import DegradationCounter, DegradationSnapshot


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

    slice 54: `seq` 추가 — 등록 시 부여하는 *단조 증가* 순번(시계 무관). created_at 등
    정렬 컬럼이 거친 시계 해상도에서 동일 틱에 충돌해도(같은 created_at) 등록 순서로
    결정론적 2차 정렬을 보장한다(`list_for_user`). `_replace`는 seq를 자동 보존(불변).
    """

    user_id: uuid.UUID
    secret_plain: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    seq: int


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
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
        order_by: OrderByField = "created_at",
        order_dir: OrderDir = "desc",
        nulls: NullsPosition = "last",
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

    async def count_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
    ) -> int:
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
        # slice 54: 단조 증가 등록 순번 발급기 — 시계 해상도와 무관한 *논리적 순서*.
        # `datetime.now(UTC)`는 플랫폼에 따라 해상도가 거칠어(예: Windows ~15ms) 빠른
        # 연속 등록이 동일 created_at을 받을 수 있다 → 정렬·페이지네이션이 dict 삽입순서
        # (구현 세부)에 암묵 의존하게 된다. seq를 2차 정렬키로 써 등록 순서를 *명시*한다.
        self._seq = itertools.count()

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
            seq=next(self._seq),  # slice 54: 등록 순번(단조 증가)
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
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
        order_by: OrderByField = "created_at",
        order_dir: OrderDir = "desc",
        nulls: NullsPosition = "last",
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        # slice 29: 본인 소유 device — created_at DESC 정렬
        # slice 32: last_used_at 함께 노출
        # slice 37: include_revoked=True면 폐기 이력 포함·revoked/revoked_at 노출
        # slice 38: limit/offset 페이지네이션
        # slice 41: since/until created_at 시간창 필터(inclusive)
        # slice 43: revoked_since/until은 revoked_at 시간창 — 미폐기 device는 자동 제외
        # (revoked_at IS NULL이라 비교 False)
        # slice 54: seq(단조 등록 순번)를 정렬 2차키로 쓰려고 (cred, DeviceInfo) 쌍으로 필터.
        matched = [
            (
                c,
                DeviceInfo(
                    device_id=d,
                    created_at=c.created_at,
                    last_used_at=c.last_used_at,
                    revoked=c.revoked,
                    revoked_at=c.revoked_at,
                ),
            )
            for d, c in self._creds.items()
            if c.user_id == owner_id
            and (include_revoked or not c.revoked)
            and (since is None or c.created_at >= since)
            and (until is None or c.created_at <= until)
            and (
                revoked_since is None
                or (c.revoked_at is not None and c.revoked_at >= revoked_since)
            )
            and (
                revoked_until is None
                or (c.revoked_at is not None and c.revoked_at <= revoked_until)
            )
            and (
                used_since is None or (c.last_used_at is not None and c.last_used_at >= used_since)
            )
            and (
                used_until is None or (c.last_used_at is not None and c.last_used_at <= used_until)
            )
        ]
        # slice 46: 동적 order_by — None 두 그룹 정렬 후 합치는 패턴.
        # slice 47: `nulls`로 None 위치 명시 — last(기본·UI 친화) 또는 first.
        # slice 54: 1차 정렬키가 동률(같은 시계 틱→같은 created_at)이면 seq로 tie-break —
        # 등록 순서를 정렬 방향과 *같은 방향*으로 적용(desc=나중 등록 먼저). 이로써 정렬·
        # 페이지네이션이 시계 해상도나 dict 삽입순서에 의존하지 않는다. None 그룹은 시간값이
        # 없어(정렬 대상 아님) 등록 순서(dict 삽입) 그대로 둔다 — slice 47 동작 보존.
        reverse = order_dir == "desc"
        not_null = [(c, info) for c, info in matched if getattr(info, order_by) is not None]
        nulls_items = [(c, info) for c, info in matched if getattr(info, order_by) is None]
        not_null.sort(key=lambda pair: (getattr(pair[1], order_by), pair[0].seq), reverse=reverse)
        ordered = not_null + nulls_items if nulls == "last" else nulls_items + not_null
        return [info for _, info in ordered[offset : offset + limit]]

    async def count_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
    ) -> int:
        # slice 39: list_for_user와 같은 필터·페이지네이션 적용 *전* 총 개수
        # slice 41: since/until 동일 시간창 필터
        # slice 43: revoked_since/until 추가(미폐기는 자동 제외)
        return sum(
            1
            for c in self._creds.values()
            if c.user_id == owner_id
            and (include_revoked or not c.revoked)
            and (since is None or c.created_at >= since)
            and (until is None or c.created_at <= until)
            and (
                revoked_since is None
                or (c.revoked_at is not None and c.revoked_at >= revoked_since)
            )
            and (
                revoked_until is None
                or (c.revoked_at is not None and c.revoked_at <= revoked_until)
            )
            and (
                used_since is None or (c.last_used_at is not None and c.last_used_at >= used_since)
            )
            and (
                used_until is None or (c.last_used_at is not None and c.last_used_at <= used_until)
            )
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
        # slice 54: 순번 발급기도 재시작 — 초기화 후 등록은 0부터(테스트 결정론).
        self._seq = itertools.count()


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

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        cipher: SupportsEnvelope | None = None,
        *,
        allow_plaintext_fallback: bool = False,
    ) -> None:
        self._sessionmaker = sessionmaker
        # slice 73: 봉투 암호화기(None이면 평문 저장·기존 동작). register는 암호화 저장,
        # verify는 복호화. 평문 행(기존·암호화 비활성)은 dual-read 폴백으로 그대로 동작.
        # SEC-28: 평문 폴백은 개발/CI에서만 명시적 플래그로 허용(prod-like에서는 부팅 실패).
        self._cipher = cipher
        self._allow_plaintext_fallback = allow_plaintext_fallback

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        # 지연 import — 순환 import 방지(models가 schema를 import, 본 모듈은 models를 import)
        from whymath_backend.db.models.device import DeviceCredential

        device_id = str(uuid.uuid4())
        secret_plain = secrets.token_urlsafe(32)
        # slice 73: cipher 있으면 암호화 저장(평문 컬럼 NULL)·없으면 평문 폴백.
        # SEC-28: 평문 폴백은 개발/CI에서만 명시적 플래그로 허용.
        plain_col, encrypted, nonce = encrypt_secret_for_storage(
            self._cipher, secret_plain, allow_plaintext_fallback=self._allow_plaintext_fallback
        )
        async with self._sessionmaker() as session:
            session.add(
                DeviceCredential(
                    device_id=device_id,
                    user_id=user_id,
                    secret_plain=plain_col,
                    secret_encrypted=encrypted,
                    secret_nonce=nonce,
                    revoked=False,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        # 응답 secret은 *생성한 평문 토큰*(저장 표현과 무관·클라이언트가 서명에 사용)
        return device_id, secret_plain

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            row: DeviceCredential | None = await session.get(DeviceCredential, device_id)
            if row is None or row.revoked:
                return False
            # slice 73: 저장 표현(암호화/평문)에서 HMAC용 평문 복원(암호화 행+키 미설정은 raise)
            secret = resolve_stored_secret(
                self._cipher, row.secret_plain, row.secret_encrypted, row.secret_nonce
            )
            expected = _compute_signature(secret, device_id)
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
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
        order_by: OrderByField = "created_at",
        order_dir: OrderDir = "desc",
        nulls: NullsPosition = "last",
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
            # slice 41: since/until created_at 시간창 필터(inclusive)
            if since is not None:
                stmt = stmt.where(DeviceCredential.created_at >= since)
            if until is not None:
                stmt = stmt.where(DeviceCredential.created_at <= until)
            # slice 43: revoked_since/until — revoked_at 시간창. 미폐기는 자동 제외(NULL 비교 False)
            if revoked_since is not None:
                stmt = stmt.where(DeviceCredential.revoked_at >= revoked_since)
            if revoked_until is not None:
                stmt = stmt.where(DeviceCredential.revoked_at <= revoked_until)
            # slice 44: used_since/until — last_used_at 시간창. 한 번도 verify 안 된 device는
            # last_used_at IS NULL이라 SQL NULL 비교 자동 False로 제외
            if used_since is not None:
                stmt = stmt.where(DeviceCredential.last_used_at >= used_since)
            if used_until is not None:
                stmt = stmt.where(DeviceCredential.last_used_at <= used_until)
            # slice 46: 동적 order_by — 컬럼·방향 모두 동적
            # slice 47: NULLS FIRST/LAST 명시 — PG/InMemory 일관성
            order_col = getattr(DeviceCredential, order_by)
            order_expr = order_col.desc() if order_dir == "desc" else order_col.asc()
            order_expr = order_expr.nulls_last() if nulls == "last" else order_expr.nulls_first()
            # slice 63: seq 2차 정렬키로 동률 tie-break — InMemory(slice 54) parity.
            #  - 비-null 그룹: 정렬 방향과 같게(desc=나중 등록[큰 seq] 먼저·asc=먼저 등록 먼저).
            #  - null 그룹: *항상* 등록순(seq ASC) — InMemory가 dict 삽입순 보존(slice 47/54).
            # 두 CASE term은 각자 자기 그룹만 정렬(상대 그룹엔 NULL→무영향)이고 primary가 이미
            # 그룹을 분리하므로 동일 primary 값 내에서만 작동(그룹 경계 침범 없음).
            nonnull_case = case((order_col.isnot(None), DeviceCredential.seq))
            nonnull_tie = nonnull_case.desc() if order_dir == "desc" else nonnull_case.asc()
            null_tie = case((order_col.is_(None), DeviceCredential.seq)).asc()
            stmt = stmt.order_by(order_expr, nonnull_tie, null_tie).limit(limit).offset(offset)
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

    async def count_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
    ) -> int:
        # slice 39: SELECT COUNT(*) WHERE user_id=X [AND revoked=False] — 같은 필터.
        # slice 41: since/until 동일 시간창 필터
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
            if since is not None:
                stmt = stmt.where(DeviceCredential.created_at >= since)
            if until is not None:
                stmt = stmt.where(DeviceCredential.created_at <= until)
            # slice 43: revoked_since/until 동일
            if revoked_since is not None:
                stmt = stmt.where(DeviceCredential.revoked_at >= revoked_since)
            if revoked_until is not None:
                stmt = stmt.where(DeviceCredential.revoked_at <= revoked_until)
            # slice 44: used_since/until — last_used_at 시간창
            if used_since is not None:
                stmt = stmt.where(DeviceCredential.last_used_at >= used_since)
            if used_until is not None:
                stmt = stmt.where(DeviceCredential.last_used_at <= used_until)
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

    async def reencrypt_plaintext_secrets(self, *, batch_size: int = 100) -> int:
        """slice 74: 평문 저장된 secret을 봉투 암호화로 전환(백필) — 재암호화한 행 수 반환.

        slice 73은 *신규* register만 암호화했다(기존 평문 행은 잔존). 본 메서드는 마스터 키
        도입 후 기존 행을 점진 전환한다 — `secret_encrypted IS NULL`(=평문 행) 중 secret_plain
        있는 것을 batch_size개까지 암호화해 `secret_encrypted`/`secret_nonce`를 채우고
        `secret_plain=NULL`로 비운다. 이미 암호화된 행은 자동 제외(idempotent). 호출자가 0
        반환까지 반복해 전체 백필(대형 테이블 메모리/락 보호). cipher 미설정이면 0(no-op).

        *운영 일회성/관리자 경로*(cleanup_stale와 동형) — 구체 PgDeviceStore로 호출(요청
        경로 아님). secret_plain·secret_encrypted 둘 다 없는 이상 행은 건너뛴다(무결성 방어).
        """
        if self._cipher is None:
            return 0
        from whymath_backend.db.models.device import DeviceCredential

        async with self._sessionmaker() as session:
            sel = (
                select(DeviceCredential.device_id, DeviceCredential.secret_plain)
                .where(DeviceCredential.secret_encrypted.is_(None))
                .limit(batch_size)
            )
            result = await session.execute(sel)
            count = 0
            for device_id, secret_plain in result.all():
                if secret_plain is None:
                    continue  # 평문·암호문 둘 다 없는 이상 행 — 건드리지 않음
                ciphertext, nonce = self._cipher.encrypt(secret_plain)
                upd = (
                    update(DeviceCredential)
                    .where(DeviceCredential.device_id == device_id)
                    .values(
                        secret_plain=None,
                        secret_encrypted=ciphertext,
                        secret_nonce=nonce,
                    )
                )
                await session.execute(upd)
                count += 1
            await session.commit()
            return count


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


def _has_any_time_filter(*values: datetime | None) -> bool:
    """slice 45: 시간 필터 페어 6종(since/until·revoked_since/until·used_since/until) 중
    하나라도 *not None*인지 — CachedDeviceStore.count_for_user의 캐시 우회 판정·6-OR 분기
    추출. 후속에 시간 필터 추가 시 호출만 확장(분기 비대화 회피)."""
    return any(v is not None for v in values)


# slice 46: order_by 가능 컬럼 — DeviceInfo의 시간 컬럼 3종(slice 41/43/44 시간 차원과 정합)
OrderByField = Literal["created_at", "last_used_at", "revoked_at"]
OrderDir = Literal["asc", "desc"]
# slice 47: NULL 위치 — `last`(UI 친화 기본·아직 verify 안된 device 등 끝으로)·`first`
NullsPosition = Literal["last", "first"]


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


# ──────────────────────────────────────────────────────────────────────────
# OPS-06 — 캐시 장애 강등: **연산마다 판정이 다르다**
#
# OPS-05가 L3 응답 캐시에서 "get 실패 → 미스, set 실패 → no-op"으로 통일한 것과 달리, 이
# 캐시는 *인증 검증 결과*를 담기 때문에 연산별로 보안 함의가 갈린다. 판정 근거:
#
#   | 연산            | 실패 시        | 판정 | 근거                                       |
#   |-----------------|----------------|------|--------------------------------------------|
#   | get(verify)     | 미스로 강등    | 안전 | DB(`inner.verify`)가 권위 — 강등은 fast-path |
#   |                 |                |      | 승인을 *줄일* 뿐 절대 느슨해지지 않는다      |
#   | setex(성공 캐싱)| no-op 강등     | 안전 | 다음 요청이 DB를 다시 조회 — 느려질 뿐       |
#   | get(count)      | 미스로 강등    | 안전 | 동일 논리(DB 재조회)                        |
#   | **delete(무효화)**| **예외 전파** | 보안 | 무효화 실패를 삼키면 폐기된 디바이스의 서명이 |
#   |                 |                |      | TTL까지 캐시에 남아 계속 통과한다            |
#
# 이 캐시가 *positive cache*(성공만 캐싱)라는 점이 앞의 세 줄을 안전하게 만든다 — 캐시가
# 못 읽히면 그냥 DB로 간다. 반대로 무효화(DEL)는 캐시에 남은 *과거의 승인*을 지우는 유일한
# 즉시 수단이라 강등 대상이 아니다.
#
# **위험 구간의 정확한 모양**(과장·축소 금지): Redis가 *완전히* 죽으면 get도 실패해 stale
# 항목을 애초에 *읽을 수 없으므로* 오히려 안전하게 DB 검증으로 떨어진다. 진짜 위험한 조합은
# **일시적 DEL 실패 + Redis 회복**이다 — 그 사이 stale 키가 살아남아 회복 후 다시 읽힌다.
# 그래서 DEL은 (강등 대신) *유한 재시도*로 일시 장애를 흡수하고, 소진되면 예외를 전파해
# 호출자·운영자에게 "무효화가 끝나지 않았다"를 알린다. 재시도가 전부 실패해도 TTL 자연
# 만료가 stale 창을 TTL 이내로 묶는다(이중 안전망).
#
# **현재 폭발 반경 메모**(2026-07-26 실측): `DeviceCredentialStore.verify`의 유일한 소비처는
# `_rate_limit._client_device_id`이고, 거기서 verify 실패는 *device 차원 rate limit 비활성*
# (fail-safe)을 뜻한다 — 즉 오늘의 stale 승인은 "보호 엔드포인트 접근 허용"이 아니라 "폐기된
# 디바이스가 유효 디바이스로 계수됨"이다. 그럼에도 이 저장소는 *디바이스 인증 프리미티브*로
# 설계됐고 후속 소비처(디바이스 게이팅 등)가 그 계약을 믿게 되므로, 무효화 계약은 지금
# 고정한다. 문서에도 이 뉘앙스 그대로 남긴다(`docs/standards/incident_response_slo.md` 함정 ④).
# ──────────────────────────────────────────────────────────────────────────

# 강등 회계의 연산 어휘 — 로그·스냅샷·테스트가 공유하는 단일 상수.
CACHE_OP_GET = "get"
CACHE_OP_SETEX = "setex"
CACHE_OP_DELETE = "delete"

# 로그에 실리는 '강등의 효과' 문구 — 운영자가 로그 한 줄로 학생 영향까지 읽게 한다.
_EFFECT_GET = "DB 검증으로 폴백합니다(캐시 미스 등가 — 승인이 느슨해지지 않습니다)."
_EFFECT_SETEX = "캐시 적재를 건너뜁니다(다음 요청이 DB를 다시 조회합니다)."
_EFFECT_DELETE = (
    "무효화는 강등하지 않습니다 — 예외를 전파합니다"
    "(폐기된 디바이스가 stale 캐시로 계속 통과하는 것을 막기 위함)."
)

# 무효화(DEL) 재시도 파라미터 기본값 — 학생 요청 예산 안에 드는 *유한* 재시도.
# max_retries=2·timeout 2.0s·backoff 0.05s(full jitter) → 최악 약 4초 후 예외 전파.
# 무한 재시도는 금물이다(요청이 매달리면 캐시 장애가 서비스 마비로 번진다 — OPS-05 근거).
_INVALIDATE_MAX_RETRIES = 2
_INVALIDATE_TIMEOUT_SECONDS = 2.0
_INVALIDATE_BACKOFF_SECONDS = 0.05

# 프로세스 전역 회계 — CachedDeviceStore 인스턴스가 여럿이어도 "이 프로세스가 디바이스 캐시
# 없이 버틴 횟수"는 하나로 합산돼야 운영 판정이 된다(OPS-05 `_PROCESS_DEGRADATION` 선례).
_PROCESS_DEGRADATION = DegradationCounter("디바이스 캐시")


def device_cache_degradation_snapshot() -> DegradationSnapshot:
    """프로세스 전역 디바이스 캐시 강등 회계 스냅샷 — 운영 노출·진단의 읽기 표면.

    아직 `/health/ready` body에는 싣지 않는다(응답 스키마 변경은 이 태스크 범위 밖).
    지금은 관측 SaaS 없이도 읽을 수 있는 인프로세스 판정치가 *존재*함을 보장한다.
    """
    return _PROCESS_DEGRADATION.snapshot()


def reset_device_cache_degradation() -> None:
    """프로세스 전역 회계 초기화 — 테스트 격리용."""
    _PROCESS_DEGRADATION.reset()


def _decode_cached(value: Any) -> str | None:
    """캐시 GET 응답을 str | None으로 방어적 정규화(OPS-05 `_decode` 미러링).

    클라이언트가 `decode_responses=True`면 str, 아니면 bytes를 돌려준다. 미스는 None이다.
    예기치 못한 타입은 None(=미스)으로 본다 — 캐시에는 우리가 넣은 str만 있어야 하므로,
    비정상 값은 사용하지 않고 DB로 가는 편이 안전하다(`hmac.compare_digest`에 str이 아닌
    값을 넘겨 TypeError를 내는 경로도 함께 닫힌다).
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return None


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

    **장애 강등(OPS-06)**: Redis 장애가 학생 대면 5xx로 번지지 않도록 조회·적재는 흡수하고
    무효화는 전파한다 — 연산별 판정과 근거는 이 클래스 바로 위의 판정표 참조. 흡수하든
    전파하든 예외 *타입명*은 항상 로그·회계에 남는다(침묵 실패 금지).
    """

    def __init__(
        self,
        inner: DeviceCredentialStore,
        cache: _CacheClient,
        ttl_seconds: int = 60,
        count_ttl_seconds: int | None = None,
        count_all_ttl_seconds: int | None = None,
        *,
        degradation: DegradationCounter | None = None,
        invalidate_timeout_seconds: float = _INVALIDATE_TIMEOUT_SECONDS,
        invalidate_max_retries: int = _INVALIDATE_MAX_RETRIES,
        invalidate_backoff_seconds: float = _INVALIDATE_BACKOFF_SECONDS,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds
        # slice 48: count_ttl 분리 — None이면 verify ttl로 폴백(슬라이스 40 backward compat).
        self._count_ttl = count_ttl_seconds if count_ttl_seconds is not None else ttl_seconds
        # slice 49: include_revoked=True 전용 TTL — None이면 _count_ttl로 폴백(slice 48 그대로).
        self._count_all_ttl = (
            count_all_ttl_seconds if count_all_ttl_seconds is not None else self._count_ttl
        )
        # OPS-06: 기본은 프로세스 전역 회계(인스턴스가 여럿이어도 합산) — 테스트는 새 카운터 주입.
        self._degradation = degradation if degradation is not None else _PROCESS_DEGRADATION
        self._invalidate_timeout = invalidate_timeout_seconds
        self._invalidate_max_retries = invalidate_max_retries
        self._invalidate_backoff = invalidate_backoff_seconds

    # ── OPS-06 캐시 접근 가드 ────────────────────────────────────────────
    def degradation_snapshot(self) -> DegradationSnapshot:
        """이 store가 쓰는 회계의 불변 스냅샷 — 인프로세스 판정치."""
        return self._degradation.snapshot()

    async def _cache_get(self, key: str) -> str | None:
        """캐시 조회 — 실패는 **미스로 강등**(None). 예외를 호출자에게 전파하지 않는다.

        강등이 안전한 이유: 이 캐시는 *성공만* 담는 positive cache이고 권위는 DB다. 못 읽으면
        `inner.verify`/`inner.count_for_user`로 가므로 **승인이 느슨해지는 방향이 아니라
        엄격해지는 방향**으로만 움직인다(대가는 DB 라운드트립 1회).

        try 범위에 디코딩까지 넣는 이유: 손상된 값(UnicodeDecodeError)도 결국 "캐시를 못 쓰는
        상태"라 같은 강등으로 다뤄야 학생 경로가 안 깨진다(OPS-05 `RedisCache.get` 선례).
        """
        try:
            raw = await self._cache.get(key)
            decoded = _decode_cached(raw)
        except Exception as exc:  # noqa: BLE001 — 캐시 장애를 학생 대면 실패로 전파 금지
            self._degradation.record_failure(CACHE_OP_GET, exc, effect=_EFFECT_GET)
            return None
        self._degradation.record_success()
        return decoded

    async def _cache_get_int(self, key: str) -> int | None:
        """count 캐시 조회 — 비정수 값도 미스로 강등(예외 타입명은 회계에 남는다)."""
        cached = await self._cache_get(key)
        if cached is None:
            return None
        try:
            return int(cached)
        except ValueError as exc:
            # 캐시에 정수가 아닌 값이 들어있다 = 캐시를 신뢰할 수 없다 → DB 재조회.
            self._degradation.record_failure(CACHE_OP_GET, exc, effect=_EFFECT_GET)
            return None

    async def _cache_setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """캐시 적재 — 실패는 **no-op 강등**(best-effort). 예외를 전파하지 않는다.

        적재 실패의 유일한 대가는 다음 요청의 DB 재조회다. 그것 때문에 이미 검증에 성공한
        학생 요청을 5xx로 죽이는 것은 우선순위 위반이다(#1 학생 ≫ #6 비용).
        """
        try:
            await self._cache.setex(key, ttl_seconds, value)
        except Exception as exc:  # noqa: BLE001 — 캐시 장애를 학생 대면 실패로 전파 금지
            self._degradation.record_failure(CACHE_OP_SETEX, exc, effect=_EFFECT_SETEX)
            return
        self._degradation.record_success()

    async def _cache_invalidate(self, *keys: str) -> None:
        """캐시 무효화(DEL) — **강등 금지**. 유한 재시도 후 소진되면 예외를 전파한다.

        여기서만 규칙이 뒤집히는 이유는 클래스 위 판정표의 마지막 줄이다: 무효화를 조용히
        건너뛰면 *과거의 승인*이 TTL까지 캐시에 살아남는다. 조회 강등은 승인을 줄이지만
        무효화 강등은 승인을 **늘린다** — 방향이 반대라 같은 처방을 쓸 수 없다.

        재시도(slice 35 `_retry_with_timeout` 재사용)는 강등이 아니라 *복원력*이다:
        일시적 깜빡임은 흡수하되, 실패를 성공으로 위장하지 않는다. full jitter로 회복 직후
        thundering herd도 막는다.

        재시도 소진 시의 상태(정직하게): DB 변경은 이미 커밋됐고 캐시만 남아 있다. 호출자가
        같은 요청을 재시도하면 무효화도 다시 시도된다(`PgDeviceStore.revoke`는 이미 폐기된
        행에도 UPDATE가 1행 매치돼 True를 돌려주므로 DEL 경로가 재진입한다). 그동안의 stale
        창은 TTL 이내로 묶인다.
        """
        if not keys:
            return

        async def _delete() -> None:
            await self._cache.delete(*keys)

        try:
            await _retry_with_timeout(
                _delete,
                timeout_seconds=self._invalidate_timeout,
                max_retries=self._invalidate_max_retries,
                backoff_seconds=self._invalidate_backoff,
                jitter=True,
            )
        except Exception as exc:
            # 전파하기 *전에* 회계·로그에 남긴다 — 상위에서 500으로 뭉개져도 원인 타입이 남는다.
            self._degradation.record_failure(
                CACHE_OP_DELETE, exc, effect=_EFFECT_DELETE, level=logging.ERROR
            )
            raise
        self._degradation.record_success()

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        result = await self._inner.register(user_id)
        # slice 40: count 캐시 invalidate(active·all 두 키) — 새 device가 count에 반영.
        # OPS-06 메모: 이 DEL이 지우는 것은 *count 캐시뿐*이라 보안 계약이 아니라 신선도
        # 문제다(폐기 서명 잔존과 무관). 그럼에도 현행 fail-loud를 유지한다 — 무효화 경로의
        # 처리를 한 곳으로 통일해 "어떤 DEL은 삼켜도 된다"는 예외를 만들지 않기 위함이고,
        # 재시도가 붙은 만큼 종전보다 실패 확률은 낮아졌다(동작 변경 없음·복원력만 추가).
        await self._cache_invalidate(
            f"{_COUNT_CACHE_KEY_PREFIX}{user_id}:active",
            f"{_COUNT_CACHE_KEY_PREFIX}{user_id}:all",
        )
        return result

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        # 1) 캐시 GET — hit + 일치면 DB 라운드트립 0 (실패는 미스로 강등 → 2)로 진행)
        cache_key = _VERIFY_CACHE_KEY_PREFIX + device_id
        cached = await self._cache_get(cache_key)
        if cached is not None:
            # 상수시간 비교 — 캐시 hit 경로도 타이밍 공격 방어
            if hmac.compare_digest(cached, signature_hex.lower()):
                return True
        # 2) 캐시 미스/불일치 → inner(DB) 위임
        result = await self._inner.verify(device_id, signature_hex)
        # 3) 성공만 캐시 — 실패는 매번 DB(공격자의 poison 시도 차단)
        if result:
            await self._cache_setex(cache_key, self._ttl, signature_hex.lower())
        return result

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        # revoke 성공 시 즉시 캐시 invalidate — stale window 최소화
        result = await self._inner.revoke(device_id, owner_id)
        if result:
            # slice 26: verify 캐시 DEL + slice 40: count 캐시 두 키 모두 DEL(폐기로 active 감소).
            # OPS-06: 여기가 *보안 계약*이다 — 실패를 삼키면 폐기된 디바이스의 서명이 TTL까지
            # 캐시에 남아 계속 통과한다. 재시도 후에도 실패하면 예외가 전파된다(강등 금지).
            await self._cache_invalidate(
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
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
        order_by: OrderByField = "created_at",
        order_dir: OrderDir = "desc",
        nulls: NullsPosition = "last",
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeviceInfo]:
        # 목록 조회는 캐시 안 함 — 등록/폐기 직후 신선도 우선(빈도 낮은 관리 표면).
        # slice 37/38/41/43/44/46/47 인자 그대로 위임
        return await self._inner.list_for_user(
            owner_id,
            include_revoked=include_revoked,
            since=since,
            until=until,
            revoked_since=revoked_since,
            revoked_until=revoked_until,
            used_since=used_since,
            used_until=used_until,
            order_by=order_by,
            order_dir=order_dir,
            nulls=nulls,
            limit=limit,
            offset=offset,
        )

    async def count_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        used_since: datetime | None = None,
        used_until: datetime | None = None,
    ) -> int:
        # slice 40: count 결과 캐시 — register/revoke가 즉시 invalidate하므로 stale 위험 ≈ 0
        # slice 41/43/44: 시간 필터 6종 중 *하나라도* 있으면 *캐시 우회*(필터 조합 무한대·
        # 키 폭발 위험·시간 필터는 보통 보안 감사용 1회성 조회·캐시 효익 낮음).
        # slice 45: 6-OR 분기를 `_has_any_time_filter` helper로 추출 — 분기 비대화 회피.
        if _has_any_time_filter(since, until, revoked_since, revoked_until, used_since, used_until):
            return await self._inner.count_for_user(
                owner_id,
                include_revoked=include_revoked,
                since=since,
                until=until,
                revoked_since=revoked_since,
                revoked_until=revoked_until,
                used_since=used_since,
                used_until=used_until,
            )
        suffix = "all" if include_revoked else "active"
        cache_key = f"{_COUNT_CACHE_KEY_PREFIX}{owner_id}:{suffix}"
        # OPS-06: 조회 실패·비정수 값은 미스로 강등 → DB 재조회(정확한 값을 돌려준다).
        cached = await self._cache_get_int(cache_key)
        if cached is not None:
            return cached
        result = await self._inner.count_for_user(owner_id, include_revoked=include_revoked)
        # slice 48/49: 키별 TTL — `:all`(include_revoked)은 더 긴 TTL 옵션
        ttl = self._count_all_ttl if include_revoked else self._count_ttl
        await self._cache_setex(cache_key, ttl, str(result))
        return result

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        # slice 34: inner가 폐기 device_id 목록을 반환하므로 *정확히* 그 키들만 캐시 invalidate.
        # slice 33의 "TTL 자연 만료" 트레이드오프 해소 — stale 기간 즉시 0(DEL 성공 가정).
        # dry_run=True면 inner도 상태 변경 0·캐시도 건드리지 않음.
        # OPS-06: revoke와 *같은 보안 계약*이다(폐기된 디바이스의 verify 캐시 무효화) — 강등
        # 금지·재시도 후 예외 전파. 태스크 지시에는 revoke/register만 열거됐으나 이 경로도
        # 동일 부류라 함께 닫는다(빠뜨리면 배치 폐기만 stale 승인을 남긴다).
        affected = await self._inner.cleanup_stale(max_age_days, dry_run=dry_run)
        if not dry_run and affected:
            await self._cache_invalidate(*[_VERIFY_CACHE_KEY_PREFIX + d for d in affected])
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
    # slice 73: 봉투 암호화기 주입(키 미설정 시 None=평문 폴백). 잘못된 키 길이는 여기서
    # ValueError로 fail-fast(lifespan startup에서 표면화).
    # SEC-28: prod-like 환경에서 키 미설정 시 RuntimeError로 부팅 거부.
    cipher = require_device_secret_cipher(settings)
    # SEC-28: 키가 없고 prod-like가 아닐 때만 평문 폴백을 명시적으로 허용(개발/CI 편의).
    # 키가 설정되면 암호화를 사용하므로 평문 폴백이 필요 없고, prod-like에서는 키 없으면 부팅 실패.
    allow_plaintext_fallback = cipher is None and not bool(settings.production_like)
    pg_store: DeviceCredentialStore = PgDeviceStore(
        sm, cipher, allow_plaintext_fallback=allow_plaintext_fallback
    )

    if mode == "pg":
        return pg_store, _noop

    # mode == "pg_cached" — Redis 클라이언트 생성·CachedDeviceStore 래핑
    redis_client = _build_redis_for_cache(settings)
    cached = CachedDeviceStore(
        pg_store,
        redis_client,
        ttl_seconds=settings.device_verify_cache_ttl_seconds,
        count_ttl_seconds=settings.device_count_cache_ttl_seconds,
        count_all_ttl_seconds=settings.device_count_all_cache_ttl_seconds,
        # OPS-06: 무효화 재시도의 시도별 상한도 소켓 타임아웃과 같은 축으로 묶는다(새 설정 키를
        # 만들지 않고 OPS-05가 세운 `redis_socket_timeout_s`를 재사용 — 운영자가 조절할 손잡이는
        # 하나면 충분하고, 소켓이 2초에 끊기는데 바깥 상한만 10초인 조합은 의미가 없다).
        invalidate_timeout_seconds=settings.redis_socket_timeout_s,
    )

    async def _close_redis() -> None:
        # redis.asyncio.Redis.aclose() — 연결 풀 반납(라이브 통합 테스트가 검증)
        close = getattr(redis_client, "aclose", None)
        if close is not None:
            await close()

    return cached, _close_redis


def _build_redis_for_cache(settings: Any) -> _CacheClient:
    """기본 redis.asyncio 클라이언트 — 지연 import(라이브러리 없는 환경 보호).

    Redis 연결 자체는 라이브 통합 테스트(@integration·실 Redis 데몬)에서 검증한다 —
    hermetic 테스트는 모드를 `pg`/`none`으로 두거나 가짜 클라이언트를 주입한다. 다만
    **소켓 타임아웃 결선은 hermetic으로도 검증한다**(실물 `redis.asyncio.Redis` 객체의
    `connection_pool.connection_kwargs` 확인 — 네트워크는 타지 않는다). CLAUDE.md: 외부 SDK
    표면을 시임만으로 정합 선언 금지.

    **소켓 타임아웃을 명시한다** (OPS-06 — OPS-05가 L3 캐시에 건 것과 같은 축):
    무응답 Redis(패킷 블랙홀·방화벽 drop)는 연결 거부보다 나쁘다 — 매 요청의 디바이스 서명
    검증이 응답을 기다리며 매달리고, asyncio 워커가 고갈되면 캐시 한 컴포넌트의 장애가
    서비스 전체 마비로 번진다. 인자를 주지 않으면 값이 **라이브러리 버전 기본값에 종속**된다
    (설치본 redis-py 8.0.1 실측 5초·pin `redis>=5.1.0`은 상한이 없다). 응답 대기와 연결 수립
    둘 다 거는 이유: 하나만 걸면 나머지 축에서 무한 대기가 그대로 남는다(연결은 되는데 응답이
    없는 블랙홀 vs SYN이 drop되는 방화벽 — 서로 다른 인자에 걸리는 두 실패 양상).
    """
    try:
        from redis.asyncio import Redis
    except ImportError as exc:
        raise RuntimeError(
            "redis Python 클라이언트가 설치되지 않았습니다. "
            "`pip install redis[hiredis]` 후 다시 시도하세요."
        ) from exc
    timeout_s = settings.redis_socket_timeout_s
    return cast(
        _CacheClient,
        Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=timeout_s,
            socket_connect_timeout=timeout_s,
        ),
    )


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
