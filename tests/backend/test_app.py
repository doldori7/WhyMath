"""FastAPI 앱 단위테스트 — TestClient + 가짜 의존성 주입 (라이브 서비스 없음).

/health·/status(도달 가능/불가)·/v1/generate(동기 정상·QUALITY 202 큐잉·큐 미가용
503)·/v1/jobs/{id}(폴링)를 검증한다. 실제 Ollama·Redis·Langfuse·Celery broker에
의존하지 않는다 — 특히 가짜 큐를 주입해 기본 CeleryJobQueue가 broker에 닿는 것을 막는다
(hermeticity: 큐 미주입 시 QUALITY 경로가 라이브 Redis로 ~20초 블록됨).

인가(SEC-07 D1): `/v1/generate`는 이제 `CurrentUser`(인증만) 게이트가 있다. 이 파일의
대부분 테스트는 라우팅/캐시/큐 *결선*이 목적이라 `_client()`가 `get_current_user`를 고정
인증 사용자로 오버라이드한다(test_concepts.py의 `require_content_admin` 오버라이드 패턴과
동형) — 인증 자체(무토큰 401)는 `TestGenerateAuthGate`가 오버라이드 없이 검증한다.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_current_user
from whymath_backend.app import create_app
from whymath_backend.config import get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l3.providers.anthropic import AnthropicStatus
from whymath_backend.l3.providers.ollama import ModelAvailability, OllamaStatus
from whymath_backend.l3.queue.celery_job_queue import JobStatus

_FAKE_USER = UserProfile(user_id=uuid.uuid4())


class StubProvider:
    """가짜 LLMProvider + check_status — 앱 결선 검증용."""

    def __init__(
        self,
        *,
        text: str = "원시출력",
        status: OllamaStatus | None = None,
    ) -> None:
        self._text = text
        self._status = status
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.calls.append((prompt, system, decision))
        return GenerationResult(self._text)

    async def check_status(self) -> OllamaStatus:
        if self._status is not None:
            return self._status
        return OllamaStatus(reachable=True, models=())


class StubCompositeProvider:
    """가짜 복합 provider — check_status(로컬) + check_cloud_status(클라우드) 노출.

    /status 클라우드 필드 매핑(S5)을 검증하기 위해 CompositeProvider 표면만 모사한다.
    """

    def __init__(
        self,
        *,
        ollama_status: OllamaStatus,
        cloud_status: AnthropicStatus | None,
    ) -> None:
        self._ollama_status = ollama_status
        self._cloud_status = cloud_status

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult("")

    async def check_status(self) -> OllamaStatus:
        return self._ollama_status

    async def check_cloud_status(self) -> AnthropicStatus | None:
        return self._cloud_status


class StubQueue:
    """가짜 AsyncJobQueue + result — 앱 결선 검증용(broker 없음).

    enqueue는 정해진 job_id를 돌려주고(또는 raises로 broker 다운 모사), result는 등록한
    JobStatus를 돌려준다(폴링 모사). result_supported=False면 result 메서드를 제거해
    '폴링 미지원 큐' 분기(/v1/jobs unknown)를 검증할 수 있다.
    """

    def __init__(
        self,
        *,
        job_id: str = "job-1",
        enqueue_raises: Exception | None = None,
        statuses: dict[str, JobStatus] | None = None,
    ) -> None:
        self._job_id = job_id
        self._enqueue_raises = enqueue_raises
        self._statuses = statuses or {}
        self.payloads: list[dict[str, object]] = []

    async def enqueue(self, payload: dict[str, object]) -> str:
        self.payloads.append(payload)
        if self._enqueue_raises is not None:
            raise self._enqueue_raises
        return self._job_id

    def result(self, job_id: str) -> JobStatus:
        return self._statuses.get(job_id, JobStatus(job_id=job_id, state="pending"))


class NoPollQueue:
    """result 메서드가 없는 가짜 큐 — /v1/jobs 폴링 미지원 분기 검증용."""

    async def enqueue(self, payload: dict[str, object]) -> str:
        return "job-x"


def _client(provider: StubProvider, queue: Any | None = None) -> TestClient:
    """provider/cache/trace/queue를 가짜로, get_current_user를 고정 인증 사용자로 오버라이드."""
    app = create_app(
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        # 기본적으로 가짜 큐 주입 — 라이브 broker 차단(hermetic).
        queue=queue if queue is not None else StubQueue(),
    )
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    return TestClient(app)


class TestHealth:
    def test_health_ok(self) -> None:
        """/health는 의존성 없이 200 ok."""
        client = _client(StubProvider())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestStatus:
    def test_status_reachable_all_present(self) -> None:
        """모든 모델 설치 시 ready=true, reachable=true."""
        status = OllamaStatus(
            reachable=True,
            models=(
                ModelAvailability("qwen2-math:1.5b", True),
                ModelAvailability("qwen3.5:27b", True),
            ),
        )
        client = _client(StubProvider(status=status))
        resp = client.get("/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["reachable"] is True
        assert body["missing"] == []

    def test_status_unreachable_reports_not_ready(self) -> None:
        """Ollama 불가 시에도 500이 아니라 200 + ready=false 보고."""
        status = OllamaStatus(
            reachable=False,
            models=(ModelAvailability("qwen2-math:1.5b", False),),
            error="ConnectionError: refused",
        )
        client = _client(StubProvider(status=status))
        resp = client.get("/status")
        assert resp.status_code == 200  # 비크래시
        body = resp.json()
        assert body["ready"] is False
        assert body["reachable"] is False
        assert body["error"] is not None
        assert "qwen2-math:1.5b" in body["missing"]

    def test_status_provider_without_check_method_reports_unreachable(self) -> None:
        """check_status가 없는 provider(가짜)를 주입하면 도달 불가로 보고(500 아님)."""

        class NoStatusProvider:
            async def generate(
                self, prompt: str, system: str, decision: RoutingDecision
            ) -> GenerationResult:
                return GenerationResult("")

        app = create_app(
            provider=NoStatusProvider(),
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
        )
        resp = TestClient(app).get("/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is False
        assert body["reachable"] is False
        assert body["error"] is not None

    def test_status_missing_some_models(self) -> None:
        """일부 모델 누락 시 ready=false + missing 채워짐."""
        status = OllamaStatus(
            reachable=True,
            models=(
                ModelAvailability("qwen2-math:1.5b", True),
                ModelAvailability("qwen3.5:27b", False),
            ),
        )
        client = _client(StubProvider(status=status))
        body = client.get("/status").json()
        assert body["ready"] is False
        assert body["reachable"] is True
        assert body["missing"] == ["qwen3.5:27b"]

    def test_status_includes_cloud_when_provider_exposes_it(self) -> None:
        """CompositeProvider 표면(check_cloud_status) → /status에 cloud_* 필드가 채워진다(S5)."""
        provider = StubCompositeProvider(
            ollama_status=OllamaStatus(
                reachable=True, models=(ModelAvailability("qwen2-math:1.5b", True),)
            ),
            cloud_status=AnthropicStatus(configured=True, reachable=True),
        )
        app = create_app(
            provider=provider,
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
            queue=StubQueue(),
        )
        body = TestClient(app).get("/status").json()
        assert body["cloud_configured"] is True
        assert body["cloud_reachable"] is True
        assert body["cloud_error"] is None
        assert body["reachable"] is True  # 로컬 필드는 그대로 보고

    def test_status_cloud_unconfigured_reports_false(self) -> None:
        """클라우드 키 미설정 → cloud_configured=False, cloud_reachable=False(비크래시)."""
        provider = StubCompositeProvider(
            ollama_status=OllamaStatus(reachable=True, models=()),
            cloud_status=AnthropicStatus(configured=False, reachable=False, error=None),
        )
        app = create_app(
            provider=provider,
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
            queue=StubQueue(),
        )
        body = TestClient(app).get("/status").json()
        assert body["cloud_configured"] is False
        assert body["cloud_reachable"] is False

    def test_status_cloud_fields_none_when_provider_lacks_cloud_check(self) -> None:
        """check_cloud_status 미노출 provider(로컬전용·가짜) → cloud_* 필드 None(기존 호환)."""
        client = _client(StubProvider(status=OllamaStatus(reachable=True, models=())))
        body = client.get("/status").json()
        assert body["cloud_configured"] is None
        assert body["cloud_reachable"] is None
        assert body["cloud_error"] is None


class TestGenerateEndpoint:
    def test_generate_happy_path_local(self) -> None:
        """LOCAL 동기 경로 → 200 + 텍스트 + 결정 메타데이터."""
        provider = StubProvider(text="생성결과")
        client = _client(provider)
        payload = {
            "request": {
                "task_type": "explain",
                "difficulty": "easy",
                "requires_reasoning": False,
                "student_subscription": "free",
                "sync": True,
            },
            "prompt": "이차방정식이 뭐야?",
            "system": "너는 수학 코치다",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "생성결과"
        assert body["cache_hit"] is False
        # 결정 메타데이터 노출 (use_enum_values=True → 문자열)
        assert body["decision"]["cost_tier"] == "local"
        assert body["decision"]["mode"] == "sync"
        assert len(provider.calls) == 1
        # 환각 없는 출력 → shadow 검증 신호 None(필드 노출 확인).
        assert body["validation_signal"] is None

    def test_generate_surfaces_shadow_validation_signal(self) -> None:
        """거짓 수치 관계 생성물 → validation_signal에 사유 노출(비차단·텍스트 불변)."""
        provider = StubProvider(text="계산:\n2 + 2 = 5")
        client = _client(provider)
        payload = {
            "request": {
                "task_type": "explain",
                "difficulty": "easy",
                "requires_reasoning": False,
                "student_subscription": "free",
                "sync": True,
            },
            "prompt": "p",
            "system": "s",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        # 비차단: 원시 텍스트 그대로 반환.
        assert body["text"] == "계산:\n2 + 2 = 5"
        # shadow 검증 신호가 응답에 노출(조용히 넘어가지 않음).
        assert body["validation_signal"] is not None
        assert "arithmetic error" in body["validation_signal"]

    def test_generate_shadow_disabled_via_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings 게이트 off → 거짓 산술이어도 validation_signal=None(검증 미실행)."""
        monkeypatch.setenv("WHYMATH_L3_SHADOW_VALIDATION_ENABLED", "false")
        get_settings.cache_clear()
        try:
            provider = StubProvider(text="2 + 2 = 5")
            client = _client(provider)
            payload = {
                "request": {
                    "task_type": "explain",
                    "difficulty": "easy",
                    "requires_reasoning": False,
                    "student_subscription": "free",
                    "sync": True,
                },
                "prompt": "p",
                "system": "s",
            }
            body = client.post("/v1/generate", json=payload).json()
            # 비차단 동일: 텍스트는 원시 그대로. 단, 검증 비활성이라 신호 없음.
            assert body["text"] == "2 + 2 = 5"
            assert body["validation_signal"] is None
        finally:
            get_settings.cache_clear()  # 다음 테스트로 게이트 상태 누수 방지.

    def test_skip_cache_on_signal_via_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """l3_skip_cache_on_signal=on → 거짓 산술은 캐시 미적재(재요청 시 재생성)."""
        monkeypatch.setenv("WHYMATH_L3_SKIP_CACHE_ON_SIGNAL", "true")
        get_settings.cache_clear()
        try:
            provider = StubProvider(text="계산:\n2 + 2 = 5")
            client = _client(provider)
            payload = {
                "request": {
                    "task_type": "explain",
                    "difficulty": "easy",
                    "requires_reasoning": False,
                    "student_subscription": "free",
                    "sync": True,
                },
                "prompt": "p",
                "system": "s",
            }
            first = client.post("/v1/generate", json=payload).json()
            second = client.post("/v1/generate", json=payload).json()
            # 신호 노출은 그대로(비차단). 그러나 거짓이라 캐시에 안 남아 2회차도 미스·재호출.
            assert first["validation_signal"] is not None
            assert second["cache_hit"] is False
            assert len(provider.calls) == 2  # 캐시 위생 → 재생성
        finally:
            get_settings.cache_clear()

    def test_skip_cache_default_off_caches_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """기본(skip off) → 거짓 산술도 캐시 적재(2회차 히트·기존 동작)."""
        get_settings.cache_clear()  # 환경 기본값(off) 확정.
        try:
            provider = StubProvider(text="계산:\n2 + 2 = 5")
            client = _client(provider)
            payload = {
                "request": {
                    "task_type": "explain",
                    "difficulty": "easy",
                    "requires_reasoning": False,
                    "student_subscription": "free",
                    "sync": True,
                },
                "prompt": "p",
                "system": "s",
            }
            client.post("/v1/generate", json=payload)
            second = client.post("/v1/generate", json=payload).json()
            assert second["cache_hit"] is True  # 적재됨(기본 동작)
            assert len(provider.calls) == 1
        finally:
            get_settings.cache_clear()

    def test_generate_cache_hit_on_second_call(self) -> None:
        """동일 요청 2회 → 2회차 cache_hit=true(같은 앱 인스턴스 캐시 공유)."""
        provider = StubProvider(text="동일")
        client = _client(provider)
        payload = {
            "request": {
                "task_type": "explain",
                "difficulty": "easy",
                "requires_reasoning": False,
                "student_subscription": "free",
                "sync": True,
            },
            "prompt": "p",
            "system": "s",
        }
        first = client.post("/v1/generate", json=payload).json()
        second = client.post("/v1/generate", json=payload).json()
        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert len(provider.calls) == 1  # 2회차는 캐시

    def test_generate_quality_returns_202_with_job_id(self) -> None:
        """QUALITY(자기검증, 비동기) → 동기 호출 대신 202 Accepted + job_id(폴링 안내).

        S4 계약 변경: 기존엔 503(큐 미구현)이었으나, 이제 작업 큐에 적재하고 202로
        job_id를 돌려준다(03a §D.3). provider는 동기 호출되지 않는다.
        """
        provider = StubProvider()
        queue = StubQueue(job_id="job-quality-1")
        client = _client(provider, queue=queue)
        payload = {
            "request": {
                "task_type": "self_verify",
                "difficulty": "hard",
                "requires_reasoning": True,
                "student_subscription": "free",
                "sync": False,
                "call_site": "self_verify",
            },
            "prompt": "검증해줘",
            "system": "",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 202
        body = resp.json()
        assert body["job_id"] == "job-quality-1"
        assert body["status"] == "queued"
        assert body["decision"]["mode"] == "async"
        assert body["decision"]["local_model"] == "quality"
        assert provider.calls == []  # 동기 호출 금지
        assert len(queue.payloads) == 1  # enqueue 1회

    def test_generate_quality_503_when_queue_unavailable(self) -> None:
        """enqueue 실패(broker 다운) → 503 JSON(스택트레이스 X, 가용성 우선)."""
        provider = StubProvider()
        queue = StubQueue(enqueue_raises=ConnectionError("broker refused"))
        client = _client(provider, queue=queue)
        payload = {
            "request": {
                "task_type": "self_verify",
                "difficulty": "hard",
                "requires_reasoning": True,
                "student_subscription": "free",
                "sync": False,
                "call_site": "self_verify",
            },
            "prompt": "검증해줘",
            "system": "",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"] == "quality_queue_unavailable"
        assert provider.calls == []  # provider 미호출

    def test_generate_rejects_unknown_request_field(self) -> None:
        """RoutingRequest는 extra=forbid → 알 수 없는 필드는 422."""
        client = _client(StubProvider())
        payload = {
            "request": {
                "task_type": "explain",
                "difficulty": "easy",
                "requires_reasoning": False,
                "student_subscription": "free",
                "sync": True,
                "bogus_field": 1,
            },
            "prompt": "p",
            "system": "s",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 422


class TestGenerateAuthGate:
    """SEC-07 D1 — `/v1/generate` 인가 회귀(오버라이드 없는 *실제* `get_current_user`).

    이전엔 인증 의존성이 0건이라 무인증 LLM 비용 남용 표면이었다(`docs/architecture/
    account_security_gap_review.md` D1). `CurrentUser`(인증만 — 역할 불문)로 게이팅한다.
    """

    def test_unauthenticated_post_returns_401(self) -> None:
        app = create_app(
            provider=StubProvider(),
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
            queue=StubQueue(),
        )

        # get_session은 get_current_user의 형제 의존성이라 무토큰이어도 FastAPI가 먼저
        # 해석을 시도한다 — 가짜로 오버라이드해 실 DB 엔진 진입을 막는다(전역 누수 가드
        # OPS-07 회피, api/test_ocr_endpoint.py 선례). credentials=None이면 get_current_user가
        # session을 실제로 쓰기 전에 401을 던지므로 더미 객체만 yield하면 충분하다.
        async def _fake_session() -> Any:
            yield object()

        app.dependency_overrides[get_session] = _fake_session
        client = TestClient(app)
        payload = {
            "request": {
                "task_type": "explain",
                "difficulty": "easy",
                "requires_reasoning": False,
                "student_subscription": "free",
                "sync": True,
            },
            "prompt": "p",
            "system": "s",
        }
        resp = client.post("/v1/generate", json=payload)
        assert resp.status_code == 401


class TestJobsEndpoint:
    """GET /v1/jobs/{job_id} — QUALITY 비동기 작업 폴링 (S4)."""

    def test_job_pending_returns_200(self) -> None:
        """진행 중(pending) → 200 + state=pending, text 없음."""
        queue = StubQueue(statuses={"j1": JobStatus(job_id="j1", state="pending")})
        client = _client(StubProvider(), queue=queue)
        resp = client.get("/v1/jobs/j1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "j1"
        assert body["state"] == "pending"
        assert body["text"] is None

    def test_job_success_returns_text(self) -> None:
        """완료(success) → 200 + text(검증 전 원시 출력). 환각 없으면 신호 None."""
        queue = StubQueue(statuses={"j2": JobStatus(job_id="j2", state="success", text="27b 결과")})
        client = _client(StubProvider(), queue=queue)
        resp = client.get("/v1/jobs/j2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "success"
        assert body["text"] == "27b 결과"
        assert body["error"] is None
        assert body["validation_signal"] is None

    def test_job_success_surfaces_shadow_signal(self) -> None:
        """완료 텍스트에 거짓 산술 → 폴링 응답이 validation_signal 노출(동기 파리티·재검증)."""
        queue = StubQueue(
            statuses={"j2x": JobStatus(job_id="j2x", state="success", text="결과:\n2 + 2 = 5")}
        )
        client = _client(StubProvider(), queue=queue)
        body = client.get("/v1/jobs/j2x").json()
        assert body["state"] == "success"
        assert body["text"] == "결과:\n2 + 2 = 5"  # 비차단·텍스트 불변
        assert body["validation_signal"] is not None
        assert "arithmetic error" in body["validation_signal"]

    def test_job_pending_has_no_signal(self) -> None:
        """미완료(pending)는 텍스트가 없어 validation_signal None(재검증 안 함)."""
        queue = StubQueue(statuses={"j5": JobStatus(job_id="j5", state="pending")})
        client = _client(StubProvider(), queue=queue)
        body = client.get("/v1/jobs/j5").json()
        assert body["validation_signal"] is None

    def test_job_signal_none_when_shadow_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings 게이트 off → 완료 텍스트가 거짓이어도 재검증 안 함(신호 None)."""
        monkeypatch.setenv("WHYMATH_L3_SHADOW_VALIDATION_ENABLED", "false")
        get_settings.cache_clear()
        try:
            queue = StubQueue(
                statuses={"j6": JobStatus(job_id="j6", state="success", text="결과:\n2 + 2 = 5")}
            )
            client = _client(StubProvider(), queue=queue)
            body = client.get("/v1/jobs/j6").json()
            assert body["text"] == "결과:\n2 + 2 = 5"
            assert body["validation_signal"] is None
        finally:
            get_settings.cache_clear()

    def test_job_failure_returns_error_not_500(self) -> None:
        """실패(failure) → 200 + state=failure + error(사유), 500 스택트레이스 아님."""
        queue = StubQueue(
            statuses={"j3": JobStatus(job_id="j3", state="failure", error="모델 오류")}
        )
        client = _client(StubProvider(), queue=queue)
        resp = client.get("/v1/jobs/j3")
        assert resp.status_code == 200  # 비크래시
        body = resp.json()
        assert body["state"] == "failure"
        assert body["error"] == "모델 오류"
        assert body["text"] is None

    def test_job_unknown_state_returns_200(self) -> None:
        """판정 불가(unknown — backend 미도달 흡수) → 200 + state=unknown."""
        queue = StubQueue(
            statuses={"j4": JobStatus(job_id="j4", state="unknown", error="backend down")}
        )
        client = _client(StubProvider(), queue=queue)
        resp = client.get("/v1/jobs/j4")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "unknown"
        assert body["error"] is not None

    def test_job_unknown_id_defaults_pending(self) -> None:
        """등록 안 된 job_id는 가짜 큐 기본(pending)으로 — 200 비크래시."""
        client = _client(StubProvider(), queue=StubQueue())
        resp = client.get("/v1/jobs/never-seen")
        assert resp.status_code == 200
        assert resp.json()["state"] == "pending"

    def test_job_queue_without_result_method_reports_unknown(self) -> None:
        """result()가 없는 큐(폴링 미지원) → unknown 보고(500 아님 — 기능 탐지)."""
        client = _client(StubProvider(), queue=NoPollQueue())
        resp = client.get("/v1/jobs/whatever")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "unknown"
        assert body["error"] is not None


def test_create_app_defaults_are_real_implementations() -> None:
    """기본 팩토리(주입 없음)는 CompositeProvider(Ollama+Anthropic, S5)
    +RedisCache(S2)+LangfuseSink(S3)+CeleryJobQueue(S4)를 단다.

    S2에서 기본 캐시가 InMemoryCache → RedisCache로, S3에서 기본 트레이스가
    RecordingTraceSink → LangfuseSink로, S4에서 기본 큐가 CeleryJobQueue로, S5에서 기본
    provider가 OllamaProvider → CompositeProvider(local=Ollama, cloud=Anthropic)로 바뀌었다.
    모두 *지연*이라 isinstance 확인만으로는 라이브 Redis·Langfuse·Celery broker·Anthropic
    키가 필요 없다(첫 사용 전엔 클라이언트/앱을 만들지 않음) → 이 단정은 hermetic하다.
    동작을 타는 테스트는 위 _client()가 가짜 의존성을 주입해 라이브 의존을 피한다.
    """
    from whymath_backend.app import _CACHE_KEY, _PROVIDER_KEY, _QUEUE_KEY, _TRACE_KEY
    from whymath_backend.l3.cache import RedisCache as _RC  # noqa: N814
    from whymath_backend.l3.providers.anthropic import AnthropicProvider as _AP  # noqa: N814
    from whymath_backend.l3.providers.composite import CompositeProvider as _CP  # noqa: N814
    from whymath_backend.l3.providers.ollama import OllamaProvider as _OP  # noqa: N814
    from whymath_backend.l3.queue import CeleryJobQueue as _CJQ  # noqa: N814
    from whymath_backend.l3.trace import LangfuseSink as _LFS  # noqa: N814

    app = create_app()
    composite = getattr(app.state, _PROVIDER_KEY)
    assert isinstance(composite, _CP)
    # 기본 복합 provider는 로컬=Ollama, 클라우드=Anthropic을 단다(S5 디스패치).
    assert isinstance(composite._local, _OP)
    assert isinstance(composite._cloud, _AP)
    assert isinstance(getattr(app.state, _CACHE_KEY), _RC)
    assert isinstance(getattr(app.state, _TRACE_KEY), _LFS)
    assert isinstance(getattr(app.state, _QUEUE_KEY), _CJQ)
    # CI hermetic 보강: 기본 LangfuseSink는 키 미설정 시 비활성(전송 X)이어야 한다.
    # (단, 환경에 WHYMATH_LANGFUSE_* 키가 실제로 있으면 활성일 수 있어 단정은 조건부.)
    from whymath_backend.config import Settings

    if not Settings().langfuse_configured:
        assert getattr(app.state, _TRACE_KEY).configured is False
