"""Lemonade Server 로컬 LLM 제공자 — interfaces.LLMProvider 구현 (OPS-43).

Lemonade Server(AMD)의 OpenAI 호환 API를 통해 로컬 GPU(Vulkan 백엔드)로 생성을
수행한다. Ollama가 Windows + AMD GPU 환경에서 GPU를 활용하지 못하는 문제(CPU 추론)
를 우회하기 위한 대안이다.

설계 정본: `docs/architecture/03a_l3_router_design.md` §A.0(모델 매트릭스)·§H 후속 4
(클cloud 티어 실제 연동). OllamaProvider와 동일한 LLMProvider 인터페이스를 구현하되,
날부적으로 OpenAI 호환 chat completions API를 사용한다.

특이 사항 (Qwen3/Qwen3.5 reasoning 모델):
- 응답의 `choices[0].message.content`가 최종 답이다.
- `reasoning_content`는 사고 과정이며 검증 대상이 아니다.
- `finish_reason == "stop"`이면 사고 완료 후 최종 답이 content에 들어있다.
- `finish_reason == "length"`이면 max_tokens 부족으로 사고가 끝나지 않은 상태다.

경계 메모 (CLAUDE.md 절대 금기): 이 제공자가 반환하는 텍스트는 *검증 전 원시 모델
출력*이다. 03 문서 환각 방어 파이프라인(스키마→SymPy/Lean→PRM→자기검증→사람검수)을
통과하기 전에는 *학생에게 직접 노출 금지* ("LLM 응답을 검증 없이 학생에게 제공 금지").
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision, Usage
from whymath_backend.l3.router import _as_cost_tier


# ──────────────────────────────────────────────────────────────────────────
# Lemonade 클라이언트 추상화 (테스트 주입용) — ollama.py 패턴 미러링.
# OpenAI 호환 API의 최소 표멧만 선언한다.
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _LemonadeClient(Protocol):
    """Lemonade Server의 최소 인터페이스 (구조적 타이핑).

    실제로는 httpx.AsyncClient를 사용하며, OpenAI 호환 chat completions API를
    호출한다. 테스트는 가짜 클라이언트를 주입해 네트워크 없이 검증한다.
    """

    async def post(self, url: str, *, json: dict[str, Any]) -> Any:
        """HTTP POST (chat completions)."""
        ...

    async def get(self, url: str) -> Any:
        """HTTP GET (모델 목록)."""
        ...


@dataclass(slots=True, frozen=True)
class LemonadeStatus:
    """Lemonade Server 준태 보고 (/status 엔드포인트용)."""

    reachable: bool
    models: tuple[str, ...]
    error: str | None = None


class LemonadeProvider:
    """Lemonade Server 생성 제공자 — interfaces.LLMProvider 충족.

    로컬 Lemonade Server(OpenAI 호환 API)로 생성을 수행한다.
    Vulkan 백엔드를 통해 AMD GPU를 활용한다(Ollama의 CPU 추론 문제 우회).

    클라이언트는 지연 생성(lazy)·주입 가능(injectable)하다 — 테스트는 가짜 클라이언트를
    `client=` 로 넣고, 프로덕션은 기본 httpx 클라이언트를 첫 호출 때 생성한다.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model_id: str | None = None,
        client: _LemonadeClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._base_url = base_url or "http://localhost:8000/api/v1"
        self._model_id = model_id
        self._client = client
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self) -> _LemonadeClient:
        """클lion트 지연 해석 — 주입 우선, 없으면 httpx.AsyncClient 생성."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=300.0)
        return self._client

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
        """Lemonade Server로 생성 (LLMProvider 구현).

        - CostTier.LOCAL이 아니면 즉시 거부(클cloud는 범위 밖).
        - `model_id`가 주어지면 그 모델을 사용하고, 없으면 decision에서 해석한다.
        - Qwen3/Qwen3.5 reasoning 모델은 `choices[0].message.content`가 최종 답이다.
          `reasoning_content`는 사고 과정이므로 사용하지 않는다.
        - reasoning 모델은 사고 과정 길이가 비결정적이라, content가 비어 있으면
          (사고가 max_tokens 안에 끝나지 않은 경우) 최대 2회 재시도한다.
        - `images`(base64)는 현재 지원하지 않는다(텍스트 전용).
        """
        cost = _as_cost_tier(decision.cost_tier)
        if cost is not CostTier.LOCAL:
            raise ValueError(
                f"LemonadeProvider는 로컬 결정만 처리한다(받은 cost_tier={cost.value}). "
                "클cloud 티어는 AnthropicProvider를 사용한다."
            )

        model_id = self._model_id or "Qwen3.5-122B-A10B-GGUF"
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 8000,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        client = self._get_client()
        start = time.monotonic()
        text = ""
        input_tokens: int | None = None
        output_tokens: int | None = None
        # reasoning 모델의 사고 길이는 비결정적이다 — content가 비어 있으면(사고가
        # max_tokens 안에 끝나지 않음) 같은 프롬프트로 최대 2회 재시도한다.
        for _attempt in range(3):
            response = await client.post(url, json=payload)
            data = response.json() if hasattr(response, "json") else response
            if isinstance(data, dict):
                choices = data.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    message = choices[0].get("message", {})
                    if isinstance(message, dict):
                        candidate = message.get("content", "") or ""
                        if candidate.strip():
                            text = candidate
                usage = data.get("usage", {})
                if isinstance(usage, dict):
                    pt = usage.get("prompt_tokens")
                    ct = usage.get("completion_tokens")
                    if isinstance(pt, int) and pt >= 0:
                        input_tokens = pt
                    if isinstance(ct, int) and ct >= 0:
                        output_tokens = ct
            if text.strip():
                break
        latency_ms = (time.monotonic() - start) * 1000.0

        return GenerationResult(
            text=text,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            ),
        )

    async def check_status(self) -> LemonadeStatus:
        """Lemonade Server 도달성 + 모델 목록 점검 (/status용)."""
        try:
            client = self._get_client()
            response = await client.get(f"{self._base_url}/models")
            data = response.json() if hasattr(response, "json") else response
            models = []
            if isinstance(data, dict):
                for m in data.get("data", []):
                    if isinstance(m, dict) and "id" in m:
                        models.append(m["id"])
            return LemonadeStatus(reachable=True, models=tuple(models), error=None)
        except Exception as exc:
            return LemonadeStatus(
                reachable=False,
                models=(),
                error=f"{type(exc).__name__}: {exc}",
            )
