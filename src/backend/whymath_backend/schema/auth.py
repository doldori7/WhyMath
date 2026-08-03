"""인증 스키마 — OAuth 콜백·토큰 응답·리프레시 교환·세션 조회(L5 로그인 계약). OAuth-a·a3·SEC-10.

OAuth(카카오·네이버) redirect가 전달한 authorization code 교환 요청과, 발급된 토큰 응답(액세스+
리프레시), 그리고 리프레시 토큰으로 새 액세스 토큰을 받는 교환 계약. 실제 provider HTTP 교환은
`api/auth.py`의 `OAuthProvider` 구현이 담당한다(이 모듈은 *계약*만).

`SessionInfo`/`SessionListResponse`(SEC-10)는 `GET /v1/auth/sessions`의 응답 계약 — 본인의 활성
리프레시 세션을 "낯선 기기 인지" 용도로만 노출한다. **IP·User-Agent 원문 필드는 의도적으로 없다**
(최소 수집 — `docs/architecture/account_security_gap_review.md` D4). `extra="forbid"`가 향후
누군가 원문 필드를 실수로 추가하는 것을 스키마 레벨에서 막는다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OAuthCallbackRequest(BaseModel):
    """OAuth provider redirect가 전달한 authorization code 교환 요청."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(description="OAuth provider가 발급한 authorization code.")
    redirect_uri: str = Field(description="code 교환에 쓸 redirect_uri(인가 요청과 동일해야 함).")
    state: str = Field(
        description=(
            "GET /v1/auth/{provider}/state로 발급받은 CSRF state 토큰(그대로 동봉). SEC-08 —"
            " 미동봉·불일치·만료 시 400(다시 로그인 요구)."
        )
    )


class OAuthTokenResponse(BaseModel):
    """로그인 성공 — 발급된 액세스 토큰(Bearer)·리프레시 토큰."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(description="서명된 JWT 액세스 토큰(Authorization: Bearer).")
    refresh_token: str = Field(
        description="서명된 JWT 리프레시 토큰(액세스 만료 시 /v1/auth/refresh로 교환)."
    )
    token_type: str = Field(default="bearer", description="토큰 타입(OAuth2 관용 'bearer').")


class RefreshRequest(BaseModel):
    """리프레시 교환 요청 — 발급받은 리프레시 토큰으로 새 액세스 토큰을 받는다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    refresh_token: str = Field(description="로그인 시 발급받은 JWT 리프레시 토큰.")


class SessionInfo(BaseModel):
    """`GET /v1/auth/sessions` 목록 원소 — 본인의 활성 리프레시 세션 1건(SEC-10).

    IP·User-Agent 원문은 없다(최소 수집) — `platform`은 좁은 요약뿐이다.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID = Field(description="세션 식별자(리프레시 토큰의 jti). 단건 삭제 시 사용.")
    platform: str | None = Field(
        default=None,
        description=(
            '로그인·리프레시 시점 User-Agent에서 도출한 좁은 요약("iOS"/"Android"/"Web"). '
            "판별 불가·이 컬럼 도입 이전 발급 세션은 null."
        ),
    )
    issued_at: datetime = Field(description="세션(리프레시 토큰) 발급 시각.")
    expires_at: datetime = Field(description="리프레시 토큰 만료 시각(실제 거부는 JWT exp가 강제).")


class SessionListResponse(BaseModel):
    """`GET /v1/auth/sessions` 응답 — 본인의 활성 세션 목록(issued_at 내림차순)."""

    model_config = ConfigDict(extra="forbid")

    sessions: list[SessionInfo] = Field(description="활성(미취소) 세션 목록.")
