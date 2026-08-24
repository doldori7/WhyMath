"""OpenRouter 클라우드 LLM 제공자 — interfaces.LLMProvider 구현 (S4-16 reference run).

OpenRouter는 OpenAI-compatible API를 제공한다. 이 제공자는 OpenRouter를 경유해 다양한
클라우드 모델(GPT-5.6, Gemini, DeepSeek 등)을 호출할 수 있는 *확장 경로*다. 현재는 S4-16
강등전의 reference run 용도로 도입하며, 라우터의 CLOUD_MID/CLOUD_HIGH 결정을 수용한다.

설계 정본: `docs/architecture/03a_l3_router_design.md` §H 후속 4("클라우드 티어 실제 연동").
AnthropicProvider의 지연 import·주입 가능·비밀 처리 패턴을 미러링한다.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision, Usage
from whymath_backend.l3.router import _as_cost_tier


@runtime_checkable
class _Completions(Protocol):
    """OpenAI client.chat.completions의 최소 인터페이스."""

    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        ...


@runtime_checkable
class _Chat(Protocol):
    """OpenAI client.chat 인터페이스."""

    completions: _Completions


@runtime_checkable
class _OpenAIClient(Protocol):
    """openai.AsyncOpenAI의 최소 인터페이스 (구조적 타이핑)."""

    chat: _Chat


@dataclass(slots=True, frozen=True)
class OpenRouterStatus:
    """OpenRouter 준비 상태 보고."""

    configured: bool
    reachable: bool
    error: str | None = None


_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL_ID = "openai/gpt-5.6-sol"


def _extract_text(response: Any) -> str:
    """OpenAI chat.completions 응답에서 텍스트를 추출."""
    choices = _read_field(response, "choices")
    if not isinstance(choices, Sequence) or not choices:
        return ""
    first = choices[0]
    message = _read_field(first, "message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, str):
            return content
    return ""


def _read_field(response: Any, name: str) -> Any:
    """응답 객체 또는 dict에서 필드값을 방어적으로 읽는다."""
    if hasattr(response, name):
        return getattr(response, name)
    if isinstance(response, dict):
        return response.get(name)
    return None


def _extract_usage(response: Any, latency_ms: float) -> Usage:
    """응답 usage에서 토큰 수를 추출."""
    raw_usage = _read_field(response, "usage")
    input_tokens: int | None = None
    output_tokens: int | None = None
    if raw_usage is not None:
        if hasattr(raw_usage, "prompt_tokens"):
            input_tokens = _coerce_token_count(raw_usage.prompt_tokens)
        elif isinstance(raw_usage, dict):
            input_tokens = _coerce_token_count(raw_usage.get("prompt_tokens"))
        if hasattr(raw_usage, "completion_tokens"):
            output_tokens = _coerce_token_count(raw_usage.completion_tokens)
        elif isinstance(raw_usage, dict):
            output_tokens = _coerce_token_count(raw_usage.get("completion_tokens"))
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms)


def _coerce_token_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _build_default_client(settings: Settings) -> _OpenAIClient:
    """OpenAI SDK로 OpenRouter 클라이언트 생성."""
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "openai Python 클라이언트가 설치되지 않았습니다. "
            "`pip install openai` 후 다시 시도하세요."
        ) from exc
    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url or _DEFAULT_BASE_URL,
        api_key=settings.openrouter_api_key.get_secret_value(),
        timeout=settings.openrouter_request_timeout_s,
    )
    return cast(_OpenAIClient, client)


class OpenRouterProvider:
    """OpenRouter 경유 클라우드 LLM 제공자.

    모델 ID는 `settings.openrouter_model_id`에서 읽거나 인자로 주입한다. 라우터의
    CLOUD_MID/CLOUD_HIGH 결정을 수용하고, LOCAL은 거부한다.
    """

    def __init__(
        self,
        *,
        client: _OpenAIClient | None = None,
        settings: Settings | None = None,
        model_id: str | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._model_id = model_id

    @property
    def _resolved_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def configured(self) -> bool:
        if self._client is not None:
            return True
        return bool(self._resolved_settings.openrouter_api_key.get_secret_value())

    def _get_client(self) -> _OpenAIClient:
        if self._client is not None:
            return self._client
        settings = self._resolved_settings
        if not settings.openrouter_api_key.get_secret_value():
            raise RuntimeError(
                "OpenRouter API 키가 미설정이라 클라우드 생성을 할 수 없습니다 "
                "(WHYMATH_OPENROUTER_API_KEY 없음)."
            )
        self._client = _build_default_client(settings)
        return self._client

    def _resolve_model_id(self, decision: RoutingDecision) -> str:
        if self._model_id is not None:
            return self._model_id
        settings = self._resolved_settings
        return settings.openrouter_model_id or _DEFAULT_MODEL_ID

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        """OpenRouter 경유 생성."""
        if images:
            raise RuntimeError("OpenRouterProvider는 멀티모달 입력을 지원하지 않습니다.")
        cost = _as_cost_tier(decision.cost_tier)
        if cost is CostTier.LOCAL:
            raise ValueError(
                f"OpenRouterProvider는 클라우드 결정만 처리한다(받은 cost_tier={cost.value}). "
                "로컬 티어는 OllamaProvider 담당이다."
            )

        settings = self._resolved_settings
        model_id = self._resolve_model_id(decision)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        extra: dict[str, Any] = {"max_tokens": settings.openrouter_max_tokens}
        if temperature is not None:
            extra["temperature"] = temperature
        if json_schema is not None:
            # OpenRouter/OpenAI json_schema 제약
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": dict(json_schema), "strict": True},
            }

        start = time.monotonic()
        response = await self._get_client().chat.completions.create(
            model=model_id,
            messages=messages,
            **extra,
        )
        latency_ms = (time.monotonic() - start) * 1000.0
        return GenerationResult(
            text=_extract_text(response),
            usage=_extract_usage(response, latency_ms),
        )

    async def check_status(self) -> OpenRouterStatus:
        """OpenRouter 구성·도달성 점검."""
        if not self.configured:
            return OpenRouterStatus(configured=False, reachable=False, error=None)
        try:
            await self._get_client().chat.completions.create(
                model=self._resolved_settings.openrouter_model_id or _DEFAULT_MODEL_ID,
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=1,
            )
        except Exception as exc:  # noqa: BLE001
            return OpenRouterStatus(configured=True, reachable=False, error=f"{type(exc).__name__}: {exc}")
        return OpenRouterStatus(configured=True, reachable=True, error=None)
