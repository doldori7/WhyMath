"""Settings(config.py) 단위 테스트 — 기본값·env override·싱글톤 캐시.

설계 정본: docs/architecture/03a_l3_router_design.md §A.1(CLOUD 모델 풀)·§F.1(캐시 TTL).
범위 메모(M1.2): 라이브 서비스 없이 *환경설정 로딩*만 검증한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings, get_settings


class TestDefaults:
    def test_default_values(self) -> None:
        """env 미설정 시 명세된 기본값을 갖는다 (시크릿은 None)."""
        s = Settings()
        assert s.ollama_host == "http://127.0.0.1:11434"
        assert s.anthropic_api_key is None
        assert s.cloud_mid_model == "claude-sonnet-4-6"  # 03a §A.1 CLOUD_MID=Sonnet
        assert s.cloud_high_model == "claude-opus-4-7"  # 03a §A.1 CLOUD_HIGH=Opus
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.langfuse_public_key is None
        assert s.langfuse_secret_key is None
        assert s.langfuse_host == "https://cloud.langfuse.com"
        assert s.cache_ttl_seconds == 86400  # 24h, 03a §F.1


class TestEnvOverride:
    def test_env_prefix_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WHYMATH_ 접두사 env가 필드를 덮어쓴다 (벤치마크와 동일 컨벤션)."""
        monkeypatch.setenv("WHYMATH_OLLAMA_HOST", "http://gpu-box:11434")
        monkeypatch.setenv("WHYMATH_ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("WHYMATH_REDIS_URL", "redis://cache:6380/2")
        monkeypatch.setenv("WHYMATH_CACHE_TTL_SECONDS", "3600")
        s = Settings()
        assert s.ollama_host == "http://gpu-box:11434"
        assert s.anthropic_api_key == "sk-test-123"
        assert s.redis_url == "redis://cache:6380/2"
        assert s.cache_ttl_seconds == 3600

    def test_cloud_models_overridable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """클라우드 모델 ID도 env로 교체 가능(모델 버전 업 시 코드 수정 불필요)."""
        monkeypatch.setenv("WHYMATH_CLOUD_MID_MODEL", "claude-sonnet-9-9")
        monkeypatch.setenv("WHYMATH_CLOUD_HIGH_MODEL", "claude-opus-9-9")
        s = Settings()
        assert s.cloud_mid_model == "claude-sonnet-9-9"
        assert s.cloud_high_model == "claude-opus-9-9"

    def test_langfuse_keys_overridable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Langfuse 키·호스트 override (03a §F.2 관측성)."""
        monkeypatch.setenv("WHYMATH_LANGFUSE_PUBLIC_KEY", "pk-1")
        monkeypatch.setenv("WHYMATH_LANGFUSE_SECRET_KEY", "sk-1")
        monkeypatch.setenv("WHYMATH_LANGFUSE_HOST", "https://lf.internal")
        s = Settings()
        assert s.langfuse_public_key == "pk-1"
        assert s.langfuse_secret_key == "sk-1"
        assert s.langfuse_host == "https://lf.internal"

    def test_unknown_env_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """모르는 WHYMATH_* env(예: 벤치 도구의 WHYMATH_BENCH_*)로 죽지 않는다(extra=ignore)."""
        monkeypatch.setenv("WHYMATH_BENCH_MODEL", "qwen2-math:7b")
        monkeypatch.setenv("WHYMATH_SOMETHING_UNRELATED", "x")
        s = Settings()  # 예외 없이 생성되어야 한다
        assert s.ollama_host == "http://127.0.0.1:11434"


class TestSingleton:
    def test_get_settings_cached(self) -> None:
        """get_settings()는 동일 인스턴스를 재사용한다(lru_cache 싱글톤)."""
        get_settings.cache_clear()
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_cache_clear_reloads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """cache_clear() 후 재호출은 env를 다시 읽는다(테스트 격리 보장)."""
        get_settings.cache_clear()
        monkeypatch.setenv("WHYMATH_OLLAMA_HOST", "http://first:11434")
        first = get_settings()
        assert first.ollama_host == "http://first:11434"

        get_settings.cache_clear()
        monkeypatch.setenv("WHYMATH_OLLAMA_HOST", "http://second:11434")
        second = get_settings()
        assert second.ollama_host == "http://second:11434"
        assert first is not second
        # 다른 테스트 오염 방지
        get_settings.cache_clear()
