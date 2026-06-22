"""OCR → Coach 2-콜 핸드오프 매핑 단위테스트 — OcrResult를 CoachRequest로 매핑(coach.py 무변경).

검증: `OcrResult`의 필드가 `CoachRequest`의 student_solution·ocr_confidence·solution_steps·
solution_step_types에 깔끔히 매핑된다(schema/ocr.py docstring 매핑 표). coach.py는 손대지
않고, 클라이언트(또는 오케스트레이션)가 이 매핑으로 두 번째 호출을 만든다는 계약을 고정한다.
"""

from __future__ import annotations

from whymath_backend.api.coach import CoachRequest
from whymath_backend.schema.enums import ContentType, StepType
from whymath_backend.schema.ocr import BBox, OcrRegion, OcrResult


def _ocr_result() -> OcrResult:
    """수식 3단계 + 텍스트 1개를 가진 OcrResult(전이 2개·step_types 2개)."""
    return OcrResult(
        regions=[
            OcrRegion(
                bbox=BBox(x=0, y=0, width=50, height=20),
                content_type=ContentType.수식,
                latex="x + 1 = 3",
                confidence=0.7,
            )
        ],
        plain_latex="x + 1 = 3 x = 2 검산: 2+1=3",
        solution_steps=["x + 1 = 3", "x = 2", "2 + 1 = 3"],
        solution_step_types=[StepType.계산, StepType.검산],
        overall_confidence=0.72,
        min_confidence=0.7,
    )


def _to_coach_request(result: OcrResult, student_input: str = "") -> CoachRequest:
    """OcrResult → CoachRequest 매핑(2-콜 핸드오프 계약·schema/ocr.py docstring)."""
    return CoachRequest(
        student_input=student_input,
        student_solution=result.plain_latex,
        ocr_confidence=result.overall_confidence,
        solution_steps=result.solution_steps,
        solution_step_types=result.solution_step_types,
    )


def test_ocr_result_maps_to_coach_request() -> None:
    """OcrResult 필드가 CoachRequest의 대응 필드를 채운다(coach.py 무변경)."""
    result = _ocr_result()
    req = _to_coach_request(result)
    assert req.student_solution == "x + 1 = 3 x = 2 검산: 2+1=3"
    assert req.ocr_confidence == 0.72
    assert req.solution_steps == ["x + 1 = 3", "x = 2", "2 + 1 = 3"]
    assert req.solution_step_types == [StepType.계산, StepType.검산]


def test_low_confidence_propagates_for_recheck_gate() -> None:
    """<0.8 신뢰도가 ocr_confidence로 전달돼 coach §3.3 재확인 게이트를 켤 수 있다."""
    result = _ocr_result()
    assert result.overall_confidence < 0.8
    req = _to_coach_request(result)
    assert req.ocr_confidence is not None
    assert req.ocr_confidence < 0.8


def test_step_types_length_matches_transitions() -> None:
    """solution_step_types 길이는 전이 수(steps-1)와 같아 coach verify_solution 규약을 만족."""
    result = _ocr_result()
    req = _to_coach_request(result)
    assert len(req.solution_step_types or []) == len(req.solution_steps or []) - 1


def test_empty_ocr_result_maps_cleanly() -> None:
    """빈 OcrResult도 CoachRequest로 깨끗이 매핑된다(student_solution 빈 문자열)."""
    req = _to_coach_request(OcrResult())
    assert req.student_solution == ""
    assert req.solution_steps == []
    assert req.ocr_confidence == 0.0
