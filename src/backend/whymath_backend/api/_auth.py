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

`get_consented_user`: 위에 더해 *알려진* 미성년자(`is_minor`)인데 `parent_consent_at`이
없으면 **403**(CLAUDE.md 학부모 동의·14세 미만 절차). 민감 데이터 엔드포인트는 `ConsentedUser`
를 쓴다.

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
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Role
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


async def get_consented_user(
    user: Annotated[UserProfile, Depends(get_current_user)],
) -> UserProfile:
    """알려진 미성년자인데 학부모 동의(parent_consent_at)가 없으면 403.

    `is_minor`가 None(미상)이면 차단하지 않는다 — *알려진* 미성년자만 게이트한다.
    """
    if user.is_minor and user.parent_consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="미성년자 학부모 동의가 필요합니다(parent_consent_at 미설정).",
        )
    return user


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
