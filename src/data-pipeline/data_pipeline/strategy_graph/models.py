"""전략 그래프 Pydantic 모델 — `StrategyNode`(문제 공략 heuristic canonical 노드).

리치 Part 2 스펙 Phase 6a. 문제 *공략 전략*(Polya 계획 단계의 heuristic)을 1급 노드로 승격한다.
노드는 학생이 문제를 만났을 때 *어떤 발상으로 접근하는가*(cognitive action)를 canonical 단위로
표현한다 — 스텝 단위 `ReasoningType`(한 추론 스텝이 무엇인가)이나 풀이 전체 `approach_type`
(완성된 풀이가 어떤 접근인가)과 **직교하는 축**이다. 상세 구별은 데이터카드 §축 구별 참조.

컨벤션(formula_graph/models.py 미러·enum-free 순수 TEXT): `ConfigDict(extra="forbid",
use_enum_values=True, str_strip_whitespace=True)` · 불변식은 `@field_validator` · 한국어 docstring.
skill_graph의 native enum·resolve.py는 미러하지 않는다(problem_type_graph/formula_graph 선례).

법적(CLAUDE.md 우선순위 #2): 전략 택소노미는 **전량 자체작성**(Polya·Schoenfeld·Engel·Zeitz의
표준 어휘로 수렴한 heuristic 추상)이라 저작권 무관 — 어느 책의 *본문도 복제하지 않는다*
(`description`은 인지행동 기준 자체 서술·`standard_codes`는 연결 코드만).

data-pipeline enum-free: 전략 family는 native enum이 아니라 순수 TEXT + 모듈 상수
`STRATEGY_FAMILIES` 화이트리스트로 검증한다(빌드타임 의존 최소·problem_type/formula 선례).
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 전략 택소노미는 자체작성 heuristic 추상 — Polya 표준 어휘로 수렴(어느 책 본문도 미복제).
SOURCE_CITATION: Final[str] = (
    "문제 공략 전략(problem-solving heuristic) 택소노미: 와이매스 자체작성"
    "(Polya 『How to Solve It』 계획 단계 표준 어휘 수렴·본문 미복제)."
)

# strategy_id 형식 — `strategy.<slug>`(교육과정·언어 무관·소문자·숫자·언더스코어[합성어]·하이픈).
# 합성 slug(work_backward 등)를 담기 위해 세그먼트 구분자로 `_`·`-`를 모두 허용한다.
STRATEGY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^strategy\.[a-z0-9]+([_-][a-z0-9]+)*$")

# 전략 slug 8종(closed 택소노미). strategy_id에서 'strategy.' 접두를 제거한 값과 일치한다.
# 두 인접 축과 문자열 disjoint하게 명명(work_backward≠backward·case_exhaustion≠case_split·
# pattern_seeking≠induction·reformulate≠transformation) — 데이터카드 §축 구별.
STRATEGY_SLUGS: Final[tuple[str, ...]] = (
    "specialize",
    "work_backward",
    "analogy",
    "reformulate",
    "auxiliary_construction",
    "pattern_seeking",
    "case_exhaustion",
    "contradiction",
)

# 전략 family 4종(closed 화이트리스트). 8 전략을 공략 발상의 성격으로 묶는다.
STRATEGY_FAMILIES: Final[tuple[str, ...]] = (
    "reduction",
    "transformation",
    "exploration",
    "indirect",
)


class StrategyNode(BaseModel):
    """전략 노드 — canonical 문제 공략 heuristic 1개(Polya 계획 단계·closed 택소노미).

    `strategy_id`(PK·`strategy.<slug>`)로 식별하고 `family`(4종 화이트리스트)로 묶는다.
    `description`은 표면 표현이 아니라 *인지행동(cognitive action) 기준*으로 무엇을 하는지 서술한다
    (자체작성·본문 미복제). 전략은 특정 성취기준에 종속되지 않으므로 `standard_codes`는 기본 빈
    배열이다. 별도 엣지·선수 DAG 없음(closed 8노드 택소노미·연결은 소비처 참조 키가 담당).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    strategy_id: str = Field(
        ...,
        description="전략 PK. 'strategy.<slug>'(예 'strategy.work_backward'). 교육과정·언어 무관.",
    )
    name_ko: str = Field(..., min_length=1, description="전략 표시명(한국어·자체작성).")
    family: str = Field(
        ...,
        min_length=1,
        description="전략 family(4종 화이트리스트: reduction·transformation·exploration·indirect).",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="인지행동 기준 자체작성 설명(표면 표현 아님·본문 미복제).",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="연결 NCIC 성취기준 코드(선택·전략은 특정 기준에 비종속·기본 []).",
    )

    @field_validator("strategy_id")
    @classmethod
    def _validate_strategy_id(cls, value: str) -> str:
        """strategy_id는 'strategy.<slug>' 형식(소문자·숫자·언더스코어·하이픈)."""
        if not STRATEGY_ID_PATTERN.match(value):
            raise ValueError(
                f"strategy_id 형식 위반: {value!r} — 'strategy.<slug>'(소문자·숫자·_·-) 필요."
            )
        return value

    @field_validator("family")
    @classmethod
    def _validate_family(cls, value: str) -> str:
        """family는 STRATEGY_FAMILIES 4종 중 하나(closed 화이트리스트·enum-free)."""
        if value not in STRATEGY_FAMILIES:
            raise ValueError(f"family 위반: {value!r} — {STRATEGY_FAMILIES} 중 하나여야 함.")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        """description은 비어있을 수 없음(인지행동 기준 자체작성 설명 필수)."""
        if not value:
            raise ValueError("description은 비어있을 수 없음 — 인지행동 기준 자체작성 설명 필요.")
        return value


__all__ = [
    "SOURCE_CITATION",
    "STRATEGY_FAMILIES",
    "STRATEGY_ID_PATTERN",
    "STRATEGY_SLUGS",
    "StrategyNode",
]
