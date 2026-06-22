"""OCR ② 영역 라우팅 — 검출 영역을 텍스트(한글 산문) vs 수식(LaTeX)으로 가른다.

`RegionRouter` Protocol은 검출 영역(`DetectedRegion`) 목록을 *유형이 붙은* 영역
(`RoutedRegion`) 목록으로 바꾼다 — 텍스트는 텍스트 인식기, 수식은 수식 인식기로 보낼
준비. 유형 판정은 *경로 결정*이지 인식이 아니다(인식은 ③ `recognize.py`).

구현:
  - `HeuristicRouter`(Phase A·현재 동작) — **모델 없이** 박스 종횡비·수학 기호 밀도·크기로
    텍스트/수식을 분류한다. 검출기(rapidocr)가 *전부 텍스트 라인*으로 주는 박스에서 수식
    줄을 휴리스틱으로 가른다.
  - `MfdRouter` 좌석(Phase B) — MFD(수식 영역 검출)가 *별도로* 수식 박스를 주는 경우, 텍스트
    박스와 수식 박스를 IoU로 병합한다(`merge_text_and_math_regions` 재사용). 스텁.

핵심 순수 함수 `merge_text_and_math_regions`: 수식 박스 좌표가 이긴다 — 수식 박스 안에 ≥50%
들어간 텍스트 박스는 버리고(수식이 텍스트로도 검출된 중복), 겹치지 않는 텍스트는 유지한다.
모델·I/O 0 — IoU/포함 비율의 결정론 계산이라 단위 테스트가 쉽다.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l5.ocr.detect import DetectedRegion, _MathDetectedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox

# 수학 기호 — 박스 인식 텍스트(검출 단계에 텍스트가 있으면)에서 수식성을 가늠하는 밀도 신호.
# 한글 산문엔 거의 없고 수식엔 흔한 기호 집합(휴리스틱·완전하지 않음·Phase A 근사).
_MATH_SYMBOLS = set("+-*/=<>≤≥≠±×÷√∑∫∂∞πθ^_{}()[]|")
_MATH_TOKEN_RE = re.compile(r"\\frac|\\sqrt|\\sum|\\int|\\lim|\\cdot|\\times|\\div|\\pm")
# 한글 음절 — 텍스트(산문)성 신호. 한글이 많으면 텍스트로 본다.
_HANGUL_RE = re.compile(r"[가-힣]")


class RoutedRegion(BaseModel):
    """유형이 붙은 영역 1개 — 경계 상자 + 유형(텍스트/수식) + (선택) 검출 시 텍스트 힌트.

    `content_type`은 `ContentType`(enums.py 재사용)의 텍스트·수식만 쓴다. `text_hint`는
    검출 단계가 이미 텍스트를 줬을 때의 *임시 인식값*(인식기가 덮어쓴다)이며, 휴리스틱
    라우팅의 입력이기도 하다(없으면 박스 기하만으로 분류).
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    bbox: BBox = Field(..., description="영역의 이미지 좌표 경계 상자")
    content_type: ContentType = Field(..., description="라우팅 유형 — 텍스트(산문)·수식(LaTeX)")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="검출/라우팅 신뢰도(인식 신뢰도와 별개)",
    )
    text_hint: str = Field(
        default="",
        description="검출 단계 텍스트(있을 때) — 휴리스틱 입력·인식기가 최종값으로 덮어쓴다.",
    )


@runtime_checkable
class RegionRouter(Protocol):
    """영역 라우팅 Protocol — 검출 영역 목록 → 유형 붙은 영역 목록."""

    def route(self, regions: list[DetectedRegion]) -> list[RoutedRegion]:
        """검출 영역들을 텍스트/수식으로 분류해 `RoutedRegion` 목록으로 반환한다."""
        ...


class HeuristicRouter:
    """모델 없는 텍스트/수식 라우터 (Phase A·현재 동작).

    검출 단계가 텍스트 힌트를 주면(rapidocr 인식 텍스트) *기호 밀도·한글 비율*로, 없으면
    *박스 종횡비·크기*로 수식/텍스트를 가른다(휴리스틱·근사). 수식은 보통 가로로 길고 한글이
    적고 수학 기호가 많다 — 그 신호를 결합해 임계 비교한다. 순수 계산이라 모델·I/O 0.

    `text_hint`는 검출이 준 텍스트를 그대로 실어 인식 단계로 넘긴다(텍스트 영역이면 그게
    최종값일 수 있고, 수식 영역이면 인식기가 LaTeX로 덮어쓴다).
    """

    def __init__(self, *, math_symbol_ratio_threshold: float = 0.15) -> None:
        """라우터 구성 — `math_symbol_ratio_threshold`는 수식 판정 기호 밀도 임계(0~1)."""
        self._symbol_threshold = math_symbol_ratio_threshold

    def route(self, regions: list[DetectedRegion]) -> list[RoutedRegion]:
        """각 검출 영역을 휴리스틱으로 텍스트/수식 분류해 `RoutedRegion`으로 변환."""
        routed: list[RoutedRegion] = []
        for region in regions:
            content_type = self._classify(region)
            routed.append(
                RoutedRegion(
                    bbox=region.bbox,
                    content_type=content_type,
                    confidence=region.confidence,
                    text_hint=region.text_hint,
                )
            )
        return routed

    def _classify(self, region: DetectedRegion) -> ContentType:
        """한 검출 영역을 텍스트/수식으로 분류 — 텍스트 힌트가 있으면 기호 밀도, 없으면 기하."""
        if region.text_hint:
            return classify_by_text(region.text_hint, symbol_threshold=self._symbol_threshold)
        return classify_by_geometry(region.bbox)


class MfdRouter:
    """MFD 기반 라우터 (Phase B·동작) — 텍스트 라인 박스 ↔ MFD 수식 박스 병합.

    `MfdDetector`가 *텍스트 라인 박스*(`DetectedRegion`)와 *수식 영역 박스*
    (`_MathDetectedRegion`)를 함께 준다. `route`는 둘을 `isinstance`로 가른 뒤 순수 함수
    `merge_text_and_math_regions`로 병합한다 — **수식 박스 좌표가 이기고**, 수식 박스에 ≥50%
    들어간 텍스트 라인(수식이 텍스트로도 검출된 중복)은 버리며, 겹치지 않는 텍스트만 텍스트로
    남긴다. 분류(휴리스틱)는 하지 않는다 — 유형은 검출 단계가 이미 정했다(수식=MFD, 그 외=텍스트).
    """

    def route(self, regions: list[DetectedRegion]) -> list[RoutedRegion]:
        """검출 영역을 수식(`_MathDetectedRegion`)/텍스트로 가른 뒤 순수 병합으로 라우팅."""
        math_boxes = [
            RoutedRegion(
                bbox=region.bbox,
                content_type=ContentType.수식,
                confidence=region.confidence,
                text_hint=region.text_hint,
            )
            for region in regions
            if isinstance(region, _MathDetectedRegion)
        ]
        text_boxes = [
            RoutedRegion(
                bbox=region.bbox,
                content_type=ContentType.텍스트,
                confidence=region.confidence,
                text_hint=region.text_hint,
            )
            for region in regions
            if not isinstance(region, _MathDetectedRegion)
        ]
        return merge_text_and_math_regions(text_boxes, math_boxes)


# ──────────────────────────────────────────────────────────────────────────
# 순수 함수 — 텍스트 박스 ↔ 수식 박스 IoU 병합 (모델·I/O 0·단위 테스트 핵심)
# ──────────────────────────────────────────────────────────────────────────
def classify_by_text(text: str, *, symbol_threshold: float = 0.15) -> ContentType:
    """인식 텍스트의 *수학 기호 밀도·한글 비율·LaTeX 토큰*으로 텍스트/수식 분류(순수).

    규칙(휴리스틱·Phase A):
      - LaTeX 토큰(\\frac·\\sqrt 등)이 있으면 즉시 수식.
      - 한글 음절 비율이 높고(>30%) 기호 밀도가 임계 미만이면 텍스트.
      - 그 외 기호 밀도가 임계 이상이면 수식·아니면 텍스트.
    빈 문자열은 텍스트로 본다(보수적·인식 실패 영역).
    """
    stripped = text.strip()
    if not stripped:
        return ContentType.텍스트
    if _MATH_TOKEN_RE.search(stripped):
        return ContentType.수식
    non_space = [ch for ch in stripped if not ch.isspace()]
    if not non_space:
        return ContentType.텍스트
    symbol_count = sum(1 for ch in non_space if ch in _MATH_SYMBOLS)
    hangul_count = len(_HANGUL_RE.findall(stripped))
    symbol_ratio = symbol_count / len(non_space)
    hangul_ratio = hangul_count / len(non_space)
    if hangul_ratio > 0.3 and symbol_ratio < symbol_threshold:
        return ContentType.텍스트
    return ContentType.수식 if symbol_ratio >= symbol_threshold else ContentType.텍스트


def classify_by_geometry(bbox: BBox) -> ContentType:
    """텍스트 힌트가 없을 때 박스 *종횡비·크기*만으로 텍스트/수식 분류(순수·근사).

    수식 한 줄은 보통 가로로 짧고 높이가 텍스트 라인보다 크다(분수·지수). 매우 가로로 긴
    박스(종횡비>8)는 산문 라인으로 보아 텍스트, 그 외는 수식으로 본다(보수적 — 수식을
    놓치는 것보다 텍스트 인식기가 산문을 받는 게 낫다). 면적 0 박스는 텍스트.
    """
    if bbox.area <= 0.0 or bbox.height <= 0.0:
        return ContentType.텍스트
    aspect = bbox.width / bbox.height
    return ContentType.텍스트 if aspect > 8.0 else ContentType.수식


def merge_text_and_math_regions(
    text_boxes: list[RoutedRegion],
    math_boxes: list[RoutedRegion],
    *,
    containment_threshold: float = 0.5,
) -> list[RoutedRegion]:
    """텍스트 박스와 (MFD) 수식 박스를 IoU 기반으로 병합 — **순수 함수**(모델·I/O 0).

    규칙(Phase B MfdRouter가 쓸 코어이나 *Phase A에서 단위 테스트 가능*):
      - **수식 박스 좌표가 이긴다** — 모든 수식 박스를 결과에 그대로 넣는다(content_type=수식).
      - **포함된 텍스트 버림** — 어떤 수식 박스 안에 *자기 면적의 ≥containment_threshold(기본
        50%)* 들어간 텍스트 박스는 버린다(수식이 텍스트 라인으로도 중복 검출된 것).
      - **겹치지 않는 텍스트 유지** — 어떤 수식 박스에도 그만큼 들어가지 않은 텍스트는 유지한다.

    결정론·교환 안정: 수식 박스를 먼저, 살아남은 텍스트를 뒤에 둔다(읽기순 정렬은 조립
    단계가 한다). 빈 입력도 안전(빈 목록 반환).

    Args:
        text_boxes: 텍스트로 라우팅된 영역(검출 라인 박스 등).
        math_boxes: MFD가 준 수식 영역(좌표 우선).
        containment_threshold: 텍스트 박스가 수식 박스에 *자기 면적의* 이 비율 이상
            들어가면 버린다(0~1·기본 0.5).

    Returns:
        병합된 `RoutedRegion` 목록 — 수식 박스 전부 + 포함되지 않은 텍스트 박스.
    """
    merged: list[RoutedRegion] = list(math_boxes)  # 수식 박스 좌표가 이긴다(전부 보존).
    for text_box in text_boxes:
        if any(
            _containment_ratio(text_box.bbox, math_box.bbox) >= containment_threshold
            for math_box in math_boxes
        ):
            continue  # 수식 박스에 ≥임계 포함된 텍스트 — 중복이라 버린다.
        merged.append(text_box)
    return merged


def _containment_ratio(inner: BBox, outer: BBox) -> float:
    """`inner`가 `outer`에 들어간 비율 = (교집합 면적) / (inner 면적). 0~1(순수 계산).

    IoU가 아니라 *inner 면적 기준* 포함 비율이다 — 작은 텍스트 박스가 큰 수식 박스 안에
    들어갔는지(중복)는 inner 기준이 맞다(IoU는 크기 차가 크면 작아져 포함을 놓친다). inner
    면적 0이면 0(판정 불가·보수적으로 미포함).
    """
    if inner.area <= 0.0:
        return 0.0
    ix0 = max(inner.x, outer.x)
    iy0 = max(inner.y, outer.y)
    ix1 = min(inner.x2, outer.x2)
    iy1 = min(inner.y2, outer.y2)
    inter_w = max(ix1 - ix0, 0.0)
    inter_h = max(iy1 - iy0, 0.0)
    return (inter_w * inter_h) / inner.area
