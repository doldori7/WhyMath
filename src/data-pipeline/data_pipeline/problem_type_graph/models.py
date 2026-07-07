"""문제유형 그래프 Pydantic 모델 — `ProblemTypeNode`(cognitive-action canonical 노드).

리치 Part 2 스펙 Phase 3. ProblemType을 `Problem` 스키마 속성에서 **1급 노드로 승격**한다. 노드는
문제가 *무슨 사고(cognitive action)를 요구하는가*를 canonical 단위로 표현한다 — 표면 구조
(`SignaturePattern`·어떻게 보이는가)와 **직교하는 축**(무엇을 사고하는가). 정본: 로드맵 Phase 3 +
ADR concept_node_layering_decision.md(스키마→1급 노드(P3)·≠surface).

**신규 enum 0(확정 D1)**: cognitive-action 축은 이미 `BehaviorArea`(Phase 2a·6종)다. 중복 archetype
enum을 두지 않고, 문제유형이 *exercise하는 스킬*(`behavior_skills`·skill_graph_v1 참조)로 "무슨
사고"를 표현한다 — 이것이 P3→P2 참조 링크이자 **신규 엣지 타입 0**의 실현이다.

컨벤션(skill_graph/models.py 미러): `ConfigDict(extra="forbid", use_enum_values=True,
str_strip_whitespace=True)` · 불변식은 `@field_validator` · 한국어 docstring.

법적(CLAUDE.md 우선순위 #2): 문제유형 택소노미는 **전량 자체작성**(cognitive-action 추상)이라
redaction 무관 — 평가원 기출 *문항 본문*을 담지 않는다(`standard_codes`는 연결 코드만).

anti-explosion: ProblemTypeNode는 **canonical·독립추정 가치 단위만**(문제마다 유형 찍어내기 금지).
유형 연결은 *참조 키*(`behavior_skills`)만 — 별도 엣지 테이블·prerequisite DAG 없음.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 문제유형 택소노미는 자체작성이라 NCIC 승계 문구 불요(기출 본문 미포함·standard_codes 코드만).
SOURCE_CITATION: Final[str] = (
    "문제유형(cognitive-action) 택소노미: 와이매스 자체작성(평가원 기출 문항 본문 미포함)."
)

# problem_type_id 형식 — `ptype.<slug>`(교육과정·언어 무관·소문자·숫자·하이픈). 표면
# `SignaturePattern`(UPPER_SNAKE 값)과 형식이 disjoint하다(분리 불변식·구조적 보장).
PROBLEM_TYPE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^ptype\.[a-z0-9]+(-[a-z0-9]+)*$")

# behavior_skills 원소 형식 — skill_graph의 `skill.<slug>`. 형식만 검증하고, 실재(dangling 0)는
# backend 거버넌스 테스트가 skill_graph_v1로 검증(cross-corpus).
_SKILL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^skill\.[a-z0-9]+(-[a-z0-9]+)*$")


class ProblemTypeNode(BaseModel):
    """문제유형 노드 — canonical cognitive-action 단위(≠surface SignaturePattern).

    `problem_type_id`(PK·`ptype.<slug>`)로 식별하고 `family`(문제유형 family 그룹)로 묶인다.
    `behavior_skills`(exercise하는 skill_id·**≥1개**)가 "무슨 사고를 요구하는가"를 표현한다 — 별도
    cognitive-action enum 없이 skill_graph_v1 스킬을 참조한다(신규 enum 0·신규 엣지 타입 0).
    `mastery_estimable`은 승격 게이트(무분별 증식 방지). 본문 슬롯 없음(자체작성 택소노미).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    problem_type_id: str = Field(
        ...,
        description="문제유형 PK. 'ptype.<slug>'(예 'ptype.optimize'). 교육과정·언어 무관.",
    )
    name_ko: str = Field(..., min_length=1, description="문제유형 표시명(한국어·자체작성).")
    family: str = Field(
        ...,
        min_length=1,
        description="문제유형 family(그룹·예 '최적화'). 관련 유형 묶음의 라벨.",
    )
    behavior_skills: list[str] = Field(
        ...,
        min_length=1,
        description="이 유형이 exercise하는 skill_id 목록(≥1개·`skill.<slug>`·skill_graph_v1). "
        "'무슨 사고인가'의 표현·P3→P2 참조 키·신규 엣지 타입 0.",
    )
    mastery_estimable: bool = Field(
        default=True,
        description="독립추정 게이트 — 이 유형의 숙달을 canonical 단위로 추정할 가치가 있는가.",
    )
    description: str | None = Field(
        default=None,
        description="문제유형 짧은 설명(자체작성·선택). 기출 문항 본문 복제 금지.",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="연결 NCIC 성취기준 코드(선택·truth source 코드만·본문 미복제).",
    )
    notes: str | None = Field(default=None, description="검수 메모(선택).")

    @field_validator("problem_type_id")
    @classmethod
    def _validate_problem_type_id(cls, value: str) -> str:
        """problem_type_id는 'ptype.<slug>' 형식(SignaturePattern 값과 형식 disjoint)."""
        if not PROBLEM_TYPE_ID_PATTERN.match(value):
            raise ValueError(
                f"problem_type_id 형식 위반: {value!r} — 'ptype.<slug>'(소문자·숫자·하이픈) 필요."
            )
        return value

    @field_validator("behavior_skills")
    @classmethod
    def _validate_behavior_skills(cls, value: list[str]) -> list[str]:
        """behavior_skills 원소는 'skill.<slug>' 형식(존재는 cross-corpus 거버넌스가 검증)."""
        for skill_id in value:
            if not _SKILL_ID_PATTERN.match(skill_id):
                raise ValueError(
                    f"behavior_skills 원소 형식 위반: {skill_id!r} — 'skill.<slug>'이어야 함."
                )
        return value


__all__ = [
    "PROBLEM_TYPE_ID_PATTERN",
    "SOURCE_CITATION",
    "ProblemTypeNode",
]
