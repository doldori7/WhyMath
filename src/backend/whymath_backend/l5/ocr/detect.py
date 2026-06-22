"""OCR ① 영역 검출 — 이미지에서 텍스트/수식 후보 영역(경계 상자)을 찾는다.

`Detector` Protocol은 한 장의 이미지를 *검출 영역 목록*(`DetectedRegion`)으로 분해한다.
검출은 *위치*만 책임진다(유형 분류는 ② 라우터, 인식은 ③ 인식기). 모델 의존이 큰 단계라
모든 구현은 무거운 라이브러리를 *메서드 내부에서 지연 import*한다 — 패키지 import만으로는
rapidocr/ultralytics가 로드되지 않는다(CI hermetic·기본 배포 경량).

구현:
  - `PaddleDetector`(Phase A·현재 동작) — rapidocr_onnxruntime로 텍스트 라인 박스를
    검출한다(손글씨·인쇄 혼합 강건). 의존 미설치면 *조용한 폴백 없이* 명확한 RuntimeError.
  - `MfdInferenceError` 좌석은 후속(Phase B) — `MfdDetector`는 MFD(수식 영역 검출, YOLO)
    좌석 스텁으로 NotImplementedError만 던진다(인터페이스·결선만·모델 미배선).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.ocr import BBox


class DetectedRegion(BaseModel):
    """검출된 영역 1개 — 경계 상자 + 검출 신뢰도(유형 미지정).

    검출 단계는 *위치*만 안다 — 텍스트/수식 분류는 ② 라우터(`router.py`)가 한다. `confidence`는
    검출기(라인 박스/MFD)의 신뢰도이며 인식 신뢰도와 별개다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    bbox: BBox = Field(..., description="검출 영역의 이미지 좌표 경계 상자")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="검출 신뢰도(0~1·인식 신뢰도와 별개)"
    )
    text_hint: str = Field(
        default="",
        description=(
            "검출 단계가 이미 얻은 텍스트(예: rapidocr는 검출+인식을 함께 한다). 라우터의 "
            "휴리스틱 입력이자 텍스트 인식기의 재사용 값(중복 인식 비용 회피). 없으면 빈 문자열."
        ),
    )


@runtime_checkable
class Detector(Protocol):
    """영역 검출 Protocol — 이미지(디코드된 객체) → 검출 영역 목록.

    `image`는 디코드된 이미지 객체(예: numpy 배열·PIL Image)다. 파이프라인이 디코드해 넘기며,
    구현은 자신이 필요한 형태로 변환한다(지연 import 포함). 순수 인터페이스라 테스트는 가짜
    구현으로 대체한다.
    """

    def detect(self, image: Any) -> list[DetectedRegion]:
        """이미지에서 텍스트/수식 후보 영역을 검출해 목록으로 반환한다."""
        ...


class PaddleDetector:
    """rapidocr_onnxruntime 기반 텍스트 라인 박스 검출기 (Phase A·현재 동작).

    `detect`는 rapidocr의 검출 단계 결과(4점 폴리곤)를 축정렬 `BBox`로 환산한다. 무거운
    의존(rapidocr_onnxruntime·onnxruntime)은 *메서드 내부에서 지연 import*한다 — 패키지
    import·기본 경로(OCR 비활성)에서는 로드되지 않는다. 의존 미설치면 *조용한 폴백 없이*
    명확한 RuntimeError를 던진다(CLAUDE.md "모르면 모른다고"·factory가 동일 정책).
    """

    def __init__(self, *, model_dir: str = "") -> None:
        """검출기 구성 — `model_dir`은 커스텀 ONNX 모델 디렉토리(빈 값=rapidocr 기본 모델).

        실제 엔진 로드는 첫 `detect`에서 지연 수행한다(import만으로 모델을 적재하지 않음).
        """
        self._model_dir = model_dir
        self._engine: Any = None

    def _ensure_engine(self) -> Any:
        """rapidocr 엔진을 1회 지연 생성·재사용. 의존 미설치면 명확한 RuntimeError."""
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR  # 지연 import — 기본 경로 미로드
        except ImportError as exc:  # 조용한 폴백 금지 — 명확히 보고
            raise RuntimeError(
                "PaddleDetector에는 rapidocr_onnxruntime가 필요합니다 — "
                '`pip install -e ".[ocr]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        self._engine = RapidOCR()
        return self._engine

    def detect(self, image: Any) -> list[DetectedRegion]:
        """이미지에서 텍스트 라인 박스를 검출 → 축정렬 `BBox` 목록(폴리곤은 외접 박스로 환산)."""
        engine = self._ensure_engine()
        # rapidocr는 (인식 결과, 처리시간)을 돌려준다 — 검출 단계만 쓰려면 결과의 박스 좌표를
        # 취한다. 결과 원소: [polygon(4점), text, score]. 검출 박스를 외접 BBox로 환산한다.
        result, _elapsed = engine(image)
        regions: list[DetectedRegion] = []
        if not result:
            return regions
        for item in result:
            polygon = item[0]
            # rapidocr는 검출+인식을 함께 한다 — item[1]은 인식 텍스트(텍스트 영역 재사용·휴리스틱
            # 입력). item[2]는 인식 점수. 검출 박스를 외접 BBox로 환산한다.
            text_hint = str(item[1]) if len(item) > 1 and item[1] is not None else ""
            score = float(item[2]) if len(item) > 2 and item[2] is not None else 1.0
            regions.append(
                DetectedRegion(
                    bbox=_polygon_to_bbox(polygon),
                    confidence=min(max(score, 0.0), 1.0),
                    text_hint=text_hint,
                )
            )
        return regions


class MfdDetector:
    """수식 영역 검출(MFD·YOLO) 좌석 — **Phase B 스텁**(인터페이스·결선만·모델 미배선).

    수식 영역을 인쇄/손글씨 라인 검출과 *분리해* 검출하는 MFD(Math Formula Detection)
    좌석이다. Phase A에서는 휴리스틱 라우터(`router.HeuristicRouter`)가 텍스트 박스에서
    수식을 가르므로 이 검출기는 쓰이지 않는다. Phase B에서 ultralytics(YOLO) 가중치를
    결선한다(`ocr_mfd_weights_path`). 호출 시 명확한 NotImplementedError(조용한 통과 금지).
    """

    def __init__(self, *, weights_path: str = "") -> None:
        """MFD 가중치 경로 좌석(`ocr_mfd_weights_path`). Phase A에서는 보관만 한다."""
        self._weights_path = weights_path

    def detect(self, image: Any) -> list[DetectedRegion]:
        """Phase B 미구현 — MFD(YOLO) 수식 영역 검출은 후속 슬라이스에서 배선한다."""
        raise NotImplementedError(
            "MfdDetector(MFD·YOLO 수식 영역 검출)는 Phase B에서 배선합니다 — "
            "현재는 HeuristicRouter가 텍스트 박스에서 수식을 가릅니다(Phase A)."
        )


def _polygon_to_bbox(polygon: Any) -> BBox:
    """검출 폴리곤(4점·[[x,y],...])을 축정렬 외접 `BBox`로 환산(순수 계산).

    rapidocr 검출 박스는 회전 폴리곤일 수 있어 min/max로 외접 직사각형을 구한다. 음수 좌표는
    0으로 클램프한다(BBox는 ge=0). 잘못된 폴리곤은 ValueError로 전파(보수적·조용한 0박스 금지).
    """
    xs = [float(point[0]) for point in polygon]
    ys = [float(point[1]) for point in polygon]
    if not xs or not ys:
        raise ValueError("빈 폴리곤 — BBox 환산 불가")
    x0, y0 = max(min(xs), 0.0), max(min(ys), 0.0)
    x1, y1 = max(xs), max(ys)
    return BBox(x=x0, y=y0, width=max(x1 - x0, 0.0), height=max(y1 - y0, 0.0))
