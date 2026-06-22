"""`assemble_regions` 순수 함수 단위테스트 — 읽기순 정렬·집계 신뢰도·단계(모델 0).

검증: 위→아래·좌→우 정렬, plain_latex 연결, solution_steps(수식만)·step_types 길이,
overall(평균)·min 신뢰도 집계, 마크다운.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.assemble import assemble_regions
from whymath_backend.l5.ocr.recognize import RecognizedRegion
from whymath_backend.schema.enums import ContentType, StepType
from whymath_backend.schema.ocr import BBox


def _math(latex: str, x: float, y: float, conf: float = 0.9) -> RecognizedRegion:
    """수식 인식 영역 헬퍼."""
    return RecognizedRegion(
        bbox=BBox(x=x, y=y, width=50, height=20),
        content_type=ContentType.수식,
        latex=latex,
        confidence=conf,
    )


def _text(text: str, x: float, y: float, conf: float = 0.95) -> RecognizedRegion:
    """텍스트 인식 영역 헬퍼."""
    return RecognizedRegion(
        bbox=BBox(x=x, y=y, width=50, height=20),
        content_type=ContentType.텍스트,
        latex=text,
        confidence=conf,
    )


def test_empty_returns_empty_result() -> None:
    """빈 입력은 빈 OcrResult."""
    result = assemble_regions([])
    assert result.regions == []
    assert result.plain_latex == ""
    assert result.overall_confidence == 0.0


def test_reading_order_top_to_bottom() -> None:
    """위→아래 순으로 정렬된다(입력 순서 무관)."""
    # 일부러 역순(아래 먼저) 입력.
    regions = [_math("b", x=0, y=100), _math("a", x=0, y=0)]
    result = assemble_regions(regions)
    assert [r.latex for r in result.regions] == ["a", "b"]


def test_reading_order_left_to_right_same_line() -> None:
    """같은 줄(비슷한 y)에서는 좌→우 순."""
    # y가 거의 같은 두 영역 — x로 정렬돼야.
    regions = [_math("right", x=200, y=10), _math("left", x=0, y=12)]
    result = assemble_regions(regions)
    assert [r.latex for r in result.regions] == ["left", "right"]


def test_plain_latex_concatenation() -> None:
    """plain_latex는 읽기순으로 인식 텍스트를 잇는다."""
    regions = [_text("기울기를 구하면", x=0, y=0), _math("m = 2", x=0, y=30)]
    result = assemble_regions(regions)
    assert result.plain_latex == "기울기를 구하면 m = 2"


def test_solution_steps_only_math() -> None:
    """solution_steps는 수식 영역만, step_types는 전이 수만큼."""
    regions = [
        _text("풀이", x=0, y=0),
        _math("x = 1", x=0, y=30),
        _math("y = 2", x=0, y=60),
        _math("z = 3", x=0, y=90),
    ]
    result = assemble_regions(regions)
    assert result.solution_steps == ["x = 1", "y = 2", "z = 3"]
    # 전이 수 = 3 - 1 = 2.
    assert len(result.solution_step_types) == 2
    assert all(t == StepType.계산 for t in result.solution_step_types)


def test_single_step_has_no_transitions() -> None:
    """단계가 1개면 전이가 없어 step_types는 빈 목록."""
    result = assemble_regions([_math("x = 1", x=0, y=0)])
    assert result.solution_steps == ["x = 1"]
    assert result.solution_step_types == []


def test_aggregate_confidence_mean_and_min() -> None:
    """overall은 평균·min은 최솟값."""
    regions = [_math("a", x=0, y=0, conf=0.8), _math("b", x=0, y=30, conf=0.6)]
    result = assemble_regions(regions)
    assert abs(result.overall_confidence - 0.7) < 1e-9
    assert abs(result.min_confidence - 0.6) < 1e-9


def test_unparseable_math_demotes_confidence_and_marks_verified_false() -> None:
    """파싱 불가 LaTeX는 verified=False·신뢰도 강등."""
    # 깨진 LaTeX(파싱 불가) — 신뢰도가 강등돼야.
    regions = [_math("x ++ == )(", x=0, y=0, conf=1.0)]
    result = assemble_regions(regions)
    assert result.regions[0].verified is False
    assert result.regions[0].confidence < 1.0


def test_valid_math_marked_verified_true() -> None:
    """파싱 가능한 수식은 verified=True·신뢰도 유지."""
    regions = [_math("x = 2", x=0, y=0, conf=0.9)]
    result = assemble_regions(regions)
    assert result.regions[0].verified is True
    assert abs(result.regions[0].confidence - 0.9) < 1e-9


def test_markdown_wraps_math_in_dollars() -> None:
    """마크다운은 수식을 $...$로 감싸고 텍스트는 그대로."""
    regions = [_text("계산", x=0, y=0), _math("x = 1", x=0, y=30)]
    result = assemble_regions(regions)
    assert result.markdown == "계산 $x = 1$"
