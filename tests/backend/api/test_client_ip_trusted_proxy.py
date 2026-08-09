"""SEC-14 — `_client_ip`의 신뢰 프록시 화이트리스트 판정 (결함주입).

이 파일이 막는 것
-----------------
수정 전 `_client_ip`는 `X-Forwarded-For` 헤더가 있으면 *검증 없이* 좌측 첫 값을 그대로
채택했다 — 이 헤더는 클라이언트가 임의로 보낼 수 있는 평범한 HTTP 헤더라, 위조만으로
① 미인증 표면(auth 콜백/리프레시·결함 신고 등)의 IP rate limit을 전면 우회하고
② `privacy.audit.hash_client_ip`가 그대로 해시해 감사 로그(미성년 동의변경·개인정보 반출)에
남기는 IP 자체를 공격자가 통제할 수 있었다.

수정 후 계약(우측-신뢰 화이트리스트): `request.client.host`(우리 서버에 직접 TCP 연결한
피어)가 `settings.trusted_proxy_ips`에 있을 때만 X-Forwarded-For를 읽고, 그것도 오른쪽부터
신뢰 프록시를 건너뛰며 처음 만나는 미신뢰 값을 채택한다. 신뢰 프록시 미구성(기본, 빈
allowlist)이면 X-Forwarded-For를 완전히 무시 — 이게 이 파일의 핵심 결함주입 검증이다
(`TestNoTrustedProxyConfigured` — 위조 XFF가 통하지 않아야 실패하는 테스트).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._rate_limit import RateLimitedIpRead, _client_ip, reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings


def _settings(**overrides: object) -> Settings:
    """테스트용 Settings — jwt secret만 채우고 나머지는 기본값(hermetic)."""
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"), **overrides)  # type: ignore[arg-type]


def _request(*, client_host: str | None, xff: str | None) -> Request:
    """`request.client.host`·`X-Forwarded-For` 헤더만 통제하는 최소 가짜 Request."""
    request = MagicMock(spec=Request)
    request.headers = {"x-forwarded-for": xff} if xff is not None else {}
    if client_host is None:
        request.client = None
    else:
        request.client = MagicMock()
        request.client.host = client_host
    return request


class TestNoTrustedProxyConfigured:
    """신뢰 프록시 미구성(기본, 빈 allowlist) — XFF 위조가 통하지 않아야 한다."""

    def test_spoofed_xff_is_ignored_without_allowlist(self) -> None:
        settings = _settings()  # trusted_proxy_ip_allowlist 기본값("") → 빈 frozenset
        assert settings.trusted_proxy_ips == frozenset()
        request = _request(client_host="203.0.113.9", xff="1.2.3.4")
        # 위조 XFF가 아니라 실제 TCP 피어가 그대로 반환돼야 한다.
        assert _client_ip(request, settings=settings) == "203.0.113.9"

    def test_spoofed_xff_claiming_to_be_trusted_proxy_is_still_ignored(self) -> None:
        # allowlist가 비어 있으면 XFF 값이 "신뢰 프록시처럼 보이든" 무관하게 전부 무시.
        settings = _settings()
        request = _request(client_host="203.0.113.9", xff="1.2.3.4, 10.0.0.1")
        assert _client_ip(request, settings=settings) == "203.0.113.9"


class TestSingleHopTrustedProxy:
    """1홉 신뢰 프록시 — direct peer가 allowlist에 있고 XFF가 진짜 클라이언트 하나뿐."""

    def test_returns_the_single_xff_value(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="10.0.0.1")
        request = _request(client_host="10.0.0.1", xff="1.2.3.4")
        assert _client_ip(request, settings=settings) == "1.2.3.4"


class TestMultiHopChain:
    """다홉 체인 — 오른쪽부터 신뢰 프록시를 건너뛰고 첫 미신뢰 값을 채택."""

    def test_skips_trusted_hop_from_the_right(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="trusted_proxy_a, trusted_proxy_b")
        request = _request(
            client_host="trusted_proxy_b",
            xff="real_client, trusted_proxy_a",
        )
        assert _client_ip(request, settings=settings) == "real_client"

    def test_skips_multiple_trusted_hops(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="proxy_a, proxy_b, proxy_c")
        request = _request(
            client_host="proxy_c",
            xff="real_client, proxy_a, proxy_b",
        )
        assert _client_ip(request, settings=settings) == "real_client"


class TestUntrustedDirectPeerSpoofAttempt:
    """신뢰 안 된 직접 피어의 XFF 위조 시도 — allowlist 밖이면 XFF 내용 전부 무시."""

    def test_ignores_xff_even_if_it_impersonates_a_trusted_proxy(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="10.0.0.1")
        # XFF가 신뢰 프록시 IP(10.0.0.1)를 사칭해도, direct peer 자체가 신뢰되지 않으면 무의미.
        request = _request(client_host="203.0.113.99", xff="1.2.3.4, 10.0.0.1")
        assert _client_ip(request, settings=settings) == "203.0.113.99"


class TestAllHopsTrusted:
    """전부 신뢰 프록시인 XFF(원 클라이언트 IP가 헤더에 없는 이상 상황) — direct peer로 폴백."""

    def test_falls_back_to_direct_peer_when_no_untrusted_hop_found(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="proxy_a, proxy_b")
        request = _request(client_host="proxy_b", xff="proxy_a")
        assert _client_ip(request, settings=settings) == "proxy_b"

    def test_falls_back_to_direct_peer_when_xff_header_absent(self) -> None:
        # direct peer는 신뢰 프록시지만 XFF 헤더 자체가 없는 경우도 동일 폴백.
        settings = _settings(trusted_proxy_ip_allowlist="proxy_b")
        request = _request(client_host="proxy_b", xff=None)
        assert _client_ip(request, settings=settings) == "proxy_b"


class TestNoClientRegression:
    """`request.client is None` — 회귀 없음(기존과 동일하게 None)."""

    def test_returns_none_regardless_of_trusted_proxy_config(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist="10.0.0.1")
        request = _request(client_host=None, xff="1.2.3.4")
        assert _client_ip(request, settings=settings) is None


class TestRateLimitBypassBlockedAtDefault:
    """rate limit 판정 레벨 통합테스트 — 신뢰 프록시 미구성 상태에서 위조 XFF로 IP rate
    limit을 우회하려는 시도가 실제로 차단되는지 확인(TestClient — direct peer는 항상
    "testclient" 고정, 이 결함주입의 핵심은 XFF를 바꿔도 그 고정 피어가 그대로 쓰인다는 것)."""

    def setup_method(self) -> None:
        # InMemoryBackend 전역 카운터 격리 — 앞 테스트의 hit이 이 테스트의 429 단정을 오염시키지
        # 않도록(테스트 순서 의존 방지, CLAUDE.md "부분 스위트 통과…" 원칙 정합).
        import asyncio

        asyncio.run(reset_store())

    def test_alternating_forged_xff_does_not_reset_the_bucket(self) -> None:
        router = APIRouter()

        @router.get("/_test/sec14-ip-limited", dependencies=[RateLimitedIpRead])
        async def _hit() -> dict[str, bool]:
            return {"ok": True}

        app = create_app()
        app.include_router(router)
        app.dependency_overrides[get_settings] = lambda: _settings(
            coach_rate_limit_read_per_minute=0,
            coach_rate_limit_write_per_minute=0,
            coach_rate_limit_ip_read_per_minute=1,
            # trusted_proxy_ip_allowlist 미설정 — 기본 deny-by-default
        )
        client = TestClient(app)
        # 1회차: XFF 위조값 A — 신뢰 프록시 미구성이므로 무시되고 direct peer("testclient")로
        # 버킷팅된다.
        r1 = client.get("/_test/sec14-ip-limited", headers={"X-Forwarded-For": "1.1.1.1"})
        assert r1.status_code == 200
        # 2회차: XFF를 *다른 값*으로 바꿔 별도 버킷을 노리는 우회 시도 — 하지만 direct peer가
        # 그대로 쓰이므로 같은 버킷에 누적되어 429가 나야 한다(우회 실패 = 이 결함주입의 통과 조건).
        r2 = client.get("/_test/sec14-ip-limited", headers={"X-Forwarded-For": "2.2.2.2"})
        assert r2.status_code == 429
        assert r2.headers["X-RateLimit-Limit"] == "1"
        assert r2.headers["X-RateLimit-Remaining"] == "0"


class TestSettingsTrustedProxyIpsProperty:
    """`Settings.trusted_proxy_ips` 파싱 프로퍼티 — deny-by-default·공백/빈 항목 처리."""

    def test_default_is_empty_frozenset(self) -> None:
        assert _settings().trusted_proxy_ips == frozenset()

    def test_parses_comma_separated_with_whitespace(self) -> None:
        settings = _settings(trusted_proxy_ip_allowlist=" 10.0.0.1 , 10.0.0.2,, ")
        assert settings.trusted_proxy_ips == frozenset({"10.0.0.1", "10.0.0.2"})


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
