"""437↔원자 크로스워크 Pydantic 모델 — `CrosswalkEntry` + `MatchMethod` 폐쇄 enum.

원자 백본 인계(§5.4 Phase 4-ⓐ): Phase 5에서 구 437 개념그래프를 폐기하려면 437-키 자산
(behavior_skills·concept_content K-12)을 원자 축으로 옮길 *다리*가 필요하다. 이 모델은 그 다리
1행 — 구 concept_id(`math.<area>.<slug>`) → 신 원자 code(들) 매핑을 표현한다.

**rekey 금지 원칙**: 기존 테이블 키는 바꾸지 않는다. 크로스워크는 독립 코퍼스이며, 소비 측
(S0-2)이 이 다리를 *읽어* 귀속만 옮긴다. 1:N 매핑 시 mastery/오개념 귀속은
`primary_atom_code`(정확히 1개) 기준이다.

컨벤션(skill_graph/models.py·atom_graph/models.py 미러): `ConfigDict(extra="forbid",
use_enum_values=True, str_strip_whitespace=True)` · 축은 `str`-Enum · 불변식은 validator ·
한국어 docstring.

법적(CLAUDE.md 우선순위 #2): 크로스워크는 양측 자체작성 코퍼스의 *코드*만 연결한다 — 성취기준
본문·교과서 본문은 만지지 않는다(redaction 불요).
"""

from __future__ import annotations

from enum import Enum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN

# 크로스워크는 양측 자체작성 코퍼스의 코드만 연결 — NCIC 승계 문구 불요(본문 미포함).
SOURCE_CITATION: Final[str] = (
    "437↔원자 크로스워크: 와이매스 자체 유도(양측 자체작성 코퍼스의 코드·이름만 사용, "
    "성취기준 본문 미포함)."
)

# review_status 고정값 — 프로그램적 유도 산출이라 전량 AI 추정(사람 검수 전).
REVIEW_STATUS_AI_ESTIMATED: Final[str] = "ai_estimated"


class MatchMethod(str, Enum):
    """매칭 방법 폐쇄 enum — 유도 규칙(derive.py) 3단계와 1:1.

    - `standard_code`: 양측 `standard_codes` 교집합 후보가 정확히 1개 → 그 원자가 primary.
    - `standard_code+name`: 후보 복수 → 이름 토큰 자카드 랭킹으로 primary 선정.
    - `unmapped`: 교집합 후보 0개 — 강제 매핑하지 않고 사유만 기록(#419 '미매핑 정직 표기' 선례).
    """

    STANDARD_CODE = "standard_code"
    STANDARD_CODE_NAME = "standard_code+name"
    UNMAPPED = "unmapped"


# enum 값의 단일 진실(테스트·검증 공용·skill_graph BEHAVIOR_AREAS 미러).
MATCH_METHODS: Final[tuple[str, ...]] = tuple(m.value for m in MatchMethod)


class CrosswalkEntry(BaseModel):
    """크로스워크 1행 — 구 437 개념 1개 → 신 원자 code(들) 매핑(+근거·신뢰도).

    `concept_id`(구 그래프 PK·`math.<area>.<slug>`)가 행 키다(코퍼스 내 유일 — 유일성은
    validate.py 그래프 레벨 규칙). `atom_codes`는 1:N 허용 후보 전체,
    `primary_atom_code`는 그중 정확히 1개(귀속 기준·S0-2 소비). 미매핑 행도 코퍼스에
    *포함*한다(437행 전량 — 커버리지가 실측으로 드러나야 함).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    concept_id: str = Field(
        ...,
        description="구 437 그래프 concept_id('math.<area>.<slug>'). 크로스워크 행 키.",
    )
    atom_codes: list[str] = Field(
        default_factory=list,
        description="매핑된 원자 code 목록(1:N 허용·code 사전순·미매핑 시 빈 목록).",
    )
    primary_atom_code: str | None = Field(
        default=None,
        description="귀속 기준 원자 code(정확히 1개·atom_codes에 포함). 미매핑 시 None.",
    )
    match_method: MatchMethod = Field(
        ...,
        description="매칭 방법(standard_code/standard_code+name/unmapped).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="매핑 신뢰도(0~1·결정론적 산식). 미매핑은 0.0.",
    )
    evidence: str = Field(
        ...,
        min_length=1,
        description="유도 근거 요약(교집합 성취기준 코드·후보 수·자카드 점수 등).",
    )
    review_status: Literal["ai_estimated"] = Field(
        default="ai_estimated",
        description="검수 상태 — 프로그램적 유도라 전량 'ai_estimated' 고정(사람 검수 전).",
    )
    unmapped_reason: str | None = Field(
        default=None,
        description="미매핑 사유(match_method='unmapped'일 때 필수·그 외 금지).",
    )

    @field_validator("concept_id")
    @classmethod
    def _validate_concept_id(cls, value: str) -> str:
        """concept_id가 새 규약(`math.<area>.<slug>`)을 지키는지 검증(concept_graph 규약 공유)."""
        if not CONCEPT_ID_PATTERN.match(value):
            raise ValueError(
                f"concept_id 규약 위반: {value!r}. 예상 'math.<area>.<slug>' "
                "(예: 'math.geometry.samgakhyeongui-hapdong')"
            )
        return value

    @field_validator("atom_codes")
    @classmethod
    def _validate_atom_codes(cls, value: list[str]) -> list[str]:
        """원자 code 목록 — 빈 문자열 금지·중복 금지·사전순 정렬(결정론)."""
        if any(not code.strip() for code in value):
            raise ValueError("atom_codes에 빈 문자열 금지")
        if len(set(value)) != len(value):
            raise ValueError(f"atom_codes 중복 금지: {value!r}")
        if value != sorted(value):
            raise ValueError(f"atom_codes는 code 사전순이어야 함(결정론): {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_invariants(self) -> CrosswalkEntry:
        """행 내부 불변식 — match_method별 atom_codes/primary/unmapped_reason 상호 일관성.

        - unmapped: 후보 0·primary 없음·사유 필수·confidence 0.0 (강제 매핑 금지).
        - standard_code: 후보 정확히 1개(교집합 유일) = primary.
        - standard_code+name: 후보 ≥2(이름 랭킹이 개입한 경우만 이 값).
        - 매핑 공통: primary는 정확히 1개이며 atom_codes에 포함·사유 금지.
        """
        if self.match_method == MatchMethod.UNMAPPED.value:
            if self.atom_codes:
                raise ValueError("unmapped 행은 atom_codes가 비어야 함")
            if self.primary_atom_code is not None:
                raise ValueError("unmapped 행은 primary_atom_code가 None이어야 함")
            if not self.unmapped_reason:
                raise ValueError("unmapped 행은 unmapped_reason 필수")
            if self.confidence != 0.0:
                raise ValueError("unmapped 행은 confidence 0.0이어야 함")
            return self

        # 매핑된 행 공통 불변식
        if not self.atom_codes:
            raise ValueError("매핑 행은 atom_codes ≥1 필요")
        if self.primary_atom_code is None:
            raise ValueError("매핑 행은 primary_atom_code 필수(정확히 1개)")
        if self.primary_atom_code not in self.atom_codes:
            raise ValueError(f"primary_atom_code {self.primary_atom_code!r}가 atom_codes에 없음")
        if self.unmapped_reason is not None:
            raise ValueError("매핑 행은 unmapped_reason 금지")
        if self.match_method == MatchMethod.STANDARD_CODE.value and len(self.atom_codes) != 1:
            raise ValueError("standard_code 행은 후보가 정확히 1개여야 함(교집합 유일)")
        if self.match_method == MatchMethod.STANDARD_CODE_NAME.value and len(self.atom_codes) < 2:
            raise ValueError("standard_code+name 행은 후보 ≥2여야 함(이름 랭킹 개입)")
        return self
