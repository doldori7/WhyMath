"""Settings 단위테스트 — 환경변수 주입·캐시 동작 (시크릿 하드코딩 금지 확인)."""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings, get_settings


def test_defaults_are_harmless_local() -> None:
    """기본값은 무해한 로컬 루프백 — 코드에 호스트/시크릿 하드코딩 없음."""
    s = Settings()
    assert s.ollama_host == "http://127.0.0.1:11434"
    assert s.ollama_request_timeout_s > 0
    assert s.cache_ttl_s >= 0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """WHYMATH_ 접두사 환경변수로 값이 덮어써진다."""
    monkeypatch.setenv("WHYMATH_OLLAMA_HOST", "http://phaiakes9.local:11434")
    monkeypatch.setenv("WHYMATH_OLLAMA_REQUEST_TIMEOUT_S", "5.5")
    s = Settings()
    assert s.ollama_host == "http://phaiakes9.local:11434"
    assert s.ollama_request_timeout_s == 5.5


def test_get_settings_is_cached() -> None:
    """get_settings()는 같은 인스턴스를 재사용(lru_cache)."""
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b
    get_settings.cache_clear()


def test_unknown_env_keys_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """다른 슬라이스(DB·결제)의 환경변수가 있어도 무시하고 깨지지 않는다."""
    monkeypatch.setenv("WHYMATH_SOME_FUTURE_DB_URL", "postgres://x")
    s = Settings()  # extra=ignore → 예외 없이 생성
    assert s.ollama_host  # 정상 로드
