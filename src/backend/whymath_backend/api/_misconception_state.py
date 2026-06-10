"""오개념 의미 매처 *프로세스 싱글톤* — lazy·thread-safe 구성 + 테스트 주입 (slice 106).

L4 `SemanticMatcher`는 카탈로그 표현을 1회 사전 임베딩해 캐시하므로(03 matcher.py
`_ensure_built`) *프로세스당 한 인스턴스*를 공유해야 라이브 모델 왕복·재임베딩을 피한다. 이
모듈이 그 싱글톤을 보관·조회한다.

**왜 app.state가 아니라 모듈 전역인가**: coach 단위테스트는 `TestClient(app)`을 컨텍스트매니저
*없이* 쓰므로 lifespan(app.state 주입 지점)이 발화하지 않는다(03 app.py `_lifespan` docstring·
starlette 기본). 따라서 app.state 의존은 테스트에서 비고, 매처는 *요청 시점에 lazy 자가구성*
돼야 한다. `_device_store.py`의 모듈 전역 `set_/get_device_store` 패턴을 미러링한다 — 단,
매처는 *lazy 자가구성*까지 하므로 double-checked locking으로 멀티스레드(=`asyncio.to_thread`
워커 풀)에서도 1회만 만든다.

**thread-safety**: coach `_compute_matches`가 `asyncio.to_thread(matcher.match, ...)`로 매처를
*워커 스레드*에서 호출한다(블로킹 임베딩이 이벤트 루프를 막지 않게). 첫 호출이 여러 스레드에서
동시에 들어오면 ① 싱글톤 *생성* 경합(`threading.Lock` double-checked로 차단) ② 매처 내부
`_ensure_built`(인덱스 1회 적재)의 경합이 있다. ②는 app.py lifespan이 게이트 ON일 때 *단일
스레드에서* 웜업(첫 match 1회)으로 미리 완료해 막는다(멀티스레드 경합 안전판). lifespan 미발화
테스트는 단일 요청부터 시작하므로 실질 경합이 없고, 통합/프로덕션은 웜업이 가드한다.

구성 체인(03 좌석 팩토리 재사용): `build_provider(settings)`(provider.py) →
`_provider_model_identity(provider, settings)`(pgvector_index.py·임베딩 공간 식별자) →
`build_vector_index(settings, provider_name=, model_name=)`(index.py·memory/pgvector) →
`SemanticMatcher(provider=, index=)`. memory(기본)면 식별자는 무시되고 InMemoryVectorIndex가
선다(03 build_vector_index docstring).
"""

from __future__ import annotations

import threading

from whymath_backend.config import get_settings
from whymath_backend.l4.misconception.semantic.index import build_vector_index
from whymath_backend.l4.misconception.semantic.matcher import SemanticMatcher
from whymath_backend.l4.misconception.semantic.pgvector_index import _provider_model_identity
from whymath_backend.l4.misconception.semantic.provider import build_provider

# 프로세스 싱글톤 + 생성 경합 차단 락(double-checked). None=미생성(첫 get에서 lazy 구성)·
# 테스트가 set_으로 주입하면 그 인스턴스를 그대로 쓴다(자가구성 skip).
_MATCHER: SemanticMatcher | None = None
_LOCK = threading.Lock()


def _build_matcher() -> SemanticMatcher:
    """Settings 기반 매처 구성 — 좌석 팩토리 체인(provider→index→matcher) 재사용.

    `build_provider`(local/openai/fake)·`build_vector_index`(memory/pgvector) 둘 다 *지연*이라
    이 구성만으로는 모델 로드·DB 연결이 없다(첫 embed/search 시점). memory(기본)면 provider/model
    식별자는 InMemoryVectorIndex가 무시한다(인터페이스 대칭을 위해 계산해 넘김).
    """
    settings = get_settings()
    provider = build_provider(settings)
    provider_name, model_name = _provider_model_identity(provider, settings)
    index = build_vector_index(settings, provider_name=provider_name, model_name=model_name)
    return SemanticMatcher(provider=provider, index=index)


def get_semantic_matcher() -> SemanticMatcher:
    """프로세스 싱글톤 의미 매처를 반환(미생성 시 lazy·thread-safe 구성).

    double-checked locking: 락 밖 빠른 경로(이미 생성)로 대부분 호출은 락을 안 잡고, 미생성일
    때만 락을 잡아 *한 번만* 만든다(`asyncio.to_thread` 워커 풀의 동시 첫 호출 경합 차단).
    테스트가 `set_semantic_matcher`로 주입했으면 그 인스턴스를 그대로 돌려준다(자가구성 skip).
    """
    matcher = _MATCHER
    if matcher is not None:
        return matcher
    with _LOCK:
        # 락 안에서 재확인 — 락 대기 중 다른 스레드가 이미 만들었을 수 있다.
        if _MATCHER is None:
            _set(_build_matcher())
        assert _MATCHER is not None  # noqa: S101 — 위에서 방금 설정(타입 좁히기)
        return _MATCHER


def _set(matcher: SemanticMatcher | None) -> None:
    """전역 싱글톤 설정(내부 헬퍼·락 보유 가정 또는 테스트 단일 스레드)."""
    global _MATCHER
    _MATCHER = matcher


def set_semantic_matcher(matcher: SemanticMatcher) -> None:
    """테스트 주입 — Fake/Scripted provider 매처를 싱글톤으로 박는다(lazy 자가구성 우회).

    coach 의미 테스트가 `set_semantic_matcher(SemanticMatcher(provider=FakeEmbeddingProvider()))`
    로 라이브 모델 없이 결합 경로를 검증한다. 매 테스트 끝에 `reset_semantic_matcher()`로 격리.
    """
    with _LOCK:
        _set(matcher)


def reset_semantic_matcher() -> None:
    """테스트 격리 — 싱글톤을 None으로 되돌린다(다음 get은 다시 lazy 구성 또는 재주입)."""
    with _LOCK:
        _set(None)
