"""디바이스 등록·폐기 HTTP 표면 — 슬라이스 22 OAuth-style 인증.

`POST /v1/devices/register` — `ConsentedUser`가 새 device_id + secret_plain 발급(서버 생성·
저장소에 영구 보관·secret_plain은 *1회만* 응답으로 노출). 클라이언트는 KeyChain/Keystore에
secret 저장 후 매 요청 `X-Device-Sig: HMAC-SHA256(secret, device_id)` 동봉(slice 21·22 검증
경로 진입).

`POST /v1/devices/{device_id}/revoke` — 등록 폐기(분실·도난·교체). 폐기 후 verify는 False.

**경계**:
- store 미설정(`set_device_store(None)`) 시 모든 엔드포인트가 **503 Service Unavailable**
  (slice 21 폴백 모드는 등록 불필요·동작 대상 아님). 운영은 lifespan에서 `set_device_store`로
  활성화 필수.
- 등록은 *인증된 사용자만*(`ConsentedUser` 게이트) — 익명 등록 금지(미성년 등록 게이팅·CLAUDE.md).
- secret_plain은 응답 body에만 노출·서버 로그/추적·DB 쿼리 응답에 *절대 미포함*(SecretStr 사용
  안 함은 1회 응답이라 필요 없으나 운영 시 로그 마스킹 미들웨어 권장).
- 슬라이스 25: `/register`에 `RateLimitedDeviceRegister`(user 5/min·IP 10/min, 별 키 공간)
  부착 — 등록 폭주 방어(sock-puppet·DB 자격증명 폭증). `/revoke`는 *드물게* 호출되고 본인
  소유 검증(slice 24)이 이미 1차 게이트라 일단 미적용(필요 시 후속).
- 슬라이스 29: `GET /v1/devices` — 본인 *활성* 디바이스 목록(폐기는 미포함, created_at DESC).
  Flutter "디바이스 관리" UI의 1차 결선. user.user_id로 *스코프*해 타인 device 노출 0.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._device_store import DeviceCredentialStore, get_device_store
from whymath_backend.api._rate_limit import RateLimitedDeviceRegister

router = APIRouter(prefix="/v1/devices", tags=["devices"])


class DeviceRegisterResponse(BaseModel):
    """등록 응답 — `device_id` + `secret_plain`(*1회만* 노출)."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(description="발급된 디바이스 ID(UUID4 문자열).")
    secret_plain: str = Field(
        description=(
            "디바이스 HMAC 서명 시크릿(URL-safe 32B 토큰). *이 응답에서만* 노출되며 이후 "
            "조회 불가. 클라이언트는 KeyChain/Keystore에 *안전 저장*하고, 매 요청 "
            "`X-Device-Sig: HMAC-SHA256(secret, device_id)` hex로 서명한다."
        ),
    )


class DeviceRevokeResponse(BaseModel):
    """폐기 응답 — 폐기 여부."""

    model_config = ConfigDict(extra="forbid")

    revoked: bool = Field(description="실제로 폐기됐는지(미존재 ID면 False).")


class DeviceInfoSchema(BaseModel):
    """본인 디바이스 정보 — 목록 응답 원소(slice 29). secret_plain·user_id PII 비노출.

    slice 32: `last_used_at` 추가 — 마지막 verify 성공 시각(`null`=한 번도 미사용). 정밀도는
    `CachedDeviceStore` 사용 시 cache TTL(기본 60s) — UI "방금 사용/X분 전" 표시에 충분.
    slice 37: `revoked` + `revoked_at` 추가 — `?include_revoked=true` 시 폐기 이력 식별·시각
    표시(UI "3일 전 폐기" 등). 본인 데이터라 PII 우려 없음.
    """

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(description="등록된 디바이스 ID(UUID4 문자열).")
    created_at: datetime = Field(description="등록 시각(UTC ISO8601).")
    last_used_at: datetime | None = Field(
        default=None,
        description=(
            "마지막 verify 성공 시각(UTC ISO8601). `null`이면 등록 후 한 번도 verify 안 됨. "
            "CachedDeviceStore 사용 시 cache miss 경로에서만 갱신(정밀도 ≈ cache TTL)."
        ),
    )
    revoked: bool = Field(
        default=False,
        description=(
            "폐기 여부 — `?include_revoked=true` 모드에서만 의미 있음(기본 false). "
            "기본 응답은 활성 device만이라 항상 false."
        ),
    )
    revoked_at: datetime | None = Field(
        default=None,
        description="폐기 시각(UTC ISO8601). `null`이면 미폐기. revoked=true일 때만 값.",
    )


class DeviceListResponse(BaseModel):
    """본인 활성 디바이스 목록 응답(slice 29) — created_at DESC. slice 39: total 옵션."""

    model_config = ConfigDict(extra="forbid")

    devices: list[DeviceInfoSchema] = Field(
        description="본인 소유 *활성*(미폐기) 디바이스 목록. 폐기된 device는 미포함."
    )
    total: int | None = Field(
        default=None,
        description=(
            "필터 조건(`include_revoked`)을 적용한 *총 device 수*. `?include_total=true`일 "
            '때만 채움(추가 COUNT 쿼리 비용 회피·기본 호출은 null). UI "Page X of Y" 또는 '
            '"총 N개" 표시용. 페이지 자체 크기는 `len(devices)`로 확인.'
        ),
    )


def _require_store() -> DeviceCredentialStore:
    store = get_device_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "디바이스 자격증명 저장소가 활성화되지 않았습니다. "
                "운영자가 `set_device_store`로 활성화해야 합니다."
            ),
        )
    return store


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="디바이스 등록 — device_id + secret_plain 1회 발급",
    dependencies=[RateLimitedDeviceRegister],
)
async def register_device(user: ConsentedUser) -> DeviceRegisterResponse:
    """새 디바이스 자격증명 발급 — 인증된 사용자만 가능. secret_plain은 응답에서만 노출."""
    store = _require_store()
    device_id, secret_plain = await store.register(user.user_id)
    return DeviceRegisterResponse(device_id=device_id, secret_plain=secret_plain)


@router.post(
    "/{device_id}/revoke",
    response_model=DeviceRevokeResponse,
    summary="디바이스 폐기 — 향후 서명 거부",
)
async def revoke_device(
    device_id: str,
    user: ConsentedUser,
) -> DeviceRevokeResponse:
    """등록된 디바이스 폐기 — *본인 소유만*. 미존재·타인 소유면 `revoked=false`(404 등가).

    slice 24: store에 `user.user_id`를 owner_id로 전달해 본인 소유 검증. 타인 device 폐기
    시도 시 404가 아닌 `{revoked: false}` 반환 — 존재 여부 노출 차단(device_id 열거 공격
    방어). idempotent 의미는 그대로(미존재·타인 소유·이미 폐기 모두 같은 응답 모양).
    """
    store = _require_store()
    revoked = await store.revoke(device_id, user.user_id)
    return DeviceRevokeResponse(revoked=revoked)


@router.get(
    "",
    response_model=DeviceListResponse,
    summary="내 디바이스 목록 — 기본 활성만·페이지네이션·옵션 total count",
)
async def list_my_devices(
    user: ConsentedUser,
    include_revoked: bool = False,
    since: Annotated[
        datetime | None,
        Query(
            description=(
                "slice 41: created_at *이후* 등록된 device만(inclusive·ISO8601). UI '지난 30일 "
                "활동'·보안 감사 화면 결선. None이면 무필터."
            ),
        ),
    ] = None,
    until: Annotated[
        datetime | None,
        Query(
            description=(
                "slice 41: created_at *이전* 등록된 device만(inclusive·ISO8601). since와 함께 "
                "시간창 지정 가능."
            ),
        ),
    ] = None,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description=(
            "페이지 크기(slice 38). 1~200·기본 50. include_revoked=true 시 폐기 이력이 "
            "폭증할 수 있어 페이지 단위 권장."
        ),
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description=(
            "건너뛸 행 수(slice 38). 다음 페이지는 `offset += len(이전 응답.devices)`. "
            "응답 길이가 limit 미만이면 더 이상 결과 없음(`has_more=false` 명시 헤더 미제공)."
        ),
    ),
    include_total: bool = Query(
        default=False,
        description=(
            "slice 39: true면 `total` 필드에 *필터 조건* 적용 후 총 device 수 채움. "
            "추가 COUNT 쿼리 비용 발생(opt-in)·UI 'Page X of Y' 표시용."
        ),
    ),
) -> DeviceListResponse:
    """본인 디바이스 목록 — `user.user_id`로 스코프(타인 device 노출 0).

    slice 29: 기본 활성만 — Flutter "디바이스 관리" UI의 1차 결선. slice 37:
    `?include_revoked=true` → 폐기 이력 포함. slice 38: `?limit&offset` 페이지네이션. slice 39:
    `?include_total=true` → 응답에 `total` 채움(opt-in·COUNT 쿼리).

    응답에 *secret_plain·user_id PII 미포함* — 표면 최소화. revoked/revoked_at은 본인 데이터.
    """
    store = _require_store()
    infos = await store.list_for_user(
        user.user_id,
        include_revoked=include_revoked,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    total: int | None = None
    if include_total:
        total = await store.count_for_user(
            user.user_id,
            include_revoked=include_revoked,
            since=since,
            until=until,
        )
    return DeviceListResponse(
        devices=[
            DeviceInfoSchema(
                device_id=i.device_id,
                created_at=i.created_at,
                last_used_at=i.last_used_at,
                revoked=i.revoked,
                revoked_at=i.revoked_at,
            )
            for i in infos
        ],
        total=total,
    )
