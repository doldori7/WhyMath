"""NCIC 성취기준 크롤러 (2022·2015 개정 교육과정 듀얼).

출처: 국가교육과정정보센터 — https://www.ncic.go.kr
라이선스: 공공누리 제1유형 (출처 표시 필수)

법적 출처 표시 양식 (모든 출력에 메타데이터로 동봉):
    출처: 교육부 고시 제2022-33호 [수학과 교육과정], 국가교육과정정보센터(NCIC)

공개 API:
  - AchievementStandard / ConceptStandardLink: 성취기준·개념연결 Pydantic 모델
  - NcicCrawler: 비동기 수집기 (HTML·PDF 폴백)
  - extract_file_a / parse_standard_row / parse_link_row: File A xlsx 추출
  - clean_text: 정제 함수
  - validate_standards / validate_links: 검증 함수
  - write_json / write_csv / write_links_json: 파일 저장
"""

from data_pipeline.ncic.clean import clean_text
from data_pipeline.ncic.collect import NcicCrawler, NcicSourceConfig
from data_pipeline.ncic.extract_xlsx import (
    ExtractError,
    extract_file_a,
    parse_link_row,
    parse_standard_row,
)
from data_pipeline.ncic.load import write_csv, write_json, write_links_json
from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    NORM_ID_PATTERN,
    SOURCE_CITATION,
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    AchievementStandardCollection,
    ConceptLinkType,
    ConceptStandardLink,
    ConceptStandardLinkCollection,
    DomainCode,
    GradeBand,
    SchoolType,
)
from data_pipeline.ncic.validate import (
    ValidationReport,
    validate_links,
    validate_standards,
)

__all__ = [
    "AchievementStandard",
    "AchievementStandardCollection",
    "ConceptLinkType",
    "ConceptStandardLink",
    "ConceptStandardLinkCollection",
    "DomainCode",
    "ExtractError",
    "GradeBand",
    "LICENSE_NOTICE",
    "NORM_ID_PATTERN",
    "NcicCrawler",
    "NcicSourceConfig",
    "STANDARD_CODE_PATTERN",
    "SchoolType",
    "SOURCE_CITATION",
    "ValidationReport",
    "clean_text",
    "extract_file_a",
    "parse_link_row",
    "parse_standard_row",
    "validate_links",
    "validate_standards",
    "write_csv",
    "write_json",
    "write_links_json",
]
