"""인증·인가 FastAPI 의존성 — Bearer JWT → 현재 사용자, 미성년 동의 게이트.

`get_current_user`: `Authorization: Bearer <token>`을 디코드해 user_id를 얻고 UserProfile을
로드한다. 토큰이 없거나(미인증)·불량/만료이거나·user_id가 UUID가 아니거나·사용자가 없으면
**401**(`WWW-Authenticate: Bearer`). `get_consented_user`: 위에 더해 *알려진* 미성년자
(`is_minor`)인데 `parent_consent_at`이 없으면 **403**(CLAUDE.md 학부모 동의·14세 미만 절차).
민감 데이터 엔드포인트는 `ConsentedUser`를 쓴다.

시크릿 미설정(서버 구성 오류)은 `decode_access_token`이 RuntimeError를 던져 500이 된다(토큰
문제 401과 구분). 토큰 발급 seam은 `whymath_backend.security.create_access_token`(실 로그인은
후속 OAuth가 호출).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
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
    """Bearer JWT → UserProfile. 없음/불량/만료/UUID아님/사용자없음 → 401."""
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


CurrentUser = Annotated[UserProfile, Depends(get_current_user)]
ConsentedUser = Annotated[UserProfile, Depends(get_consented_user)]
