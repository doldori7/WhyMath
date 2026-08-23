"""Celery 큐 통합 테스트 — 실제 celery + redis (Phaiakes9 전용).

기본 SKIP. 실행하려면 환경변수 `WHYMATH_RUN_INTEGRATION=1`(+ 필요 시
`WHYMATH_REDIS_URL`/`WHYMATH_CELERY_BROKER_URL`)을 설정한다. CI는 이 변수를 설정하지
않으므로 자동으로 빠진다(tests/backend/conftest.py 게이트). redis 통합 테스트
(test_redis_integration.py)·langfuse 통합 테스트와 동일한 게이트·graceful-skip 패턴이다.

목적: (1) eager 모드에서 enqueue→태스크 실행→result 폴링이 *실제 Celery 객체*로
end-to-end 동작하는지, (2) 실 broker로 send_task 디스패치가 되는지(워커 없이 PENDING
관측)를 Kiki가 Phaiakes9에서 확인. 라이브러리(celery·redis)는 이미 의존성에 있다.

QUALITY(MoE) *실제 모델 실행*은 이 통합 테스트의 범위가 아니다(GPU·ollama 필요, p50≈
2.3초). 여기서는 큐 *배관*(enqueue·result·디스패치)만 가짜 provider로 검증한다 —
모델 실행 자체는 ollama 통합 테스트(test_ollama_integration.py)가 별도로 다룬다.

설계 정본: docs/architecture/03a_l3_router_design.md §D.3(QUALITY 비동기 큐 경로).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.models import GenerationResult
from whymath_backend.l3.queue.celery_app import build_celery_app
from whymath_backend.l3.queue.celery_job_queue import CeleryJobQueue

pytestmark = pytest.mark.integration


def _broker_reachable(settings: Settings) -> bool:
    """broker(redis)에 ping이 닿는지 — 미도달이면 graceful skip 판정용."""
    try:
        from redis import Redis  # 동기 redis(통합 테스트 한정 — 의존성에 이미 있음)

        client = Redis.from_url(settings.effective_celery_broker_url)
        return bool(client.ping())
    except Exception:  # noqa: BLE001 — 미도달을 False로(통합 skip)
        return False


def test_eager_apply_and_poll_e2e() -> None:
    """eager(.apply) 실행 → result backend 저장 → CeleryJobQueue.result=success 폴링.

    `.apply()`는 eager 설정과 무관하게 *항상* 태스크를 인라인 실행하고, store_eager_result
    True면 결과를 실 backend(redis)에 저장한다 → 별도 워커 프로세스 없이 태스크 본체 +
    result 폴링 배관을 실 Celery·redis로 검증할 수 있다(QUALITY 실제 모델 대신 가짜
    provider 주입 — GPU·ollama 회피). backend(redis)가 미도달이면 graceful skip.

    주의: CeleryJobQueue.enqueue는 의도적으로 send_task를 쓰는데(프로덕션 이름 기반
    디스패치), send_task는 eager를 무시한다 — 그래서 *실행*은 .apply()로 트리거하고,
    *조회*만 CeleryJobQueue.result로 검증한다(폴링 경로가 핵심 검증 대상).
    """
    settings = Settings()
    if not _broker_reachable(settings):
        pytest.skip("Celery result backend(redis) 미도달 — 통합 테스트 건너뜀")

    app = build_celery_app(settings)
    # store_eager_result: .apply() 결과를 실 backend(redis)에 저장 → result 폴링 가능.
    app.conf.update(task_store_eager_result=True)

    # 가짜 provider를 쓰는 태스크를 이 app에 등록(실제 ollama·GPU 회피).
    from whymath_backend.l3.models import CostTier, LocalModelTier, RoutingDecision
    from whymath_backend.l3.queue.tasks import (
        PAYLOAD_DECISION,
        PAYLOAD_PROMPT,
        PAYLOAD_SYSTEM,
        QUALITY_TASK_NAME,
        run_quality_generation_payload,
    )

    class _FakeProvider:
        async def generate(self, prompt: str, system: str, decision: Any) -> GenerationResult:
            return GenerationResult(f"eager-ok::{prompt}")

    @app.task(name=QUALITY_TASK_NAME, bind=False)
    def _eager_task(payload: dict[str, Any]) -> str:
        return run_quality_generation_payload(payload, provider=_FakeProvider())

    decision = RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=None,
        local_model=LocalModelTier.QUALITY,
        mode="async",
        est_latency_ms=2300,
    )
    payload = {
        PAYLOAD_PROMPT: "검증",
        PAYLOAD_SYSTEM: "시스템",
        PAYLOAD_DECISION: decision.model_dump(),
    }

    # .apply()는 인라인 실행하고 결과 핸들(.id)을 준다 — 그 id로 우리 큐의 폴링을 검증.
    eager_result = _eager_task.apply(args=[payload])
    job_id = eager_result.id
    assert job_id

    status = CeleryJobQueue(app=app).result(job_id)
    assert status.state == "success"
    assert status.text == "eager-ok::검증"


def test_real_broker_dispatch_e2e() -> None:
    """실 broker로 send_task 디스패치 — 워커 없이도 PENDING 상태가 관측된다.

    broker가 미도달이면 graceful skip(redis 통합 테스트 패턴). 워커를 띄우지 않으므로
    태스크는 실행되지 않고 PENDING(=pending)으로 남는다 — 디스패치 배관만 확인한다.
    """
    settings = Settings()
    if not _broker_reachable(settings):
        pytest.skip("Celery broker(redis) 미도달 — 통합 테스트 건너뜀")

    app = build_celery_app(settings)
    queue = CeleryJobQueue(app=app)

    payload = {"prompt": f"p-{uuid.uuid4().hex}", "system": "s", "decision": {}}
    import asyncio

    job_id = asyncio.run(queue.enqueue(payload))
    assert job_id

    # 워커가 없으니 즉시 결과는 없다 — pending(또는 backend 사정상 unknown). 비크래시.
    status = queue.result(job_id)
    assert status.state in ("pending", "unknown")
