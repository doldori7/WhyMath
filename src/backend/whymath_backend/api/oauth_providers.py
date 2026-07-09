"""실 OAuth provider 구현(카카오·네이버 httpx) — code → 검증된 외부 신원. OAuth-a2.

`api/auth.py`의 `OAuthProvider` Protocol을 충족한다(seam에 주입). authorization code를 provider
토큰 엔드포인트로 교환하고 userinfo로 이메일·subject를 얻어 `OAuthIdentity`를 만든다. 키 설정 시
`build_oauth_providers`가 레지스트리를 구성해 콜백에 연결한다(미설정이면 빈 dict→404).

★검증 경계(정직): 카카오/네이버 외부 API 계약(URL·요청/응답 필드)은 *공개 문서 기반 인코딩*이라
mock httpx 단위테스트는 *이 모듈의 로직*(요청 구성·응답 파싱·에러 매핑)만 검증한다.
실 provider와의 통합(필드명·스코프·실제 응답 구조)은 **라이브 크레덴셜로만 확인 가능**(로컬 미검증)
— 배포 전 실 카카오/네이버 콘솔로 검증 필요. 클라이언트는 주입 가능(테스트 MockTransport)·미주입
시 호출당 생성·종료. 네트워크/타임아웃은 `httpx.HTTPError` → `OAuthProviderError`로 매핑(콜백 502).
"""

from __future__ import annotations

import httpx

from whymath_backend.api.auth import OAuthIdentity, OAuthProvider, OAuthProviderError
from whymath_backend.api.demo_auth import register_demo_provider
from whymath_backend.config import Settings

_TIMEOUT = httpx.Timeout(10.0)


class KakaoOAuthProvider:
    """카카오 OAuth — kauth.kakao.com 토큰 교환 + kapi.kakao.com userinfo."""

    _TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    _USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client

    async def fetch_identity(self, code: str, redirect_uri: str) -> OAuthIdentity:
        client = self._client or httpx.AsyncClient(timeout=_TIMEOUT)
        owns = self._client is None
        try:
            access = await self._exchange(client, code, redirect_uri)
            return await self._userinfo(client, access)
        except httpx.HTTPError as exc:  # 네트워크·타임아웃 → provider 오류(콜백 502)
            raise OAuthProviderError(f"카카오 통신 실패: {exc}") from exc
        finally:
            if owns:
                await client.aclose()

    async def _exchange(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> str:
        resp = await client.post(
            self._TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        if resp.status_code != 200:
            raise OAuthProviderError(f"카카오 토큰 교환 실패(status={resp.status_code}).")
        access = resp.json().get("access_token")
        if not access:
            raise OAuthProviderError("카카오 토큰 응답에 access_token이 없습니다.")
        return str(access)

    async def _userinfo(self, client: httpx.AsyncClient, access_token: str) -> OAuthIdentity:
        resp = await client.get(
            self._USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise OAuthProviderError(f"카카오 userinfo 실패(status={resp.status_code}).")
        data = resp.json()
        subject = str(data.get("id") or "")
        account = data.get("kakao_account") or {}
        email = account.get("email")
        if not subject or not email:
            raise OAuthProviderError("카카오 userinfo에 id·email이 없습니다(이메일 동의 필요).")
        return OAuthIdentity(provider="kakao", subject=subject, email=str(email))


class NaverOAuthProvider:
    """네이버 OAuth — nid.naver.com 토큰 교환 + openapi.naver.com userinfo."""

    _TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
    _USERINFO_URL = "https://openapi.naver.com/v1/nid/me"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client

    async def fetch_identity(self, code: str, redirect_uri: str) -> OAuthIdentity:
        client = self._client or httpx.AsyncClient(timeout=_TIMEOUT)
        owns = self._client is None
        try:
            access = await self._exchange(client, code, redirect_uri)
            return await self._userinfo(client, access)
        except httpx.HTTPError as exc:
            raise OAuthProviderError(f"네이버 통신 실패: {exc}") from exc
        finally:
            if owns:
                await client.aclose()

    async def _exchange(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> str:
        resp = await client.post(
            self._TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code != 200:
            raise OAuthProviderError(f"네이버 토큰 교환 실패(status={resp.status_code}).")
        access = resp.json().get("access_token")
        if not access:
            raise OAuthProviderError("네이버 토큰 응답에 access_token이 없습니다.")
        return str(access)

    async def _userinfo(self, client: httpx.AsyncClient, access_token: str) -> OAuthIdentity:
        resp = await client.get(
            self._USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise OAuthProviderError(f"네이버 userinfo 실패(status={resp.status_code}).")
        profile = (resp.json() or {}).get("response") or {}
        subject = str(profile.get("id") or "")
        email = profile.get("email")
        if not subject or not email:
            raise OAuthProviderError("네이버 userinfo에 id·email이 없습니다(이메일 동의 필요).")
        return OAuthIdentity(provider="naver", subject=subject, email=str(email))


def build_oauth_providers(settings: Settings) -> dict[str, OAuthProvider]:
    """구성된(키 존재) OAuth provider만 레지스트리로 — `create_app` 기본 주입.

    키 미설정(CI·미구성 배포)이면 빈 dict라 콜백이 404(현 동작 보존). 클라이언트는 지연이라
    구성만으로 네트워크를 타지 않는다.
    """
    providers: dict[str, OAuthProvider] = {}
    if settings.kakao_configured:
        providers["kakao"] = KakaoOAuthProvider(
            client_id=settings.kakao_client_id,
            client_secret=settings.kakao_client_secret.get_secret_value(),
        )
    if settings.naver_configured:
        providers["naver"] = NaverOAuthProvider(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret.get_secret_value(),
        )
    # 시연 전용 가짜 provider(S1 게이트 ①) — demo_auth_enabled일 때만·실 provider 미구성 시에만
    # 등록(이중 방어는 register_demo_provider가 담당). 실 provider 등록 뒤 호출한다.
    register_demo_provider(providers, settings)
    return providers
