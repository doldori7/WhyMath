"""L5 OCR 서브시스템 — 손글씨 풀이 이미지 → 구조(`OcrResult`) 인식 파이프라인.

5단계 파이프라인(부품은 모두 *주입*·전역 로드 없음):
  ① 검출(`detect`)   — Detector Protocol·PaddleDetector(Phase A)·MfdDetector(Phase B 스텁).
  ② 라우팅(`router`) — RegionRouter Protocol·HeuristicRouter(Phase A·모델 0)·MfdRouter(B 스텁).
                       핵심 순수 함수 `merge_text_and_math_regions`(IoU 병합·단위 테스트 가능).
  ③ 인식(`recognize`)— _BaseMathRecognizer(ABC)·RapidLatexRecognizer(A)·TexTeller(B 스텁)·
                       QwenVlRecognizer(C 스텁·L3 라우터 경유)·PaddleTextRecognizer(A).
  ④ 조립(`assemble`) — `assemble_regions` 순수 함수(읽기순 정렬·집계).
  ④-검증(`verify`)   — `parse_check_latex` SymPy 왕복(결정론·LLM 0).
  텍스트 단계 분해(`text_segmentation`) — `segment_solution_text`(구조 판별만·LLM 0·
                       `data/segmentation_contract.json` 골든 계약).
  오케스트레이션(`pipeline`) — `run_ocr_pipeline`(부품 주입).
  부품 조립(`factory`) — `build_ocr_components(settings)`.

LLM/VLM 호출은 *반드시 L3 라우터 경유*(QwenVlRecognizer는 `l3.pipeline.generate`만 호출·
Ollama 직접 호출 금지·CLAUDE.md). 산출은 *구조*(표현 ≠ 의미) — 렌더는 클라이언트 책임.
"""

from __future__ import annotations

from whymath_backend.l5.ocr.assemble import assemble_regions
from whymath_backend.l5.ocr.detect import (
    DetectedRegion,
    Detector,
    MfdDetector,
    PaddleDetector,
)
from whymath_backend.l5.ocr.factory import OcrComponents, build_ocr_components
from whymath_backend.l5.ocr.pipeline import run_ocr_pipeline
from whymath_backend.l5.ocr.recognize import (
    PaddleTextRecognizer,
    QwenVlRecognizer,
    RapidLatexRecognizer,
    RecognizedRegion,
    TexTellerRecognizer,
    TextRecognizer,
)
from whymath_backend.l5.ocr.router import (
    HeuristicRouter,
    MfdRouter,
    RegionRouter,
    RoutedRegion,
    classify_by_geometry,
    classify_by_text,
    merge_text_and_math_regions,
)
from whymath_backend.l5.ocr.text_segmentation import (
    SegmentationResult,
    segment_solution_text,
)
from whymath_backend.l5.ocr.verify import (
    LatexParseResult,
    demote_confidence_if_unparseable,
    parse_check_latex,
)

__all__ = [
    # 검출 ①
    "DetectedRegion",
    "Detector",
    "MfdDetector",
    "PaddleDetector",
    # 라우팅 ②
    "HeuristicRouter",
    "MfdRouter",
    "RegionRouter",
    "RoutedRegion",
    "classify_by_geometry",
    "classify_by_text",
    "merge_text_and_math_regions",
    # 인식 ③
    "PaddleTextRecognizer",
    "QwenVlRecognizer",
    "RapidLatexRecognizer",
    "RecognizedRegion",
    "TexTellerRecognizer",
    "TextRecognizer",
    # 조립·검증 ④
    "LatexParseResult",
    "assemble_regions",
    "demote_confidence_if_unparseable",
    "parse_check_latex",
    # 텍스트 단계 분해(NLP-03)
    "SegmentationResult",
    "segment_solution_text",
    # 오케스트레이션·조립
    "OcrComponents",
    "build_ocr_components",
    "run_ocr_pipeline",
]
