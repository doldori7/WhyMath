"""`run_ocr_pipeline` 단위테스트 — 가짜 부품으로 오케스트레이션 글루 검증(모델·I/O 0).

라이브 모델·이미지 디코드 없음: 가짜 Detector/Router/TextRecognizer/MathRecognizer를
`OcrComponents`로 주입하고, 디코드를 monkeypatch해 부품 결선·읽기순 조립을 검증한다.
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.l5.ocr import pipeline as pipeline_mod
from whymath_backend.l5.ocr.detect import DetectedRegion
from whymath_backend.l5.ocr.factory import OcrComponents
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline
from whymath_backend.l5.ocr.recognize import RecognizedRegion
from whymath_backend.l5.ocr.router import RoutedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox, OcrResult


class _FakeDetector:
    """주어진 검출 영역을 그대로 돌려주는 가짜(이미지 무시)."""

    def __init__(self, regions: list[DetectedRegion]) -> None:
        self._regions = regions

    def detect(self, image: Any) -> list[DetectedRegion]:
        return self._regions


class _FakeRouter:
    """검출 영역을 text_hint 유무로 텍스트/수식 분류(휴리스틱 없이 결정론)."""

    def route(self, regions: list[DetectedRegion]) -> list[RoutedRegion]:
        routed: list[RoutedRegion] = []
        for region in regions:
            # hint에 '='가 있으면 수식으로 보낸다(테스트 결정론).
            ctype = ContentType.수식 if "=" in region.text_hint else ContentType.텍스트
            routed.append(
                RoutedRegion(
                    bbox=region.bbox,
                    content_type=ctype,
                    confidence=region.confidence,
                    text_hint=region.text_hint,
                )
            )
        return routed


class _FakeTextRecognizer:
    """텍스트 영역의 text_hint를 그대로 인식값으로 쓰는 가짜."""

    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        return RecognizedRegion(
            bbox=region.bbox,
            content_type=ContentType.텍스트,
            latex=region.text_hint,
            confidence=region.confidence,
        )


class _FakeMathRecognizer:
    """수식 영역의 text_hint를 LaTeX로 쓰는 가짜(crop·모델 없음)."""

    def _recognize_crop(self, crop: Any) -> str:
        return ""

    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        return RecognizedRegion(
            bbox=region.bbox,
            content_type=ContentType.수식,
            latex=region.text_hint,
            confidence=region.confidence,
        )

    async def arecognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        # 파이프라인이 arecognize를 await한다(PR2) — 동기 백엔드는 recognize를 감싼다.
        return self.recognize(region, image)


def _components(detected: list[DetectedRegion]) -> OcrComponents:
    """가짜 부품 묶음."""
    return OcrComponents(
        detector=_FakeDetector(detected),
        router=_FakeRouter(),
        text_recognizer=_FakeTextRecognizer(),
        math_recognizer=_FakeMathRecognizer(),  # type: ignore[arg-type]
    )


def _det(hint: str, x: float, y: float) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, width=50, height=20), confidence=0.9, text_hint=hint)


@pytest.fixture(autouse=True)
def _stub_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    """이미지 디코드를 stub — Pillow/numpy 없이 더미 객체 반환(부품이 이미지 무시)."""
    monkeypatch.setattr(pipeline_mod, "_decode_image", lambda _b: object())


async def test_empty_bytes_returns_empty() -> None:
    """빈 바이트는 빈 OcrResult(디코드·검출 미발생)."""
    result = await run_ocr_pipeline(b"", components=_components([]))
    assert isinstance(result, OcrResult)
    assert result.regions == []


async def test_no_detection_returns_empty() -> None:
    """검출 0이면 빈 OcrResult."""
    result = await run_ocr_pipeline(b"img", components=_components([]))
    assert result.regions == []


async def test_routes_text_and_math_to_correct_recognizers() -> None:
    """텍스트 영역은 텍스트 인식기, 수식 영역은 수식 인식기로 라우팅된다."""
    detected = [_det("계산하면", x=0, y=0), _det("x = 2", x=0, y=30)]
    result = await run_ocr_pipeline(b"img", components=_components(detected))
    # 읽기순(위→아래): 텍스트 먼저, 수식 뒤.
    assert len(result.regions) == 2
    assert result.regions[0].content_type == ContentType.텍스트
    assert result.regions[0].latex == "계산하면"
    assert result.regions[1].content_type == ContentType.수식
    assert result.regions[1].latex == "x = 2"


async def test_structured_output_has_steps_and_confidence() -> None:
    """파이프라인 산출은 구조 — solution_steps·집계 신뢰도가 채워진다."""
    detected = [_det("x = 1", x=0, y=0), _det("y = 2", x=0, y=30)]
    result = await run_ocr_pipeline(b"img", components=_components(detected))
    assert result.solution_steps == ["x = 1", "y = 2"]
    assert result.overall_confidence > 0.0
    assert result.plain_latex == "x = 1 y = 2"
