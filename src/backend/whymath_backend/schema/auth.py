"""인증 스키마 — OAuth 콜백 요청·토큰 응답(L5 로그인 계약). OAuth-a.

OAuth(카카오·네이버) redirect가 전달한 authorization code 교환 요청과, 발급된 액세스 토큰 응답.
실제 provider HTTP 교환은 `api/auth.py`의 `OAuthProvider` 구현이 담당한다(이 모듈은 *계약*만).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OAuthCallbackRequest(BaseModel):
    """OAuth provider redirect가 전달한 authorization code 교환 요청."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(description="OAuth provider가 발급한 authorization code.")
    redirect_uri: str = Field(description="code 교환에 쓸 redirect_uri(인가 요청과 동일해야 함).")


class OAuthTokenResponse(BaseModel):
    """로그인 성공 — 발급된 액세스 토큰(Bearer)."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(description="서명된 JWT 액세스 토큰(Authorization: Bearer).")
    token_type: str = Field(default="bearer", description="토큰 타입(OAuth2 관용 'bearer').")
