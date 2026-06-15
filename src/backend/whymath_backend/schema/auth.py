"""인증 스키마 — OAuth 콜백 요청·토큰 응답·리프레시 교환(L5 로그인 계약). OAuth-a·a3.

OAuth(카카오·네이버) redirect가 전달한 authorization code 교환 요청과, 발급된 토큰 응답(액세스+
리프레시), 그리고 리프레시 토큰으로 새 액세스 토큰을 받는 교환 계약. 실제 provider HTTP 교환은
`api/auth.py`의 `OAuthProvider` 구현이 담당한다(이 모듈은 *계약*만).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OAuthCallbackRequest(BaseModel):
    """OAuth provider redirect가 전달한 authorization code 교환 요청."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(description="OAuth provider가 발급한 authorization code.")
    redirect_uri: str = Field(description="code 교환에 쓸 redirect_uri(인가 요청과 동일해야 함).")


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
