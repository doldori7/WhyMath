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
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
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
