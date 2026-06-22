"""`merge_text_and_math_regions` 순수 함수 단위테스트 — IoU 병합 규칙(모델·I/O 0).

검증 규칙(router.py docstring):
  - 수식 박스 좌표가 이긴다(전부 보존).
  - 수식 박스에 ≥50% 들어간 텍스트 박스는 버린다(중복 검출).
  - 겹치지 않는 텍스트 박스는 유지한다.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.router import RoutedRegion, merge_text_and_math_regions
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox


def _text(x: float, y: float, w: float, h: float) -> RoutedRegion:
    """텍스트 RoutedRegion 헬퍼."""
    return RoutedRegion(
        bbox=BBox(x=x, y=y, width=w, height=h),
        content_type=ContentType.텍스트,
        text_hint="t",
    )


def _math(x: float, y: float, w: float, h: float) -> RoutedRegion:
    """수식 RoutedRegion 헬퍼."""
    return RoutedRegion(bbox=BBox(x=x, y=y, width=w, height=h), content_type=ContentType.수식)


def test_contained_text_dropped() -> None:
    """수식 박스에 완전히 들어간 텍스트 박스는 버려진다(중복)."""
    math_box = _math(0, 0, 100, 100)
    text_box = _text(10, 10, 20, 20)  # 수식 박스 안에 100% 포함.
    merged = merge_text_and_math_regions([text_box], [math_box])
    assert len(merged) == 1
    assert merged[0].content_type == ContentType.수식


def test_non_overlapping_text_kept() -> None:
    """수식 박스와 전혀 겹치지 않는 텍스트는 유지된다."""
    math_box = _math(0, 0, 50, 50)
    text_box = _text(200, 200, 30, 20)  # 완전히 분리.
    merged = merge_text_and_math_regions([text_box], [math_box])
    assert len(merged) == 2
    # 수식 박스가 먼저(좌표 우선), 텍스트가 뒤.
    assert merged[0].content_type == ContentType.수식
    assert merged[1].content_type == ContentType.텍스트


def test_math_coords_win() -> None:
    """모든 수식 박스가 그대로 결과에 보존된다(좌표 우선)."""
    math_boxes = [_math(0, 0, 40, 40), _math(100, 0, 40, 40)]
    merged = merge_text_and_math_regions([], math_boxes)
    assert len(merged) == 2
    assert {r.content_type for r in merged} == {ContentType.수식}
    # 좌표가 입력 그대로 보존됐다.
    assert merged[0].bbox.x == 0
    assert merged[1].bbox.x == 100


def test_partial_overlap_below_threshold_kept() -> None:
    """수식 박스에 50% 미만만 겹친 텍스트는 유지된다(중복 아님)."""
    math_box = _math(0, 0, 100, 100)
    # 텍스트 박스 면적 100×100=10000, 교집합 = (100-90)*(100)=1000 → 10% < 50%.
    text_box = _text(90, 0, 100, 100)
    merged = merge_text_and_math_regions([text_box], [math_box])
    assert len(merged) == 2


def test_overlap_at_threshold_dropped() -> None:
    """정확히 50% 들어간 텍스트는 버려진다(>= 임계)."""
    math_box = _math(0, 0, 100, 100)
    # 텍스트 면적 100×100, 교집합 = 50*100 = 5000 → 정확히 50%.
    text_box = _text(50, 0, 100, 100)
    merged = merge_text_and_math_regions([text_box], [math_box])
    assert len(merged) == 1
    assert merged[0].content_type == ContentType.수식


def test_empty_inputs_safe() -> None:
    """빈 입력은 빈 목록(안전)."""
    assert merge_text_and_math_regions([], []) == []


def test_custom_threshold() -> None:
    """containment_threshold를 낮추면 더 적은 겹침으로도 텍스트가 버려진다."""
    math_box = _math(0, 0, 100, 100)
    text_box = _text(90, 0, 100, 100)  # 10% 겹침.
    # 임계 0.05 → 10% > 5%라 버려진다.
    merged = merge_text_and_math_regions([text_box], [math_box], containment_threshold=0.05)
    assert len(merged) == 1
