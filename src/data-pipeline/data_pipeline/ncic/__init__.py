"""NCIC 성취기준 크롤러 (2022 개정 교육과정).

출처: 국가교육과정정보센터 — https://www.ncic.go.kr
라이선스: 공공누리 제1유형 (출처 표시 필수)

법적 출처 표시 양식 (모든 출력에 메타데이터로 동봉):
    출처: 교육부 고시 제2022-33호 [수학과 교육과정], 국가교육과정정보센터(NCIC)

공개 API:
  - AchievementStandard: 성취기준 Pydantic 모델
  - NcicCrawler: 비동기 수집기 (HTML·PDF 폴백)
  - clean_text: 정제 함수
  - validate_standards: 검증 함수
  - write_json / write_csv: 파일 저장
"""

from data_pipeline.ncic.clean import clean_text
from data_pipeline.ncic.collect import NcicCrawler, NcicSourceConfig
from data_pipeline.ncic.load import write_csv, write_json
from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    AchievementStandard,
    DomainCode,
    GradeBand,
    SchoolType,
)
from data_pipeline.ncic.validate import ValidationReport, validate_standards

__all__ = [
    "AchievementStandard",
    "DomainCode",
    "GradeBand",
    "LICENSE_NOTICE",
    "NcicCrawler",
    "NcicSourceConfig",
    "SchoolType",
    "SOURCE_CITATION",
    "ValidationReport",
    "clean_text",
    "validate_standards",
    "write_csv",
    "write_json",
]
