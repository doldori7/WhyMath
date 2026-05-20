"""LLMProvider 어댑터(providers.py) 단위 테스트 — Ollama·Anthropic·디스패처.

설계 정본: docs/architecture/03a_l3_router_design.md §A.0(resolve_model)·§A.1(CLOUD 풀).
범위 메모(M1.2): 라이브 SDK 없이, 손으로 짠 가짜 클라이언트를 주입해 *어댑터 계약*만
검증한다 — Ollama가 (패밀리×크기)→모델 ID를 해석하는지, Anthropic이 cost_tier→Sonnet/
Opus로 매핑하는지, 디스패처가 cost_tier로 위임하는지. 모킹 라이브러리 미사용.
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.providers import (
    AnthropicProvider,
    OllamaProvider,
    RoutingLLMProvider,
)


# ──────────────────────────────────────────────────────────────────────────
# 결정 빌더 — 불변식을 지키며 테스트 결정을 만든다
# ──────────────────────────────────────────────────────────────────────────
def _local_decision(
    family: ModelFamily | None,
    model: LocalModelTier,
    *,
    mode: str = "sync",
) -> RoutingDecision:
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=family,
        local_model=model,
        mode=mode,
        reason="test",
        est_latency_ms=1010,
        est_cost_krw=0.0,
    )


def _cloud_decision(cost: CostTier) -> RoutingDecision:
    return RoutingDecision(
        cost_tier=cost,
        local_family=None,
        local_model=None,
        mode="sync",
        reason="test",
        est_latency_ms=3000,
        est_cost_krw=10.0,
    )


# ──────────────────────────────────────────────────────────────────────────
# 가짜 클라이언트 (손으로 작성)
# ──────────────────────────────────────────────────────────────────────────
class _FakeOllama:
    """가짜 ollama.AsyncClient — generate 호출 인자를 기록하고 고정 응답을 돌려준다."""

    def __init__(self, response_text: str = "로컬 응답") -> None:
        self._response_text = response_text
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": stream,
                "options": options,
            }
        )
        return {"response": self._response_text}


class _FakeMessages:
    """가짜 anthropic messages 네임스페이스 — create 인자 기록 + content 블록 응답."""

    def __init__(self, response_text: str = "클라우드 응답") -> None:
        self._response_text = response_text
        self.calls: list[dict[str, Any]] = []

    async def create(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> Any:
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            }
        )
        return _FakeAnthropicMessage(self._response_text)


class _FakeTextBlock:
    """가짜 anthropic 텍스트 블록 — .text 노출."""

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeAnthropicMessage:
    """가짜 anthropic Message — content 블록 리스트(.text)."""

    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeAnthropic:
    """가짜 anthropic.AsyncAnthropic — .messages 프로퍼티 노출."""

    def __init__(self, response_text: str = "클라우드 응답") -> None:
        self._messages = _FakeMessages(response_text)

    @property
    def messages(self) -> _FakeMessages:
        return self._messages


# ──────────────────────────────────────────────────────────────────────────
# OllamaProvider — resolve_model로 모델 ID 해석 (03a §A.0)
# ──────────────────────────────────────────────────────────────────────────
class TestOllamaProvider:
    async def test_resolves_general_fast_model(self) -> None:
        """GENERAL×FAST → qwen2.5:3b로 호출 (A.0 매트릭스)."""
        fake = _FakeOllama()
        provider = OllamaProvider(client=fake, settings=Settings())
        decision = _local_decision(ModelFamily.GENERAL, LocalModelTier.FAST)
        await provider.generate("프롬프트", "시스템", decision)
        assert fake.calls[0]["model"] == "qwen2.5:3b"

    async def test_resolves_math_mid_model(self) -> None:
        """MATH×MID → qwen2-math:7b로 호출."""
        fake = _FakeOllama()
        provider = OllamaProvider(client=fake, settings=Settings())
        decision = _local_decision(ModelFamily.MATH, LocalModelTier.MID)
        await provider.generate("p", "s", decision)
        assert fake.calls[0]["model"] == "qwen2-math:7b"

    async def test_resolves_quality_model_family_irrelevant(self) -> None:
        """QUALITY(패밀리 None) → qwen3.5:27b (27b가 양 패밀리 포괄)."""
        fake = _FakeOllama()
        provider = OllamaProvider(client=fake, settings=Settings())
        decision = _local_decision(None, LocalModelTier.QUALITY, mode="async")
        await provider.generate("p", "s", decision)
        assert fake.calls[0]["model"] == "qwen3.5:27b"

    async def test_passes_prompt_and_system(self) -> None:
        """prompt·system을 ollama generate에 그대로 전달한다."""
        fake = _FakeOllama()
        provider = OllamaProvider(client=fake, settings=Settings())
        await provider.generate(
            "내 프롬프트", "내 시스템", _local_decision(ModelFamily.MATH, LocalModelTier.FAST)
        )
        call = fake.calls[0]
        assert call["prompt"] == "내 프롬프트"
        assert call["system"] == "내 시스템"
        assert call["stream"] is False

    async def test_returns_response_field(self) -> None:
        """ollama 응답의 response 필드를 텍스트로 반환한다."""
        fake = _FakeOllama(response_text="42입니다")
        provider = OllamaProvider(client=fake, settings=Settings())
        text = await provider.generate(
            "p", "s", _local_decision(ModelFamily.MATH, LocalModelTier.FAST)
        )
        assert text == "42입니다"

    async def test_missing_response_returns_empty(self) -> None:
        """response 필드 누락 시 빈 문자열(방어적)."""

        class _NoResponse(_FakeOllama):
            async def generate(
                self,
                model: str,
                prompt: str,
                system: str = "",
                stream: bool = False,
                options: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                return {}

        provider = OllamaProvider(client=_NoResponse(), settings=Settings())
        text = await provider.generate(
            "p", "s", _local_decision(ModelFamily.MATH, LocalModelTier.FAST)
        )
        assert text == ""

    async def test_lazy_build_uses_settings_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """client 미주입 시 settings.ollama_host로 lazy build한다(빌더를 가짜로 가로챔)."""
        captured: dict[str, str] = {}

        def _fake_build(host: str) -> _FakeOllama:
            captured["host"] = host
            return _FakeOllama()

        # _build_default_ollama_client를 가짜로 치환 — 라이브 SDK 생성 회피.
        monkeypatch.setattr(
            "whymath_backend.l3.providers._build_default_ollama_client", _fake_build
        )
        settings = Settings(ollama_host="http://gpu-host:11434")
        provider = OllamaProvider(client=None, settings=settings)
        await provider.generate("p", "s", _local_decision(ModelFamily.MATH, LocalModelTier.FAST))
        assert captured["host"] == "http://gpu-host:11434"

    async def test_satisfies_protocol(self) -> None:
        """OllamaProvider는 LLMProvider Protocol을 충족한다."""
        assert isinstance(OllamaProvider(client=_FakeOllama(), settings=Settings()), LLMProvider)


# ──────────────────────────────────────────────────────────────────────────
# AnthropicProvider — cost_tier → Sonnet/Opus (03a §A.1)
# ──────────────────────────────────────────────────────────────────────────
class TestAnthropicProvider:
    async def test_cloud_mid_maps_to_sonnet(self) -> None:
        """CLOUD_MID → settings.cloud_mid_model (Claude Sonnet)."""
        fake = _FakeAnthropic()
        provider = AnthropicProvider(client=fake, settings=Settings())
        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert fake.messages.calls[0]["model"] == "claude-sonnet-4-6"

    async def test_cloud_high_maps_to_opus(self) -> None:
        """CLOUD_HIGH → settings.cloud_high_model (Claude Opus)."""
        fake = _FakeAnthropic()
        provider = AnthropicProvider(client=fake, settings=Settings())
        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_HIGH))
        assert fake.messages.calls[0]["model"] == "claude-opus-4-7"

    async def test_custom_model_ids_from_settings(self) -> None:
        """settings로 교체한 모델 ID가 반영된다."""
        fake = _FakeAnthropic()
        settings = Settings(cloud_mid_model="sonnet-x", cloud_high_model="opus-x")
        provider = AnthropicProvider(client=fake, settings=settings)
        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert fake.messages.calls[0]["model"] == "sonnet-x"

    async def test_system_and_user_message_placement(self) -> None:
        """system은 system 파라미터로, prompt는 user 메시지로 전달한다."""
        fake = _FakeAnthropic()
        provider = AnthropicProvider(client=fake, settings=Settings())
        await provider.generate("학생 질문", "너는 코치다", _cloud_decision(CostTier.CLOUD_MID))
        call = fake.messages.calls[0]
        assert call["system"] == "너는 코치다"
        assert call["messages"] == [{"role": "user", "content": "학생 질문"}]

    async def test_extracts_text_from_content_blocks(self) -> None:
        """응답 content 블록의 text를 결합해 반환한다."""
        fake = _FakeAnthropic(response_text="증명 완료")
        provider = AnthropicProvider(client=fake, settings=Settings())
        text = await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_HIGH))
        assert text == "증명 완료"

    async def test_local_decision_rejected(self) -> None:
        """LOCAL 결정을 AnthropicProvider에 주면 오류(클라우드 전용)."""
        fake = _FakeAnthropic()
        provider = AnthropicProvider(client=fake, settings=Settings())
        with pytest.raises(ValueError):
            await provider.generate(
                "p", "s", _local_decision(ModelFamily.MATH, LocalModelTier.FAST)
            )

    async def test_lazy_build_requires_api_key(self) -> None:
        """client 미주입 + api_key 미설정 → 명확한 에러(시크릿 없이 호출 불가)."""
        provider = AnthropicProvider(client=None, settings=Settings(anthropic_api_key=None))
        with pytest.raises(RuntimeError, match="anthropic_api_key"):
            await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))

    async def test_lazy_build_uses_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """client 미주입 시 settings.anthropic_api_key로 lazy build한다(빌더 가로챔)."""
        captured: dict[str, str] = {}

        def _fake_build(api_key: str) -> _FakeAnthropic:
            captured["api_key"] = api_key
            return _FakeAnthropic()

        monkeypatch.setattr(
            "whymath_backend.l3.providers._build_default_anthropic_client", _fake_build
        )
        settings = Settings(anthropic_api_key="sk-live-xyz")
        provider = AnthropicProvider(client=None, settings=settings)
        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_HIGH))
        assert captured["api_key"] == "sk-live-xyz"

    async def test_empty_content_returns_empty(self) -> None:
        """content가 None이면 빈 문자열(방어적)."""

        class _EmptyMessage:
            content = None

        class _EmptyMessages:
            async def create(
                self,
                model: str,
                max_tokens: int,
                system: str,
                messages: list[dict[str, Any]],
            ) -> Any:
                return _EmptyMessage()

        class _EmptyClient:
            @property
            def messages(self) -> _EmptyMessages:
                return _EmptyMessages()

        provider = AnthropicProvider(client=_EmptyClient(), settings=Settings())
        text = await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert text == ""

    async def test_skips_blocks_without_text(self) -> None:
        """`.text` 없는 블록(예: tool_use)은 건너뛰고 텍스트 블록만 결합한다."""

        class _ToolBlock:
            """text 속성이 없는 블록(텍스트 외 블록 모사)."""

        class _MixedMessage:
            def __init__(self) -> None:
                self.content = [_ToolBlock(), _FakeTextBlock("진짜 답"), _ToolBlock()]

        class _MixedMessages:
            async def create(
                self,
                model: str,
                max_tokens: int,
                system: str,
                messages: list[dict[str, Any]],
            ) -> Any:
                return _MixedMessage()

        class _MixedClient:
            @property
            def messages(self) -> _MixedMessages:
                return _MixedMessages()

        provider = AnthropicProvider(client=_MixedClient(), settings=Settings())
        text = await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert text == "진짜 답"

    async def test_satisfies_protocol(self) -> None:
        """AnthropicProvider는 LLMProvider Protocol을 충족한다."""
        assert isinstance(
            AnthropicProvider(client=_FakeAnthropic(), settings=Settings()), LLMProvider
        )


# ──────────────────────────────────────────────────────────────────────────
# RoutingLLMProvider — cost_tier로 위임 (디스패처)
# ──────────────────────────────────────────────────────────────────────────
class TestRoutingLLMProvider:
    def _dispatcher(self) -> tuple[RoutingLLMProvider, _FakeOllama, _FakeAnthropic]:
        ollama_fake = _FakeOllama(response_text="로컬")
        anthropic_fake = _FakeAnthropic(response_text="클라우드")
        dispatcher = RoutingLLMProvider(
            ollama=OllamaProvider(client=ollama_fake, settings=Settings()),
            anthropic=AnthropicProvider(client=anthropic_fake, settings=Settings()),
        )
        return dispatcher, ollama_fake, anthropic_fake

    async def test_local_dispatches_to_ollama(self) -> None:
        """LOCAL 결정 → ollama로 위임(anthropic 미호출)."""
        dispatcher, ollama_fake, anthropic_fake = self._dispatcher()
        text = await dispatcher.generate(
            "p", "s", _local_decision(ModelFamily.MATH, LocalModelTier.FAST)
        )
        assert text == "로컬"
        assert len(ollama_fake.calls) == 1
        assert len(anthropic_fake.messages.calls) == 0

    async def test_cloud_mid_dispatches_to_anthropic(self) -> None:
        """CLOUD_MID 결정 → anthropic으로 위임(ollama 미호출)."""
        dispatcher, ollama_fake, anthropic_fake = self._dispatcher()
        text = await dispatcher.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert text == "클라우드"
        assert len(anthropic_fake.messages.calls) == 1
        assert len(ollama_fake.calls) == 0

    async def test_cloud_high_dispatches_to_anthropic(self) -> None:
        """CLOUD_HIGH 결정 → anthropic으로 위임."""
        dispatcher, _, anthropic_fake = self._dispatcher()
        await dispatcher.generate("p", "s", _cloud_decision(CostTier.CLOUD_HIGH))
        assert anthropic_fake.messages.calls[0]["model"] == "claude-opus-4-7"

    async def test_satisfies_protocol(self) -> None:
        """RoutingLLMProvider는 LLMProvider Protocol을 충족한다."""
        dispatcher, _, _ = self._dispatcher()
        assert isinstance(dispatcher, LLMProvider)
