"""CeleryJobQueue(queue.py) 단위 테스트 — enqueue→job_id를 가짜 sender로 검증.

설계 정본: docs/architecture/03a_l3_router_design.md §D.3(QUALITY 비동기 큐 경로).
범위 메모(M1.2): 라이브 Celery broker 없이, 손으로 짠 가짜 sender를 주입해 *큐 계약*
(enqueue(payload)→job_id 즉시 반환)만 검증한다. 모킹 라이브러리 미사용(pyproject 의도).
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import AsyncJobQueue
from whymath_backend.l3.queue import CeleryJobQueue


class _FakeSender:
    """손으로 짠 가짜 작업 sender — payload를 기록하고 결정적 job_id를 돌려준다.

    실제 sender(_build_default_sender)는 Celery task.apply_async를 감싸 AsyncResult.id를
    반환하지만, 테스트는 broker 없이 *큐 경계*만 본다 — payload가 그대로 전달되고
    job_id가 호출자에게 즉시 반환되는지(03a §D.3).
    """

    def __init__(self, job_id: str = "job-001") -> None:
        self._job_id = job_id
        self.payloads: list[dict[str, object]] = []
        self.call_count = 0

    async def __call__(self, payload: dict[str, object]) -> str:
        self.call_count += 1
        self.payloads.append(payload)
        return self._job_id


def _queue(sender: _FakeSender) -> CeleryJobQueue:
    """가짜 sender를 주입한 CeleryJobQueue."""
    return CeleryJobQueue(sender=sender, settings=Settings())


class TestCeleryJobQueue:
    async def test_enqueue_returns_job_id(self) -> None:
        """enqueue는 sender의 job_id를 즉시 반환한다(03a §D.3 즉시 반환)."""
        sender = _FakeSender(job_id="quality-42")
        job_id = await _queue(sender).enqueue({"prompt": "p"})
        assert job_id == "quality-42"
        assert sender.call_count == 1

    async def test_enqueue_forwards_payload(self) -> None:
        """payload가 sender로 그대로 전달된다(워커 입력 보존)."""
        sender = _FakeSender()
        payload: dict[str, object] = {"prompt": "풀이", "system": "sys", "decision": {}}
        await _queue(sender).enqueue(payload)
        assert sender.payloads == [payload]

    async def test_multiple_enqueue(self) -> None:
        """여러 enqueue가 각각 전송된다."""
        sender = _FakeSender()
        q = _queue(sender)
        await q.enqueue({"n": 1})
        await q.enqueue({"n": 2})
        assert sender.call_count == 2
        assert sender.payloads == [{"n": 1}, {"n": 2}]

    async def test_satisfies_protocol(self) -> None:
        """CeleryJobQueue는 AsyncJobQueue Protocol을 충족한다(runtime_checkable)."""
        assert isinstance(_queue(_FakeSender()), AsyncJobQueue)

    async def test_lazy_build_uses_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """sender 미주입 시 settings로 lazy build한다(빌더를 가짜로 가로챔)."""
        captured: dict[str, object] = {}

        def _fake_build(settings: Settings) -> _FakeSender:
            captured["url"] = settings.redis_url
            return _FakeSender(job_id="lazy-job")

        # _build_default_sender를 가짜로 치환 — 라이브 Celery broker 생성 회피.
        monkeypatch.setattr("whymath_backend.l3.queue._build_default_sender", _fake_build)
        queue = CeleryJobQueue(sender=None, settings=Settings(redis_url="redis://h:6379/9"))
        job_id = await queue.enqueue({"n": 1})  # 첫 enqueue에서 lazy build 발동
        assert captured["url"] == "redis://h:6379/9"
        assert job_id == "lazy-job"
