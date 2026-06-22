"""OCR ④ 조립 — 인식 영역들을 읽기순으로 모아 `OcrResult`(구조)로 만든다(순수·모델 0).

`assemble_regions`는 인식 영역(`RecognizedRegion`) 목록을 받아:
  1. **읽기 순서 정렬**(위→아래·좌→우) — 줄 단위 그룹핑 후 줄 내 좌→우.
  2. **수식 영역 검증**(`verify.py`) — 파싱 불가 LaTeX는 신뢰도 강등 + `verified=False`.
  3. **집계 뷰** 구성 — `plain_latex`(읽기순 연결)·`solution_steps`(수식 영역)·
     `solution_step_types`(전이별·기본 계산)·`markdown`(표시용)·신뢰도(평균·최소).

7계층 경계(표현 ≠ 의미): 산출은 *구조*(`OcrResult`)다. `markdown`은 표시 편의 파생 뷰이지
코어 진실이 아니다(렌더는 클라이언트 책임). L4 코치 핸드오프 매핑은 `schema/ocr.py` docstring.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.recognize import RecognizedRegion
from whymath_backend.l5.ocr.verify import (
    demote_confidence_if_unparseable,
    parse_check_latex,
)
from whymath_backend.schema.enums import ContentType, StepType
from whymath_backend.schema.ocr import OcrRegion, OcrResult

# 줄 그룹핑 임계 — 두 영역의 y중심 차가 (둘 중 작은 높이)의 이 비율 미만이면 *같은 줄*로 본다.
# 손글씨는 라인이 흔들려 완전 정렬이 드물어, 높이 비례 허용폭으로 같은 줄을 묶는다(근사).
_SAME_LINE_RATIO = 0.6


def assemble_regions(recognized: list[RecognizedRegion]) -> OcrResult:
    """인식 영역들을 읽기순 정렬·검증·집계해 `OcrResult`로 조립한다 — **순수 함수**(모델 0).

    Args:
        recognized: 인식 완료 영역 목록(순서 무관·이 함수가 읽기순 정렬).

    Returns:
        읽기순 `regions` + 집계 뷰(plain_latex·solution_steps·solution_step_types·
        markdown·overall/min confidence)를 채운 `OcrResult`. 빈 입력은 빈 `OcrResult`.
    """
    if not recognized:
        return OcrResult()

    ordered = _sort_reading_order(recognized)

    regions: list[OcrRegion] = []
    for region in ordered:
        verified: bool | None = None
        confidence = region.confidence
        if region.content_type == ContentType.수식 and region.latex:
            # 수식만 SymPy 왕복 검증 — 파싱 불가면 신뢰도 강등 + verified=False(품질 신호).
            ok = parse_check_latex(region.latex).ok
            verified = ok
            confidence = demote_confidence_if_unparseable(region.latex, region.confidence)
        regions.append(
            OcrRegion(
                bbox=region.bbox,
                content_type=region.content_type,
                latex=region.latex,
                confidence=confidence,
                verified=verified,
            )
        )

    plain_latex = " ".join(r.latex for r in regions if r.latex)
    solution_steps = [r.latex for r in regions if r.content_type == ContentType.수식 and r.latex]
    # 전이별 단계 유형 — 기본 계산(전이 수 = max(len(steps)-1, 0)). 풍부한 유형 추론(조건해석·
    # 케이스분류 등)은 후속(공간/의미 분석) — 여기선 규약 길이를 채우는 보수적 기본값.
    step_types: list[StepType] = [StepType.계산] * max(len(solution_steps) - 1, 0)
    markdown = _build_markdown(regions)

    confidences = [r.confidence for r in regions]
    overall = sum(confidences) / len(confidences) if confidences else 0.0
    minimum = min(confidences) if confidences else 0.0

    return OcrResult(
        regions=regions,
        plain_latex=plain_latex,
        solution_steps=solution_steps,
        solution_step_types=step_types,
        markdown=markdown,
        overall_confidence=overall,
        min_confidence=minimum,
    )


def _sort_reading_order(regions: list[RecognizedRegion]) -> list[RecognizedRegion]:
    """영역을 읽기 순서(위→아래·줄 안에서 좌→우)로 정렬 — 줄 그룹핑 후 줄 내 정렬(순수).

    먼저 y중심 오름차순으로 본 뒤, y중심이 *같은 줄 허용폭* 안이면 같은 줄로 묶어 그 줄을
    x(좌→우)로 정렬한다. 줄들은 줄 최상단 y로 정렬한다. 손글씨 라인 흔들림을 높이 비례
    허용폭(`_SAME_LINE_RATIO`)으로 흡수한다(근사·결정론).
    """
    by_y = sorted(regions, key=lambda r: r.bbox.y + r.bbox.height / 2.0)
    lines: list[list[RecognizedRegion]] = []
    for region in by_y:
        y_center = region.bbox.y + region.bbox.height / 2.0
        placed = False
        for line in lines:
            ref = line[0]
            ref_center = ref.bbox.y + ref.bbox.height / 2.0
            tolerance = min(region.bbox.height, ref.bbox.height) * _SAME_LINE_RATIO
            if abs(y_center - ref_center) <= tolerance:
                line.append(region)
                placed = True
                break
        if not placed:
            lines.append([region])
    # 줄들을 최상단 y로 정렬하고, 각 줄을 좌→우(x)로 정렬해 평탄화.
    lines.sort(key=lambda line: min(r.bbox.y for r in line))
    ordered: list[RecognizedRegion] = []
    for line in lines:
        ordered.extend(sorted(line, key=lambda r: r.bbox.x))
    return ordered


def _build_markdown(regions: list[OcrRegion]) -> str:
    """영역을 사람이 읽기 좋은 마크다운으로 연결(표시 편의 파생 뷰·순수).

    텍스트 영역은 그대로, 수식 영역은 인라인 `$...$`로 감싼다(렌더 힌트). 빈 LaTeX는 건너뛴다.
    이는 *표현*이라 코어 진실(`regions`)이 아니다 — 클라이언트가 다시 렌더할 수 있다.
    """
    parts: list[str] = []
    for region in regions:
        if not region.latex:
            continue
        if region.content_type == ContentType.수식:
            parts.append(f"${region.latex}$")
        else:
            parts.append(region.latex)
    return " ".join(parts)
