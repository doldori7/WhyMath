"""대학 성취기준 데이터 모델 (Pydantic) — **자체작성**(NCIC 아님).

`data_pipeline/ncic/models.py`(NCIC 공공누리 1유형 K-12 성취기준)의 *대학 짝*이다. 차이:
  - **라이선스: 와이매스 자체작성** — 대학 성취기준 본문은 원자노드DB 핵심명제를 종합한 자체 저작물
    (AI 추정·검수필요)이며 NCIC 공공누리 자료가 아니다. 따라서 redaction 불요(K-12 본문과 구분).
  - **검증이 느슨하다**: NCIC 모델은 학교급·학년군·코드 형식을 K-12 `Literal`/정규식으로 좁히지만,
    대학 코드(`[CALC1-01-01]`·`school_type=대학교`)는 그 형식 밖이다. 대학 전용 *완화* 검증만
    둔다(닫힌 enum 날조 회피 — backend `schema/standard.py`가 분류 필드를 str로 둔 방침과 동형).

backend 적재기(`l1/standards/standard_loader.py`)는 코퍼스 dict의 `standards`/`links` 배열만 읽고
backend `schema/standard.py`(분류 필드 전부 str·코드 정규식 없음)로 재검증하므로, 이 모델이 내는
산출 키가 그 스키마와 정합하면 그대로 적재된다(코퍼스 `code`→backend `official_code` rename은 로더가
수행·`concept_src_id`→`concept_code` 동일).
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ──────────────────────────────────────────────────────────────────────────
# 라이선스·출처 (자체작성 — 공공누리 아님)
# ──────────────────────────────────────────────────────────────────────────
SOURCE_CITATION: Final[str] = (
    "출처: 와이매스 자체작성 — 대학 수학 성취기준(원자노드DB 핵심명제 종합·AI 추정·검수필요). "
    "단원/소단원 코드는 대학과정 단원소단원 코드참조(CALC1-U1·CALC1-U1-S1 등) 재사용."
)
"""자체작성 출처 표기 — 모든 산출 표지에 동봉(NCIC 공공누리 SOURCE_CITATION과 구분)."""

LICENSE_NOTICE: Final[str] = (
    "본 데이터(대학 성취기준 본문·요약)는 와이매스 자체 저작물입니다. NCIC 공공누리 자료가 아니며 "
    "redaction이 불요합니다. 대학 성취기준 본문은 AI 추정 초안으로 수학 전문가 검수가 필요합니다."
)
"""자체작성 라이선스 안내문(redaction 불요·검수필요 표기)."""

# 대학 성취기준 코드: `[<과목약자>-<영역2자리>-<순번2자리>]` (예: [CALC1-01-01]·[GALOIS-01-01]).
# 과목약자는 대문자+숫자(CALC1·LINA2·TOPO1 등). norm_id는 `대학_<과목>_<2자리>_<2자리>`.
UNIV_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\[[A-Z]+[0-9]*-\d{2}-\d{2}\]$")
UNIV_NORM_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^대학_[A-Z]+[0-9]*_\d{2}_\d{2}$")
# 대학 소단원(개념ID·링크 타깃) 코드: `<과목약자>-U<단원>-S<소단원>` (예: CALC1-U1-S1).
UNIV_SUBUNIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]+[0-9]*-U\d+-S\d+$")

ConceptLinkType = Literal["직접", "재매핑", "준용"]
"""개념↔성취기준 연결 의미(backend `schema/standard.py`와 동일 한글 정본)."""


class UniversityStandard(BaseModel):
    """대학 성취기준 한 건 — 자체작성. backend `schema/standard.py` 키와 정합(`code` 키 보존).

    backend 로더가 코퍼스 `code`→`official_code`로 rename하므로 여기선 *코퍼스 규약대로 `code`*를
    둔다. 분류 필드(school_type·subject·domain)는 str(닫힌 enum 강제 안 함). 본문(statement)은
    자체작성이라 보유 허용(redaction 불요).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    norm_id: str = Field(..., description="정규화 식별자(PK) — '대학_<과목>_<2자리>_<2자리>'")
    code: str = Field(
        ..., description="대학 성취기준 코드(코퍼스 규약·로더가 official_code로 rename)"
    )
    curriculum_revision: str = Field(default="대학", description="교육과정 — 대학은 '대학' 상수")
    grade_band: str = Field(default="대학교", description="학년군 — 대학은 '대학교'")
    school_type: str = Field(default="대학교", description="학교급 — '대학교'")
    subject: str = Field(..., description="과목명(예: '갈루아 이론'·'미적분학 I')")
    domain: str = Field(..., description="영역(단원) (예: '체확장 복습')")
    sub_domain: str | None = Field(default=None, description="소단원(개념) (예: '분해체')")
    statement: str = Field(..., description="성취기준 본문(자체작성·AI 추정·검수필요)")
    commentary: str | None = Field(default=None, description="성취기준 요약(간결)")
    big_idea: str | None = Field(default=None, description="핵심 아이디어 (선택)")
    parent_codes: list[str] = Field(default_factory=list, description="선수 성취기준 코드 (선택)")
    source_url: str = Field(
        default="", description="원자료 URL — 자체작성이라 공란(provenance 별도)"
    )
    source_document: str = Field(
        default="와이매스 자체작성 대학 성취기준 (성취기준 통합마스터 2026-06-22)",
        description="출처 문서 식별자(자체작성 표기)",
    )

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        """대학 코드 형식 검증 — `[과목-NN-NN]`. 미적 하이픈 사태(코드 정합) 방지."""
        if not UNIV_CODE_PATTERN.match(value):
            raise ValueError(f"대학 성취기준 코드 형식 위반: {value!r} (예: '[CALC1-01-01]')")
        return value

    @field_validator("norm_id")
    @classmethod
    def _check_norm_id(cls, value: str) -> str:
        """norm_id 형식 검증 — '대학_<과목>_<2자리>_<2자리>'."""
        if not UNIV_NORM_ID_PATTERN.match(value):
            raise ValueError(f"대학 norm_id 형식 위반: {value!r} (예: '대학_CALC1_01_01')")
        return value

    @field_validator("statement")
    @classmethod
    def _check_statement(cls, value: str) -> str:
        """본문 비공란 검증(검수보고: statement 빈값 0 보장)."""
        if not value.strip():
            raise ValueError("대학 성취기준 statement는 공란일 수 없습니다.")
        return value


class UniversityConceptStandardLink(BaseModel):
    """대학 소단원(개념) ↔ 성취기준 단일 연결 — 자체작성. backend 로더 `links` 키와 정합.

    `concept_src_id`=대학 소단원 코드(`CALC1-U1-S1`·backend `concept`/`atom_node` code 공간),
    `norm_id`=성취기준 식별자, `link_type`='직접'(소단원↔성취기준 1:1). backend 로더가
    `concept_src_id`→`concept_code` rename 후 `{source_id: code}` 맵으로 해석한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    concept_src_id: str = Field(..., description="대학 소단원 코드(링크 소스·예 'CALC1-U1-S1')")
    norm_id: str = Field(..., description="연결 대상 성취기준 식별자(norm_id)")
    link_type: ConceptLinkType = Field(default="직접", description="연결 의미 — 대학은 '직접'")
    note: str | None = Field(default=None, description="연결 근거·비고 (선택)")

    @field_validator("concept_src_id")
    @classmethod
    def _check_subunit(cls, value: str) -> str:
        """소단원 코드 형식 검증 — `<과목>-U<단원>-S<소단원>`(원자노드DB 조인 보존)."""
        if not UNIV_SUBUNIT_PATTERN.match(value):
            raise ValueError(f"대학 소단원 코드 형식 위반: {value!r} (예: 'CALC1-U1-S1')")
        return value


__all__ = [
    "LICENSE_NOTICE",
    "SOURCE_CITATION",
    "UNIV_CODE_PATTERN",
    "UNIV_NORM_ID_PATTERN",
    "UNIV_SUBUNIT_PATTERN",
    "ConceptLinkType",
    "UniversityConceptStandardLink",
    "UniversityStandard",
]
