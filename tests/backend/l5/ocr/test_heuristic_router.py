"""`HeuristicRouter`·분류 순수 함수 단위테스트 — 텍스트/수식 휴리스틱(모델 0).

검증: 텍스트 힌트가 있으면 기호 밀도·한글 비율로, 없으면 박스 종횡비로 분류한다.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.detect import DetectedRegion
from whymath_backend.l5.ocr.router import (
    HeuristicRouter,
    RoutedRegion,
    classify_by_geometry,
    classify_by_text,
)
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox


def _detected(
    x: float = 0, y: float = 0, w: float = 100, h: float = 20, *, hint: str = ""
) -> DetectedRegion:
    """검출 영역 헬퍼."""
    return DetectedRegion(bbox=BBox(x=x, y=y, width=w, height=h), confidence=0.9, text_hint=hint)


def test_classify_by_text_hangul_prose_is_text() -> None:
    """한글 산문은 텍스트."""
    assert classify_by_text("두 점을 지나는 직선의 기울기를 구한다") == ContentType.텍스트


def test_classify_by_text_latex_token_is_math() -> None:
    """LaTeX 토큰(\\frac 등)이 있으면 수식."""
    assert classify_by_text("x = \\frac{1}{2}") == ContentType.수식


def test_classify_by_text_symbol_dense_is_math() -> None:
    """수학 기호 밀도가 높으면 수식."""
    assert classify_by_text("x^2 + 2*x - 1 = 0") == ContentType.수식


def test_classify_by_text_empty_is_text() -> None:
    """빈 문자열은 보수적으로 텍스트."""
    assert classify_by_text("") == ContentType.텍스트


def test_classify_by_geometry_wide_is_text() -> None:
    """매우 가로로 긴 박스(종횡비>8)는 텍스트 산문 라인."""
    assert classify_by_geometry(BBox(x=0, y=0, width=900, height=20)) == ContentType.텍스트


def test_classify_by_geometry_square_is_math() -> None:
    """정사각형에 가까운 박스(종횡비 작음)는 수식."""
    assert classify_by_geometry(BBox(x=0, y=0, width=40, height=30)) == ContentType.수식


def test_classify_by_geometry_zero_area_is_text() -> None:
    """면적 0 박스는 텍스트(보수적)."""
    assert classify_by_geometry(BBox(x=0, y=0, width=0, height=0)) == ContentType.텍스트


def test_router_uses_text_hint_when_present() -> None:
    """힌트가 있으면 기하 대신 텍스트 분류를 쓴다(가로로 긴 수식이라도 기호 밀도로 수식)."""
    # 가로로 길어 기하만 보면 텍스트지만, 힌트가 기호 밀집이라 수식으로 분류돼야 한다.
    region = _detected(w=900, h=20, hint="a + b - c = d * e")
    routed = HeuristicRouter().route([region])
    assert len(routed) == 1
    assert routed[0].content_type == ContentType.수식
    assert routed[0].text_hint == "a + b - c = d * e"


def test_router_falls_back_to_geometry_without_hint() -> None:
    """힌트가 없으면 박스 기하로 분류한다."""
    region = _detected(w=900, h=20)  # 가로로 김 → 텍스트.
    routed = HeuristicRouter().route([region])
    assert routed[0].content_type == ContentType.텍스트


def test_router_preserves_confidence() -> None:
    """검출 신뢰도가 RoutedRegion으로 전달된다."""
    routed = HeuristicRouter().route([_detected(hint="안녕하세요 수학")])
    assert isinstance(routed[0], RoutedRegion)
    assert routed[0].confidence == 0.9
