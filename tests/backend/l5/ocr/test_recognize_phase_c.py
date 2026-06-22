"""L5 OCR Phase C 인식기 단위테스트 — TexTeller(가짜 엔진) + 한국어 rec 모델 wiring.

실 모델(TexTeller 약 1.2GB·transformers·torch)은 Phaiakes9 검증이라 CI에서는 *가짜 엔진 주입*
으로 hermetic 검증한다(crop→LaTeX 콜러블). 한국어 rapidocr rec 모델 경로 구성은 순수 함수
`_rapidocr_rec_kwargs`로 직접 검증한다(rapidocr 미설치 무관).
"""

from __future__ import annotations

import pytest

from whymath_backend.l5.ocr.recognize import (
    TexTellerRecognizer,
    _rapidocr_rec_kwargs,
)
from whymath_backend.l5.ocr.router import RoutedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox


def _math_region() -> RoutedRegion:
    return RoutedRegion(bbox=BBox(x=0, y=0, width=60, height=20), content_type=ContentType.수식)


def test_texteller_uses_injected_engine_and_normalizes() -> None:
    """주입한 가짜 엔진(crop→'$x^{2}$')의 결과를 정규화해 RecognizedRegion으로 조립한다."""
    rec = TexTellerRecognizer(engine=lambda crop: "$x^{2}$")
    out = rec.recognize(_math_region(), image=object())
    assert out.content_type == ContentType.수식.value
    assert out.latex == "x^{2}"  # _normalize_latex가 둘러싼 $ 제거
    assert out.confidence == pytest.approx(1.0)  # 라우팅 신뢰도 출발값(비어있지 않음)


def test_texteller_empty_result_demotes_confidence() -> None:
    """엔진이 빈 문자열을 주면 신뢰도를 0으로 강등한다(인식 실패)."""
    rec = TexTellerRecognizer(engine=lambda crop: "")
    out = rec.recognize(_math_region(), image=object())
    assert out.latex == ""
    assert out.confidence == 0.0


def test_texteller_missing_deps_raises_runtimeerror() -> None:
    """엔진 미주입 + transformers/torch 미설치 → 명확한 RuntimeError(조용한 폴백 없음)."""
    rec = TexTellerRecognizer()  # 엔진 미주입 → 지연 로드 시도
    with pytest.raises(RuntimeError, match="transformers"):
        rec.recognize(_math_region(), image=object())


def test_korean_rec_kwargs_when_korean_and_model_dir() -> None:
    """한국어 + model_dir이면 한국어 PP-OCRv4 rec 모델·사전 경로를 구성한다."""
    kwargs = _rapidocr_rec_kwargs("korean", "/models/korean")
    assert kwargs["rec_model_path"].endswith("korean_PP-OCRv4_rec.onnx")
    assert kwargs["rec_keys_path"].endswith("korean_dict.txt")
    assert "/models/korean" in kwargs["rec_model_path"]
    # 'ko' 약어도 동일하게 인식한다.
    assert _rapidocr_rec_kwargs("ko", "/m") != {}


def test_korean_rec_kwargs_empty_when_no_model_dir_or_other_language() -> None:
    """model_dir이 없거나 한국어가 아니면 빈 dict(rapidocr 기본 모델)."""
    assert _rapidocr_rec_kwargs("korean", "") == {}  # 경로 없음 → 기본
    assert _rapidocr_rec_kwargs("en", "/models/korean") == {}  # 타 언어 → 기본
