"""대학 성취기준 통합마스터 추출 파이프라인 (자체작성·L1 데이터 기반).

`ncic`(NCIC 공공누리 K-12 성취기준)의 *대학 짝*이다. 업로드 통합마스터 xlsx의 `성취기준_목록`
대학 행을 자체작성 standards 코퍼스(`data/corpus/standards_university_v1/`)로 정형화한다 — backend
`l1/standards/standard_loader.py`가 읽는 Collection 포맷(standards·links)·키 정합.
"""

from __future__ import annotations

from data_pipeline.standards_university.extract import extract_university_standard_rows
from data_pipeline.standards_university.models import (
    UniversityConceptStandardLink,
    UniversityStandard,
)
from data_pipeline.standards_university.transform import transform_rows
from data_pipeline.standards_university.validate import (
    StandardsValidationReport,
    validate_standards,
)

__all__ = [
    "StandardsValidationReport",
    "UniversityConceptStandardLink",
    "UniversityStandard",
    "extract_university_standard_rows",
    "transform_rows",
    "validate_standards",
]
