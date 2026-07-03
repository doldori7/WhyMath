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

# 지원 교육과정 개정 — curriculum_revision 검증·norm_id prefix의 **단일 진실**(risk_register ⑩).
# 개정 추가(예 '2028 개정')는 *여기 한 곳*만 고치면 아래 NORM_ID_PATTERN 정규식이 파생으로 따라온다
# (하드코딩 drift 0). 노드/코드가 개정을 의미로 들지 않고 이 폐집합이 개정 축을 쥔다.
_VALID_CURRICULUM_REVISIONS: Final[frozenset[str]] = frozenset({"2022 개정", "2015 개정"})
"""허용 교육과정 개정 집합 (2022·2015)."""

# norm_id/official_code prefix에 쓰는 개정연도 토큰 — 위 단일 진실에서 *파생*(내림차순·최신 우선).
# "2022 개정" → "2022". NORM_ID_PATTERN alternation이 이 파생을 공유해 폐집합↔정규식 drift를 없앤다.
# 개정 라벨 형식이 "<연도> 개정"임을 전제(split()[0]=연도) — 형식 변경 시 이 파생도 조정.
_REVISION_YEAR_TOKENS: Final[tuple[str, ...]] = tuple(
    sorted((rev.split()[0] for rev in _VALID_CURRICULUM_REVISIONS), reverse=True)
)
"""개정연도 토큰(내림차순) — _VALID_CURRICULUM_REVISIONS 파생 ('2022', '2015')."""

# norm_id: 교육과정(2022/2015) × 학년·과목 토큰 × 영역 × 순번을 합친 **교육과정 간 유일 식별자**.
#
# 형식:  <개정연도>_<학년+과목토큰>_<영역2자리>_<순번2자리>
#   예: 2022_2수_01_01 · 2022_10공수1_01_01 · 2015_12미적_01_03
#
# 도입 배경 (P1-1): `code`(official_code, 고시 원문코드)는 2022·2015 두 교육과정에서
#   *동일 문자열로 충돌*할 수 있다(예: 양쪽에 `[12미적01-01]`). 따라서 PK를 official_code가
#   아닌 norm_id로 옮겨 충돌을 해소한다.
#
# 토큰셋 주의: 학년+과목토큰 부분은 `[가-힣A-Za-z0-9]{1,8}`로 *느슨하게* 받는다.
#   File A(성취기준 마스터 xlsx) 도착 전이라 실제 토큰 집합이 미확정이므로, 로마숫자(Ⅰ/Ⅱ)는
#   build_norm_id가 ASCII(I/II)로 정규화한 뒤 이 패턴에 통과시키는 것을 전제로 한다.
#   File A 도착 시 정밀 토큰셋(예: 허용 과목 enum)으로 좁힐 것 — 그때 이 주석과 함께 조정.
# 개정연도 alternation은 _REVISION_YEAR_TOKENS(단일 진실 파생)에서 만든다 — 하드코딩 금지(⑩ drift).
NORM_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(" + "|".join(_REVISION_YEAR_TOKENS) + r")_[가-힣A-Za-z0-9]{1,8}_\d{2}_\d{2}$"
)
"""norm_id 패턴. <개정연도>_<학년+과목토큰>_<영역>_<순번> (예: '2022_2수_01_01')."""

# 연결 유형 — 개념↔성취기준 링크의 의미.
#   직접   = 개념이 해당 성취기준을 곧장 다룸
#   재매핑 = 2015↔2022 개정 사이에서 대응되는 성취기준으로 옮겨 연결
#   준용   = 정확히 같진 않으나 교수학적으로 준하여 적용
ConceptLinkType = Literal["직접", "재매핑", "준용"]
"""개념↔성취기준 연결 유형."""


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
      - `norm_id`: **PK(식별 필드)**. `NORM_ID_PATTERN` 검증. 교육과정(2022/2015) 간 유일.
      - `code`: official_code(고시 원문코드). `STANDARD_CODE_PATTERN` 검증. 교육과정 간 *비유일*.
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

    norm_id: str = Field(
        ...,
        description=(
            "정규화 식별자(PK) — 교육과정(2022/2015) 간 유일. "
            "<개정연도>_<학년+과목토큰>_<영역>_<순번> (예: '2022_2수_01_01')"
        ),
        examples=["2022_2수_01_01", "2022_10공수1_01_01"],
    )
    code: str = Field(
        ...,
        description=(
            "official_code(고시 원문코드, 예: '[9수01-01]', '[10공수1-01-01]'). "
            "이제 **교육과정 간 비유일** — 동일 code가 2022·2015에 동시 존재 가능. "
            "교육과정 간 유일 식별은 norm_id가 담당한다."
        ),
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
        description="교육과정 개정 표시 ('2022 개정' | '2015 개정')",
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
    @field_validator("norm_id")
    @classmethod
    def _validate_norm_id_format(cls, v: str) -> str:
        """norm_id 형식 검증 — NORM_ID_PATTERN (교육과정 간 유일 식별자)."""
        if not NORM_ID_PATTERN.match(v):
            raise ValueError(
                f"norm_id 형식 오류: {v!r}. "
                f"예상 패턴: '<2022|2015>_<학년+과목토큰>_<영역2자리>_<순번2자리>', "
                f"예: '2022_2수_01_01', '2022_10공수1_01_01'"
            )
        return v

    @field_validator("curriculum_revision")
    @classmethod
    def _validate_curriculum_revision(cls, v: str) -> str:
        """교육과정 개정 표시는 지원 집합('2022 개정'·'2015 개정')으로 제한."""
        if v not in _VALID_CURRICULUM_REVISIONS:
            raise ValueError(
                f"지원하지 않는 교육과정 개정: {v!r}. "
                f"허용: {sorted(_VALID_CURRICULUM_REVISIONS)}"
            )
        return v

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


# ──────────────────────────────────────────────────────────────────────────
# 개념 ↔ 성취기준 연결 모델 (Concept Graph 연결 레이어 — data-engineer L1 자산 9번)
# ──────────────────────────────────────────────────────────────────────────
class ConceptStandardLink(BaseModel):
    """개념 노드 ↔ 성취기준(norm_id) 단일 연결.

    개념 그래프(Neo4j)의 `Concept` 노드와 성취기준 사이를 잇는 *연결 레이어*.
    L1은 이 연결의 *데이터*를 보유하고, 개념 노드 자체의 소유는 concept_graph 모듈이다.

    필드 결정 사항:
      - `concept_src_id`: 개념 소스 식별자 (concept_graph가 부여, L1은 *참조만*)
      - `norm_id`: 연결 대상 성취기준 식별자. `NORM_ID_PATTERN` 검증
      - `link_type`: 연결 의미 ('직접'·'재매핑'·'준용')
      - `note`: 연결 근거·비고 (선택)
    """

    model_config = ConfigDict(
        # AchievementStandard와 동일 — 추가 필드 금지 + 문자열 양끝 공백 제거
        extra="forbid",
        str_strip_whitespace=True,
    )

    concept_src_id: str = Field(
        ...,
        description="개념 소스 식별자 (concept_graph 부여, L1은 참조만)",
        min_length=1,
    )
    norm_id: str = Field(
        ...,
        description="연결 대상 성취기준 식별자 (norm_id)",
        examples=["2022_2수_01_01"],
    )
    link_type: ConceptLinkType = Field(
        ...,
        description="연결 의미 ('직접'·'재매핑'·'준용')",
    )
    note: str | None = Field(
        default=None,
        description="연결 근거·비고 (선택)",
    )

    @field_validator("norm_id")
    @classmethod
    def _validate_norm_id_format(cls, v: str) -> str:
        """연결 대상 norm_id도 NORM_ID_PATTERN으로 검증."""
        if not NORM_ID_PATTERN.match(v):
            raise ValueError(
                f"norm_id 형식 오류: {v!r}. "
                f"예상 패턴: '<2022|2015>_<학년+과목토큰>_<영역2자리>_<순번2자리>'"
            )
        return v


class ConceptStandardLinkCollection(BaseModel):
    """개념↔성취기준 연결 묶음 + 메타데이터 (JSON 저장 단위).

    `AchievementStandardCollection`을 거울처럼 따른다 — 출처·라이선스 표지를 포함한다.
    (개념-성취기준 연결의 *성취기준 측* 원천은 NCIC 공공누리 1유형이므로 동일 표지 유지)
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
    links: list[ConceptStandardLink] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """수록 연결 수."""
        return len(self.links)
