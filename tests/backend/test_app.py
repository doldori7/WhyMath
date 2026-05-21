"""FastAPI 앱 단위테스트 — TestClient + 가짜 의존성 주입 (라이브 서비스 없음).

/health·/status(도달 가능/불가)·/v1/generate(정상·QUALITY 차단)를 검증한다.
실제 Ollama·Redis·Langfuse에 의존하지 않는다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whymath_backend.app import create_app
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.l3.providers.ollama import ModelAvailability, OllamaStatus


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
    ) -> str:
        self.calls.append((prompt, system, decision))
        return self._text

    async def check_status(self) -> OllamaStatus:
        if self._status is not None:
            return self._status
        return OllamaStatus(reachable=True, models=())


def _client(provider: StubProvider) -> TestClient:
    app = create_app(
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
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
            ) -> str:
                return ""

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

    def test_generate_quality_blocked_returns_503(self) -> None:
        """QUALITY(자기검증, 비동기)는 동기 호출 불가 → 503 JSON(스택트레이스 X)."""
        provider = StubProvider()
        client = _client(provider)
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
        assert "S4" in body["detail"]
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


def test_create_app_defaults_are_real_implementations() -> None:
    """기본 팩토리(주입 없음)는 OllamaProvider + RedisCache(S2) + 트레이스 스텁을 단다.

    S2에서 기본 캐시가 InMemoryCache → RedisCache로 바뀌었다. RedisCache는 *지연
    연결*이라 isinstance 확인만으로는 라이브 Redis가 필요 없다(첫 캐시 접근 전엔
    클라이언트를 만들지 않음) → 이 단정은 hermetic하다. 캐시 *동작*을 타는 테스트는
    위 _client()가 InMemoryCache를 주입해 라이브 Redis를 피한다.
    """
    from whymath_backend.app import _CACHE_KEY, _PROVIDER_KEY, _TRACE_KEY
    from whymath_backend.l3.cache import RedisCache as _RC
    from whymath_backend.l3.interfaces import RecordingTraceSink as _RTS
    from whymath_backend.l3.providers.ollama import OllamaProvider as _OP

    app = create_app()
    assert isinstance(getattr(app.state, _PROVIDER_KEY), _OP)
    assert isinstance(getattr(app.state, _CACHE_KEY), _RC)
    assert isinstance(getattr(app.state, _TRACE_KEY), _RTS)
