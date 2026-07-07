"""L3 멀티모달(VL) 인프라 단위테스트 — 비전 라우팅·VL 모델 해석·이미지 캐시 키·provider 스루.

PR1(L3 계약 확장): `requires_vision` 라우팅, `ModelFamily.VISION`→qwen3-vl 매트릭스, 캐시 키의
이미지 다이제스트(하위호환), OllamaProvider images 스루, AnthropicProvider 비전 거부,
pipeline.generate images 전달·이미지별 캐시 분리. 전부 hermetic(가짜 client/provider).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.providers.anthropic import AnthropicProvider
from whymath_backend.l3.providers.ollama import OllamaProvider
from whymath_backend.l3.router import Router, cache_key_for, resolve_model


def _vision_request() -> RoutingRequest:
    return RoutingRequest(
        task_type="extract",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        requires_vision=True,
    )


def _text_decision() -> RoutingDecision:
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=ModelFamily.GENERAL,
        local_model=LocalModelTier.FAST,
        est_latency_ms=1010,
    )


# ── 라우팅: requires_vision → LOCAL/VISION/FAST/sync ──
def test_vision_request_routes_to_local_vision_fast() -> None:
    decision = Router().route(_vision_request())
    assert decision.cost_tier == CostTier.LOCAL.value
    assert decision.local_family == ModelFamily.VISION.value
    assert decision.local_model == LocalModelTier.FAST.value
    assert decision.mode == "sync"  # 비전은 동기 즉답


def test_resolve_vision_model_is_qwen3_vl() -> None:
    # 명시 핀(`:latest` 드리프트 회피) — pull_ocr_models.sh·런북과 일치(2026-06-23 태그 확인).
    assert resolve_model(ModelFamily.VISION, LocalModelTier.FAST) == "qwen3-vl:8b"


# ── 캐시 키: 이미지 다이제스트 (하위호환) ──
def test_cache_key_unchanged_without_image_digest() -> None:
    """image_digest=None(텍스트)이면 키가 기존과 100% 동일(하위호환)."""
    d = _text_decision()
    assert cache_key_for("p", "s", d) == cache_key_for("p", "s", d, image_digest=None)


def test_cache_key_differs_with_image_digest() -> None:
    """이미지 다이제스트가 있으면 키가 달라지고, 같은 다이제스트는 같은 키."""
    d = _text_decision()
    base = cache_key_for("p", "s", d)
    with_img = cache_key_for("p", "s", d, image_digest="abc123")
    assert with_img != base
    assert with_img == cache_key_for("p", "s", d, image_digest="abc123")
    assert with_img != cache_key_for("p", "s", d, image_digest="def456")


# ── OllamaProvider: images 스루 + VL 모델 해석 ──
class _FakeOllamaClient:
    """ollama client 가짜 — generate 호출 인자를 기록(images 포함)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str,
        images: Sequence[str] | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> Any:
        self.calls.append({"model": model, "images": images})
        return {"response": "x^{2}"}

    async def list(self) -> Any:
        return {"models": []}


async def test_ollama_passes_images_and_resolves_vl_model() -> None:
    client = _FakeOllamaClient()
    provider = OllamaProvider(client=client)
    decision = Router().route(_vision_request())  # LOCAL/VISION/FAST
    out = await provider.generate("이 수식을 LaTeX로", "수식 추출", decision, images=["BASE64IMG"])
    assert out.text == "x^{2}"
    assert client.calls[0]["model"] == "qwen3-vl:8b"  # VISION/FAST → qwen3-vl:8b(명시 핀)
    assert client.calls[0]["images"] == ["BASE64IMG"]


async def test_ollama_text_call_omits_images_kwarg() -> None:
    """텍스트 호출(images=None)은 images 인자 없이 호출된다(하위호환·기본 None 기록)."""
    client = _FakeOllamaClient()
    await OllamaProvider(client=client).generate("p", "s", _text_decision())
    assert client.calls[0]["images"] is None


# ── AnthropicProvider: 비전 거부 ──
async def test_anthropic_rejects_images() -> None:
    cloud_decision = RoutingDecision(cost_tier=CostTier.CLOUD_MID, est_latency_ms=3000)
    with pytest.raises(RuntimeError, match="멀티모달"):
        await AnthropicProvider().generate("p", "s", cloud_decision, images=["IMG"])


# ── pipeline.generate: images 전달 + 이미지별 캐시 분리 ──
class _RecordingProvider:
    """provider 가짜 — generate 호출 수와 받은 images를 기록."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_images: Sequence[str] | None = None

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision, *, images: Any = None
    ) -> GenerationResult:
        self.calls += 1
        self.last_images = images
        return GenerationResult("LATEX_OUT")


async def test_pipeline_forwards_images_and_caches_by_image() -> None:
    provider = _RecordingProvider()
    cache = InMemoryCache()
    trace = RecordingTraceSink()
    req = _vision_request()

    # 1차: 캐시 미스 → provider 호출(images 전달)
    r1 = await pipeline.generate(
        req, "p", "s", provider=provider, cache=cache, trace=trace, images=["IMG_A"]
    )
    assert r1.text == "LATEX_OUT"
    assert provider.last_images == ["IMG_A"]
    assert provider.calls == 1

    # 2차: 같은 이미지 → 캐시 적중(provider 재호출 없음)
    r2 = await pipeline.generate(
        req, "p", "s", provider=provider, cache=cache, trace=trace, images=["IMG_A"]
    )
    assert r2.cache_hit is True
    assert provider.calls == 1

    # 3차: 다른 이미지 → 다른 캐시 키 → provider 재호출
    await pipeline.generate(
        req, "p", "s", provider=provider, cache=cache, trace=trace, images=["IMG_B"]
    )
    assert provider.calls == 2


def test_image_digest_none_for_empty() -> None:
    """_image_digest: None/빈 목록은 None(텍스트 캐시 키 불변)."""
    assert pipeline._image_digest(None) is None
    assert pipeline._image_digest([]) is None
    assert pipeline._image_digest(["x"]) is not None
