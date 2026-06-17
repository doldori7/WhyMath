"""CeleryJobQueue 단위테스트 — 가짜 Celery 앱 주입 (broker·워커 없음).

ollama.py·redis_cache.py 단위테스트(가짜 클라이언트를 시임으로 주입)를 미러링한다.
실제 Celery broker·result backend에 의존하지 않는다 → CI hermetic.

검증 범위:
  - enqueue: send_task(이름, [payload]) 디스패치 → 반환 핸들의 .id를 job_id로.
  - result: celery 상태 → JobStatus.state 정규화(pending/success/failure/unknown).
  - never-break: result backend 도달 실패(예외)를 흡수해 state=unknown으로 보고.
  - enqueue 실패(broker 다운)는 *전파*(파이프라인이 도메인 예외로 감쌈).

설계 정본: docs/architecture/03a_l3_router_design.md §D.3(QUALITY 비동기 큐 경로).
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.l3.queue import CeleryJobQueue, JobStatus
from whymath_backend.l3.queue.celery_job_queue import (
    _CeleryApp,
    _coerce_text,
)
from whymath_backend.l3.queue.tasks import QUALITY_TASK_NAME


class FakeAsyncResult:
    """가짜 celery AsyncResult — state·result를 정해서 돌려준다(폴링 모사).

    `state_raises`/`result_raises`로 result backend 도달 실패도 모사한다(never-break
    경로 검증). `id`는 핸들 식별자.
    """

    def __init__(
        self,
        task_id: str,
        *,
        state: str = "PENDING",
        result: Any = None,
        state_raises: Exception | None = None,
        result_raises: Exception | None = None,
    ) -> None:
        self._id = task_id
        self._state = state
        self._result = result
        self._state_raises = state_raises
        self._result_raises = result_raises

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> str:
        if self._state_raises is not None:
            raise self._state_raises
        return self._state

    @property
    def result(self) -> Any:
        if self._result_raises is not None:
            raise self._result_raises
        return self._result


class FakeCeleryApp:
    """가짜 celery.Celery — send_task·AsyncResult를 인메모리로 모사.

    `_CeleryApp` 시임을 구조적으로 충족한다. send_task는 (name, args)를 기록하고
    정해진 job_id 핸들을 돌려준다. AsyncResult는 job_id → 미리 등록한 FakeAsyncResult를
    돌려준다(없으면 PENDING 기본). `send_raises`로 broker 다운(디스패치 실패)을 모사한다.
    """

    def __init__(
        self,
        *,
        enqueue_id: str = "task-abc",
        send_raises: Exception | None = None,
        results: dict[str, FakeAsyncResult] | None = None,
        async_result_raises: Exception | None = None,
    ) -> None:
        self._enqueue_id = enqueue_id
        self._send_raises = send_raises
        self._results = results or {}
        self._async_result_raises = async_result_raises
        self.send_calls: list[tuple[str, Any]] = []
        self.async_result_calls: list[str] = []

    def send_task(self, name: str, args: Any = None, kwargs: Any = None) -> Any:
        self.send_calls.append((name, args))
        if self._send_raises is not None:
            raise self._send_raises
        return FakeAsyncResult(self._enqueue_id)

    def AsyncResult(self, task_id: str) -> Any:  # noqa: N802 — celery API 이름 보존
        self.async_result_calls.append(task_id)
        if self._async_result_raises is not None:
            raise self._async_result_raises
        return self._results.get(task_id, FakeAsyncResult(task_id, state="PENDING"))


def _payload() -> dict[str, object]:
    """대표 enqueue payload(파이프라인이 만드는 형태)."""
    return {"prompt": "p", "system": "s", "decision": {"cost_tier": "local"}}


class TestEnqueue:
    async def test_enqueue_dispatches_by_name_and_returns_id(self) -> None:
        """enqueue → send_task(QUALITY_TASK_NAME, [payload]) → 반환 핸들 .id."""
        app = FakeCeleryApp(enqueue_id="job-777")
        queue = CeleryJobQueue(app=app)
        job_id = await queue.enqueue(_payload())
        assert job_id == "job-777"
        assert len(app.send_calls) == 1
        name, args = app.send_calls[0]
        assert name == QUALITY_TASK_NAME
        assert args == [_payload()]  # payload 1건을 args로

    async def test_enqueue_returns_str_even_if_id_nonstr(self) -> None:
        """job_id는 항상 str로 정규화한다(계약: enqueue→str)."""

        class IntIdResult(FakeAsyncResult):
            @property
            def id(self) -> str:  # type: ignore[override] — 비정상 타입 모사
                return 12345  # type: ignore[return-value]

        class IntIdApp(FakeCeleryApp):
            def send_task(self, name: str, args: Any = None, kwargs: Any = None) -> Any:
                self.send_calls.append((name, args))
                return IntIdResult("ignored")

        queue = CeleryJobQueue(app=IntIdApp())
        job_id = await queue.enqueue(_payload())
        assert job_id == "12345"
        assert isinstance(job_id, str)

    async def test_enqueue_propagates_broker_failure(self) -> None:
        """broker 다운(send_task 예외)은 *전파*한다 — 파이프라인이 도메인 예외로 감쌈.

        여기서 흡수하면 job_id 계약(항상 str)을 어기게 되므로, 큐는 raw 예외를
        그대로 올리고 상위(pipeline.generate)가 QualityQueueUnavailableError로 변환한다.
        """
        app = FakeCeleryApp(send_raises=ConnectionError("broker refused"))
        queue = CeleryJobQueue(app=app)
        with pytest.raises(ConnectionError):
            await queue.enqueue(_payload())


class TestResult:
    def test_pending_states_map_to_pending(self) -> None:
        """PENDING/RECEIVED/STARTED/RETRY → state=pending(미확정)."""
        for celery_state in ("PENDING", "RECEIVED", "STARTED", "RETRY"):
            app = FakeCeleryApp(results={"j": FakeAsyncResult("j", state=celery_state)})
            status = CeleryJobQueue(app=app).result("j")
            assert status.state == "pending", celery_state
            assert status.ready is False
            assert status.text is None

    def test_success_returns_text(self) -> None:
        """SUCCESS → state=success + text(생성 결과)."""
        app = FakeCeleryApp(results={"j": FakeAsyncResult("j", state="SUCCESS", result="27b 결과")})
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "success"
        assert status.ready is True
        assert status.text == "27b 결과"
        assert status.error is None

    def test_success_with_nonstr_result_coerces_text_none(self) -> None:
        """SUCCESS인데 결과가 비정상 타입이면 text=None(안전 처리)."""
        app = FakeCeleryApp(results={"j": FakeAsyncResult("j", state="SUCCESS", result={"k": "v"})})
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "success"
        assert status.text is None

    def test_failure_returns_error_string(self) -> None:
        """FAILURE/REVOKED → state=failure + error(사유 문자열, 스택트레이스 아님)."""
        for celery_state in ("FAILURE", "REVOKED"):
            app = FakeCeleryApp(
                results={
                    "j": FakeAsyncResult("j", state=celery_state, result=ValueError("모델 오류"))
                }
            )
            status = CeleryJobQueue(app=app).result("j")
            assert status.state == "failure", celery_state
            assert status.ready is True
            assert status.error == "모델 오류"
            assert status.text is None

    def test_failure_with_none_result_error_none(self) -> None:
        """FAILURE인데 result가 None이면 error=None(사유 미상, 비크래시)."""
        app = FakeCeleryApp(results={"j": FakeAsyncResult("j", state="FAILURE", result=None)})
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "failure"
        assert status.error is None

    def test_unknown_celery_state_maps_to_pending(self) -> None:
        """표에 없는 celery 상태는 보수적으로 pending(미확정)으로 본다."""
        app = FakeCeleryApp(results={"j": FakeAsyncResult("j", state="WEIRD_STATE")})
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "pending"

    def test_backend_unreachable_absorbed_as_unknown(self) -> None:
        """result backend 도달 실패(AsyncResult 예외)는 흡수 → state=unknown(비크래시)."""
        app = FakeCeleryApp(async_result_raises=ConnectionError("backend down"))
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "unknown"
        assert status.ready is False
        assert status.error is not None
        assert "ConnectionError" in status.error

    def test_state_read_failure_absorbed_as_unknown(self) -> None:
        """상태 읽기 자체가 예외(backend 끊김)면 unknown으로 흡수."""
        app = FakeCeleryApp(
            results={"j": FakeAsyncResult("j", state_raises=TimeoutError("read timeout"))}
        )
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "unknown"
        assert status.error is not None

    def test_success_result_read_failure_absorbed_as_unknown(self) -> None:
        """SUCCESS 판정 후 결과 읽기가 실패하면 unknown으로 흡수(역직렬화 장애)."""
        app = FakeCeleryApp(
            results={
                "j": FakeAsyncResult("j", state="SUCCESS", result_raises=ValueError("deser fail"))
            }
        )
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "unknown"
        assert status.error is not None

    def test_failure_result_read_failure_error_none(self) -> None:
        """FAILURE 사유 읽기가 실패해도 비크래시 — state=failure·error=None."""
        app = FakeCeleryApp(
            results={
                "j": FakeAsyncResult(
                    "j", state="FAILURE", result_raises=ValueError("meta deser fail")
                )
            }
        )
        status = CeleryJobQueue(app=app).result("j")
        assert status.state == "failure"
        assert status.error is None


class TestLazyDefaults:
    def test_default_app_built_from_settings(self) -> None:
        """app 미주입 시 Settings로 기본 Celery 앱을 지연 생성(broker 연결 없음).

        build_celery_app는 broker에 즉시 연결하지 않으므로 라이브 Redis 없이도 안전하다.
        _build_default_app·_get_app·_resolved_settings 기본 경로를 모두 통과시킨다.
        """
        from whymath_backend.config import Settings

        queue = CeleryJobQueue(settings=Settings(redis_url="redis://127.0.0.1:6379/0"))
        app = queue._get_app()
        assert isinstance(app, _CeleryApp)  # runtime_checkable Protocol 충족
        # 두 번째 호출은 캐시된 같은 인스턴스(지연 1회 생성).
        assert queue._get_app() is app

    def test_resolved_settings_falls_back_to_global(self) -> None:
        """settings 미주입 시 전역 get_settings()로 폴백한다."""
        from whymath_backend.config import Settings, get_settings

        get_settings.cache_clear()
        queue = CeleryJobQueue()
        assert isinstance(queue._resolved_settings, Settings)

    def test_satisfies_async_job_queue_protocol(self) -> None:
        """CeleryJobQueue는 AsyncJobQueue Protocol을 충족한다(runtime_checkable)."""
        from whymath_backend.l3.interfaces import AsyncJobQueue

        assert isinstance(CeleryJobQueue(app=FakeCeleryApp()), AsyncJobQueue)


class TestJobStatus:
    def test_ready_only_for_terminal_states(self) -> None:
        """ready는 success/failure에서만 True, pending/unknown은 False."""
        assert JobStatus("j", "success", text="t").ready is True
        assert JobStatus("j", "failure", error="e").ready is True
        assert JobStatus("j", "pending").ready is False
        assert JobStatus("j", "unknown", error="e").ready is False


class TestCoerceText:
    def test_str_passthrough(self) -> None:
        assert _coerce_text("값") == "값"

    def test_nonstr_returns_none(self) -> None:
        assert _coerce_text(123) is None
        assert _coerce_text({"k": "v"}) is None
        assert _coerce_text(None) is None


def test_fake_app_satisfies_seam_protocol() -> None:
    """가짜 앱이 _CeleryApp 시임을 구조적으로 충족하는지 확인(테스트 위생)."""
    assert isinstance(FakeCeleryApp(), _CeleryApp)
