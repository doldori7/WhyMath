"""OCR 부품 조립 — Settings로 검출기/라우터/인식기를 *1회* 구성한다(모델 1회 로드).

`build_ocr_components(settings)`는 `ocr_detector`·`ocr_recognizer_backend`·`ocr_language`
좌석을 읽어 검출기·라우터·텍스트 인식기·수식 인식기를 골라 `OcrComponents`로 묶는다. 무거운
모델은 각 부품의 *지연 import*라 이 함수는 *부품 인스턴스만* 만든다(첫 호출 시 모델 적재) —
다만 운영(lifespan)은 부팅 시 1회 호출해 부품을 app.state에 올려 둔다.

정직성(CLAUDE.md "모르면 모른다고"): 미지원 좌석 값·미설치 의존은 *조용한 폴백 없이* 명확한
RuntimeError로 보고한다(검출기/인식기 내부 지연 import도 동일 정책). 부품 자체 생성은 의존을
로드하지 않으므로(지연 import) 이 함수는 hermetic하다(CI·OCR 비활성 환경 안전).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from whymath_backend.config import Settings
from whymath_backend.l5.ocr.detect import Detector, MfdDetector, PaddleDetector
from whymath_backend.l5.ocr.recognize import (
    PaddleTextRecognizer,
    QwenVlRecognizer,
    RapidLatexRecognizer,
    TexTellerRecognizer,
    TextRecognizer,
    _BaseMathRecognizer,
)
from whymath_backend.l5.ocr.router import HeuristicRouter, MfdRouter, RegionRouter

if TYPE_CHECKING:
    # L3 의존 타입(주입용) — qwen_vl 백엔드만 사용. 지연 참조라 런타임 import 0(계층 격리).
    from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink


@dataclass(frozen=True)
class OcrComponents:
    """OCR 파이프라인 부품 묶음 — 검출기·라우터·텍스트 인식기·수식 인식기.

    파이프라인(`pipeline.run_ocr_pipeline`)이 이 부품들을 *주입*받아 오케스트레이션한다
    (전역 로드 없음). frozen — 구성 후 불변(부품 교체는 새 묶음 생성).
    """

    detector: Detector
    router: RegionRouter
    text_recognizer: TextRecognizer
    math_recognizer: _BaseMathRecognizer
    # 재확인(저신뢰) 게이트 임계 — `ocr_min_confidence` 좌석(0=비활성·현 동작). 조립이 이 미만
    # 영역에 needs_review를 단다(비파괴·신호만). 출력 집계 `OcrResult.min_confidence`(영역
    # 신뢰도 최솟값)와는 *다른* 것 — 여긴 *정책 임계*다(이름 충돌 회피로 review_threshold).
    review_threshold: float = 0.0


def build_ocr_components(
    settings: Settings,
    *,
    llm_provider: LLMProvider | None = None,
    llm_cache: CacheBackend | None = None,
    trace_sink: TraceSink | None = None,
) -> OcrComponents:
    """Settings 좌석으로 OCR 부품을 골라 `OcrComponents`로 조립(모델은 첫 사용 시 지연 로드).

    좌석:
      - `ocr_detector`: paddle(rapidocr 라인 검출·Phase A) / mfd(rapid-layout PP 계열 수식
        검출·Phase B·동작 — YOLO/ultralytics 아님·AGPL 거부는 `detect.py` 참조).
      - `ocr_recognizer_backend`: rapid_latex(Phase A) / texteller(Phase C·동작·`[ocr-heavy]`) /
        qwen_vl(비동기 경로 실배선·L3 라우터 경유).
      - `ocr_language`: 텍스트 인식 언어(rapidocr·기본 한국어).
      - `ocr_min_confidence`: 재확인 게이트 임계(0=비활성). 조립이 이 미만 영역에
        needs_review를 단다(`OcrComponents.review_threshold`로 운반·비파괴 신호).

    미지원 값은 ValueError가 아니라 RuntimeError로 보고한다(좌석 오설정도 명확히·조용한
    폴백 금지). 무거운 부품도 *구성은 허용*하되(좌석 결선 테스트·지연 로드), 의존 미설치
    (texteller의 `[ocr-heavy]` 등)·미지원 진입(qwen_vl 동기 `recognize`)은 실제 호출 시 명확한
    RuntimeError가 난다. 각 부품의 현재 상태(Phase·동작 여부)는 해당 모듈 docstring이 정본.
    """
    detector = _build_detector(settings)
    router = _build_router(settings)
    text_recognizer = PaddleTextRecognizer(
        language=settings.ocr_language, model_dir=settings.ocr_model_dir
    )
    math_recognizer = _build_math_recognizer(
        settings, llm_provider=llm_provider, llm_cache=llm_cache, trace_sink=trace_sink
    )
    return OcrComponents(
        detector=detector,
        router=router,
        text_recognizer=text_recognizer,
        math_recognizer=math_recognizer,
        review_threshold=settings.ocr_min_confidence,
    )


def _build_detector(settings: Settings) -> Detector:
    """`ocr_detector` 좌석으로 검출기 선택 — paddle(Phase A) / mfd(Phase B·rapid-layout PP)."""
    if settings.ocr_detector == "paddle":
        return PaddleDetector(model_dir=settings.ocr_model_dir)
    if settings.ocr_detector == "mfd":
        # Phase B — rapid-layout PP 계열(Apache-2.0)로 수식 영역 검출 + 내부 텍스트 라인 검출.
        # AGPL(yolov8/doclayout) model_type은 MfdDetector가 거부한다(config Literal로도 차단).
        return MfdDetector(
            model_type=settings.ocr_mfd_model_type,
            text_detector=PaddleDetector(model_dir=settings.ocr_model_dir),
            model_dir=settings.ocr_model_dir,
        )
    raise RuntimeError(
        f"알 수 없는 ocr_detector 좌석: {settings.ocr_detector!r}(조용한 폴백 없음)."
    )


def _build_router(settings: Settings) -> RegionRouter:
    """`ocr_detector` 좌석으로 라우터 선택 — mfd면 MfdRouter(병합), 그 외 HeuristicRouter."""
    if settings.ocr_detector == "mfd":
        # MFD 검출기는 텍스트/수식 박스를 함께 주므로, isinstance 기반 병합 라우터를 쓴다.
        return MfdRouter()
    return HeuristicRouter()  # Phase A: 모델 없는 휴리스틱 라우터(검출기가 전부 라인 박스).


def _build_math_recognizer(
    settings: Settings,
    *,
    llm_provider: LLMProvider | None = None,
    llm_cache: CacheBackend | None = None,
    trace_sink: TraceSink | None = None,
) -> _BaseMathRecognizer:
    """`ocr_recognizer_backend` 좌석으로 수식 인식기 선택 — rapid_latex / texteller / qwen_vl."""
    backend = settings.ocr_recognizer_backend
    if backend == "rapid_latex":
        return RapidLatexRecognizer()
    if backend == "texteller":
        return TexTellerRecognizer()  # Phase C·동작(transformers·[ocr-heavy]·Phaiakes9 검증).
    if backend == "qwen_vl":
        # Phase C·동작 — L3 라우터 경유(직접 Ollama 금지·CLAUDE.md). provider/cache/trace는
        # app.state의 L3 의존을 factory가 주입한다. provider 미주입이면 명확한 RuntimeError.
        if llm_provider is None or llm_cache is None or trace_sink is None:
            raise RuntimeError(
                "qwen_vl 백엔드는 L3 provider/cache/trace 주입이 필요합니다 — "
                "build_ocr_components(settings, llm_provider=, llm_cache=, trace_sink=)로 "
                "app.state의 L3 의존을 넘기세요(직접 Ollama 호출 금지)."
            )
        return QwenVlRecognizer(
            provider=llm_provider,
            cache=llm_cache,
            trace=trace_sink,
            student_subscription="free",
        )
    raise RuntimeError(f"알 수 없는 ocr_recognizer_backend 좌석: {backend!r}(조용한 폴백 없음).")
