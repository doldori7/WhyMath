"""K-12 개념 교수학 콘텐츠 추출 파이프라인 (자체작성·L1 데이터 기반).

대학 U4(`concept_content_university`)의 *K-12 짝*. 업로드 통합마스터의 `개념`(학교급!='대학교')+
`암기카드`를 개념ID로 조인해 자체작성 콘텐츠 코퍼스(`data/corpus/concept_content_v1/`)로 캡처한다
(은유·오개념·정식정의[내부]·허용표현·설명·암기카드). **K-12 성취기준 본문은 NCIC 저작물이라
미수록**·연결 성취기준 코드만 다리로 보존. 콘텐츠 4종 DB 투영은 Phase 3 — 여기선 휘발 xlsx
자산을 커밋 코퍼스로 보존한다.
"""

from __future__ import annotations

from data_pipeline.concept_content.extract import extract_k12_content
from data_pipeline.concept_content.models import (
    ConceptContent,
    Flashcard,
)
from data_pipeline.concept_content.validate import validate_content

__all__ = [
    "ConceptContent",
    "Flashcard",
    "extract_k12_content",
    "validate_content",
]
