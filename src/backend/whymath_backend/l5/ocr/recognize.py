"""OCR ③ 영역 인식 — 라우팅된 영역의 픽셀을 텍스트(한글) 또는 LaTeX(수식)로 변환한다.

수식 인식기는 `_BaseMathRecognizer`(ABC)로 *공통 흐름*(crop → 인식 → 신뢰도·정규화)을 묶고,
백엔드별로 `_recognize_crop`(한 영역 크롭 → LaTeX 문자열)만 구현한다(Template Method). 텍스트
인식기는 `TextRecognizer` Protocol + `PaddleTextRecognizer`(rapidocr 한글 모델).

무거운 의존(rapid_latex_ocr·rapidocr·transformers·torch)은 *메서드 내부 지연 import*다 —
패키지 import·기본 경로(OCR 비활성)에서 로드되지 않는다(CI hermetic). 의존 미설치면 조용한
폴백 없이 명확한 RuntimeError.

백엔드:
  - `RapidLatexRecognizer`(Phase A·현재 동작) — rapid_latex_ocr로 수식 크롭 → LaTeX.
  - `TexTellerRecognizer`(Phase C·동작) — TexTeller(transformers VisionEncoderDecoder) 고정밀
    수식 인식. transformers·torch 지연 import(`[ocr-heavy]`)·미설치 시 RuntimeError. 라이브
    모델(`OleehyO/TexTeller`·약 1.2GB)은 Phaiakes9에서 검증(CI는 가짜 엔진 주입·hermetic).
  - `QwenVlRecognizer`(보류) — 멀티모달 VLM. **L3 라우터 경유 필수**이나 현 L3 provider 계약
    (`LLMProvider.generate(prompt, system, decision)`)이 텍스트 전용이라 멀티모달 인터페이스
    확장이 선행돼야 함 → 별도 슬라이스로 보류(현재 NotImplementedError·호출 형태만 docstring).
  - `PaddleTextRecognizer`(Phase A·Phase C 한국어 wiring) — rapidocr로 텍스트 영역 인식.
    `language=korean`+`model_dir`이면 한국어 PP-OCRv4 rec 모델·사전을 rapidocr에 주입한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
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

    async def arecognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        """비동기 인식 진입점 — 파이프라인(async)이 await한다.

        기본 구현은 *동기* `recognize`를 그대로 감싼다(ONNX 백엔드는 동기라 즉시 반환). L3
        라우터 경유(async)가 필요한 백엔드(`QwenVlRecognizer`)만 이 메서드를 오버라이드한다 —
        그렇게 하면 `run_ocr_pipeline`은 항상 `arecognize`를 await하고, 동기 백엔드도 무변경으로
        통과한다(하위호환·동기 백엔드는 오버라이드 불요).
        """
        return self.recognize(region, image)


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
    """TexTeller(transformers VisionEncoderDecoder) 고정밀 수식 인식기 (Phase C·동작).

    rapid_latex_ocr(경량 ONNX)보다 강건한 손글씨/복잡 수식 인식을 제공한다(2D 분수·적분·
    행렬). 무거운 의존(transformers·torch·PIL)은 *지연 import*다 — `[ocr-heavy]` 미설치면
    조용한 폴백 없이 명확한 RuntimeError. 라이브 모델(`OleehyO/TexTeller`·약 1.2GB)은
    Phaiakes9에서 검증한다(CI는 가짜 엔진 주입으로 hermetic — 실 모델 미로드).

    `engine`을 주입하면 실 모델 대신 그 콜러블(crop→LaTeX str)을 쓴다(테스트·대체 백엔드).
    """

    def __init__(self, *, model_name: str = "OleehyO/TexTeller", engine: Any = None) -> None:
        """TexTeller 구성 — `model_name`은 HF 모델 ID, `engine`은 테스트용 주입 콜러블."""
        self._model_name = model_name
        self._engine = engine

    def _ensure_engine(self) -> Any:
        """transformers VisionEncoderDecoder 엔진을 1회 지연 생성·재사용. 미설치면 RuntimeError.

        엔진은 `crop(numpy/PIL) → LaTeX str` 콜러블이다. 실제 모델 적재·생성은 Phaiakes9에서
        검증하며, 여기서는 표준 VisionEncoderDecoder + 이미지 프로세서 흐름으로 구성한다.
        """
        if self._engine is not None:
            return self._engine
        try:
            import torch  # 지연 import — 기본 경로 미로드
            from PIL import Image
            from transformers import AutoImageProcessor, VisionEncoderDecoderModel
        except ImportError as exc:  # 조용한 폴백 금지 — 명확히 보고
            raise RuntimeError(
                "TexTellerRecognizer에는 transformers·torch가 필요합니다 — "
                '`pip install -e ".[ocr-heavy]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        model = VisionEncoderDecoderModel.from_pretrained(self._model_name)
        processor = AutoImageProcessor.from_pretrained(self._model_name)

        def _run(crop: Any) -> str:
            image = crop if isinstance(crop, Image.Image) else Image.fromarray(crop)
            pixel_values = processor(images=image, return_tensors="pt").pixel_values
            with torch.no_grad():
                generated = model.generate(pixel_values, max_new_tokens=512)
            return str(processor.batch_decode(generated, skip_special_tokens=True)[0])

        self._engine = _run
        return self._engine

    def _recognize_crop(self, crop: Any) -> str:
        """수식 크롭 → LaTeX(TexTeller). 엔진 콜러블에 위임(지연 로드·주입 가능)."""
        result = self._ensure_engine()(crop)
        return str(result) if result is not None else ""


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
        """동기 진입점은 쓰지 않는다 — Qwen3-VL은 *비동기 L3 라우터 경유*(arecognize)다."""
        raise RuntimeError(
            "QwenVlRecognizer는 동기 호출을 지원하지 않습니다 — 비동기 `arecognize`를 쓰세요 "
            "(L3 라우터 경유·run_ocr_pipeline가 await). Ollama 직접 호출은 금지입니다(CLAUDE.md)."
        )

    async def arecognize(self, region: RoutedRegion, image: Any) -> RecognizedRegion:
        """수식 크롭을 *L3 라우터 경유*로 Qwen3-VL에 보내 LaTeX로 인식(라우터·캐시·Langfuse).

        크롭을 base64 PNG로 인코딩해 `requires_vision=True` 요청으로 `l3.pipeline.generate`를
        호출한다 — 라우터가 LOCAL Qwen3-VL(VISION 패밀리)로 라우팅하고, 캐시·관측이 자동
        적용된다(직접 Ollama 호출 금지·CLAUDE.md). provider/cache/trace는 factory가 주입한다.
        반환 LaTeX는 *검증 전 원시 출력*이다(verify.py가 후속 SymPy 검증).
        """
        if self._provider is None or self._cache is None or self._trace is None:
            raise RuntimeError(
                "QwenVlRecognizer는 L3 provider/cache/trace 주입이 필요합니다 — "
                "factory(build_ocr_components)가 app.state의 L3 의존을 넣습니다(직접 Ollama 금지)."
            )
        # 지연 import — L5는 L3를 *호출*만 한다(하위 계층). 패키지 import만으로 L3를 끌어오지 않음.
        from whymath_backend.l3 import pipeline as l3_pipeline
        from whymath_backend.l3.models import RoutingRequest

        crop = _crop(image, region.bbox)
        image_b64 = _encode_crop_png_base64(crop)
        req = RoutingRequest(
            task_type="extract",  # ① 개념/수식 추출 호출지점(03a §B.2)
            difficulty="easy",
            requires_reasoning=False,
            student_subscription=self._student_subscription,
            sync=True,  # 인식은 즉답
            requires_vision=True,  # → 라우터 비전 단축 경로(LOCAL Qwen3-VL)
        )
        result = await l3_pipeline.generate(
            req,
            prompt=_QWEN_VL_PROMPT,
            system=_QWEN_VL_SYSTEM,
            provider=self._provider,
            cache=self._cache,
            trace=self._trace,
            images=[image_b64],
        )
        latex = _normalize_latex(result.text)
        confidence = region.confidence if latex else 0.0
        return RecognizedRegion(
            bbox=region.bbox,
            content_type=ContentType.수식,
            latex=latex,
            confidence=confidence,
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

    def __init__(self, *, language: str = "korean", model_dir: str = "") -> None:
        """텍스트 인식기 구성 — `language`(rapidocr 언어)·`model_dir`(한국어 모델 디렉토리).

        `language`가 한국어(korean/ko)이고 `model_dir`이 주어지면 한국어 PP-OCRv4 rec 모델·
        사전을 rapidocr에 주입한다(검출·방향분류는 언어 무관이라 기본 모델 유지). 빈 model_dir
        이면 rapidocr 기본 모델(중영)을 쓴다(한국어 미설정·정직히 기본 동작).
        """
        self._language = language
        self._model_dir = model_dir
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
        # 한국어(korean/ko)+model_dir이면 한국어 rec 모델·사전 주입·아니면 기본 모델.
        self._engine = RapidOCR(**_rapidocr_rec_kwargs(self._language, self._model_dir))
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


def _rapidocr_rec_kwargs(language: str, model_dir: str) -> dict[str, str]:
    """언어·모델 디렉토리로 rapidocr 한국어 *인식(rec)* 모델 kwargs를 구성(순수 계산).

    한국어(`korean`/`ko`)이면서 `model_dir`이 있으면 한국어 PP-OCRv4 rec ONNX·사전 경로를
    돌려준다(검출 모델은 언어 무관이라 미지정·기본). 그 외(빈 model_dir·타 언어)는 빈 dict를
    돌려 rapidocr 기본 모델을 쓴다. 파일명은 Phase A 한국어 모델 규약(README §4-1) 정합:
    `korean_PP-OCRv4_rec.onnx`·`korean_dict.txt`. 모델 파일은 배포 시 내려받는다(미커밋).
    """
    if language.strip().lower() in {"korean", "ko"} and model_dir:
        base = Path(model_dir)
        return {
            "rec_model_path": str(base / "korean_PP-OCRv4_rec.onnx"),
            "rec_keys_path": str(base / "korean_dict.txt"),
        }
    return {}


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


# Qwen3-VL 수식 추출 프롬프트 — LaTeX 본문만 받도록 강하게 제약(설명·코드펜스 배제).
_QWEN_VL_SYSTEM = (
    "너는 수학 수식 인식기다. 이미지 속 수식을 LaTeX로만 출력한다. 설명·문장·코드펜스 없이 "
    "순수 LaTeX 본문만 출력한다(예: x^{2}-5x+6=0)."
)
_QWEN_VL_PROMPT = "이 이미지의 수식을 LaTeX로 변환해줘. LaTeX 본문만 출력해."


def _encode_crop_png_base64(crop: Any) -> str:
    """크롭(numpy 배열/PIL Image)을 PNG로 인코딩해 base64 문자열로 반환 — VL 입력용(지연 import).

    무거운 의존(Pillow)은 메서드 내부 지연 import다 — 미설치면 조용한 폴백 없이 RuntimeError.
    numpy 배열이면 PIL Image로 변환 후 PNG 바이트 → base64(ascii) 문자열.
    """
    try:
        import base64
        import io

        from PIL import Image
    except ImportError as exc:  # 조용한 폴백 금지
        raise RuntimeError(
            "QwenVlRecognizer 이미지 인코딩에는 Pillow가 필요합니다 — "
            '`pip install -e ".[ocr]"`로 설치하세요(조용한 폴백 없음).'
        ) from exc
    image = crop if isinstance(crop, Image.Image) else Image.fromarray(crop)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
