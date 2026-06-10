"""L3 의존(provider·cache·trace·queue)을 app.state에 보관·조회 — app.py와 라우터가 공유.

provider/cache/trace/queue는 *앱 수명 동안 공유*되는 의존이라(DB 세션의 요청별 Depends와
달리) `create_app`이 `app.state`에 1회 저장하고 `request.app.state`로 조회한다. 이 모듈로
키·조회를 모아 app.py(저장 측)와 라우터 모듈(api/visualization.py 등·조회 측)이 *순환 import
없이* 공유한다 — 라우터가 app.py를 import하면 순환이다(app.py가 라우터를 include하므로).
"""

from __future__ import annotations

from fastapi import Request

from whymath_backend.l3.interfaces import (
    AsyncJobQueue,
    CacheBackend,
    LLMProvider,
    TraceSink,
)

# app.state 속성 키 — create_app(app.py)이 저장하고 아래 getter가 조회(문자열 단일 출처).
PROVIDER_KEY = "llm_provider"
CACHE_KEY = "llm_cache"
TRACE_KEY = "trace_sink"
QUEUE_KEY = "job_queue"


def get_provider(request: Request) -> LLMProvider:
    """요청의 app.state에서 LLM provider를 꺼낸다(create_app 주입)."""
    provider: LLMProvider = getattr(request.app.state, PROVIDER_KEY)
    return provider


def get_cache(request: Request) -> CacheBackend:
    """요청의 app.state에서 캐시 백엔드를 꺼낸다."""
    cache: CacheBackend = getattr(request.app.state, CACHE_KEY)
    return cache


def get_trace(request: Request) -> TraceSink:
    """요청의 app.state에서 관측 싱크를 꺼낸다."""
    trace: TraceSink = getattr(request.app.state, TRACE_KEY)
    return trace


def get_queue(request: Request) -> AsyncJobQueue:
    """요청의 app.state에서 비동기 작업 큐를 꺼낸다."""
    queue: AsyncJobQueue = getattr(request.app.state, QUEUE_KEY)
    return queue
