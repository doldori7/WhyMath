"""스킬 그래프 Pydantic 모델 — `SkillNode` 노드 + `BehaviorArea` 폐쇄 enum.

리치 Part 2 스펙 Phase 2a. Skill을 `CognitiveType` enum 속성에서 **1급 노드로 승격**한다. 노드는
개념이 *행동*으로 무엇을 하는지(cognitive action)를 mastery 독립추정 단위로 표현한다 — 개념(무엇)과
직교하는 축(어떻게). 정본: 로드맵 `/root/.claude/plans/part-2-scalable-lobster.md` Phase 2a +
ADR `docs/architecture/concept_node_layering_decision.md` §2.

컨벤션(concept_graph/models.py·atom_graph/models.py 미러): `ConfigDict(extra="forbid",
use_enum_values=True, str_strip_whitespace=True)` · 축은 `str`-Enum · 불변식은 `@field_validator` ·
한국어 docstring.

법적(CLAUDE.md 우선순위 #2): 행동영역·스킬 택소노미는 **전량 와이매스 자체작성**이라 redaction
대상이 아니다(성취기준·교과서 본문 미포함). `standard_codes`는 선택적 연결 *코드*만(본문 미복제).

anti-explosion(구축 플레이북 2대 철칙): SkillNode는 **canonical·mastery 독립추정 단위만** —
개념마다 스킬을 찍어내지 않는다(무분별 증식 금지). 스킬 연결은 *참조 키*(`prerequisite_skill_ids`·
개념측 `behavior_skills`)만 — **신규 엣지 타입 0**(별도 SkillEdge·그래프 미도입).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 스킬 택소노미는 자체작성이라 NCIC 승계 문구 불요(성취기준 본문 미포함·standard_codes 코드만).
SOURCE_CITATION: Final[str] = "행동영역·스킬 택소노미: 와이매스 자체작성(성취기준 본문 미포함)."


class BehaviorArea(str, Enum):
    """행동영역(cognitive action) 폐쇄 enum — 6종(2026-07-03 확정). 개념이 *어떻게* 작동하는지의 축.

    English value(backend `CognitiveType` 스타일 미러·backend `schema/enums.py::BehaviorArea`와 값
    동일). 폐쇄 6종 — 확장은 ADR 갱신 전제(무분별 증식 금지·`test_skill_governance` 동결).
    """

    COMPUTE = "COMPUTE"  # 계산실행 — 절차·연산 수행(예: 다항식 나눗셈)
    TRANSFORM = "TRANSFORM"  # 식변형 — 표현을 등가 형태로 변형(예: 인수분해)
    INTERPRET = "INTERPRET"  # 조건해석 — 주어진 조건·문제를 수학 구조로 해석
    REPRESENT = "REPRESENT"  # 표상/표현 — 그래프·도형·다중표현 전환
    REASON = "REASON"  # 추론 — 연역·논리적 근거 전개
    VERIFY = "VERIFY"  # 검증 — 결과 점검·반례·타당성 확인(Polya 반성)


# enum 값의 단일 진실(테스트·검증·backend 정합 공용). 추가 시 위 Enum만 갱신.
BEHAVIOR_AREAS: Final[tuple[str, ...]] = tuple(a.value for a in BehaviorArea)

# skill_id 형식 — `skill.<slug>`(교육과정·언어 무관 의미론 id·concept_graph id 규약 축소).
# behavior_area는 별도 필드가 단일 진실이라 id에 *넣지 않는다*(드리프트 방지·id는 opaque 식별자).
SKILL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^skill\.[a-z0-9]+(-[a-z0-9]+)*$")


class SkillNode(BaseModel):
    """스킬 노드 — mastery 독립추정 가능한 cognitive-action 단위(개념과 직교하는 '어떻게' 축).

    `skill_id`(PK·`skill.<slug>` 의미론 id)로 식별하고 `behavior_area`(6종 폐쇄 축)에 속하며
    `family`(Skill Family 연속체)로 묶인다. `mastery_estimable`은 승격 게이트 — 이 노드가 실제로
    학습자별 숙달을 독립추정할 가치가 있는지의 명시 플래그(무분별 증식 방지·리치 스펙 기준).

    스킬 연결은 *참조 키*만: `prerequisite_skill_ids`(선수 스킬)·개념측 `behavior_skills`(Phase 2b).
    별도 엣지 테이블·그래프를 두지 않는다(신규 엣지 타입 0·anti-explosion). 본문 슬롯 없음(자체작성
    택소노미라 redaction 무관하나, `description`은 자체작성 짧은 설명만 — 교과서 본문 아님).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    skill_id: str = Field(
        ...,
        description="스킬 PK. 'skill.<slug>'(예 'skill.polynomial-division'). 교육과정·언어 무관.",
    )
    name_ko: str = Field(..., min_length=1, description="스킬 표시명(한국어·자체작성).")
    behavior_area: BehaviorArea = Field(
        ..., description="행동영역(6종 폐쇄 축·COMPUTE/TRANSFORM/INTERPRET/REPRESENT/REASON/VERIFY)"
    )
    family: str = Field(
        ...,
        min_length=1,
        description="Skill Family(연속체 그룹·예 '다항식 연산'). 관련 스킬 묶음의 라벨.",
    )
    mastery_estimable: bool = Field(
        default=True,
        description="mastery 독립추정 게이트 — 학습자별 숙달을 독립추정할 canonical 가치가 있는가.",
    )
    description: str | None = Field(
        default=None,
        description="스킬 짧은 설명(자체작성·선택). 교과서 본문 복제 금지.",
    )
    prerequisite_skill_ids: list[str] = Field(
        default_factory=list,
        description="선수 스킬 skill_id 목록(참조 키·초기 dangling 허용·신규 엣지 타입 0).",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="연결 NCIC 성취기준 코드(선택·truth source 코드만·본문 미복제).",
    )
    notes: str | None = Field(default=None, description="검수 메모(선택).")

    @field_validator("skill_id")
    @classmethod
    def _validate_skill_id(cls, value: str) -> str:
        """skill_id는 'skill.<slug>' 형식(교육과정·언어 무관 의미론 id)."""
        if not SKILL_ID_PATTERN.match(value):
            raise ValueError(
                f"skill_id 형식 위반: {value!r} — 'skill.<slug>'(소문자·숫자·하이픈)이어야 합니다."
            )
        return value


__all__ = [
    "BEHAVIOR_AREAS",
    "SKILL_ID_PATTERN",
    "SOURCE_CITATION",
    "BehaviorArea",
    "SkillNode",
]
