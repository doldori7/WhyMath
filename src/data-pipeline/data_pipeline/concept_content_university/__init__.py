"""대학 소단원 교수학 콘텐츠 추출 파이프라인 (자체작성·L1 데이터 기반).

`standards_university`(성취기준)의 *콘텐츠 짝*. 업로드 통합마스터의 `개념`(대학)+`암기카드`를
소단원 코드로 조인해 자체작성 콘텐츠 코퍼스(`data/corpus/concept_content_university_v1/`)로 캡처한다
(은유·오개념·정식정의[내부]·허용표현·설명·암기카드). 콘텐츠 4종 DB 투영은 Phase 3 — 여기선 휘발
xlsx 자산을 커밋 코퍼스로 보존한다.
"""

from __future__ import annotations

from data_pipeline.concept_content_university.extract import extract_university_content
from data_pipeline.concept_content_university.models import (
    Flashcard,
    UniversityConceptContent,
)
from data_pipeline.concept_content_university.validate import validate_content

__all__ = [
    "Flashcard",
    "UniversityConceptContent",
    "extract_university_content",
    "validate_content",
]
