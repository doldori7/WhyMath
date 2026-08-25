"""인증·인가 FastAPI 의존성 — Bearer JWT → 현재 사용자, 미성년 동의 게이트, 역할 게이트.

`get_current_user`: `Authorization: Bearer <token>`을 디코드해 user_id를 얻고 UserProfile을
로드한다. 토큰이 없거나(미인증)·불량/만료이거나·user_id가 UUID가 아니거나·사용자가 없거나·
**비활성(`is_active=False`)·삭제됨(`is_deleted=True`)이면 401**(`WWW-Authenticate: Bearer`) —
비활성·삭제 검사는 SEC-07 D1(`docs/architecture/account_security_gap_review.md`)에서 추가:
`UserProfile.is_active`/`is_deleted`(`db/models/user.py`)는 기존 컬럼이었으나 이 함수가 그
**첫 reader**였다(탈퇴·비활성 계정의 미만료 토큰이 그전까지 통과했다). `is_active is False`·
`is_deleted is True`로 *명시적* 값만 차단한다(직접 생성한 미영속 UserProfile처럼 컬럼이
`None`인 경우는 "미상"이라 차단하지 않는다 — `get_consented_user`의 `is_minor` None-미상
불차단 방침과 동형이며, DB에서 읽은 행은 두 컬럼 다 NOT NULL이라 실제로는 항상 True/False다).

`get_consented_user`: 위에 더해 *알려진* 미성년자(`is_minor`)인데 동의가 **없거나·철회됐거나·
만료됐으면 403**(CLAUDE.md 학부모 동의·14세 미만 절차). 민감 데이터 엔드포인트는 `ConsentedUser`
를 쓴다. 철회·만료 판정은 SEC-20(`account_security_gap_review_r2.md` D9)에서 추가됐다 —
그전까지 이 게이트는 `parent_consent_at`(설정됐는가) 하나만 읽어서 **한 번 받은 동의가 영구히
유효**했고, `ParentalConsent.revoked_at`·`expires_at`은 writer가 상수 `None` 1곳뿐이고
**reader가 0**이었다(만료 재확인용 인덱스 `idx_parental_consent_user`까지 있는데 읽는 사람이
없었다). 이 함수가 그 두 컬럼의 **첫 reader**다.

`require_role(*roles)`: `get_current_user` 위에 얹는 역할 게이트(SEC-07 D1) — 토큰이 아예
없으면 `get_current_user`가 먼저 401을 던지고, 유효한 토큰이지만 역할이 불일치하면 **403**
(인증됐으나 그 작업엔 권한이 없다는 표준 의미 — `get_consented_user`의 인증-후-403 패턴과
동형). `Role`(`schema/enums.py`)은 v0 2값(STUDENT/CONTENT_ADMIN)뿐이라 `require_content_admin`
= `require_role(Role.CONTENT_ADMIN)`을 미리 만들어 콘텐츠 CUD 라우터가 재사용한다(모듈
로드 시 1회 생성 — 테스트가 `dependency_overrides`로 오버라이드할 안정적 단일 대상이 된다).

시크릿 미설정(서버 구성 오류)은 `decode_access_token`이 RuntimeError를 던져 500이 된다(토큰
문제 401과 구분). 토큰 발급 seam은 `whymath_backend.security.create_access_token`(실 로그인은
후속 OAuth가 호출).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import ConsentScope, Role
from whymath_backend.security import decode_access_token

# auto_error=False — 헤더 없을 때 FastAPI 기본 403 대신 우리가 401(WWW-Authenticate)로 처리.
_bearer = HTTPBearer(auto_error=False, description="JWT 액세스 토큰(Bearer)")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다(유효한 Bearer 토큰).",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserProfile:
    """Bearer JWT → UserProfile. 없음/불량/만료/UUID아님/사용자없음/비활성/삭제됨 → 401."""
    if credentials is None:
        raise _unauthorized()
    try:
        subject = decode_access_token(credentials.credentials, settings=settings)
        pk = uuid.UUID(subject)
    except (JWTError, ValueError) as exc:
        raise _unauthorized() from exc
    user = await session.get(UserProfile, pk)
    if user is None:
        raise _unauthorized()
    # SEC-07 D1: 비활성·삭제 계정의 미만료 토큰 차단(is_active/is_deleted의 첫 reader).
    # 명시적 False/True만 차단 — None(미영속 직접생성 객체의 "미상")은 통과시킨다.
    if user.is_active is False or user.is_deleted is True:
        raise _unauthorized()
    return user


def _consent_required(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _effective_scope(scope: ConsentScope) -> ConsentScope:
    """동의 검사 시 `service_core`와 동일 취급할 scope를 정규화.

    AI Tutor 응답 생성(`ai_inference`)은 서비스 본 기능에 속하므로 `service_core` 동의로
    충족한다. 별도 `ai_inference` 동의 레코드는 감사/고지 목적으로 남을 수 있으나, 게이트
    판정에서는 `service_core`와 동일하게 본다(EOS §45·§48).
    """
    if scope is ConsentScope.ai_inference:
        return ConsentScope.service_core
    return scope


async def _latest_consent_for_scope(
    user_id: uuid.UUID,
    session: AsyncSession,
    scope: ConsentScope,
) -> ParentalConsent | None:
    """특정 scope의 최신 `parental_consent` 행 1건을 반환(없으면 None)."""
    effective = _effective_scope(scope)
    latest: ParentalConsent | None = await session.scalar(
        select(ParentalConsent)
        .where(
            ParentalConsent.user_id == user_id,
            ParentalConsent.consent_scope == effective.value,
        )
        .order_by(ParentalConsent.consent_signed_at.desc().nullslast())
        .limit(1)
    )
    return latest


def _is_consent_active(consent: ParentalConsent | None) -> bool:
    """동의 행이 존재하고 철회·만료되지 않았으면 True."""
    if consent is None:
        return False
    if consent.revoked_at is not None:
        return False
    if consent.expires_at is not None and consent.expires_at <= datetime.now(tz=timezone.utc):
        return False
    return True


async def has_scope_consent(
    user: UserProfile,
    session: AsyncSession,
    scope: ConsentScope,
) -> bool:
    """사용자가 `scope`에 대해 유효한 동의를 가지고 있으면 True.

    - 성인(`is_minor=False`)은 `service_core`·`ai_inference`에 대해 True(서비스 이용 자체가
      동의 의사로 본다). 그 외 scope(ai_training·research·marketing)에 대해서는 현재
      별도 성인 동의 저장소가 없으므로 **False**(privacy-by-default, 후속 성인 동의 UI에서
      확장).
    - 미성년자(`is_minor=True`)는 `parental_consent` 테이블에서 해당 scope 최신 행의
      철회·만료 여부를 확인한다.
    - `is_minor`가 None(미상)이면 추가 쿼리 없이 True(기존 방침 유지).
    """
    # service_core는 ai_inference와 동일 취급.
    effective = _effective_scope(scope)

    # 성인 또는 연령 미상: service_core/ai_inference만 허용, 나머지는 기본 거부.
    if not user.is_minor:
        return effective is ConsentScope.service_core

    # 미성년자: service_core는 기존 parent_consent_at gate와 함께 체크.
    if effective is ConsentScope.service_core:
        if user.parent_consent_at is None:
            return False
        # 동의 원장이 없으면(legacy) parent_consent_at만으로 판정(기존 방침).
        latest = await _latest_consent_for_scope(user.user_id, session, effective)
        if latest is None:
            return True
        return _is_consent_active(latest)

    # 미성년자: service_core 외 scope은 해당 scope의 동의 행을 직접 본다.
    latest = await _latest_consent_for_scope(user.user_id, session, effective)
    return _is_consent_active(latest)


async def _check_scope_consent(
    user: UserProfile,
    session: AsyncSession,
    scope: ConsentScope,
) -> UserProfile:
    """`has_scope_consent`가 False이면 403, 아니면 user를 그대로 반환."""
    if not await has_scope_consent(user, session, scope):
        scope_label = scope.value
        if _effective_scope(scope) is ConsentScope.service_core:
            detail = f"미성년자 학부모 동의가 필요합니다(scope={scope_label})."
        else:
            detail = f"해당 개인정보 처리에 대한 동의가 필요합니다(scope={scope_label})."
        raise _consent_required(detail)
    return user


async def get_consented_user(
    user: Annotated[UserProfile, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """알려진 미성년자인데 학부모 동의가 없거나·철회됐거나·만료됐으면 403(SEC-20 D9).

    `service_core`(서비스 본 기능) scope에 대한 동의를 검사한다. 다른 scope별 판정은
    `has_scope_consent` 또는 `require_consent`를 사용.
    """
    return await _check_scope_consent(user, session, ConsentScope.service_core)


def require_consent(scope: ConsentScope) -> Callable[..., Awaitable[UserProfile]]:
    """특정 `ConsentScope` 동의를 요구하는 FastAPI 의존성 팩토리.

    사용 예:
        RequireAiTrainingConsent = Annotated[
            UserProfile, Depends(require_consent(ConsentScope.ai_training))
        ]
    """

    async def _dependency(
        user: Annotated[UserProfile, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> UserProfile:
        return await _check_scope_consent(user, session, scope)

    return _dependency


def require_role(*roles: Role) -> Callable[..., Awaitable[UserProfile]]:
    """`get_current_user` 위에 얹는 역할 게이트 팩토리 — 지정 역할이 아니면 403(SEC-07 D1).

    `get_consented_user`와 같은 패턴(기존 의존성에 `Depends`로 얹기·재계산 0). 무인증 요청은
    이 함수가 아니라 `get_current_user`가 먼저 401을 던진다(체인 순서상 도달 못 함) — 인증됐지만
    역할이 안 맞는 경우만 이 함수의 403이 발화한다.
    """

    async def _dependency(
        user: Annotated[UserProfile, Depends(get_current_user)],
    ) -> UserProfile:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="권한이 없습니다(관리자 전용 작업).",
            )
        return user

    return _dependency


CurrentUser = Annotated[UserProfile, Depends(get_current_user)]
ConsentedUser = Annotated[UserProfile, Depends(get_consented_user)]

# 콘텐츠 CUD(개념·문제 생성/수정/삭제) 게이트 — 모듈 로드 시 1회 생성해 concepts.py·problems.py가
# 동일 객체를 공유한다(테스트가 `dependency_overrides[require_content_admin] = ...`로 오버라이드할
# 안정적 단일 대상이 되려면 매 라우터 호출마다 새 클로저를 만들면 안 된다).
require_content_admin = require_role(Role.CONTENT_ADMIN)
RequireContentAdmin = Annotated[UserProfile, Depends(require_content_admin)]
