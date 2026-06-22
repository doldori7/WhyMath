"""OCR ① 영역 검출 — 이미지에서 텍스트/수식 후보 영역(경계 상자)을 찾는다.

`Detector` Protocol은 한 장의 이미지를 *검출 영역 목록*(`DetectedRegion`)으로 분해한다.
검출은 *위치*만 책임진다(유형 분류는 ② 라우터, 인식은 ③ 인식기). 모델 의존이 큰 단계라
모든 구현은 무거운 라이브러리를 *메서드 내부에서 지연 import*한다 — 패키지 import만으로는
rapidocr/rapid-layout가 로드되지 않는다(CI hermetic·기본 배포 경량).

구현:
  - `PaddleDetector`(Phase A·현재 동작) — rapidocr_onnxruntime로 텍스트 라인 박스를
    검출한다(손글씨·인쇄 혼합 강건). 의존 미설치면 *조용한 폴백 없이* 명확한 RuntimeError.
  - `MfdDetector`(Phase B·동작) — rapid-layout(RapidAI·**Apache-2.0**·순수 ONNX)의 PP 계열
    레이아웃 모델로 *수식 영역*을 별도 검출하고, 내부 텍스트 검출기(PaddleDetector)의 라인
    박스와 함께 돌려준다. 수식 영역은 `_MathDetectedRegion`으로 표시(라우터가 isinstance로
    구분). **ultralytics(YOLOv8/DocLayout-YOLO)는 AGPL-3.0이라 금지** — model_type을 PP
    계열로 강제하고 AGPL 값은 RuntimeError로 거부한다(결정 우선순위 #2 법적 준수).
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


class _MathDetectedRegion(DetectedRegion):
    """MFD가 *수식 영역*으로 검출한 박스 표시용 서브클래스(필드 추가 없음).

    `DetectedRegion`과 구조가 같되 *타입*만 다르다 — `MfdRouter`가 `isinstance`로 수식 박스와
    텍스트 라인 박스를 구분해 병합한다(`extra="forbid"`라 새 필드 없이 타입만으로 표시).
    """


# rapid-layout PP 계열(Apache-2.0) model_type 화이트리스트 — 이외(특히 yolov8*/doclayout*)는
# AGPL-3.0이라 상용 SaaS에 금지(결정 우선순위 #2). __init__에서 강제한다.
_PP_LAYOUT_MODEL_TYPES = frozenset(
    {
        "pp_layout_cdla",
        "pp_layout_publaynet",
        "pp_layout_table",
        "pp_doc_layoutv2",
        "pp_doc_layoutv3",
    }
)
# 수식 영역 클래스 라벨 별칭 — CDLA는 'Equation', PP-DocLayout는 'formula'/'formula_number'.
# 버전 견고성을 위해 소문자 비교한다.
_DEFAULT_FORMULA_ALIASES = frozenset({"equation", "formula", "formula_number"})


class MfdDetector:
    """MFD(수식 영역 검출) — rapid-layout PP 계열(Apache-2.0·ONNX)로 수식 박스를 별도 검출.

    줄 단위 텍스트 검출기가 2D 수식(분수·적분·시그마)을 가로줄로 찢는 문제를, *수식 전용*
    레이아웃 검출로 한 덩어리로 잡아 해결한다(콴다 대비 핵심 우위). `detect`는:
      1. 내부 텍스트 검출기(`PaddleDetector`)로 텍스트 라인 박스를 얻고,
      2. rapid-layout PP 모델의 레이아웃 결과에서 *수식 클래스*(`Equation`/`formula`…)만 골라
         `_MathDetectedRegion`으로 만들어,
      3. 둘을 합쳐 돌려준다(병합·중복 제거는 ② `MfdRouter`가 순수 함수로 수행).

    **라이선스(우선순위 #2)**: model_type은 PP 계열(Apache-2.0)만 허용한다 — ultralytics
    기반 `yolov8*`/`doclayout*`(AGPL-3.0)은 `__init__`에서 RuntimeError로 거부한다. rapid-layout
    미설치도 *조용한 폴백 없이* 명확한 RuntimeError(CLAUDE.md "모르면 모른다고").
    """

    def __init__(
        self,
        *,
        model_type: str = "pp_layout_cdla",
        text_detector: Detector | None = None,
        layout_engine: Any = None,
        model_dir: str = "",
        formula_aliases: frozenset[str] | None = None,
        conf_threshold: float = 0.0,
    ) -> None:
        """MFD 검출기 구성 — model_type(PP 계열만)·내부 텍스트 검출기·수식 클래스 별칭.

        `layout_engine`을 주입하면 실 rapid-layout 대신 그 객체를 쓴다(테스트용 가짜 주입).
        AGPL model_type(`yolov8*`/`doclayout*`)은 즉시 RuntimeError로 거부한다.
        """
        normalized = model_type.strip().lower()
        if normalized.startswith("yolov8") or normalized.startswith("doclayout"):
            raise RuntimeError(
                f"MFD model_type {model_type!r}은 ultralytics 기반(AGPL-3.0)이라 금지합니다 — "
                "상용 SaaS는 PP 계열(Apache-2.0)만 사용합니다(결정 우선순위 #2 법적 준수)."
            )
        if normalized not in _PP_LAYOUT_MODEL_TYPES:
            raise RuntimeError(
                f"지원하지 않는 MFD model_type {model_type!r} — PP 계열(Apache-2.0)만 허용: "
                f"{sorted(_PP_LAYOUT_MODEL_TYPES)}(조용한 폴백 없음)."
            )
        self._model_type = normalized
        self._text_detector: Detector = text_detector or PaddleDetector(model_dir=model_dir)
        self._layout_engine = layout_engine
        self._formula_aliases = frozenset(
            alias.lower() for alias in (formula_aliases or _DEFAULT_FORMULA_ALIASES)
        )
        self._conf_threshold = conf_threshold

    def _ensure_layout_engine(self) -> Any:
        """rapid-layout PP 엔진을 1회 지연 생성·재사용. 미설치면 명확한 RuntimeError."""
        if self._layout_engine is not None:
            return self._layout_engine
        try:
            from rapid_layout import ModelType, RapidLayout, RapidLayoutInput  # 지연 import
        except ImportError as exc:  # 조용한 폴백 금지 — 명확히 보고
            raise RuntimeError(
                "MfdDetector에는 rapid-layout(Apache-2.0)가 필요합니다 — "
                '`pip install -e ".[ocr-layout]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        # 문자열 값 → ModelType enum(PP 계열만·AGPL은 __init__에서 이미 차단).
        self._layout_engine = RapidLayout(RapidLayoutInput(model_type=ModelType(self._model_type)))
        return self._layout_engine

    def detect(self, image: Any) -> list[DetectedRegion]:
        """텍스트 라인 박스 + 수식 영역 박스를 함께 검출(수식은 `_MathDetectedRegion`)."""
        regions: list[DetectedRegion] = list(self._text_detector.detect(image))
        engine = self._ensure_layout_engine()
        output = engine(image)
        boxes = getattr(output, "boxes", None) or []
        class_names = getattr(output, "class_names", None) or []
        scores = getattr(output, "scores", None) or []
        for box, class_name, score in zip(boxes, class_names, scores, strict=False):
            if str(class_name).strip().lower() not in self._formula_aliases:
                continue  # 수식 클래스가 아닌 레이아웃 영역(텍스트·표·그림 등)은 건너뜀.
            confidence = min(max(float(score), 0.0), 1.0)
            if confidence < self._conf_threshold:
                continue
            regions.append(_MathDetectedRegion(bbox=_corners_to_bbox(box), confidence=confidence))
        return regions


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


def _corners_to_bbox(box: Any) -> BBox:
    """rapid-layout 박스(코너 `[x1,y1,x2,y2]`)를 축정렬 `BBox`로 환산(순수 계산).

    rapid-layout은 검출 박스를 좌상단·우하단 코너 좌표로 준다. 음수는 0으로 클램프하고
    너비/높이가 음수면 0으로 둔다(BBox는 ge=0). 좌표 4개 미만이면 ValueError(보수적).
    """
    coords = [float(value) for value in box]
    if len(coords) < 4:
        raise ValueError(f"수식 검출 박스 좌표가 4개 미만입니다: {box!r}")
    x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
    x0, y0 = max(min(x1, x2), 0.0), max(min(y1, y2), 0.0)
    return BBox(x=x0, y=y0, width=max(abs(x2 - x1), 0.0), height=max(abs(y2 - y1), 0.0))
