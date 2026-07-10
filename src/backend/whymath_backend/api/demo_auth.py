"""시연(데모) 전용 가짜 OAuth provider — S1 탈출 게이트 ①(실기기 학습 루프 15분 녹화) 인에이블먼트.

목적: 실기기 시연을 막는 하드 블로커 ①(인증)을 해소한다. 보호 엔드포인트
(`/v1/me/next-problem`·코치 세션·`/v1/ocr`)는 토큰 없으면 401인데, 실 로그인 webview(OAuth-c3)가
미배선이라 시연이 돌지 않는다. 이 모듈은 `api/auth.py`의 `OAuthProvider` Protocol을 구조적으로
충족하는 가짜 provider를 제공해, **기존 콜백 경로**(`POST /v1/auth/{provider}/callback`)를 그대로
타고 고정 데모 계정의 실 JWT를 발급한다 — `security.py`·`_auth.py`는 손대지 않는다.

★보안 경계(정직): 이 provider는 신원을 전혀 검증하지 않는다(어떤 code든 고정 신원 반환). 따라서
`create_app`이 이를 등록하는 것은 **`settings.demo_auth_enabled`가 명시적으로 True일 때만**이고,
그마저도 실 provider(kakao/naver)가 구성된 환경(=prod 신호)에서는 **이중 방어**로 등록을 거부한다.
로컬 시연 호스트 밖에서 `WHYMATH_DEMO_AUTH_ENABLED`를 켜면 임의 데모 계정 토큰이 발급되므로
절대 금지다. demo 코드를 실 `oauth_providers.py`와 물리 분리해 시연 코드가 실 로그인 경로에 섞이지
않게 한다.
"""

from __future__ import annotations

import logging

from whymath_backend.api.auth import OAuthIdentity, OAuthProvider
from whymath_backend.config import Settings

logger = logging.getLogger(__name__)

# 시연 계정 결정론 상수 — 안정 upsert(같은 이메일=같은 email_hash=같은 UserProfile·재실행 안전).
DEMO_PROVIDER_NAME = "demo"
DEMO_EMAIL = "demo-student@whymath.example"
DEMO_SUBJECT = "demo-fixed-subject"
# 비미성년 출생연도 — is_minor=False로 파생돼 동의 게이트(get_consented_user 403)를 통과한다.
# (코치·OCR 등 ConsentedUser 라우트가 시연 루프에 포함되므로 필수.) 페르소나는 resolve_user가
# 기본값 A_일반고고3으로 채운다(시연 페르소나와 정합).
DEMO_BIRTH_YEAR = 2006


class FakeOAuthProvider:
    """시연 전용 — 어떤 code든 고정 데모 신원을 반환(실 provider 대체·라이브 의존 0).

    `api/auth.py`의 `OAuthProvider` Protocol을 구조적으로 충족한다. `fetch_identity`가 결정론적
    `OAuthIdentity`를 돌려줘 콜백의 `resolve_user`가 안정 데모 사용자를 upsert한다(비미성년 →
    동의 게이트 통과). code·redirect_uri는 검증 없이 무시한다(시연 편의·라이브 provider 불필요).
    """

    async def fetch_identity(self, code: str, redirect_uri: str) -> OAuthIdentity:
        """code 무시하고 고정 데모 신원 반환 — 콜백이 이 신원으로 실 JWT를 발급한다."""
        return OAuthIdentity(
            provider=DEMO_PROVIDER_NAME,
            subject=DEMO_SUBJECT,
            email=DEMO_EMAIL,
            birth_year=DEMO_BIRTH_YEAR,
        )


def register_demo_provider(providers: dict[str, OAuthProvider], settings: Settings) -> None:
    """`demo_auth_enabled`일 때만 시연 provider를 레지스트리에 추가한다(loud warning).

    **이중 방어**: 실 provider(kakao/naver)가 구성된 환경(=prod 신호)에서는 플래그가 True여도
    등록을 거부한다 — prod엔 항상 실 provider가 있으므로 플래그가 실수로 새더라도 가짜가 등록되지
    않는다. `build_oauth_providers`가 실 provider 등록 뒤 호출한다.
    """
    if not settings.demo_auth_enabled:
        return
    if settings.kakao_configured or settings.naver_configured:
        logger.warning(
            "WHYMATH_DEMO_AUTH_ENABLED=true 무시 — 실 OAuth provider(kakao/naver) 구성됨"
            "(prod 추정). 시연 가짜 provider를 등록하지 않는다(이중 방어)."
        )
        return
    logger.warning(
        "⚠ 시연 전용 가짜 OAuth provider 등록됨 — POST /v1/auth/%s/callback이 신원 검증 없이 "
        "고정 데모 계정 토큰을 발급한다. 로컬 시연 호스트 전용·prod 금지.",
        DEMO_PROVIDER_NAME,
    )
    providers[DEMO_PROVIDER_NAME] = FakeOAuthProvider()
