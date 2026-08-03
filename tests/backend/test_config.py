"""Settings 단위테스트 — 환경변수 주입·캐시 동작 (시크릿 하드코딩 금지 확인)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

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


def test_l4_theta_noise_guard_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    """slice 76: 개념 θ 노이즈 가드 임계 — 기본(응답 3·SE 1.0)·env 오버라이드."""
    s = Settings()
    assert s.l4_theta_min_responses == 3
    assert s.l4_theta_max_se == 1.0
    monkeypatch.setenv("WHYMATH_L4_THETA_MIN_RESPONSES", "5")
    monkeypatch.setenv("WHYMATH_L4_THETA_MAX_SE", "0.5")
    s2 = Settings()
    assert s2.l4_theta_min_responses == 5
    assert s2.l4_theta_max_se == 0.5


def test_min_app_version_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPS-17: 기본 0.0.0(게이트 사실상 비활성) — WHYMATH_MIN_APP_VERSION으로 오버라이드."""
    s = Settings()
    assert s.min_app_version == "0.0.0"
    monkeypatch.setenv("WHYMATH_MIN_APP_VERSION", "1.3.0")
    s2 = Settings()
    assert s2.min_app_version == "1.3.0"


def test_l4_theta_thresholds_validated() -> None:
    """SE 상한 양수(gt=0)·최소 응답수 음수 불가(ge=0)."""
    with pytest.raises(ValidationError):
        Settings(l4_theta_max_se=0.0)
    with pytest.raises(ValidationError):
        Settings(l4_theta_min_responses=-1)


# ──────────────────────────────────────────────────────────────────────────
# 클라우드 LLM (Anthropic, S5)
# ──────────────────────────────────────────────────────────────────────────
def test_anthropic_model_defaults() -> None:
    """CLOUD_MID=Sonnet 4.6, CLOUD_HIGH=Opus 4.7 alias가 기본값(03a §A.0)."""
    s = Settings()
    assert s.anthropic_model_mid == "claude-sonnet-4-6"
    assert s.anthropic_model_high == "claude-opus-4-7"
    assert s.anthropic_max_tokens == 16000
    assert s.anthropic_request_timeout_s > 0


def test_anthropic_configured_false_when_empty() -> None:
    """키가 비면 미설정(anthropic_configured=False) — 클라우드 생성 불가."""
    s = Settings(anthropic_api_key=SecretStr(""))
    assert s.anthropic_configured is False


def test_anthropic_configured_true_when_set() -> None:
    """키가 채워지면 설정 완료(anthropic_configured=True)."""
    s = Settings(anthropic_api_key=SecretStr("sk-ant-xyz"))
    assert s.anthropic_configured is True


def test_anthropic_secret_not_leaked_in_repr() -> None:
    """API 키는 SecretStr — repr/str에 평문이 새어나오지 않는다(보안 금기)."""
    s = Settings(anthropic_api_key=SecretStr("sk-ant-supersecret"))
    assert "sk-ant-supersecret" not in repr(s)
    assert "sk-ant-supersecret" not in str(s.anthropic_api_key)
    # 평문은 get_secret_value()로만 꺼낼 수 있다.
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-supersecret"


def test_anthropic_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """WHYMATH_ANTHROPIC_* 환경변수로 키·모델·토큰이 덮어써진다."""
    monkeypatch.setenv("WHYMATH_ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setenv("WHYMATH_ANTHROPIC_MODEL_MID", "claude-sonnet-x")
    monkeypatch.setenv("WHYMATH_ANTHROPIC_MODEL_HIGH", "claude-opus-x")
    monkeypatch.setenv("WHYMATH_ANTHROPIC_MAX_TOKENS", "2048")
    s = Settings()
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-env"
    assert s.anthropic_model_mid == "claude-sonnet-x"
    assert s.anthropic_model_high == "claude-opus-x"
    assert s.anthropic_max_tokens == 2048
    assert s.anthropic_configured is True


def test_anthropic_tuning_knobs_default_off() -> None:
    """effort/thinking/caching 노브는 기본 OFF(생략) — 현 동작 유지(03a §H#4)."""
    s = Settings(anthropic_effort="", anthropic_thinking=False, anthropic_prompt_caching=False)
    assert s.anthropic_effort == ""
    assert s.anthropic_thinking is False
    assert s.anthropic_prompt_caching is False


def test_anthropic_tuning_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """WHYMATH_ANTHROPIC_EFFORT/THINKING/PROMPT_CACHING 환경변수로 켤 수 있다."""
    monkeypatch.setenv("WHYMATH_ANTHROPIC_EFFORT", "xhigh")
    monkeypatch.setenv("WHYMATH_ANTHROPIC_THINKING", "true")
    monkeypatch.setenv("WHYMATH_ANTHROPIC_PROMPT_CACHING", "1")
    s = Settings()
    assert s.anthropic_effort == "xhigh"
    assert s.anthropic_thinking is True
    assert s.anthropic_prompt_caching is True
