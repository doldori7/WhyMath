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
  - `QwenVlRecognizer`(실배선) — 멀티모달 VLM. **L3 라우터 경유 필수**이며 provider 계약이
    `generate(..., images=...)`로 확장돼 비동기 `arecognize`가 실동작한다. 동기 진입점은 의도적
    RuntimeError(라우터 경유가 async라서). 라이브 인식 *정확도*는 Phaiakes9 미검증.
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

        엔진은 `crop(numpy/PIL) → LaTeX str` 콜러블이다. 이미지 프로세서로 픽셀을 만들고
        `model.generate` 후 *텍스트 토크나이저*로 디코드한다(ViT+TrOCR+RobertaTokenizerFast 구조).
        실제 모델 적재·생성(`OleehyO/TexTeller`·~1.2GB·Apache-2.0)은 Phaiakes9에서 검증한다.
        잔여 불확실성(정직): 이 repo가 `AutoImageProcessor`용 preprocessor_config를 싣는지는
        라이브에서 최종 확인한다 — 디코더 토크나이저 결선은 실 API 확인으로 확정(2026-06-23).
        """
        if self._engine is not None:
            return self._engine
        try:
            import torch  # 지연 import — 기본 경로 미로드
            from PIL import Image
            from transformers import (
                AutoImageProcessor,
                AutoTokenizer,
                VisionEncoderDecoderModel,
            )
        except ImportError as exc:  # 조용한 폴백 금지 — 명확히 보고
            raise RuntimeError(
                "TexTellerRecognizer에는 transformers·torch가 필요합니다 — "
                '`pip install -e ".[ocr-heavy]"`로 설치하세요(조용한 폴백 없음).'
            ) from exc
        # TexTeller = VisionEncoderDecoder(ViT + TrOCRForCausalLM + RobertaTokenizerFast).
        # 핵심: 디코딩은 *텍스트 토크나이저*(AutoTokenizer→RobertaTokenizerFast)로 한다 —
        # 이미지 프로세서로 batch_decode 금지(디코더가 텍스트 토큰). 2026-06-23 실 API 확인.
        model = VisionEncoderDecoderModel.from_pretrained(self._model_name)
        image_processor = AutoImageProcessor.from_pretrained(self._model_name)
        tokenizer = AutoTokenizer.from_pretrained(self._model_name)

        def _run(crop: Any) -> str:
            image = crop if isinstance(crop, Image.Image) else Image.fromarray(crop)
            pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
            with torch.no_grad():
                generated = model.generate(pixel_values, max_new_tokens=512)
            return str(tokenizer.batch_decode(generated, skip_special_tokens=True)[0])

        self._engine = _run
        return self._engine

    def _recognize_crop(self, crop: Any) -> str:
        """수식 크롭 → LaTeX(TexTeller). 엔진 콜러블에 위임(지연 로드·주입 가능)."""
        result = self._ensure_engine()(crop)
        return str(result) if result is not None else ""


class QwenVlRecognizer(_BaseMathRecognizer):
    """Qwen3-VL 멀티모달 수식 인식기 — **비동기 경로 실배선**. *반드시 L3 라우터 경유*.

    CLAUDE.md 절대 원칙("LLM 호출은 항상 라우터 경유 — 직접 호출 금지"): VLM 인식도 LLM
    호출이므로 Ollama를 *직접* 부르지 않고 L3 파이프라인(`l3.pipeline.generate`)을 통한다.
    실동작 경로는 아래 `arecognize`이며 크롭을 base64 PNG로 인코딩해 `requires_vision=True`
    요청으로 L3를 호출한다(라우터가 LOCAL Qwen3-VL로 라우팅·캐시·Langfuse 자동 적용).

    **미검증인 것은 *구현*이 아니라 *라이브 정확도*다** — Phaiakes9 실모델 인식 품질 측정이
    아직 없다(목표 90%·PRD §12.3). 2026-07-31 `nlp_module_gap_review.md` §정정: 이 docstring이
    "Phase C 스텁·NotImplementedError"라 기술해 실제보다 못하다고 말하던 stale을 바로잡았다 —
    그 stale이 실제로 갭 대조의 착수 가설을 한 번 틀리게 했다.

    동기 진입점 `_recognize_crop`은 **의도적으로 RuntimeError**다(비동기 전용). L3 파이프라인이
    async라 동기 시그니처로는 라우터를 경유할 수 없고, 우회하면 직접 Ollama 호출이 된다.
    provider/cache/trace는
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

        비동기 `arecognize`가 이 의존으로 `l3.pipeline.generate`를 호출한다(라우터 경유·
        CLAUDE.md). 주입이 없으면 `arecognize`가 RuntimeError로 거부한다(조용한 폴백 없음).
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
        from whymath_backend.l3.data_grade_defaults import STUDENT_SUBMITTED
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
            # 등급: 프롬프트에 실리는 것은 *학생 본인의 손글씨 크롭*이다 — USER_GENERATED는
            # 권리 모델에서 반출 불가(export=False)라 국외 프로바이더로 나갈 수 없다.
            # 오늘도 비전 단축 경로가 LOCAL을 강제하므로 동작 변화는 0이며, 이 선언은
            # 그 경로가 바뀌더라도 미성년자 자료가 국외로 새지 않게 하는 이중 잠금이다.
            data_licenses=STUDENT_SUBMITTED,
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
