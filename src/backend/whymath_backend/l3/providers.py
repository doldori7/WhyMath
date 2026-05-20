"""L3 LLM 제공자 어댑터 — `LLMProvider` Protocol의 라이브 구현.

설계 정본: docs/architecture/03a_l3_router_design.md
  §A.0(패밀리×크기 → 실제 모델 ID, resolve_model)·§A.1(CLOUD 모델 풀)·
  §C.4 메모(라우터는 *어디서 생성할지*만 정하고, 생성물은 환각 방어 파이프라인을
  반드시 통과해야 학생에게 노출된다 — CLAUDE.md 절대 금기).

세 어댑터:
  - OllamaProvider   — 축1=LOCAL. resolve_model()로 (패밀리×크기)→모델 ID를 얻어 호출.
  - AnthropicProvider — 축1=CLOUD_MID/CLOUD_HIGH. settings의 Sonnet/Opus 모델로 매핑.
  - RoutingLLMProvider — 디스패처. decision.cost_tier로 위 둘 중 하나에 위임.

테스트 가능성(bench_latency.py·quality_eval.py 패턴 미러링):
  - SDK 클라이언트는 `_OllamaClientProtocol`·`_AnthropicClientProtocol` 추상 경유.
  - 실제 SDK(`ollama`·`anthropic`) import는 *함수 안에서만*(lazy) — 모듈은 stdlib만으로
    로드 가능해야 테스트 수집이 라이브 SDK 없이 통과한다.
  - 테스트는 손으로 짠 가짜 클라이언트를 주입한다(모킹 라이브러리 미사용).
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.router import _as_cost_tier, resolve_model

# 로컬 생성 토큰 한도 — 벤치(DEFAULT_NUM_PREDICT)와 동일 기본값(512).
# 수학 모델 과추론 잘림 방지(quality_eval.py 메모) 겸 응답 길이 상한.
_DEFAULT_NUM_PREDICT: int = 512
# 클라우드 생성 토큰 한도 — Anthropic은 max_tokens 필수 인자라 보수적 기본값을 둔다.
_DEFAULT_MAX_TOKENS: int = 1024


# ──────────────────────────────────────────────────────────────────────────
# Ollama 클라이언트 추상화 (bench_latency.py _OllamaClientProtocol 미러링)
# ──────────────────────────────────────────────────────────────────────────
class _OllamaClientProtocol(Protocol):
    """ollama 비동기 클라이언트의 최소 인터페이스.

    실제 `ollama.AsyncClient`와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    `generate`는 system 프롬프트를 별도 인자로 받는다(ollama.generate의 `system`).
    """

    async def generate(  # noqa: D401 — 외부 라이브러리 시그니처 보존
        self,
        model: str,
        prompt: str,
        system: str = "",
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def _build_default_ollama_client(host: str) -> _OllamaClientProtocol:  # pragma: no cover
    """기본 ollama AsyncClient 생성. import 실패 시 명확한 에러.

    라이브 SDK 생성 shim — 라이브 Ollama 없이는 실행 불가하므로 커버리지 제외(테스트는
    이 함수를 monkeypatch로 치환해 lazy build 경로만 검증한다, test_providers.py).
    `ollama` import는 *이 함수 안에서만* 한다(모듈 최상단 X). importlib로 동적 로드해
    타입 스텁 유무와 무관하게 mypy --strict를 통과하고, 실제 `AsyncClient`는
    `.get(...)` 가능한 응답을 돌려주므로 Protocol과 런타임 동형이라 cast로 연결한다
    (quality_eval.py _build_default_client와 동일 패턴).
    """
    import importlib

    try:
        ollama = importlib.import_module("ollama")
    except ImportError as exc:
        raise RuntimeError(
            "ollama Python 클라이언트가 설치되지 않았습니다. `pip install ollama` 후 재시도."
        ) from exc
    client = ollama.AsyncClient(host=host)
    return cast("_OllamaClientProtocol", client)


class OllamaProvider:
    """로컬(Phaiakes9) LLM 제공자 — `LLMProvider` 충족 (축1=LOCAL).

    `decision.local_family`·`decision.local_model`을 resolve_model()로 실제 모델 ID
    (예: GENERAL×FAST=qwen2.5:3b, MATH×MID=qwen2-math:7b, QUALITY=qwen3.5:27b)로
    해석한 뒤 ollama로 호출한다(03a §A.0 매트릭스).

    클라이언트 주입 가능 — 기본 None이면 첫 호출 시 settings.ollama_host로 lazy build.
    """

    def __init__(
        self,
        *,
        client: _OllamaClientProtocol | None = None,
        settings: Settings | None = None,
        num_predict: int = _DEFAULT_NUM_PREDICT,
    ) -> None:
        self._client = client
        self._settings = settings if settings is not None else get_settings()
        self._num_predict = num_predict

    def _ensure_client(self) -> _OllamaClientProtocol:
        """주입된 클라이언트가 없으면 settings.ollama_host로 lazy 생성."""
        if self._client is None:
            self._client = _build_default_ollama_client(self._settings.ollama_host)
        return self._client

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        """로컬 모델로 응답 생성 — resolve_model()로 모델 ID 해석 후 ollama.generate.

        decision은 LOCAL이어야 한다(local_model이 있어야 resolve_model이 동작).
        반환은 ollama 응답의 `response` 필드(생성 텍스트). 환각 방어는 호출 측 책임.
        """
        model_id = resolve_model(decision.local_family, decision.local_model)
        client = self._ensure_client()
        response = await client.generate(
            model=model_id,
            prompt=prompt,
            system=system,
            stream=False,
            options={"num_predict": self._num_predict},
        )
        # ollama 응답: {"response": "...", ...}. 누락 시 빈 문자열(방어적).
        return str(response.get("response", "") or "")


# ──────────────────────────────────────────────────────────────────────────
# Anthropic 클라이언트 추상화 (CLOUD_MID=Sonnet / CLOUD_HIGH=Opus, 03a §A.1)
# ──────────────────────────────────────────────────────────────────────────
class _AnthropicMessagesProtocol(Protocol):
    """anthropic 비동기 클라이언트의 `messages.create` 최소 인터페이스."""

    async def create(  # noqa: D401 — 외부 라이브러리 시그니처 보존
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> Any: ...


class _AnthropicClientProtocol(Protocol):
    """anthropic 비동기 클라이언트의 최소 인터페이스(`.messages.create` 노출).

    실제 `anthropic.AsyncAnthropic`와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    """

    @property
    def messages(self) -> _AnthropicMessagesProtocol: ...


def _build_default_anthropic_client(api_key: str) -> _AnthropicClientProtocol:  # pragma: no cover
    """기본 anthropic AsyncAnthropic 생성. import 실패 시 명확한 에러.

    라이브 SDK 생성 shim — 라이브 API 키 없이는 실행 불가하므로 커버리지 제외(테스트는
    monkeypatch로 치환해 lazy build 경로만 검증한다, test_providers.py).
    `anthropic` import는 *이 함수 안에서만* 한다(lazy). importlib 동적 로드 + cast로
    mypy --strict를 통과한다(quality_eval.py 패턴).
    """
    import importlib

    try:
        anthropic = importlib.import_module("anthropic")
    except ImportError as exc:
        raise RuntimeError(
            "anthropic Python 클라이언트가 설치되지 않았습니다. `pip install anthropic` 후 재시도."
        ) from exc
    client = anthropic.AsyncAnthropic(api_key=api_key)
    return cast("_AnthropicClientProtocol", client)


def _extract_anthropic_text(message: Any) -> str:
    """Anthropic Messages 응답에서 텍스트를 추출한다(content 블록 결합).

    응답 형식: `message.content`는 블록 리스트이고 각 텍스트 블록은 `.text`를 가진다
    (anthropic SDK Message). text 블록만 골라 이어 붙인다. 형식이 예상과 달라도
    죽지 않도록 방어적으로 처리한다(라이브 SDK 응답 형태 변화 대비).
    """
    content = getattr(message, "content", None)
    if content is None:
        return ""
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(str(text))
    return "".join(parts)


class AnthropicProvider:
    """클라우드 LLM 제공자 — `LLMProvider` 충족 (축1=CLOUD_MID/CLOUD_HIGH).

    decision.cost_tier를 settings 모델로 매핑한다(03a §A.1):
      CLOUD_MID  → settings.cloud_mid_model  (Claude Sonnet 4.6)
      CLOUD_HIGH → settings.cloud_high_model (Claude Opus 4.7)
    system은 Anthropic system 파라미터로, prompt는 user 메시지로 전달한다.

    클라이언트 주입 가능 — 기본 None이면 첫 호출 시 settings.anthropic_api_key로
    lazy build(키 미설정 시 명확한 에러).
    """

    def __init__(
        self,
        *,
        client: _AnthropicClientProtocol | None = None,
        settings: Settings | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self._client = client
        self._settings = settings if settings is not None else get_settings()
        self._max_tokens = max_tokens

    def _ensure_client(self) -> _AnthropicClientProtocol:
        """주입된 클라이언트가 없으면 settings.anthropic_api_key로 lazy 생성."""
        if self._client is None:
            api_key = self._settings.anthropic_api_key
            if not api_key:
                raise RuntimeError(
                    "anthropic_api_key가 설정되지 않았습니다(WHYMATH_ANTHROPIC_API_KEY). "
                    "CLOUD 라우팅에는 키가 필요합니다."
                )
            self._client = _build_default_anthropic_client(api_key)
        return self._client

    def _model_for(self, decision: RoutingDecision) -> str:
        """decision.cost_tier → 실제 클라우드 모델 ID (03a §A.1)."""
        cost = _as_cost_tier(decision.cost_tier)
        if cost is CostTier.CLOUD_HIGH:
            return self._settings.cloud_high_model
        if cost is CostTier.CLOUD_MID:
            return self._settings.cloud_mid_model
        raise ValueError(
            f"AnthropicProvider는 CLOUD_* 결정에만 적용된다(현재 cost_tier={cost.value})"
        )

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        """클라우드 모델로 응답 생성 — system은 system 파라미터, prompt는 user 메시지."""
        model_id = self._model_for(decision)
        client = self._ensure_client()
        message = await client.messages.create(
            model=model_id,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_anthropic_text(message)


class RoutingLLMProvider:
    """디스패처 제공자 — `LLMProvider` 충족. decision.cost_tier로 위임.

    오케스트레이션(GenerationService)이 단일 LLMProvider만 알도록, 축1에 따라
    로컬(Ollama) vs 클라우드(Anthropic) 위임을 캡슐화한다. CLAUDE.md "LLM 호출은
    항상 라우터 경유" — 이 디스패처는 *라우터 결정(decision)을 그대로* 따른다.
    """

    def __init__(self, *, ollama: OllamaProvider, anthropic: AnthropicProvider) -> None:
        self._ollama = ollama
        self._anthropic = anthropic

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        """축1=LOCAL → ollama, CLOUD_* → anthropic으로 위임."""
        cost = _as_cost_tier(decision.cost_tier)
        if cost is CostTier.LOCAL:
            return await self._ollama.generate(prompt, system, decision)
        return await self._anthropic.generate(prompt, system, decision)
