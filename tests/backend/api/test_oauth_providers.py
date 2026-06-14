"""실 OAuth provider(카카오·네이버) 단위테스트 — httpx MockTransport로 라이브 없이 검증. OAuth-a2.

★범위: *요청 구성·응답 파싱·에러 매핑* 로직만 검증한다 — 카카오/네이버 외부 API 계약은 문서 기반
인코딩이라 실 통합(필드명·실제 응답)은 라이브 크레덴셜로만 확인 가능(로컬 미검증). 레지스트리
구성(`build_oauth_providers`)도 검증.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from whymath_backend.api.auth import OAuthProviderError
from whymath_backend.api.oauth_providers import (
    KakaoOAuthProvider,
    NaverOAuthProvider,
    build_oauth_providers,
)
from whymath_backend.config import Settings

_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── 카카오 ──────────────────────────────────────────────────────────────────
def _kakao_ok(request: httpx.Request) -> httpx.Response:
    if "oauth/token" in str(request.url):
        return httpx.Response(200, json={"access_token": "tok"})
    if "user/me" in str(request.url):
        return httpx.Response(200, json={"id": 42, "kakao_account": {"email": "u@kakao.com"}})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_kakao_success() -> None:
    client = _client(_kakao_ok)
    provider = KakaoOAuthProvider(client_id="id", client_secret="s", client=client)
    identity = await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()
    assert identity.provider == "kakao"
    assert identity.subject == "42"
    assert identity.email == "u@kakao.com"


@pytest.mark.asyncio
async def test_kakao_token_failure_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_grant"})

    client = _client(handler)
    provider = KakaoOAuthProvider(client_id="id", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("bad", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_kakao_missing_email_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, json={"id": 42, "kakao_account": {}})  # 이메일 없음

    client = _client(handler)
    provider = KakaoOAuthProvider(client_id="id", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


# ── 네이버 ──────────────────────────────────────────────────────────────────
def _naver_ok(request: httpx.Request) -> httpx.Response:
    if "oauth2.0/token" in str(request.url):
        return httpx.Response(200, json={"access_token": "tok"})
    if "nid/me" in str(request.url):
        return httpx.Response(200, json={"response": {"id": "n9", "email": "u@naver.com"}})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_naver_success() -> None:
    client = _client(_naver_ok)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    identity = await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()
    assert identity.provider == "naver"
    assert identity.subject == "n9"
    assert identity.email == "u@naver.com"


@pytest.mark.asyncio
async def test_naver_userinfo_failure_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.0/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(500)

    client = _client(handler)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


# ── 에러 경로 + lazy 클라이언트 (악성/불량 provider 응답 → 깔끔한 오류) ──────────
@pytest.mark.asyncio
async def test_kakao_token_missing_access_token_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})  # access_token 없음

    client = _client(handler)
    provider = KakaoOAuthProvider(client_id="id", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_kakao_userinfo_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(401)

    client = _client(handler)
    provider = KakaoOAuthProvider(client_id="id", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_kakao_network_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    provider = KakaoOAuthProvider(client_id="id", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_kakao_lazy_client_created_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """client 미주입 → provider가 자체 httpx 클라이언트 생성·finally에서 종료(lazy 경로)."""
    mock = _client(_kakao_ok)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock)
    provider = KakaoOAuthProvider(client_id="id", client_secret="s")  # client 미주입
    identity = await provider.fetch_identity("code", "https://app/cb")
    assert identity.email == "u@kakao.com"
    assert mock.is_closed


@pytest.mark.asyncio
async def test_naver_token_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client(handler)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_token_missing_access_token_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    client = _client(handler)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_userinfo_missing_email_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.0/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, json={"response": {"id": "n9"}})  # email 없음

    client = _client(handler)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_network_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    provider = NaverOAuthProvider(client_id="id", client_secret="s", client=client)
    with pytest.raises(OAuthProviderError):
        await provider.fetch_identity("code", "https://app/cb")
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_lazy_client_created_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """client 미주입 → provider가 자체 httpx 클라이언트 생성·finally에서 종료(lazy 경로)."""
    mock = _client(_naver_ok)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: mock)
    provider = NaverOAuthProvider(client_id="id", client_secret="s")  # client 미주입
    identity = await provider.fetch_identity("code", "https://app/cb")
    assert identity.email == "u@naver.com"
    assert mock.is_closed


# ── build_oauth_providers ────────────────────────────────────────────────────
def test_build_registers_configured_only() -> None:
    """key가 설정된 provider만 레지스트리에 등록."""
    settings = Settings(
        kakao_client_id="kid",
        naver_client_id="nid",
        naver_client_secret=SecretStr("ns"),
    )
    registry = build_oauth_providers(settings)
    assert set(registry) == {"kakao", "naver"}


def test_build_empty_when_unconfigured() -> None:
    """키 미설정(CI) → 빈 레지스트리(콜백 404·현 동작 보존)."""
    settings = Settings(kakao_client_id="", naver_client_id="")
    assert build_oauth_providers(settings) == {}
