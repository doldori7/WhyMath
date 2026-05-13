"""NCIC 성취기준 데이터 모델 (Pydantic).

설계 메모:
  - Phase 1 (현재) — PostgreSQL 미배포 → Pydantic 모델만 운영
  - Phase 2 — `[postgres]` extra 설치 후 동일 필드를 SQLAlchemy 매핑
  - 필드 명세 근거: `docs/data/ncic_scheme.md` + `.claude/agents/data-engineer.md`
  - 라이선스: 공공누리 제1유형 — 모든 직렬화 결과에 SOURCE_CITATION 동봉
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ──────────────────────────────────────────────────────────────────────────
# 라이선스·출처 (공공누리 제1유형 의무 표시)
# ──────────────────────────────────────────────────────────────────────────
SOURCE_CITATION: Final[str] = (
    "출처: 교육부 고시 제2022-33호 [수학과 교육과정], "
    "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)"
)
"""공공누리 제1유형 요구: 모든 출력에 이 문구를 메타데이터로 동봉."""

LICENSE_NOTICE: Final[str] = (
    "본 데이터는 공공누리 제1유형(출처 표시) 조건에 따라 자유로이 이용 가능합니다. "
    "상업적 이용 및 변경(2차적 저작물 작성)이 허용되며, "
    "이용 시 반드시 위 출처를 명시해야 합니다."
)
"""공공누리 1유형 약관 안내문."""

# ──────────────────────────────────────────────────────────────────────────
# Enum 타입 (Literal 사용 — Pydantic이 자동 검증)
# ──────────────────────────────────────────────────────────────────────────
GradeBand = Literal[
    "초등학교 1~2학년군",
    "초등학교 3~4학년군",
    "초등학교 5~6학년군",
    "중학교 1~3학년군",
    "고등학교",
]
"""성취기준 학년군. 2022 개정 교육과정 기준."""

SchoolType = Literal["초등학교", "중학교", "고등학교"]
"""학교급."""

DomainCode = Literal["01", "02", "03", "04", "05"]
"""영역 코드 — 2022 개정 수학과는 학교급별로 다름.

  중학교:
    01 수와 연산 / 02 변화와 관계 / 03 도형과 측정 / 04 자료와 가능성

  고등학교 공통과목 (공통수학1·2):
    01 다항식 / 02 방정식과 부등식 / 03 도형의 방정식 / 04 집합과 명제 / 05 함수와 그래프
    (과목별 영역 구성은 NCIC 원문 참조 — 검증 단계에서 사후 확인)
"""

# 코드 정규식: 두 가지 형식 지원 (2022 개정)
#
# 형식 A (중학교·기본):  `[<학년><과목한글>-옵션 없음-<영역2자리>-<순번2자리>]`
#   예: [9수01-01], [12대수01-01], [12미적Ⅰ01-01], [12확통03-05]
#
# 형식 B (고1 공통수학):  `[<학년><과목한글><과목숫자>-<영역2자리>-<순번2자리>]`
#   예: [10공수1-01-01], [10공수2-02-03]
#       — '공수1' = 공통수학1 (과목명에 숫자 포함), 영역과 순번은 두 번의 '-'로 구분
#
# 분리:
#   - 학년 대수: \d{1,2}    (2, 4, 6, 9, 10, 12)
#   - 과목 한글 부분: [ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6}
#   - 과목 숫자 접미사 (선택): \d?       ← '공수1' 같이 0~1자리
#   - 첫 번째 dash (B형식만, 선택)
#   - 영역 2자리: \d{2}
#   - 두 번째 dash
#   - 순번 2자리: \d{2}
STANDARD_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\[(\d{1,2})([ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6})(\d?)(?:-)?(\d{2})-(\d{2})\]$"
)
"""성취기준 코드 패턴. 학년대수·과목한글·(과목숫자)·영역·순번."""


# ──────────────────────────────────────────────────────────────────────────
# 핵심 모델
# ──────────────────────────────────────────────────────────────────────────
class AchievementStandard(BaseModel):
    """단일 성취기준.

    SQL DDL 대응(향후 Phase 2):
        achievement_standards(code, grade_band, domain, sub_domain, statement,
                              commentary, big_idea, curriculum_revision,
                              effective_from, parent_codes[]).

    필드 결정 사항:
      - `code`: PK. `STANDARD_CODE_PATTERN` 검증
      - `parent_codes`: 선수 성취기준. 비어있을 수 있음(예: 초등 1~2학년군)
      - `source_url` / `source_document`: 출처 추적용 — 공공누리 1유형 의무
      - `curriculum_revision`: 기본 "2022 개정" (다른 개정과 혼동 방지)
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델은 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로 (Literal은 str 그대로)
        use_enum_values=True,
        # JSON 직렬화 시 한국어 그대로 (ensure_ascii=False 효과)
        str_strip_whitespace=True,
    )

    code: str = Field(
        ...,
        description="성취기준 코드 (예: '[9수01-01]', '[10공수1-01-01]')",
        examples=["[9수01-01]", "[10공수1-01-01]"],
    )
    grade_band: GradeBand = Field(..., description="학년군")
    school_type: SchoolType = Field(..., description="학교급")
    subject: str = Field(
        ...,
        description=(
            "과목명 — 2022 개정 " "(예: '수학', '공통수학1', '대수', '미적분Ⅰ', '확률과 통계')"
        ),
        min_length=1,
        max_length=50,
    )
    domain: str = Field(
        ...,
        description="영역 (예: '수와 연산', '변화와 관계', '도형과 측정', '자료와 가능성')",
        min_length=1,
        max_length=50,
    )
    sub_domain: str | None = Field(
        default=None,
        description="세부 영역 (선택)",
        max_length=100,
    )
    statement: str = Field(
        ...,
        description="성취기준 본문 (정제 후)",
        min_length=1,
    )
    commentary: str | None = Field(
        default=None,
        description="성취기준 해설 (선택)",
    )
    big_idea: str | None = Field(
        default=None,
        description="해당 영역의 핵심 아이디어 (선택)",
    )
    curriculum_revision: str = Field(
        default="2022 개정",
        description="교육과정 개정 표시",
    )
    effective_from: date | None = Field(
        default=None,
        description="시행 시작일 (학년별 단계 시행)",
    )
    parent_codes: list[str] = Field(
        default_factory=list,
        description="선수 성취기준 코드 (선택, 분석 결과로 후처리 채움 가능)",
    )
    source_url: str = Field(
        ...,
        description="원자료 URL — 공공누리 1유형 출처 표시 의무",
    )
    source_document: str | None = Field(
        default=None,
        description="PDF/HWP 등 첨부 문서 식별자 (선택)",
    )

    # ── 검증자 ────────────────────────────────────────────────────
    @field_validator("code")
    @classmethod
    def _validate_code_format(cls, v: str) -> str:
        """코드 형식 검증 — STANDARD_CODE_PATTERN."""
        if not STANDARD_CODE_PATTERN.match(v):
            raise ValueError(
                f"성취기준 코드 형식 오류: {v!r}. "
                f"예상 패턴: '[<학년><과목><영역2자리>-<순번2자리>]', "
                f"예: '[9수01-01]', '[10공수1-01-01]'"
            )
        return v

    @field_validator("parent_codes")
    @classmethod
    def _validate_parent_codes(cls, v: list[str]) -> list[str]:
        """선수 코드도 동일 패턴 검증."""
        for code in v:
            if not STANDARD_CODE_PATTERN.match(code):
                raise ValueError(f"선수 성취기준 코드 형식 오류: {code!r}")
        return v

    @model_validator(mode="after")
    def _validate_school_band_consistency(self) -> AchievementStandard:
        """학교급과 학년군의 정합성."""
        if self.school_type == "초등학교" and not self.grade_band.startswith("초등학교"):
            raise ValueError(
                f"학교급-학년군 불일치: school_type={self.school_type!r}, "
                f"grade_band={self.grade_band!r}"
            )
        if self.school_type == "중학교" and self.grade_band != "중학교 1~3학년군":
            raise ValueError(
                f"학교급-학년군 불일치: school_type={self.school_type!r}, "
                f"grade_band={self.grade_band!r}"
            )
        if self.school_type == "고등학교" and self.grade_band != "고등학교":
            raise ValueError(
                f"학교급-학년군 불일치: school_type={self.school_type!r}, "
                f"grade_band={self.grade_band!r}"
            )
        return self


class AchievementStandardCollection(BaseModel):
    """성취기준 묶음 + 메타데이터 (JSON 저장 단위).

    공공누리 1유형 의무: `source_citation`, `license_notice` 필드를 표지에 포함.
    """

    model_config = ConfigDict(extra="forbid")

    source_citation: str = Field(default=SOURCE_CITATION)
    license_notice: str = Field(default=LICENSE_NOTICE)
    curriculum_revision: str = Field(default="2022 개정")
    collected_at: str = Field(
        ...,
        description="수집 시각 (ISO 8601, UTC)",
    )
    crawler_version: str = Field(default="0.1.0")
    standards: list[AchievementStandard] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """수록 성취기준 수."""
        return len(self.standards)
