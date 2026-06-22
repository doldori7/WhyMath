"""POST /v1/ocr 통합테스트 — 실 모델([ocr] extra)로 라이브 인식. 기본 skip(@integration).

CI(라이브 모델·extra 미설치)에서는 conftest 게이트로 자동 skip된다. Phaiakes9에서
`WHYMATH_RUN_INTEGRATION=1` + `pip install -e ".[dev,ocr]"`로 켜고 돌린다. 합성 이미지에
간단한 수식을 그려 파이프라인이 구조(OcrResult)를 만드는지 확인한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l5.ocr.factory import build_ocr_components
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline

pytestmark = pytest.mark.integration


def _synthetic_equation_png() -> bytes:
    """간단한 수식("2+2=4")을 흰 배경에 그린 PNG 바이트(Pillow 필요·[ocr] extra)."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 60), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "2 + 2 = 4", fill="black")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_live_pipeline_produces_structure() -> None:
    """실 모델로 합성 수식 이미지를 인식해 구조(OcrResult)를 만든다(내용 정확도는 비단언)."""
    settings = Settings(ocr_enabled=True)
    components = build_ocr_components(settings)
    result = await run_ocr_pipeline(_synthetic_equation_png(), components=components)
    # 인식 정확도는 환경 의존이라 단언하지 않는다 — *구조*가 나오는지(영역·신뢰도)만 본다.
    assert result is not None
    assert isinstance(result.overall_confidence, float)
