"""수식 그래프 Pydantic 모델 — `FormulaNode`(canonical-only 수식 노드).

리치 Part 2 스펙 Phase 5a. 수식을 1급 노드로 승격하되 **canonical 표현만** 노드화한다 — 변형식
(변수명 치환·항 순서·표기 변이)은 노드화하지 않는다(조합폭발 방지·`math_dsl_risk_register.md` Q1③).
변형↔canonical 동치 판정은 **런타임 SymPy**(`l3/symbolic_equivalence.py`)에 위임한다 — 이 노드는
수식의 *정체성·참조 대상*만 담고 동치 계산(CAS·재작성 규칙)을 내장하지 않는다(SymPy 재구현 금지·
`math_dsl_evolution.md` §2.1).

**ID≠Signature 분리(확정 D1)**: `formula_id`는 **사람 관리 안정 code**(`formula.<slug>`)이지 SymPy
계산값이 아니다 — 알고리즘이 바뀌면 KG id 전체가 바뀌는 참사를 막는다. `canonical_signature`는
검색·dedup용 **optional 보조 메타**일 뿐 정체성이 아니다. `equivalence_class`·`sympy_repr`는 저장
안 함(변형 열거=anti-explosion·동치는 SymPy 런타임 위임·표준형은 dsl에서 파생).

컨벤션(problem_type_graph/models.py 미러): `ConfigDict(extra="forbid", use_enum_values=True,
str_strip_whitespace=True)` · 불변식은 `@field_validator` · 한국어 docstring.

법적(CLAUDE.md 우선순위 #2): canonical 수식은 **수학적 사실·표준 표기 자체작성**이라 저작권 무관
(교과서·기출 본문 미포함·`standard_codes`는 연결 코드만).

data-pipeline sympy-free: dsl의 SymPy-parseable 검증은 **backend 거버넌스**(sympy 보유)가 한다 —
빌드타임 파이프라인은 형식만 본다(계층 무관·의존 최소).
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# canonical 수식 = 수학적 사실·표준 표기 자체작성(교과서·기출 본문 미포함·standard_codes 코드만).
SOURCE_CITATION: Final[str] = (
    "canonical 수식 택소노미: 와이매스 자체작성(수학적 사실·표준 표기·교과서/기출 본문 미포함)."
)

# formula_id 형식 — `formula.<slug>`(교육과정·언어 무관·소문자·숫자·하이픈·점 계층 허용).
# 사람 관리 안정 code(SymPy 계산값 아님·알고리즘 변경 시 id 불변).
FORMULA_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^formula\.[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)*$"
)


class FormulaNode(BaseModel):
    """수식 노드 — canonical 표현 1개(변형 노드화 금지·동치는 SymPy 런타임 위임).

    `formula_id`(PK·`formula.<slug>`·사람 관리 안정 code)로 식별하고 `family`(수식 그룹)로 묶인다.
    `latex`(display 표기)·`dsl`(SymPy-parseable canonical 식)이 표현이고, `canonical_signature`는
    검색·dedup 보조 메타일 뿐 정체성이 아니다(optional). `aliases`는 *같은* canonical 수식의 display
    별칭 목록(변형 열거 아님). 본문 슬롯 없음(자체작성 수학 사실).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    formula_id: str = Field(
        ...,
        description="수식 PK. 'formula.<slug>'(예 'formula.quadratic.roots'). 사람 관리 안정 code.",
    )
    name_ko: str = Field(..., min_length=1, description="수식 표시명(한국어·자체작성).")
    family: str = Field(
        ...,
        min_length=1,
        description="수식 family(그룹·예 '근의공식'·'곱셈공식'). 관련 수식 묶음의 라벨.",
    )
    latex: str = Field(
        ...,
        min_length=1,
        description="canonical 표현의 display LaTeX(자체작성 표준 표기·화면용).",
    )
    dsl: str = Field(
        ...,
        min_length=1,
        description="canonical 표현의 SymPy-parseable 식(닫힌 검증 DSL). 동치 판정은 런타임 SymPy. "
        "parseable 검증은 backend 거버넌스가 수행.",
    )
    canonical_signature: str | None = Field(
        default=None,
        description="검색·dedup 보조 signature(optional·정체성 아님). 계산 backfill은 Phase 5b.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="같은 canonical 수식의 display 별칭(선택·변형 열거 아님·동치는 SymPy).",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="연결 NCIC 성취기준 코드(선택·truth source 코드만·본문 미복제).",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="성립 조건·사용범위(자체작성 텍스트·예 'a≠0'). 무조건 항등식은 []. "
        "유도·증명 슬롯이 아니다 — 유도는 Theorem/Proof 축(P6·D2) 위임(S4-06).",
    )
    mnemonic: str | None = Field(
        default=None,
        description="암기팁(선택·자체작성·자연스러운 것만 — 날조 저작 금지). 대부분 None(S4-06).",
    )
    notes: str | None = Field(default=None, description="검수 메모(선택).")

    @field_validator("formula_id")
    @classmethod
    def _validate_formula_id(cls, value: str) -> str:
        """formula_id는 'formula.<slug>' 형식(사람 관리 안정 code·SymPy 계산값 아님)."""
        if not FORMULA_ID_PATTERN.match(value):
            raise ValueError(
                f"formula_id 형식 위반: {value!r} — 'formula.<slug>'(소문자·숫자·하이픈·점) 필요."
            )
        return value


__all__ = [
    "FORMULA_ID_PATTERN",
    "SOURCE_CITATION",
    "FormulaNode",
]
