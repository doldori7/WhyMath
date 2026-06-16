"""user 도메인 HTTP API — 인증된 본인 프로필 조회/수정(`/v1/users/me`).

`ConsentedUser`(인증 + 미성년 동의 게이트) 뒤에 노출한다. **PII**(email_hash·parent_email_hash)는
응답에서 제외(`response_model_exclude`). **PATCH는 자기 편집 가능 필드 화이트리스트만 허용** —
동의·신원·결제·시스템·감사 필드(parent_consent_at·is_minor·email_hash·persona_*·subscription_*·
created_at 등)는 사용자가 바꿀 수 없다(미성년 *동의 게이트 우회 방지*가 핵심 보안 요구).

다른 사용자 프로필 조회/관리(관리자)는 범위 밖 — 본인(`me`)만 노출(CLAUDE.md 미성년 PII 보호).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._concurrency import ensure_if_match, etag_for
from whymath_backend.config import Settings, get_settings
from whymath_backend.consent import current_year_kst, derive_is_minor
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.user import UserProfile as UserProfileSchema

router = APIRouter(prefix="/v1/users", tags=["user"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

# 응답에서 항상 제외하는 PII(해시 식별자 — 클라이언트에 불필요).
_PII_EXCLUDE = {"email_hash", "parent_email_hash"}

# 사용자가 자기 PATCH로 바꿀 수 있는 필드(화이트리스트). 여기 없는 키는 422로 거부 —
# 특히 parent_consent_at·is_minor(동의 게이트)·email_hash(신원)·subscription_*(결제)·
# persona_*·diagnostic_*(시스템 판정)·created_at 등 감사/신원/결제 필드는 자가수정 불가.
#
# `birth_year`는 *수정 가능*하다(온보딩에서 사용자가 입력) — 단 그 결과로 정해지는
# `is_minor`(미성년 동의 게이트의 입력)는 클라가 *직접 못 정한다*: is_minor는 화이트리스트에
# 없어 직접 PATCH가 422고, patch_me가 매 쓰기마다 birth_year에서 *서버 파생*해 덮어쓴다
# (consent.derive_is_minor — 단일 진실). 즉 미성년이 is_minor=false를 보내 게이트를 우회할
# 수 없다(클라 입력 미신뢰). birth_year를 거짓 신고하는 것은 자가신고 연령의 본질적 한계로
# 정확한 만나이 검증(생일 수집)·신원 확인은 변호사 자문 후속(pipa_data_matrix.md §3).
_SELF_EDITABLE = frozenset(
    {
        "nickname",
        "birth_year",
        "primary_device",
        "has_apple_pencil",
        "note_app",
        "accessibility_needs",
        "target_universities",
        "target_major_category",
        "target_grade",
        "target_score",
        "target_exam_date",
        "uses_inkang",
        "inkang_provider",
        "uses_offline_academy",
        "monthly_education_spend",
    }
)


@router.get(
    "/me",
    response_model=UserProfileSchema,
    response_model_exclude=_PII_EXCLUDE,
    summary="내 프로필 조회",
)
async def read_me(user: ConsentedUser, response: Response) -> UserProfileSchema:
    """인증된 본인 프로필 — PII(해시) 제외, ETag 동봉(이후 조건부 PATCH용)."""
    result = user.to_schema()
    response.headers["ETag"] = etag_for(result)
    return result


@router.patch(
    "/me",
    response_model=UserProfileSchema,
    response_model_exclude=_PII_EXCLUDE,
    summary="내 프로필 부분 수정",
)
async def patch_me(
    body: dict[str, Any],
    user: ConsentedUser,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> UserProfileSchema:
    """본인 프로필 부분 수정 — 화이트리스트 필드만(동의·신원·결제 필드는 422로 거부).

    `If-Match`(GET ETag)로 낙관적 동시성(412). 병합 결과를 schema로 재검증(불변식 유지) 후
    `session.merge`로 PK 기준 갱신. 응답에 새 ETag.

    **미성년 게이트(서버측 is_minor 파생)**: `is_minor`는 화이트리스트에 없어 클라가 직접 못
    바꾸고(여기까지 오면 위 disallowed 422), 병합 후 *항상* 현재 birth_year에서 서버 파생해
    덮어쓴다(`consent.derive_is_minor` — 클라 입력 미신뢰의 단일 진실). 매 쓰기마다 재파생하는
    이유: birth_year를 바꾼 경우 새 값으로 갱신되고, 안 바꾼 경우라도 stale/잘못된 is_minor를
    *자가 치유*하기 때문(is_minor는 birth_year의 순수 서버 투영). 따라서 미성년이 is_minor=
    false로 게이트를 우회할 수 없다(우회 차단의 핵심).
    """
    disallowed = set(body) - _SELF_EDITABLE
    if disallowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"수정할 수 없는 필드입니다(자가수정 불가): {sorted(disallowed)}",
        )
    ensure_if_match(if_match, etag_for(user.to_schema()))
    merged = user.to_schema().model_dump()
    merged.update(body)
    merged["user_id"] = user.user_id  # PK 고정(본인)
    # is_minor를 *서버 파생*으로 덮어쓴다(클라 입력·stale 값 무시) — 병합된 birth_year 기준.
    # 미성년 동의 게이트 우회 방지의 핵심: is_minor는 birth_year의 순수 서버 투영이다.
    merged["is_minor"] = derive_is_minor(
        merged.get("birth_year"),
        current_year=current_year_kst(),
        threshold=settings.minor_consent_age,
    )
    try:
        validated = UserProfileSchema.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "수정 본문 병합 결과가 스키마를 위반합니다.",
                "errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()],
            },
        ) from exc
    updated = await session.merge(UserProfile.from_schema(validated))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="고유 제약 위반으로 수정할 수 없습니다.",
        ) from exc
    result = updated.to_schema()
    response.headers["ETag"] = etag_for(result)
    return result
