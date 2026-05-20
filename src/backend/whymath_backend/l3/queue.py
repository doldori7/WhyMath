"""L3 비동기 작업 큐 — `AsyncJobQueue` Protocol의 Celery 구현.

설계 정본: docs/architecture/03a_l3_router_design.md §D.3(QUALITY 비동기 큐 경로).
QUALITY(27b)는 동기 호출 불가(p50≈14초·병렬 미작동) → 모든 QUALITY 요청은 이 큐로
enqueue되고, 호출자에게는 *즉시 job_id*를 돌려준다(완료는 폴링/콜백).

워커 동시성 = 1 (운영 설정):
    QUALITY는 단일 GPU 100% 점유라 병렬 시 throughput 무이득·p50 폭발(03a §D.3·§E.1).
    따라서 워커는 반드시 동시성 1로 띄운다 — 이는 *런타임 기동 옵션*이지 코드 상수가
    아니다. Phaiakes9에서:

        celery -A whymath_backend.l3.queue:celery_app worker --concurrency=1 -Q quality

    (단일 큐 `quality`에 동시성 1 워커 1대. 큐 깊이 임계 초과 시 ⑤ 자기검증 샘플링
    비율을 낮춰 부하 조절 — 03a §D.3·§F. 그 동적 조절은 §H 후속6 큐 SLA 범위.)

**왜 Celery인가 (Redis 리스트 큐가 아니라):**
    pyproject 의존성에 celery>=5.4.0이 이미 있고(브로커=settings.redis_url, Redis 재사용),
    재시도·결과 백엔드·워커 관리가 기성품이라 운영 부담이 작다. 테스트화가 무거운
    것은 *Celery app 자체*가 아니라 *broker 연결*인데, 이를 `_TaskSenderProtocol`
    (apply_async 한 메서드)로 추상화해 분리한다 — bench_latency.py가 `ollama.AsyncClient`
    를 `_OllamaClientProtocol` 뒤에 둔 것과 동형. 테스트는 가짜 sender를 주입하고,
    실제 sender는 lazy로 Celery task의 .apply_async를 감싼다. 따라서 Celery를 쓰면서도
    단위테스트는 broker·워커 없이 통과한다(Redis 리스트 큐로 후퇴할 이유가 없다).

테스트 가능성(bench_latency.py·quality_eval.py 패턴 미러링):
  - `celery` import는 *함수 안에서만*(lazy) — 모듈은 stdlib만으로 로드 가능해야 한다.
  - 작업 전송은 `_TaskSenderProtocol` 추상 경유 — 테스트는 손으로 짠 가짜 sender 주입.
"""

from __future__ import annotations

from typing import Any, Protocol

from whymath_backend.config import Settings, get_settings

# Celery 큐·태스크 이름 — 워커 기동(-Q quality)·라우팅과 일치해야 한다(모듈 docstring).
_QUEUE_NAME: str = "quality"
_TASK_NAME: str = "whymath.l3.quality_generate"


class _TaskSenderProtocol(Protocol):
    """비동기 작업 전송기의 최소 인터페이스 (job_id 반환).

    실제로는 Celery task의 `apply_async`를 감싸지만, 테스트에서는 가짜 sender로
    대체 가능하다(가짜는 job_id 문자열만 돌려준다). payload 1건을 전송하고 job_id를
    반환한다 — bench_latency.py의 `_OllamaClientProtocol`과 같은 *주입 경계*다.
    """

    async def __call__(self, payload: dict[str, object]) -> str:
        """payload를 큐에 넣고 job_id(str)를 반환한다."""
        ...


def _build_celery_app(settings: Settings) -> Any:  # pragma: no cover
    """Celery 앱 인스턴스 생성 (broker·backend = settings.redis_url).

    라이브 SDK 생성 shim — 라이브 broker 없이는 의미 없으므로 커버리지 제외(§H 후속6).
    `celery` import는 *이 함수 안에서만* 한다(lazy). importlib 동적 로드로 타입 스텁
    유무와 무관하게 mypy --strict를 통과한다(quality_eval.py 패턴). broker·result
    backend 모두 Redis(settings.redis_url) — 캐시용 Redis와 같은 인스턴스를 재사용한다.
    """
    import importlib

    try:
        celery_mod = importlib.import_module("celery")
    except ImportError as exc:
        raise RuntimeError("celery가 설치되지 않았습니다. `pip install celery` 후 재시도.") from exc
    app = celery_mod.Celery(
        "whymath_l3",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    return app


def _build_default_sender(settings: Settings) -> _TaskSenderProtocol:  # pragma: no cover
    """기본 Celery 기반 sender 생성 — task.apply_async를 job_id 반환 코루틴으로 감싼다.

    라이브 broker 생성 shim — broker·워커 없이는 실행 불가하므로 커버리지 제외(테스트는
    monkeypatch로 치환해 lazy build 경로만 검증한다, test_queue.py).

    Celery task 본체(워커가 실행할 QUALITY 생성)는 *워커 프로세스*에서 동작하므로
    여기서는 등록만 한다(name=_TASK_NAME, queue=_QUEUE_NAME). enqueue 시 apply_async는
    AsyncResult를 돌려주고 그 `.id`가 job_id다(03a §D.3 "즉시 job_id 반환").
    apply_async는 동기 호출이지만 Protocol은 async라, 얇은 코루틴으로 감싼다(이벤트
    루프를 막지 않으려면 후속에서 to_thread로 옮길 수 있음 — §H 후속6).
    """
    app = _build_celery_app(settings)

    # app은 Any(Celery 동적 로드) — @app.task 데코레이터·apply_async는 타입 미상이라
    # 이 빌더 내부는 통째로 동적 영역이다. 데코레이터가 함수를 동적화하는 것은 의도된
    # 동작이라 untyped-decorator를 좁게 무시한다(함수 전체는 def 줄 pragma로 제외됨).
    @app.task(name=_TASK_NAME, queue=_QUEUE_NAME)  # type: ignore[untyped-decorator]
    def _quality_generate(payload: dict[str, object]) -> dict[str, object]:
        """QUALITY(27b) 생성 작업 본체 — 워커(동시성 1)가 실행한다.

        실제 생성 로직(OllamaProvider로 qwen3.5:27b 호출 + 환각 방어)은 §H 후속6에서
        워커 측에 연결한다. 여기서는 큐 계약(payload in → 결과 dict)만 고정한다.
        """
        raise NotImplementedError("QUALITY 워커 본체는 §H 후속6에서 연결한다(broker·GPU 필요).")

    async def _send(payload: dict[str, object]) -> str:
        result = _quality_generate.apply_async(args=[payload], queue=_QUEUE_NAME)
        return str(result.id)

    return _send


class CeleryJobQueue:
    """Celery 기반 비동기 큐 — `AsyncJobQueue` 충족 (03a §D.3).

    enqueue(payload) → job_id 즉시 반환. sender 주입 가능 — 기본 None이면 첫 enqueue 시
    settings.redis_url 브로커로 lazy build. 워커 동시성 1은 *기동 옵션*이다(모듈 docstring).
    """

    def __init__(
        self,
        *,
        sender: _TaskSenderProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._sender = sender
        self._settings = settings if settings is not None else get_settings()

    def _ensure_sender(self) -> _TaskSenderProtocol:
        """주입된 sender가 없으면 settings로 lazy 생성."""
        if self._sender is None:
            self._sender = _build_default_sender(self._settings)
        return self._sender

    async def enqueue(self, payload: dict[str, object]) -> str:
        """작업을 큐에 넣고 job_id를 반환한다(03a §D.3 즉시 반환)."""
        return await self._ensure_sender()(payload)
