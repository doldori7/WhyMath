"""MfdDetector(Phase B·수식 영역 검출) 단위테스트 — 가짜 백엔드로 hermetic 검증.

rapid-layout(실 모델·ONNX)은 주입 가능한 `layout_engine`으로 대체하고, 내부 텍스트 검출기도
가짜로 주입한다. 검증 핵심:
  - 수식 클래스(Equation/formula…)만 `_MathDetectedRegion`으로 만들고 좌표를 BBox로 환산.
  - 텍스트 검출기 라인 박스는 그대로 보존(수식과 함께 반환).
  - **AGPL model_type(yolov8*/doclayout*) 거부**(결정 우선순위 #2) + 미지원 model_type 거부.
  - rapid-layout 미설치 시 명확한 RuntimeError(조용한 폴백 없음).
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.l5.ocr.detect import (
    DetectedRegion,
    MfdDetector,
    _MathDetectedRegion,
)
from whymath_backend.schema.ocr import BBox


class _FakeTextDetector:
    """내부 텍스트 검출기 대체 — 고정 라인 박스를 돌려준다(rapidocr 미사용)."""

    def __init__(self, regions: list[DetectedRegion]) -> None:
        self._regions = regions

    def detect(self, image: Any) -> list[DetectedRegion]:
        return list(self._regions)


class _FakeLayoutOutput:
    """rapid-layout 출력 대체 — boxes(코너)·class_names·scores 속성만 갖는다."""

    def __init__(self, boxes: list[list[float]], class_names: list[str], scores: list[float]):
        self.boxes = boxes
        self.class_names = class_names
        self.scores = scores


class _FakeLayoutEngine:
    """rapid-layout 엔진 대체 — 호출 시 고정 출력을 돌려주는 콜러블."""

    def __init__(self, output: _FakeLayoutOutput) -> None:
        self._output = output

    def __call__(self, image: Any) -> _FakeLayoutOutput:
        return self._output


def _text_region(x: float) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=0, width=40, height=12), text_hint="지문")


def test_only_formula_class_becomes_math_region() -> None:
    """레이아웃 출력 중 수식 클래스(Equation)만 _MathDetectedRegion이 되고 좌표를 환산한다."""
    layout = _FakeLayoutEngine(
        _FakeLayoutOutput(
            boxes=[[10, 20, 60, 50], [0, 100, 200, 130], [5, 200, 80, 240]],
            class_names=["Equation", "Text", "Table"],  # 수식만 채택
            scores=[0.91, 0.99, 0.88],
        )
    )
    detector = MfdDetector(
        model_type="pp_layout_cdla",
        text_detector=_FakeTextDetector([]),
        layout_engine=layout,
    )
    regions = detector.detect(object())
    math = [r for r in regions if isinstance(r, _MathDetectedRegion)]
    assert len(math) == 1  # Text/Table은 수식이 아니므로 제외
    assert math[0].bbox == BBox(x=10, y=20, width=50, height=30)  # [x1,y1,x2,y2]→x/y/w/h
    assert math[0].confidence == pytest.approx(0.91)


def test_text_lines_preserved_alongside_formula() -> None:
    """내부 텍스트 검출기의 라인 박스는 보존되고, 수식 박스가 함께 반환된다."""
    layout = _FakeLayoutEngine(
        _FakeLayoutOutput(boxes=[[10, 20, 60, 50]], class_names=["formula"], scores=[0.8])
    )
    detector = MfdDetector(
        model_type="pp_doc_layoutv3",
        text_detector=_FakeTextDetector([_text_region(0), _text_region(100)]),
        layout_engine=layout,
    )
    regions = detector.detect(object())
    text = [r for r in regions if not isinstance(r, _MathDetectedRegion)]
    math = [r for r in regions if isinstance(r, _MathDetectedRegion)]
    assert len(text) == 2  # 텍스트 라인 보존
    assert len(math) == 1  # 'formula' 클래스 채택(대소문자 무관)


def test_formula_alias_match_is_case_insensitive() -> None:
    """클래스 라벨은 대소문자 무관으로 별칭 매칭한다(CDLA 'Equation' vs 'EQUATION')."""
    layout = _FakeLayoutEngine(
        _FakeLayoutOutput(boxes=[[1, 2, 3, 4]], class_names=["EQUATION"], scores=[0.7])
    )
    detector = MfdDetector(text_detector=_FakeTextDetector([]), layout_engine=layout)
    assert len([r for r in detector.detect(object()) if isinstance(r, _MathDetectedRegion)]) == 1


@pytest.mark.parametrize("agpl_model", ["yolov8n_layout_paper", "doclayout_yolo_docstructbench"])
def test_agpl_model_type_rejected(agpl_model: str) -> None:
    """ultralytics 기반(yolov8*/doclayout*) model_type은 AGPL이라 RuntimeError로 거부한다."""
    with pytest.raises(RuntimeError, match="AGPL"):
        MfdDetector(model_type=agpl_model)


def test_unknown_model_type_rejected() -> None:
    """PP 계열 화이트리스트에 없는 model_type은 RuntimeError(조용한 폴백 없음)."""
    with pytest.raises(RuntimeError, match="PP 계열"):
        MfdDetector(model_type="some_unknown_model")


def test_missing_rapid_layout_raises_runtimeerror() -> None:
    """layout_engine 미주입 + rapid-layout 미설치 → 명확한 RuntimeError(조용한 폴백 없음)."""
    detector = MfdDetector(text_detector=_FakeTextDetector([]))  # layout_engine 없음 → 지연 로드
    with pytest.raises(RuntimeError, match="rapid-layout"):
        detector.detect(object())
