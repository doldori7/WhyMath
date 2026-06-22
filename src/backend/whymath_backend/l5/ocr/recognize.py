"""OCR ③ 영역 인식 — 라우팅된 영역의 픽셀을 텍스트(한글) 또는 LaTeX(수식)로 변환한다.

수식 인식기는 `_BaseMathRecognizer`(ABC)로 *공통 흐름*(crop → 인식 → 신뢰도·정규화)을 묶고,
백엔드별로 `_recognize_crop`(한 영역 크롭 → LaTeX 문자열)만 구현한다(Template Method). 텍스트
인식기는 `TextRecognizer` Protocol + `PaddleTextRecognizer`(rapidocr 한글 모델).

무거운 의존(rapid_latex_ocr·rapidocr·transformers·torch)은 *메서드 내부 지연 import*다 —
패키지 import·기본 경로(OCR 비활성)에서 로드되지 않는다(CI hermetic). 의존 미설치면 조용한
폴백 없이 명확한 RuntimeError.

백엔드:
  - `RapidLatexRecognizer`(Phase A·현재 동작) — rapid_latex_ocr로 수식 크롭 → LaTeX.
  - `TexTellerRecognizer`(Phase B 스텁) — TexTeller(transformers) 좌석·NotImplementedError.
  - `QwenVlRecognizer`(Phase C 스텁) — 멀티모달 VLM 인식. **반드시 L3 라우터 경유**
    (`l3.pipeline.generate` — Ollama 직접 호출 금지·CLAUDE.md). 현재 NotImplementedError이되
    L3 호출 형태를 docstring·시그니처로 박아 둔다(Phase C에서 본문만 채운다).
  - `PaddleTextRecognizer`(Phase A·현재 동작) — rapidocr 한글 모델로 텍스트 영역 인식.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l5.ocr.router import RoutedRegion
from whymath_backend.schema.enums import ContentType
from whymath_backend.schema.ocr import BBox

if TYPE_CHECKING:
    from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink


class RecognizedRegion(BaseModel):
    """인식 완료된 영역 1개 — 위치·유형·인식 텍스트(LaTeX/한글)·신뢰도.

    조립(`assemble.py`)이 이 목록을 읽기순으로 모아 `OcrResult`를 만든다. `latex` 필드는
    수식이면 LaTeX, 텍스트면 한글 산문(스키마 `OcrRegion.latex`와 동일 의미).
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)

    bbox: BBox = Field(..., description="영역의 이미지 좌표 경계 상자")
    content_type: ContentType = Field(..., description="영역 유형 — 텍스트·수식")
    latex: str = Field(default="", description="인식 결과 — 수식이면 LaTeX·텍스트면 한글 산문")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="인식 신뢰도(0~1)")


def _crop(image: Any, bbox: BBox) -> Any:
    """이미지에서 `bbox` 영역을 크롭(순수·numpy 슬라이싱 가정). 디코드 형식은 호출자 책임.

    numpy 배열(H×W×C)이라면 `image[y0:y1, x0:x1]` 슬라이싱이다. 좌표는 정수로 내림/올림해
    경계를 포함한다. numpy가 아닌 객체(테스트 가짜)는 슬라이싱이 가능하면 그대로 시도한다.
    """
    x0, y0 = int(bbox.x), int(bbox.y)
    x1, y1 = int(bbox.x2 + 0.999), int(bbox.y2 + 0.999)
    try:
        return image[y0:y1, x0:x1]
    except (TypeError, IndexError):
        # 슬라이싱 불가 객체 — 크롭 없이 원본을 넘긴다(인식기가 처리·테스트 가짜 호환).
        return image


class _BaseMathRecognizer(ABC):
    """수식 인식기 공통 흐름(Template Method) — crop → `_recognize_crop` → 신뢰도·정규화.

    `recognize`(concrete)는 영역을 크롭해 `_recognize_crop`(abstract·백엔드별)에 넘기고,
    결과 LaTeX를 정규화·신뢰도와 함께 `RecognizedRegion`으로 조립한다. 백엔드는
    `_recognize_crop`(한 크롭 → LaTeX) 하나만 구현하면 된다.
    """

    @abstractmethod
    def _recognize_crop(self, crop: Any) -> str:
        """한 영역 크롭(픽셀)을 LaTeX 문자열로 인식 — 백엔드별 구현(지연 import 포함)."""
        ...

    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        """수식 영역을 크롭·인식·정규화해 `RecognizedRegion`으로 조립(공통 흐름).

        라우터가 준 `confidence`를 인식 신뢰도의 출발값으로 쓴다(백엔드가 토큰 신뢰도를
        주지 않는 경우의 보수적 근사). 빈 LaTeX는 신뢰도를 0으로 강등한다(인식 실패).
        """
        crop = _crop(image, region.bbox)
        latex = _normalize_latex(self._recognize_crop(crop))
        confidence = region.confidence if latex else 0.0
        return RecognizedRegion(
            bbox=region.bbox,
            content_type=ContentType.수식,
            latex=latex,
            confidence=confidence,
        )


class RapidLatexRecognizer(_BaseMathRecognizer):
    """rapid_latex_ocr 기반 수식 인식기 (Phase A·현재 동작).

    `_recognize_crop`이 rapid_latex_ocr로 수식 크롭을 LaTeX로 변환한다. 무거운 의존
    (rapid_latex_ocr·onnxruntime)은 *지연 import*다 — 의존 미설치면 명확한 RuntimeError.
    """

    def __init__(self) -> None:
        self._engine: Any = None

    def _ensure_engine(self) -> Any:
        """rapid_latex_ocr 엔진을 1회 지연 생성·재사용. 의존 미설치면 명확한 RuntimeError."""
        if self._engine is not None:
            return self._engine
        try:
            from rapid_latex_ocr import LatexOCR  # 지연 import — 기본 경로 미로드
        except ImportError as exc:  # 조용한 폴백 금지
            raise RuntimeError(
                "RapidLatexRecognizer에는 rapid_latex_ocr가 필요합니다 — "
                '`pip install -e ".[ocr]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        self._engine = LatexOCR()
        return self._engine

    def _recognize_crop(self, crop: Any) -> str:
        """수식 크롭 → LaTeX(rapid_latex_ocr). 반환은 (latex, 처리시간) 튜플이라 [0]만 취한다."""
        engine = self._ensure_engine()
        result = engine(crop)
        # rapid_latex_ocr는 (latex_str, elapsed)을 돌려준다 — 문자열만 취한다.
        if isinstance(result, tuple):
            return str(result[0]) if result and result[0] is not None else ""
        return str(result) if result is not None else ""


class TexTellerRecognizer(_BaseMathRecognizer):
    """TexTeller(transformers) 수식 인식기 좌석 — **Phase B 스텁**(인터페이스만·모델 미배선).

    Phase B에서 TexTeller(transformers·torch)를 결선해 rapid_latex_ocr보다 강건한 손글씨
    수식 인식을 제공한다. Phase A에서는 호출 시 명확한 NotImplementedError(조용한 통과 금지).
    """

    def _recognize_crop(self, crop: Any) -> str:
        """Phase B 미구현 — TexTeller(transformers) 수식 인식은 후속 슬라이스에서 배선한다."""
        raise NotImplementedError(
            "TexTellerRecognizer(transformers TexTeller)는 Phase B에서 배선합니다 — "
            "현재는 RapidLatexRecognizer를 씁니다(Phase A)."
        )


class QwenVlRecognizer(_BaseMathRecognizer):
    """Qwen3-VL 멀티모달 수식 인식기 좌석 — **Phase C 스텁**. *반드시 L3 라우터 경유*.

    CLAUDE.md 절대 원칙("LLM 호출은 항상 라우터 경유 — 직접 호출 금지"): VLM 인식도 LLM
    호출이므로 Ollama를 *직접* 부르지 않고 L3 파이프라인(`l3.pipeline.generate`)을 통한다.
    Phase C에서 `_recognize_crop`은 크롭을 base64 이미지로 인코딩해 멀티모달 프롬프트를
    구성하고, 다음 형태로 L3를 호출한다(현재는 NotImplementedError·형태만 박아 둔다):

        from whymath_backend.l3 import pipeline
        from whymath_backend.l3.models import RoutingRequest

        req = RoutingRequest(
            task_type="extract",        # ① 개념/수식 추출 호출지점(03a §B.2 CONCEPT_EXTRACT)
            difficulty="easy",
            requires_reasoning=False,
            student_subscription=...,    # 호출자 구독(클라우드 승급 가드)
            sync=True,                   # 인식은 즉답 필요(파이프라인 동기 경로)
        )
        result = await pipeline.generate(
            req,
            prompt=<멀티모달 프롬프트(이미지 + "이 손글씨 수식을 LaTeX로">,
            system=<수식 추출 시스템 프롬프트>,
            provider=self._provider,     # 주입된 L3 LLMProvider(Ollama Qwen3-VL 등)
            cache=self._cache,           # 인식 캐시(같은 크롭 재인식 회피)
            trace=self._trace,           # Langfuse 추적
        )
        return result.text               # 검증 전 원시 LaTeX(verify.py가 후속 검증)

    `_recognize_crop`이 동기 시그니처라 Phase C에서는 `recognize`를 async로 오버라이드하거나
    파이프라인 호출을 별도 동기 진입점으로 감싼다(설계 결정은 Phase C). provider/cache/trace는
    *생성자 주입*이다(전역 import·직접 Ollama 금지) — factory가 L3 의존을 넣는다.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        cache: CacheBackend | None = None,
        trace: TraceSink | None = None,
        student_subscription: str = "free",
    ) -> None:
        """L3 의존 주입 좌석 — provider/cache/trace는 factory가 넣는다(직접 Ollama 금지).

        Phase A/B에서는 보관만 한다. Phase C에서 `_recognize_crop`이 이 의존으로
        `l3.pipeline.generate`를 호출한다(라우터 경유·CLAUDE.md).
        """
        self._provider = provider
        self._cache = cache
        self._trace = trace
        self._student_subscription = student_subscription

    def _recognize_crop(self, crop: Any) -> str:
        """Phase C 미구현 — Qwen3-VL 인식은 *L3 라우터 경유*로 후속 배선(docstring 형태 참조)."""
        raise NotImplementedError(
            "QwenVlRecognizer(Qwen3-VL 멀티모달)는 Phase C에서 배선합니다 — "
            "반드시 l3.pipeline.generate(라우터 경유)로 호출하며 Ollama 직접 호출은 금지입니다"
            "(CLAUDE.md). 호출 형태는 클래스 docstring 참조."
        )


@runtime_checkable
class TextRecognizer(Protocol):
    """텍스트(한글 산문) 인식 Protocol — 라우팅된 텍스트 영역 → `RecognizedRegion`."""

    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        """텍스트 영역을 크롭·인식해 `RecognizedRegion`(content_type=텍스트)으로 반환한다."""
        ...


class PaddleTextRecognizer:
    """rapidocr 한글 텍스트 인식기 (Phase A·현재 동작).

    텍스트 영역 크롭을 rapidocr로 인식한다(언어는 `language`·기본 한국어). 검출 단계가 이미
    텍스트를 줬다면(`text_hint`) 재인식 없이 그 값을 신뢰한다(중복 비용 회피). 무거운 의존은
    *지연 import*이며 미설치면 명확한 RuntimeError.
    """

    def __init__(self, *, language: str = "korean") -> None:
        """텍스트 인식기 구성 — `language`는 rapidocr 언어(기본 한국어·`ocr_language`)."""
        self._language = language
        self._engine: Any = None

    def _ensure_engine(self) -> Any:
        """rapidocr 엔진을 1회 지연 생성·재사용. 의존 미설치면 명확한 RuntimeError."""
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR  # 지연 import — 기본 경로 미로드
        except ImportError as exc:  # 조용한 폴백 금지
            raise RuntimeError(
                "PaddleTextRecognizer에는 rapidocr_onnxruntime가 필요합니다 — "
                '`pip install -e ".[ocr]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        self._engine = RapidOCR()
        return self._engine

    def recognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        """텍스트 영역 인식 — 검출 텍스트 힌트가 있으면 재사용·없으면 크롭 재인식."""
        hint = region.text_hint
        if hint:
            return RecognizedRegion(
                bbox=region.bbox,
                content_type=ContentType.텍스트,
                latex=hint.strip(),
                confidence=region.confidence,
            )
        engine = self._ensure_engine()
        crop = _crop(image, region.bbox)
        result, _elapsed = engine(crop)
        text = " ".join(str(item[1]) for item in result) if result else ""
        return RecognizedRegion(
            bbox=region.bbox,
            content_type=ContentType.텍스트,
            latex=text.strip(),
            confidence=region.confidence if text else 0.0,
        )


def _normalize_latex(latex: str) -> str:
    """인식 LaTeX의 가벼운 정규화 — 양끝 공백 제거·둘러싼 `$`·`\\(\\)` 제거(순수).

    인식기마다 `$...$`/`\\(...\\)`로 감싸 줄 수 있어 코어가 다루기 쉽게 *수식 본문만* 남긴다
    (마크다운 렌더는 조립 단계가 다시 `$`로 감싼다 — 표현은 렌더 책임). 빈 문자열은 그대로.
    """
    text = latex.strip()
    if not text:
        return ""
    for left, right in (("$$", "$$"), ("$", "$"), ("\\(", "\\)"), ("\\[", "\\]")):
        wrapped = text.startswith(left) and text.endswith(right)
        if wrapped and len(text) > len(left) + len(right) - 1:
            text = text[len(left) : len(text) - len(right)].strip()
            break
    return text
