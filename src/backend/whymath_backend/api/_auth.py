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


def _consent_required(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def get_consented_user(
    user: Annotated[UserProfile, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """알려진 미성년자인데 학부모 동의가 없거나·철회됐거나·만료됐으면 403(SEC-20 D9).

    판정 순서(비용 순):
      1. `is_minor`가 참이 아니면 즉시 통과 — **성인·미상 사용자는 추가 쿼리 0**이다
         (`is_minor` None은 "미상"이라 차단하지 않는다: 추정으로 학습을 막지 않는 기존 방침).
      2. `parent_consent_at`이 없으면 403(동의 미설정 — 종전과 동일).
      3. 미성년이고 동의가 있으면 **최신 `parental_consent` 행 1건**을 읽어 `revoked_at`(철회)·
         `expires_at`(만료)을 확인한다. 인덱스 `idx_parental_consent_user(user_id,
         consent_signed_at DESC)`가 이미 이 접근 경로용으로 존재한다(신규 인덱스 0).

    **동의 행이 없으면 차단하지 않는다**: `parent_consent_at`은 설정됐는데 원장 행을 못 찾는
    경우는 "철회/만료를 판정할 근거가 없음"이지 "철회됨"이 아니다. `is_minor` None을 미상으로
    보고 통과시키는 방침과 동형이며, 원장 도입 이전 데이터가 조용히 잠기는 것을 막는다.

    **`expires_at`은 아직 writer가 없다**(SEC-20 범위: reader만 세운다). 재확인 *주기 숫자*는
    법령 유래 판단이라 `MGMT-02`(변호사 회신) 선행이며, 주기가 확정되면 GRANT 경로에서
    `expires_at`을 채우는 1줄로 발화한다 — **읽는 쪽을 먼저 세우는 것이 dead 컬럼을 만들지 않는
    순서**다. 그때까지 만료 분기는 "값이 있으면 존중한다"는 계약으로만 존재한다.
    """
    if not user.is_minor:
        return user
    if user.parent_consent_at is None:
        raise _consent_required("미성년자 학부모 동의가 필요합니다(parent_consent_at 미설정).")

    latest = await session.scalar(
        select(ParentalConsent)
        .where(ParentalConsent.user_id == user.user_id)
        .order_by(ParentalConsent.consent_signed_at.desc().nullslast())
        .limit(1)
    )
    if latest is None:
        # 판정 근거 부재 = 미상 → 통과(위 docstring 참조).
        return user
    if latest.revoked_at is not None:
        raise _consent_required("미성년자 학부모 동의가 철회되었습니다(재동의가 필요합니다).")
    if latest.expires_at is not None and latest.expires_at <= datetime.now(tz=timezone.utc):
        raise _consent_required("미성년자 학부모 동의가 만료되었습니다(재확인이 필요합니다).")
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
