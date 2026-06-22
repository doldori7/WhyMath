"""schema/ocr.py 단위테스트 — extra forbid·유효 생성·step_types 길이 불변식·enum 직렬화.

설계: OCR 산출은 *구조*(표현 ≠ 의미). BBox·OcrRegion·OcrResult가 coach 핸드오프 매핑의
착지점이다(schema/ocr.py docstring).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import ContentType, StepType
from whymath_backend.schema.ocr import BBox, OcrRegion, OcrResult


def test_bbox_valid_construction_and_derived() -> None:
    """BBox 생성 + 파생 프로퍼티(x2·y2·area)."""
    bbox = BBox(x=10, y=20, width=30, height=40)
    assert bbox.x2 == 40
    assert bbox.y2 == 60
    assert bbox.area == 1200


def test_bbox_negative_rejected() -> None:
    """음수 좌표/크기는 거부(ge=0)."""
    with pytest.raises(ValidationError):
        BBox(x=-1, y=0, width=10, height=10)


def test_bbox_extra_forbidden() -> None:
    """알 수 없는 필드는 거부(extra=forbid)."""
    with pytest.raises(ValidationError):
        BBox(x=0, y=0, width=10, height=10, foo="bar")  # type: ignore[call-arg]


def test_ocr_region_valid() -> None:
    """OcrRegion 유효 생성 — 수식 영역."""
    region = OcrRegion(
        bbox=BBox(x=0, y=0, width=50, height=20),
        content_type=ContentType.수식,
        latex="x = 2",
        confidence=0.9,
        verified=True,
    )
    # use_enum_values=True → 값이 문자열로 보관되나 str-enum이라 비교 동일.
    assert region.content_type == ContentType.수식
    assert region.confidence == 0.9


def test_ocr_region_extra_forbidden() -> None:
    """OcrRegion 미지정 필드 거부."""
    with pytest.raises(ValidationError):
        OcrRegion(
            bbox=BBox(x=0, y=0, width=1, height=1),
            content_type=ContentType.텍스트,
            unknown=1,  # type: ignore[call-arg]
        )


def test_ocr_region_confidence_range() -> None:
    """신뢰도 0~1 범위 강제."""
    with pytest.raises(ValidationError):
        OcrRegion(
            bbox=BBox(x=0, y=0, width=1, height=1),
            content_type=ContentType.텍스트,
            confidence=1.5,
        )


def test_ocr_result_default_empty() -> None:
    """기본 OcrResult는 빈 구조."""
    result = OcrResult()
    assert result.regions == []
    assert result.solution_steps == []
    assert result.overall_confidence == 0.0


def test_ocr_result_step_types_length_ok() -> None:
    """solution_step_types 길이는 전이 수(steps-1)면 허용."""
    result = OcrResult(
        solution_steps=["a", "b", "c"],
        solution_step_types=[StepType.계산, StepType.검산],
    )
    assert len(result.solution_step_types) == 2


def test_ocr_result_step_types_empty_ok() -> None:
    """solution_step_types 빈 목록(미지정)도 허용."""
    result = OcrResult(solution_steps=["a", "b", "c"], solution_step_types=[])
    assert result.solution_step_types == []


def test_ocr_result_step_types_wrong_length_rejected() -> None:
    """전이 수와 다른 길이(0·전이수 둘 다 아님)는 거부."""
    with pytest.raises(ValidationError):
        OcrResult(
            solution_steps=["a", "b", "c"],
            solution_step_types=[StepType.계산],  # 전이 수는 2인데 1개.
        )


def test_ocr_result_extra_forbidden() -> None:
    """OcrResult 미지정 필드 거부."""
    with pytest.raises(ValidationError):
        OcrResult(unexpected="x")  # type: ignore[call-arg]


def test_coach_handoff_field_names_present() -> None:
    """coach 핸드오프 매핑 착지 필드가 OcrResult에 존재한다(coach.py 매핑 보장)."""
    fields = set(OcrResult.model_fields)
    assert {
        "plain_latex",
        "overall_confidence",
        "solution_steps",
        "solution_step_types",
    } <= fields
