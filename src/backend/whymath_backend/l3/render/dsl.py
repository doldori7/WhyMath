"""교수법-중립 콘텐츠 계약(ConceptDSL) — 렌더 어댑터의 유일한 입력.

설계 정본: `docs/architecture/03c_content_strategy_cache.md` §1(교수법-중립 콘텐츠 DSL).

이 모듈은 "무엇을 가르치는가"만 담는 렌더 입력 계약을 놓는다. **교수 *방식*(강의식·발견학습·
문답식·게임·탐구)은 이 계약에 들어오지 않는다** — 방식은 렌더 시점에 `PedagogyStrategy` 어댑터가
얹는다(Renderer=Plugin·5대 분리 Concept≠Renderer). 그 결과 저장 자산은 (개념 × 교수법)의 곱이
아니라 (중립 DSL + 어댑터 N개)의 합으로 유지된다(조합폭발 방지).

────────────────────────────────────────────────────────────────────────────
좌석 위치가 `schema/`가 아니라 `l3/render/`인 이유
────────────────────────────────────────────────────────────────────────────
`concept_content`는 projection-table 계열이라 schema/ Pydantic 표면을 두지 않는 house style이다
(`db/models/pedagogy_dsl.py` 모듈 docstring). 이 `ConceptDSL`은 *영속 계약*이 아니라 **렌더 입력
view**다 — 테이블을 새로 만들지 않고 기존 `concept_content` 행을 렌더가 소비할 형태로 투영한다.
따라서 소비처(L3 렌더)에 응집시키고, `schema/`가 `db/`를 임포트하는 역방향 결합도 피한다.

────────────────────────────────────────────────────────────────────────────
중립성 불변식 (`@model_validator` — 방식 오염을 형식 게이트에서 잡는다)
────────────────────────────────────────────────────────────────────────────
필드 *값*이 교수 방식을 지시하는 문장("소크라테스식으로 질문하라")을 담는 것은 계약 위반이다.
전수 검출은 불가능하므로(자연어), best-effort lint로 대표적 방식 지시어를 차단한다. 구조적
방어는 별도로 거버넌스 테스트(`test_render_governance.py`)가 *필드 이름* 축에서 동결한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 방식 지시어 블록리스트 — DSL 본문에 새어 들면 거부(교수법-중립 위반의 양성 신호).
# 이 목록은 *교수 방식*을 지시하는 어휘만 겨냥한다. 일반 교수학 어휘(정의·예시·오개념 등)는
# 콘텐츠의 정당한 구성요소이므로 넣지 않는다(오탐 방지·best-effort lint).
PEDAGOGY_METHOD_BLOCKLIST: tuple[str, ...] = (
    "소크라테스식",
    "문답식",
    "강의식",
    "발견학습",
    "완전예제",
    "게임형",
    "탐구식",
)


class ConceptAssessment(BaseModel):
    """평가 재료 — 렌더 결과를 기계 검증(SymPy)하기 위한 구조화 입력.

    `conditions`·`answer_map`은 `l3.verify_answer.verify_answer()`의 입력 형식 그대로다 —
    어댑터가 평가 문항을 렌더하면 같은 재료로 정답을 검증해 미검증 노출을 막는다. 평가 재료가
    없는 개념도 많으므로 `ConceptDSL.assessment`는 선택(None)이다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    conditions: tuple[str, ...] = Field(..., min_length=1, description="만족해야 할 조건식(AND)")
    answer_map: dict[str, str] = Field(..., description="변수→값 매핑(verify_answer 입력)")
    prompt: str | None = Field(
        default=None, description="평가 발문(방식 중립 — 없으면 어댑터가 조립)"
    )

    @model_validator(mode="after")
    def _require_answer(self) -> ConceptAssessment:
        """`answer_map`이 비면 검증이 불가능하므로 거부한다(빈 검증의 통과 위장 금지)."""
        if not self.answer_map:
            raise ValueError("ConceptAssessment.answer_map이 비었습니다 — 검증 불가한 평가 재료.")
        return self


class ConceptDSL(BaseModel):
    """교수법-중립 개념 콘텐츠 — 렌더 어댑터의 입력 계약("무엇을 가르치나"만).

    `db/models/concept_content.py::ConceptContent` 행의 렌더용 투영이다(`from_concept_content`).
    어떤 필드도 전달 *방식*을 규정하지 않는다 — 같은 인스턴스가 DIRECT·SOCRATIC·ANALOGY 어댑터에
    각각 들어가 서로 다른 화면을 낸다.

    본문 표기는 **렌더러-중립 LaTeX + 구조 태그**다(CLAUDE.md "표현≠의미" — 화면 문자열 금지).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., min_length=1, description="개념 코드(concept_content.code)")
    name: str = Field(..., min_length=1, description="개념명")
    subject: str = Field(..., min_length=1, description="과목")
    unit: str | None = Field(default=None, description="단원·영역")
    definition: str | None = Field(default=None, description="정의(정식 정의·학생 비노출 가능)")
    intuition: str | None = Field(default=None, description="직관·비유(표상 보조 — 방식 아님)")
    examples: tuple[str, ...] = Field(default=(), description="예시(표현 사례)")
    misconceptions: tuple[str, ...] = Field(
        default=(), description="오개념(반응형 소비·preload 아님)"
    )
    relations: tuple[str, ...] = Field(
        default=(), description="연결 코드(성취기준·원자 — 느슨참조)"
    )
    assessment: ConceptAssessment | None = Field(default=None, description="평가 재료(선택)")

    @model_validator(mode="after")
    def _enforce_pedagogy_neutrality(self) -> ConceptDSL:
        """중립성 불변식 — 본문에 교수 *방식* 지시어가 있으면 거부한다(best-effort lint).

        검사 대상은 자유 서술 필드(정의·직관·예시)다. `name`·`subject`·`unit`은 고유명사 성격이라
        제외한다(오탐 방지). 위반 시 어떤 필드의 어떤 어휘인지 밝혀 저작자가 고칠 수 있게 한다.
        """
        targets: list[tuple[str, str]] = []
        if self.definition is not None:
            targets.append(("definition", self.definition))
        if self.intuition is not None:
            targets.append(("intuition", self.intuition))
        targets.extend((f"examples[{i}]", text) for i, text in enumerate(self.examples))

        for field_name, text in targets:
            hits = [word for word in PEDAGOGY_METHOD_BLOCKLIST if word in text]
            if hits:
                raise ValueError(
                    f"교수법-중립 위반: code={self.code} 의 {field_name}에 교수 방식 지시어가 "
                    f"포함됐습니다: {hits}. 콘텐츠는 '무엇을 가르치나'만 담고, 전달 방식은 렌더 "
                    "어댑터(PedagogyStrategy)가 결정합니다."
                )
        return self


def _clean(value: object) -> str | None:
    """자유 텍스트 정규화 — 빈 문자열·공백만이면 None(없음과 빈칸을 구분하지 않는다)."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def from_concept_content(row: Any) -> ConceptDSL:
    """`ConceptContent` ORM 행 → 교수법-중립 `ConceptDSL` 투영.

    **이 함수 자체가 교수법-중립성 감사다** — `concept_content`의 모든 필드가 "무엇을 가르치나"
    축으로만 매핑되며, 전달 방식으로 매핑되는 필드가 하나도 없음을 코드로 증명한다:

      name                        → name          (무엇)
      formal_definition_internal  → definition    (무엇 — 학생 노출은 소비계층 정책)
      metaphor                    → intuition     (표상 보조·방식 아님)
      accepted_expressions        → examples      (표현 사례)
      misconception               → misconceptions(반응형 재료)
      standard_codes + atom_codes → relations     (연결)

    `explanation`(연결 맥락 gloss)은 의도적으로 매핑하지 않는다 — 코퍼스 실사용은 성취기준
    패러프레이즈지만, 필드 성격상 전달 서술이 누적될 위험이 가장 큰 자리라 렌더 입력에서 제외해
    중립성을 보수적으로 지킨다(필요해지면 별도 결정으로 연다).

    `flashcards`도 매핑하지 않는다 — `exposure_condition`(노출 시점)이 섞여 있어 순수 콘텐츠가
    아니라 노출·순서 힌트를 포함하며, 그 판단은 렌더/게이팅(L5·L6) 소관이다.

    인자 타입이 `Any`인 것은 이 모듈이 `db/`를 임포트하지 않기 위해서다(렌더는 ORM 세션에
    묶이지 않는다 — 어떤 공급원이든 같은 속성만 있으면 투영된다·테스트가 가벼워진다).
    """
    relations: list[str] = []
    for attr in ("standard_codes", "atom_codes"):
        codes = getattr(row, attr, None) or []
        relations.extend(str(code) for code in codes if str(code).strip())

    accepted = _clean(getattr(row, "accepted_expressions", None))
    misconception = _clean(getattr(row, "misconception", None))

    return ConceptDSL(
        code=str(row.code),
        name=str(row.name),
        subject=str(row.subject),
        unit=_clean(getattr(row, "unit", None)),
        definition=_clean(getattr(row, "formal_definition_internal", None)),
        intuition=_clean(getattr(row, "metaphor", None)),
        examples=(accepted,) if accepted else (),
        misconceptions=(misconception,) if misconception else (),
        relations=tuple(relations),
        assessment=None,  # 평가 재료는 concept_content에 없다 — 공급원이 따로 주입한다.
    )


__all__ = [
    "PEDAGOGY_METHOD_BLOCKLIST",
    "ConceptAssessment",
    "ConceptDSL",
    "from_concept_content",
]
