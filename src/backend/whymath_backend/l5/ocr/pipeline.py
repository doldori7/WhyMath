"""OCR 파이프라인 오케스트레이션 — ① 검출 → ② 라우팅 → ③ 인식 → ④ 조립·검증.

`run_ocr_pipeline`은 이미지 바이트를 받아 부품(`OcrComponents`)을 *순수 조율*해 구조
(`OcrResult`)를 만든다. 모델은 *전부 부품으로 주입*된다 — 여기서 전역 로드를 하지 않는다
(factory가 1회 구성, app.state 보관). 그래서 테스트는 가짜 부품으로 라이브 모델 없이
오케스트레이션 글루를 검증한다.

흐름:
  1. 이미지 바이트 디코드(numpy 배열) — Pillow 지연 import(미설치면 명확한 RuntimeError).
  2. `detector.detect(image)` → 검출 영역.
  3. `router.route(regions)` → 텍스트/수식 유형 부여.
  4. 영역별 인식 — 수식은 `math_recognizer`, 텍스트는 `text_recognizer`.
  5. `assemble_regions(recognized)` → 읽기순 정렬·SymPy 검증·집계 → `OcrResult`.

7계층 경계: L5 인식만 책임진다. L4 코치 조합은 *호출자*(2-콜 핸드오프)가 한다(api/ocr.py
순수 엔드포인트·schema/ocr.py 매핑 docstring).
"""

from __future__ import annotations

from typing import Any

from whymath_backend.l5.ocr.assemble import assemble_regions
from whymath_backend.l5.ocr.factory import OcrComponents
from whymath_backend.l5.ocr.recognize import RecognizedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import OcrPagesResult, OcrResult


async def run_ocr_pipeline(image_bytes: bytes, *, components: OcrComponents) -> OcrResult:
    """이미지 바이트 → OCR 구조(`OcrResult`). 부품 주입·순수 오케스트레이션(전역 로드 0).

    Args:
        image_bytes: 인코딩된 이미지 바이트(PNG/JPEG 등). 빈 바이트는 빈 `OcrResult`.
        components: factory가 구성한 부품 묶음(검출기·라우터·인식기 2종). 모델은 부품
            내부 지연 로드(이 함수는 결선만).

    Returns:
        읽기순 영역 + 집계 뷰를 채운 `OcrResult`(구조). 검출 0이면 빈 `OcrResult`.
    """
    if not image_bytes:
        return OcrResult()

    image = _decode_image(image_bytes)

    # ① 검출 — 위치(경계 상자) 후보.
    detected = components.detector.detect(image)
    if not detected:
        return OcrResult()

    # ② 라우팅 — 텍스트/수식 유형 부여.
    routed = components.router.route(detected)

    # ③ 인식 — 수식은 수식 인식기, 텍스트는 텍스트 인식기로.
    # 수식은 `arecognize`를 await한다 — 동기 백엔드(RapidLatex·TexTeller)는 기본 구현이 동기
    # recognize를 감싸 즉시 반환하고, L3 라우터 경유 백엔드(Qwen3-VL)만 실제 비동기 인식을 한다.
    recognized: list[RecognizedRegion] = []
    for region in routed:
        if region.content_type == ContentType.수식:
            recognized.append(await components.math_recognizer.arecognize(region, image))
        else:
            recognized.append(components.text_recognizer.recognize(region, image))

    # ④ 조립·검증 — 읽기순 정렬·SymPy 왕복 검증·집계 → 구조.
    # 부품이 운반한 재확인 임계(ocr_min_confidence)를 넘겨 저신뢰 영역에 needs_review를 단다.
    return assemble_regions(recognized, review_threshold=components.review_threshold)


async def run_ocr_pipeline_pages(
    images: list[bytes], *, components: OcrComponents
) -> OcrPagesResult:
    """여러 장의 이미지 바이트 → 다중 페이지 OCR 구조(`OcrPagesResult`). 부품 주입·순수 조율.

    각 페이지를 `run_ocr_pipeline`로 *독립* 인식해 업로드(페이지) 순서대로 모으고, 신뢰도
    롤업을 계산한다(`OcrPagesResult.from_pages`). L5는 페이지별 인식만 책임지고, 페이지
    합성(코치 핸드오프)은 호출자/오케스트레이션 몫이다(7계층 경계).

    Args:
        images: 페이지 순서대로의 인코딩된 이미지 바이트 목록. 빈 목록은 빈
            `OcrPagesResult`(page_count=0). 빈 바이트 페이지는 빈 `OcrResult`로 담긴다.
        components: factory가 구성한 부품 묶음(단일 파이프라인과 공유).

    Returns:
        페이지별 `OcrResult`(`pages`) + 신뢰도 롤업을 채운 `OcrPagesResult`(구조).
    """
    pages = [await run_ocr_pipeline(image_bytes, components=components) for image_bytes in images]
    return OcrPagesResult.from_pages(pages)


def _decode_image(image_bytes: bytes) -> Any:
    """이미지 바이트를 numpy 배열(RGB)로 디코드 — Pillow 지연 import(미설치면 명확한 RuntimeError).

    무거운 의존(Pillow·numpy)은 *여기서 지연 import*한다 — 패키지 import·기본 경로(OCR
    비활성)에서 로드되지 않는다. 미설치면 조용한 폴백 없이 RuntimeError(CLAUDE.md).
    """
    try:
        import io

        import numpy as np
        from PIL import Image
    except ImportError as exc:  # 조용한 폴백 금지 — 명확히 보고
        raise RuntimeError(
            "OCR 이미지 디코드에는 Pillow·numpy가 필요합니다 — "
            '`pip install -e ".[ocr]"`로 설치하세요(조용한 폴백 없음).'
        ) from exc
    with Image.open(io.BytesIO(image_bytes)) as img:
        return np.asarray(img.convert("RGB"))
