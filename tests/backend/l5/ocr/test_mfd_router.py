"""MfdRouter(Phase B) 단위테스트 — isinstance 분기 + 순수 병합(merge_text_and_math_regions).

MfdDetector가 주는 텍스트 라인 박스(`DetectedRegion`)와 수식 박스(`_MathDetectedRegion`)를
MfdRouter가 가른 뒤 병합한다. 검증 핵심: 수식 박스 안에 ≥50% 들어간 텍스트 라인은 버려지고
(중복), 겹치지 않는 텍스트만 텍스트로 남으며, 수식 박스는 수식으로 유지된다.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.detect import DetectedRegion, _MathDetectedRegion
from whymath_backend.l5.ocr.router import MfdRouter
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox


def test_text_inside_formula_dropped_formula_kept() -> None:
    """수식 박스에 포함된 텍스트 라인은 버리고, 겹치지 않는 텍스트와 수식 박스는 유지한다."""
    formula = _MathDetectedRegion(bbox=BBox(x=0, y=0, width=100, height=40), confidence=0.9)
    text_inside = DetectedRegion(bbox=BBox(x=10, y=10, width=30, height=10), text_hint="frac")
    text_outside = DetectedRegion(bbox=BBox(x=0, y=100, width=50, height=12), text_hint="지문")

    routed = MfdRouter().route([text_inside, formula, text_outside])

    types = sorted(r.content_type for r in routed)
    assert len(routed) == 2  # 포함된 텍스트 1개 제거(중복) → 수식 1 + 바깥 텍스트 1
    assert ContentType.수식.value in types
    assert ContentType.텍스트.value in types
    # 살아남은 텍스트는 수식 박스 바깥의 그것이다.
    kept_text = next(r for r in routed if r.content_type == ContentType.텍스트.value)
    assert kept_text.bbox == BBox(x=0, y=100, width=50, height=12)
    # 수식 박스 좌표는 그대로 보존된다.
    kept_math = next(r for r in routed if r.content_type == ContentType.수식.value)
    assert kept_math.bbox == BBox(x=0, y=0, width=100, height=40)


def test_no_formula_keeps_all_text() -> None:
    """수식 박스가 없으면 모든 텍스트 라인이 텍스트로 유지된다(병합 대상 없음)."""
    regions: list[DetectedRegion] = [
        DetectedRegion(bbox=BBox(x=0, y=0, width=40, height=12), text_hint="가"),
        DetectedRegion(bbox=BBox(x=0, y=20, width=40, height=12), text_hint="나"),
    ]
    routed = MfdRouter().route(regions)
    assert len(routed) == 2
    assert all(r.content_type == ContentType.텍스트.value for r in routed)


def test_only_formula_returns_math() -> None:
    """텍스트 없이 수식 박스만 있으면 수식 하나만 반환한다."""
    formula = _MathDetectedRegion(bbox=BBox(x=5, y=5, width=80, height=30), confidence=0.8)
    routed = MfdRouter().route([formula])
    assert len(routed) == 1
    assert routed[0].content_type == ContentType.수식.value
