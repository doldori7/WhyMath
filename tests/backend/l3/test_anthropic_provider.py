"""AnthropicProvider 단위테스트 — 가짜 Anthropic 클라이언트 주입 (라이브 서비스 없음).

ollama.py(FakeOllamaClient)·langfuse_sink.py(FakeLangfuseClient) 단위테스트를 미러링한다.
실제 anthropic 라이브러리·네트워크·API 키에 의존하지 않는다 → CI hermetic.

검증 핵심(S5 위험 표면):
  - 모델 해석: CLOUD_MID→anthropic_model_mid, CLOUD_HIGH→anthropic_model_high (03a §A.0).
  - 호출 규약: messages.create(model/max_tokens/system/messages=[user]) — 샘플링 인자 없음.
  - 텍스트 추출: content 블록 중 type=="text"만 이어붙임(thinking/tool 제외, dict·객체 양형).
  - 로컬 거부: LOCAL 결정은 거부(OllamaProvider 담당).
  - 미설정: 키 없으면 configured=False·generate 시 명확한 오류(조용한 강등 금지).

설계 정본: docs/architecture/03a_l3_router_design.md §A.0·§C.1·§H 후속 4.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.providers.anthropic import (
    AnthropicProvider,
    _AnthropicClient,
    _build_default_client,
    _extract_text,
    resolve_cloud_model,
)


# ──────────────────────────────────────────────────────────────────────────
# 가짜 클라이언트 — anthropic.AsyncAnthropic의 messages.create·models.list만 모사
# ──────────────────────────────────────────────────────────────────────────
class _FakeMessages:
    def __init__(self, *, response: Any, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
                "kwargs": kwargs,
            }
        )
        if self._raises is not None:
            raise self._raises
        return self._response


class _FakeModels:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.list_calls = 0

    async def list(self) -> Any:
        self.list_calls += 1
        if self._raises is not None:
            raise self._raises
        return {"data": [{"id": "claude-sonnet-4-6"}, {"id": "claude-opus-4-7"}]}


class FakeAnthropicClient:
    """`_AnthropicClient` 시임을 구조적으로 충족하는 가짜 클라이언트."""

    def __init__(
        self,
        *,
        message_response: Any = None,
        create_raises: Exception | None = None,
        list_raises: Exception | None = None,
    ) -> None:
        if message_response is None:
            message_response = _dict_message("원시 출력")
        self.messages = _FakeMessages(response=message_response, raises=create_raises)
        self.models = _FakeModels(raises=list_raises)


# ── 응답 형태 빌더 (dict·객체 양쪽 정규화 경로 테스트) ──
def _dict_message(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


class _Block:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class _ObjMessage:
    def __init__(self, blocks: list[Any]) -> None:
        self.content = blocks


# ── 결정·설정 헬퍼 ──
def _cloud_decision(cost: CostTier) -> RoutingDecision:
    return RoutingDecision(
        cost_tier=cost,
        local_family=None,
        local_model=None,
        mode="sync",
        reason="cloud",
        est_latency_ms=3000,
        est_cost_krw=10.0,
    )


def _local_decision() -> RoutingDecision:
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=ModelFamily.MATH,
        local_model=LocalModelTier.FAST,
        mode="sync",
        reason="local",
        est_latency_ms=1010,
        est_cost_krw=0.0,
    )


def _model_settings() -> Settings:
    """모델 매핑을 결정적으로 검증하기 위한 센티넬 모델 ID Settings."""
    return Settings(
        anthropic_model_mid="model-mid-sentinel",
        anthropic_model_high="model-high-sentinel",
        anthropic_max_tokens=1234,
    )


def _configured_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"anthropic_api_key": SecretStr("sk-ant-test")}
    base.update(overrides)
    return Settings(**base)


def _unconfigured_settings() -> Settings:
    return Settings(anthropic_api_key=SecretStr(""))


# ──────────────────────────────────────────────────────────────────────────
# generate — 모델 해석 + 호출 규약
# ──────────────────────────────────────────────────────────────────────────
class TestGenerate:
    async def test_cloud_mid_resolves_to_mid_model(self) -> None:
        """CLOUD_MID → anthropic_model_mid로 호출, 원시 텍스트 반환."""
        client = FakeAnthropicClient(message_response=_dict_message("42"))
        provider = AnthropicProvider(client=client, settings=_model_settings())

        out = await provider.generate("2+2?", "system", _cloud_decision(CostTier.CLOUD_MID))

        assert out == "42"
        assert len(client.messages.calls) == 1
        call = client.messages.calls[0]
        assert call["model"] == "model-mid-sentinel"
        assert call["max_tokens"] == 1234
        assert call["system"] == "system"
        assert call["messages"] == [{"role": "user", "content": "2+2?"}]

    async def test_cloud_high_resolves_to_high_model(self) -> None:
        """CLOUD_HIGH → anthropic_model_high로 호출."""
        client = FakeAnthropicClient()
        provider = AnthropicProvider(client=client, settings=_model_settings())

        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_HIGH))

        assert client.messages.calls[0]["model"] == "model-high-sentinel"

    async def test_default_model_ids_are_claude_aliases(self) -> None:
        """기본 설정에서 CLOUD_MID=Sonnet 4.6, CLOUD_HIGH=Opus 4.7 alias로 해석된다."""
        defaults = Settings()
        client_mid = FakeAnthropicClient()
        await AnthropicProvider(client=client_mid, settings=defaults).generate(
            "p", "s", _cloud_decision(CostTier.CLOUD_MID)
        )
        client_high = FakeAnthropicClient()
        await AnthropicProvider(client=client_high, settings=defaults).generate(
            "p", "s", _cloud_decision(CostTier.CLOUD_HIGH)
        )
        assert client_mid.messages.calls[0]["model"] == "claude-sonnet-4-6"
        assert client_high.messages.calls[0]["model"] == "claude-opus-4-7"

    async def test_local_decision_rejected(self) -> None:
        """LOCAL 결정은 거부(OllamaProvider 담당) — 호출 자체가 없어야 한다."""
        client = FakeAnthropicClient()
        provider = AnthropicProvider(client=client, settings=_model_settings())

        with pytest.raises(ValueError, match="클라우드 결정만"):
            await provider.generate("p", "s", _local_decision())
        assert client.messages.calls == []

    async def test_extract_text_from_object_blocks(self) -> None:
        """content가 객체 블록(.type/.text)이어도 텍스트 추출."""
        msg = _ObjMessage([_Block("text", "객체응답")])
        client = FakeAnthropicClient(message_response=msg)
        provider = AnthropicProvider(client=client, settings=_model_settings())

        out = await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        assert out == "객체응답"

    async def test_generate_unconfigured_raises(self) -> None:
        """키 미설정 + 클라이언트 미주입 → generate가 명확한 오류(조용한 강등 금지)."""
        provider = AnthropicProvider(settings=_unconfigured_settings())
        with pytest.raises(RuntimeError, match="API 키"):
            await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))


# ──────────────────────────────────────────────────────────────────────────
# 튜닝 노브 — effort/thinking/caching은 *설정된 경우에만* 전달 (기본 OFF, 03a §H#4)
# ──────────────────────────────────────────────────────────────────────────
class TestTuningKnobs:
    async def _call_kwargs(self, settings: Settings) -> dict[str, Any]:
        client = FakeAnthropicClient()
        provider = AnthropicProvider(client=client, settings=settings)
        await provider.generate("p", "s", _cloud_decision(CostTier.CLOUD_MID))
        kwargs: dict[str, Any] = client.messages.calls[0]["kwargs"]
        return kwargs

    async def test_defaults_omit_all_tuning_args(self) -> None:
        """기본값(전부 OFF)이면 output_config·thinking·cache_control 키를 싣지 않는다."""
        kwargs = await self._call_kwargs(
            Settings(
                anthropic_effort="",
                anthropic_thinking=False,
                anthropic_prompt_caching=False,
            )
        )
        assert kwargs == {}

    async def test_effort_passed_when_set(self) -> None:
        kwargs = await self._call_kwargs(Settings(anthropic_effort="high"))
        assert kwargs["output_config"] == {"effort": "high"}
        assert "thinking" not in kwargs
        assert "cache_control" not in kwargs

    async def test_thinking_passed_when_enabled(self) -> None:
        kwargs = await self._call_kwargs(Settings(anthropic_thinking=True))
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "output_config" not in kwargs

    async def test_caching_passed_when_enabled(self) -> None:
        kwargs = await self._call_kwargs(Settings(anthropic_prompt_caching=True))
        assert kwargs["cache_control"] == {"type": "ephemeral"}

    async def test_all_three_together(self) -> None:
        kwargs = await self._call_kwargs(
            Settings(
                anthropic_effort="xhigh",
                anthropic_thinking=True,
                anthropic_prompt_caching=True,
            )
        )
        assert kwargs["output_config"] == {"effort": "xhigh"}
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["cache_control"] == {"type": "ephemeral"}


# ──────────────────────────────────────────────────────────────────────────
# _extract_text — content 블록 정규화 (dict·객체·엣지)
# ──────────────────────────────────────────────────────────────────────────
class TestExtractText:
    def test_joins_text_blocks_skips_non_text(self) -> None:
        """여러 text 블록은 이어붙이고 thinking/tool 등 비텍스트는 건너뛴다."""
        msg = {
            "content": [
                {"type": "thinking", "thinking": "속으로..."},
                {"type": "text", "text": "안녕"},
                {"type": "tool_use", "name": "x"},
                {"type": "text", "text": "하세요"},
            ]
        }
        assert _extract_text(msg) == "안녕하세요"

    def test_object_blocks(self) -> None:
        msg = _ObjMessage([_Block("thinking", "x"), _Block("text", "본문")])
        assert _extract_text(msg) == "본문"

    def test_no_content_attr_returns_empty(self) -> None:
        assert _extract_text(12345) == ""

    def test_content_not_list_returns_empty(self) -> None:
        assert _extract_text({"content": "not a list"}) == ""

    def test_text_block_without_text_value_skipped(self) -> None:
        """type=text이나 text 값이 없는(또는 비문자열) 블록은 건너뛴다."""
        msg = {
            "content": [
                {"type": "text"},
                {"type": "text", "text": 7},
                {"type": "text", "text": "ok"},
            ]
        }
        assert _extract_text(msg) == "ok"

    def test_empty_content_returns_empty(self) -> None:
        assert _extract_text({"content": []}) == ""

    def test_block_neither_object_nor_dict_and_text_block_without_text_attr(self) -> None:
        """객체도 dict도 아닌 블록, 그리고 type=text이나 .text 속성이 없는 블록은 건너뛴다."""

        class _TypeOnly:
            type = "text"  # text 타입이지만 .text 속성이 없는 객체(방어 경로)

        msg = {"content": [7, _TypeOnly()]}
        assert _extract_text(msg) == ""


# ──────────────────────────────────────────────────────────────────────────
# resolve_cloud_model — 티어 → 모델 ID 매핑
# ──────────────────────────────────────────────────────────────────────────
class TestResolveCloudModel:
    def test_mid_and_high(self) -> None:
        s = _model_settings()
        assert resolve_cloud_model(CostTier.CLOUD_MID, s) == "model-mid-sentinel"
        assert resolve_cloud_model(CostTier.CLOUD_HIGH, s) == "model-high-sentinel"

    def test_accepts_string_cost_tier(self) -> None:
        """use_enum_values=True 환경 대비 — 문자열 cost_tier도 정규화한다."""
        assert resolve_cloud_model("cloud_mid", _model_settings()) == "model-mid-sentinel"

    def test_local_rejected(self) -> None:
        with pytest.raises(ValueError, match="클라우드 티어에만"):
            resolve_cloud_model(CostTier.LOCAL, _model_settings())


# ──────────────────────────────────────────────────────────────────────────
# check_status — 구성·도달성 보고
# ──────────────────────────────────────────────────────────────────────────
class TestCheckStatus:
    async def test_configured_and_reachable(self) -> None:
        """주입 클라이언트 + models.list 성공 → configured·reachable True."""
        client = FakeAnthropicClient()
        provider = AnthropicProvider(client=client)

        st = await provider.check_status()

        assert st.configured is True
        assert st.reachable is True
        assert st.error is None
        assert client.models.list_calls == 1

    async def test_configured_unreachable_absorbs_error(self) -> None:
        """models.list 실패(인증·네트워크)는 흡수 → reachable=False + 사유."""
        client = FakeAnthropicClient(list_raises=ConnectionError("refused"))
        provider = AnthropicProvider(client=client)

        st = await provider.check_status()

        assert st.configured is True
        assert st.reachable is False
        assert st.error is not None
        assert "ConnectionError" in st.error

    async def test_unconfigured_reports_without_network(self) -> None:
        """키 미설정(클라이언트 미주입) → configured=False, 네트워크·클라이언트 없음."""
        provider = AnthropicProvider(settings=_unconfigured_settings())

        st = await provider.check_status()

        assert st.configured is False
        assert st.reachable is False
        assert st.error is None


# ──────────────────────────────────────────────────────────────────────────
# configured·지연 생성·기본 클라이언트
# ──────────────────────────────────────────────────────────────────────────
class TestConfiguredAndLazy:
    def test_injected_client_configured_true_regardless_of_keys(self) -> None:
        """주입 클라이언트가 있으면 키 미설정이어도 configured=True(DI 우선)."""
        provider = AnthropicProvider(
            client=FakeAnthropicClient(), settings=_unconfigured_settings()
        )
        assert provider.configured is True

    def test_unconfigured_settings_configured_false(self) -> None:
        provider = AnthropicProvider(settings=_unconfigured_settings())
        assert provider.configured is False

    def test_configured_settings_true(self) -> None:
        provider = AnthropicProvider(settings=_configured_settings())
        assert provider.configured is True

    def test_get_client_raises_when_unconfigured(self) -> None:
        """미설정 시 _get_client는 명확한 RuntimeError(조용한 강등 금지)."""
        provider = AnthropicProvider(settings=_unconfigured_settings())
        with pytest.raises(RuntimeError, match="API 키"):
            provider._get_client()

    def test_default_client_built_lazily_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """클라이언트 미주입 + 키 설정 → 첫 _get_client에서 1회 생성·재사용(빌더 monkeypatch)."""
        built: list[Settings] = []

        def _fake_builder(settings: Settings) -> Any:
            built.append(settings)
            return FakeAnthropicClient()

        monkeypatch.setattr(
            "whymath_backend.l3.providers.anthropic._build_default_client",
            _fake_builder,
        )
        provider = AnthropicProvider(settings=_configured_settings())
        c1 = provider._get_client()
        c2 = provider._get_client()
        assert c1 is c2
        assert len(built) == 1

    def test_resolved_settings_falls_back_to_global(self) -> None:
        from whymath_backend.config import get_settings

        get_settings.cache_clear()
        provider = AnthropicProvider()
        assert isinstance(provider._resolved_settings, Settings)

    async def test_build_default_client_constructs_real_async_anthropic(self) -> None:
        """_build_default_client가 실제 AsyncAnthropic을 생성한다(시임 충족·cast 경로).

        ollama.py/langfuse_sink.py가 실제 클라이언트를 생성해 기본 경로를 커버한 것을
        미러링한다. AsyncAnthropic 생성자는 네트워크를 타지 않는다(실제 호출 시 연결).
        잔여 httpx 클라이언트는 close()로 정리한다.
        """
        client = _build_default_client(_configured_settings())
        assert isinstance(client, _AnthropicClient)  # messages·models 보유
        close = getattr(client, "close", None)
        if close is not None:
            await close()


# ──────────────────────────────────────────────────────────────────────────
# Protocol 위생
# ──────────────────────────────────────────────────────────────────────────
def test_provider_satisfies_llm_provider_protocol() -> None:
    """AnthropicProvider는 LLMProvider Protocol을 충족한다(runtime_checkable)."""
    assert isinstance(AnthropicProvider(client=FakeAnthropicClient()), LLMProvider)


def test_fake_client_satisfies_seam_protocol() -> None:
    """가짜 클라이언트가 _AnthropicClient 시임을 구조적으로 충족(테스트 위생)."""
    assert isinstance(FakeAnthropicClient(), _AnthropicClient)
