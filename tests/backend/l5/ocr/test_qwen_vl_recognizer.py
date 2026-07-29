"""L5 OCR Phase C-PR2 — QwenVlRecognizer(L3 라우터 경유 멀티모달) + async 인식 브리지.

QwenVlRecognizer.arecognize는 *실 pipeline.generate*를 통과시켜 검증한다(가짜 provider 주입·
InMemoryCache·RecordingTraceSink) — 라우터가 비전 결정을 내리고 provider가 이미지를 받는지,
결과 LaTeX가 정규화되는지. 동기 백엔드의 기본 arecognize 위임, 미주입 가드, 동기 거부도 검증.
실 Qwen3-VL 모델은 미사용(hermetic).
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from PIL import Image
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, ModelFamily, RoutingDecision
from whymath_backend.l5.ocr.detect import DetectedRegion
from whymath_backend.l5.ocr.factory import OcrComponents
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline
from whymath_backend.l5.ocr.recognize import (
    QwenVlRecognizer,
    RecognizedRegion,
    TexTellerRecognizer,
    _BaseMathRecognizer,
)
from whymath_backend.l5.ocr.router import RoutedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox


def _math_region() -> RoutedRegion:
    return RoutedRegion(bbox=BBox(x=0, y=0, width=50, height=20), content_type=ContentType.수식)


def _white_image() -> Image.Image:
    return Image.new("RGB", (50, 20), "white")


class _FakeVisionProvider:
    """L3 provider 가짜 — generate가 받은 images·decision을 기록하고 고정 LaTeX 반환."""

    def __init__(self) -> None:
        self.received_images: Any = None
        self.decision: Any = None

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision, *, images: Any = None
    ) -> GenerationResult:
        self.received_images = images
        self.decision = decision
        return GenerationResult("$x^{2}$")


async def test_qwen_vl_arecognize_routes_vision_and_passes_image() -> None:
    """arecognize → 실 pipeline.generate: 라우터 비전 결정 + provider 이미지 수신 + LaTeX 정규화."""
    provider = _FakeVisionProvider()
    rec = QwenVlRecognizer(provider=provider, cache=InMemoryCache(), trace=RecordingTraceSink())
    out = await rec.arecognize(_math_region(), _white_image())

    assert out.content_type == ContentType.수식.value
    assert out.latex == "x^{2}"  # _normalize_latex가 둘러싼 $ 제거
    # provider가 base64 이미지 1장을 받았다(멀티모달 전달).
    assert provider.received_images is not None
    assert len(provider.received_images) == 1
    assert isinstance(provider.received_images[0], str) and provider.received_images[0]
    # 라우터가 비전 단축 경로로 LOCAL/VISION 결정을 내렸다.
    assert provider.decision.local_family == ModelFamily.VISION.value


async def test_qwen_vl_requires_l3_deps() -> None:
    """provider/cache/trace 미주입이면 arecognize는 명확한 RuntimeError(직접 Ollama 금지)."""
    rec = QwenVlRecognizer()  # 의존 미주입
    with pytest.raises(RuntimeError, match="provider"):
        await rec.arecognize(_math_region(), _white_image())


def test_qwen_vl_sync_recognize_crop_rejected() -> None:
    """동기 _recognize_crop은 거부 — Qwen3-VL은 비동기 arecognize 전용."""
    rec = QwenVlRecognizer()
    with pytest.raises(RuntimeError, match="비동기"):
        rec._recognize_crop(object())


async def test_base_arecognize_delegates_to_sync() -> None:
    """동기 백엔드(TexTeller 등)의 기본 arecognize는 동기 recognize를 감싼다(오버라이드 불요)."""
    rec = TexTellerRecognizer(engine=lambda crop: "$y+1$")
    out = await rec.arecognize(_math_region(), _white_image())
    assert out.latex == "y+1"


# ── 파이프라인 async 브리지: run_ocr_pipeline가 arecognize를 await ──
class _FakeDetector:
    def detect(self, image: Any) -> list[DetectedRegion]:
        return [DetectedRegion(bbox=BBox(x=0, y=0, width=50, height=20))]


class _FakeRouter:
    def route(self, regions: list[DetectedRegion]) -> list[RoutedRegion]:
        return [_math_region()]


class _DummyTextRecognizer:
    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        return RecognizedRegion(bbox=region.bbox, content_type=ContentType.텍스트, latex="t")


class _AsyncOnlyMathRecognizer(_BaseMathRecognizer):
    """동기 경로를 쓰면 실패 — 파이프라인이 arecognize(비동기)를 쓰는지 증명용."""

    def _recognize_crop(self, crop: Any) -> str:
        raise AssertionError("동기 recognize 경로가 호출됨 — 파이프라인은 arecognize를 써야 한다")

    async def arecognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        return RecognizedRegion(
            bbox=region.bbox, content_type=ContentType.수식, latex="async_ok", confidence=1.0
        )


async def test_pipeline_awaits_arecognize_for_math() -> None:
    """run_ocr_pipeline는 수식 인식에 arecognize(비동기)를 await한다(동기 경로 미사용)."""
    buffer = io.BytesIO()
    _white_image().save(buffer, format="PNG")
    components = OcrComponents(
        detector=_FakeDetector(),
        router=_FakeRouter(),
        text_recognizer=_DummyTextRecognizer(),
        math_recognizer=_AsyncOnlyMathRecognizer(),
    )
    result = await run_ocr_pipeline(buffer.getvalue(), components=components)
    assert any(r.latex == "async_ok" for r in result.regions)
