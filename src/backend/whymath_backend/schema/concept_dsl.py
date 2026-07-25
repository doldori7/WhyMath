"""교수법-중립 콘텐츠 계약 `ConceptDSL` — "무엇을 가르치는가"만 담는 저장 자산(03c §1).

설계 정본: `docs/architecture/03c_content_strategy_cache.md` §1. 콘텐츠 DSL은 **교수법-중립**으로
한 번 생성해 영구 자산으로 저장하고, 학생 화면은 렌더 시점에 *교수법 어댑터*(`l3/render`)가
얹는다. 조합폭발의 해: 저장 = 중립 DSL(atom당 1) + 어댑터 N개(개념 무관) — *곱이 아니라 합*.

────────────────────────────────────────────────────────────────────────────
방식 지시 금지 (03c §1 절대 금기 — 이 계약의 정체성)
────────────────────────────────────────────────────────────────────────────
`ConceptDSL`의 **어떤 필드도 "이것을 소크라테스식으로 가르쳐라" 같은 *방식 지시*를 담지 않는다.**
방식(설명/질문/문제/비유/시각화…)은 `schema/enums.py::PedagogyStrategy`로 표현되고, 렌더 시점에
어댑터가 결정한다(방식은 어댑터가 렌더 시점에·03c §2). 이 금기는 두 방향에서 구조적으로 강제된다:
  ① `ConfigDict(extra="forbid")` — 외부에서 `strategy`/`mode` 등 방식 필드를 주입할 수 없다.
  ② `@model_validator`(`_governance`) — 계약 *자신의* 필드명이 방식 토큰을 포함하지 않음을 동결
     (미래 세션이 방식 필드를 심으면 즉시 red — `test_embedding_namespace_governance` 선례 동형).

본문 표기는 **렌더러-중립 LaTeX + 구조 태그**(완전 AST 아님·화면 문자열 금지·CLAUDE.md L55).
숫자·맥락은 슬롯화(`ExampleSpec.slots`)해 "숫자/이름만 다른 두 DSL = 위반"(render 바인딩이지 새
자산 아님·03c §5) 거버넌스를 뒷받침한다.

────────────────────────────────────────────────────────────────────────────
평가 시드의 닫힌 검증 DSL (SymPy 검증 가능 구조) — *게이트는 l3/render*
────────────────────────────────────────────────────────────────────────────
`AssessmentSeed.conditions`는 **SymPy로 검증 가능한 닫힌 (부)등식 DSL**만 허용하고, 정답
(`answer`)은 `verify_answer` 치환맵 계약(예 `{"x":"2"}`)을 따른다(코드가 정답을 소유·검증
·derive-and-verify). 다만 그 닫힌-DSL 게이트(`condition_dsl_violation`·pseudo-DSL 거부)는
**여기서 실행하지 않는다** — `condition_dsl_violation`은 `l3.equivalent`(SymPy 래퍼)에 있고,
schema는 7계층 최하위라 상위(l1~l6)를 import할 수 없기 때문이다(import-linter 계약·역방향 금지).
게이트는 이 계약을 *소비하는* `l3/render.validate_concept_dsl`(schema·l3.equivalent 둘 다 정당하게
import)에서 구성 경계에 건다 — 관심사 분리(순수 데이터 계약 ≠ SymPy 의미 게이트)이자 단일 진실
원천 재사용(게이트 로직 복제 없음).

7계층: schema(최하위 순수 타입·상위 계층 import 0). 이 모듈은 Pydantic·표준 라이브러리만 쓴다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 근 선택(answer_selection) 허용 값 — verify_root_selection·derive_selected_root와 동일 규약.
_ALLOWED_SELECTIONS: frozenset[str] = frozenset({"largest", "smallest", "unique"})

# 방식(교수법) 토큰 — 계약 필드명이 이 중 하나를 *부분 문자열로* 포함하면 거버넌스 위반.
# 콘텐츠(무엇을)와 방식(어떻게)의 경계 동결: `strategy`/`socratic`/`worked` 등이 필드로 새어들면
# ConceptDSL이 방식-중립을 잃는다(03c §1). ⚠️ "misconception"(오개념 *참조*)·"example"(예시
# *콘텐츠*)·"relation"(개념 관계)은 방식이 아니라 콘텐츠이므로 포함하지 않는다.
_FORBIDDEN_METHOD_TOKENS: frozenset[str] = frozenset(
    {
        "strategy",
        "pedagogy",
        "socratic",
        "worked_example",
        "problem_based",
        "retrieval",
        "spacing",
        "interleaving",
        "self_explanation",
        "analogy",
        "visualization",
        "game",
        "gamif",
        "teach",
        "instruction",
        "render_as",
        "how_to",
        "hint_level",
    }
)


class ExampleSpec(BaseModel):
    """구조화 예시 하나 — 렌더러-중립 본문 + 슬롯화된 숫자/맥락.

    `statement`는 렌더러-중립 LaTeX(+구조 태그)이고, 숫자·맥락은 `slots`로 분리해 "숫자만 다른
    두 예시 = 같은 구조"(render 바인딩)를 뒷받침한다. `note`는 부가 설명(선택).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement: str = Field(..., description="예시 본문(렌더러-중립 LaTeX + 구조 태그)")
    slots: dict[str, str] = Field(
        default_factory=dict, description="숫자/맥락 슬롯(예 {'a':'2','context':'거리'})"
    )
    note: str | None = Field(default=None, description="부가 설명(선택·렌더러-중립)")


class RelationRef(BaseModel):
    """개념 관계 참조 — 원자 code 느슨참조 + 관계 유형(prerequisite 등).

    `atom_code`는 원자 백본 노드 code로의 *느슨참조*(FK 아님·`concept_content` 선례)다. `kind`는
    관계 유형 문자열(예 'prerequisite')로, `schema/enums.py::EdgeType` 의미와 느슨 정합하되 저장
    경계에서는 str로 둔다(느슨참조·curriculum overlay 원칙). 본문은 담지 않는다(id/코드 참조만).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    atom_code: str = Field(..., description="원자 백본 노드 code(느슨참조·본문 미보유)")
    kind: str = Field(..., description="관계 유형(예 'prerequisite'·EdgeType 의미와 느슨 정합)")


class AssessmentSeed(BaseModel):
    """평가 재료 시드 — SymPy 검증 가능한 조건 + 정답 치환맵(+선택적 근 선택).

    `conditions`는 닫힌 검증 DSL(맨 (부)등식)만 허용한다(`condition_dsl_violation` 게이트).
    `answer`는 `verify_answer` 치환맵 계약(예 {"x":"2"})으로, 코드가 정답을 소유·검증한다.
    `selection`(선택)은 "큰 근/작은 근/유일"류 문항에서 어느 근인지(`derive_selected_root` 규약).
    `prompt`(선택)는 렌더러-중립 발문(어댑터가 문제/완전예제로 렌더).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    conditions: list[str] = Field(
        ..., min_length=1, description="SymPy 검증 가능 조건(닫힌 (부)등식 DSL·최소 1)"
    )
    answer: dict[str, str] = Field(..., description="정답 치환맵(verify_answer 계약·예 {'x':'2'})")
    selection: str | None = Field(
        default=None, description="근 선택(largest/smallest/unique)·선택적"
    )
    prompt: str | None = Field(default=None, description="발문(선택·렌더러-중립)")

    @model_validator(mode="after")
    def _validate_seed(self) -> AssessmentSeed:
        """정답 비어있지 않음 + 근 선택 허용값 검증(구조적 시드 유효성)."""
        if not self.answer:
            raise ValueError("assessment answer 치환맵이 비어 있습니다(정답 미보유)")
        if self.selection is not None and self.selection not in _ALLOWED_SELECTIONS:
            raise ValueError(
                f"selection={self.selection!r}은 허용되지 않습니다 — "
                f"{sorted(_ALLOWED_SELECTIONS)} 중 하나여야 합니다."
            )
        return self


class ConceptDSL(BaseModel):
    """교수법-중립 콘텐츠 계약 — "무엇을 가르치는가"만 담는 영구 저장 자산(03c §1).

    방식(설명/질문/문제/비유…)은 담지 않는다 — 방식은 어댑터가 렌더 시점에(`PedagogyStrategy` +
    `l3/render`). `extra="forbid"` + `_governance` 검증이 방식-중립을 양방향으로 동결한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., description="개념명(과목 불변 id — 예 'math.algebra.linear-equation')")
    definition: str = Field(..., description="정의(렌더러-중립 LaTeX + 구조 태그)")
    examples: list[ExampleSpec] = Field(
        default_factory=list, description="구조화 예시(숫자/맥락 슬롯화)"
    )
    misconception_ids: list[str] = Field(
        default_factory=list,
        description="오개념 참조 id(본문 미보유·반응형 — misconception_catalog 위임)",
    )
    relations: list[RelationRef] = Field(
        default_factory=list, description="개념 관계(atom_code 느슨참조·prerequisite 등)"
    )
    assessment: list[AssessmentSeed] = Field(
        default_factory=list, description="평가 재료 시드(SymPy 검증 가능 구조)"
    )

    @model_validator(mode="after")
    def _governance(self) -> ConceptDSL:
        """거버넌스 게이트(구조) — 방식-중립 동결(03c §1·§5).

        방식 필드 금지(구조 동결): 계약 *자신의* 필드명이 방식 토큰(strategy/socratic/…)을
        포함하지 않음을 확인한다. `extra="forbid"`가 외부 주입을 막고, 이 검사가 내부 필드 증식을
        막는다(양방향 — 미래 세션이 방식 필드를 심으면 즉시 red·`test_concept_dsl` 동결).

        ⚠️ 평가 조건 *닫힌-DSL* 게이트(`condition_dsl_violation`·pseudo-DSL 거부)는 여기가 아니라
        `l3/render.validate_concept_dsl`에 있다 — schema는 최하위라 l3(SymPy 래퍼)를 import할 수
        없다(import-linter 역방향 금지). 게이트는 이 계약을 소비하는 렌더 계층 구성 경계에서 건다.
        """
        # 방식 필드 금지 — 필드명(소문자)에 방식 토큰이 부분 문자열로 있으면 위반.
        for field_name in type(self).model_fields:
            lowered = field_name.lower()
            for token in _FORBIDDEN_METHOD_TOKENS:
                if token in lowered:
                    raise ValueError(
                        f"ConceptDSL 필드명 {field_name!r}에 방식 토큰 {token!r}이 포함됩니다 — "
                        "방식 지시 금지(방식은 어댑터가 렌더 시점에·03c §1)."
                    )
        return self


__all__ = [
    "AssessmentSeed",
    "ConceptDSL",
    "ExampleSpec",
    "RelationRef",
    "build_example_concept_dsl",
]


def build_example_concept_dsl(
    *,
    name: str = "math.algebra.linear-equation",
    coef: int = 2,
    const: int = 3,
    rhs: int = 7,
    var: str = "x",
    context: str = "거리",
) -> ConceptDSL:
    """테스트·문서용 유효 `ConceptDSL` 팩토리 — SymPy 검증 가능한 일차 조건 시드 포함.

    `coef*var + const = rhs` (예 `2*x + 3 = 7` → `x = 2`)를 조건으로, 정답은 코드가 계산한다
    (`(rhs - const) / coef` — 정수로 나눠떨어지는 인자만 전달할 것). `name`·숫자·`context`만 바꾼
    두 DSL은 *구조 동일·바인딩만 다름*(거버넌스 대칭 테스트의 재료). 방식은 담지 않는다.
    """
    if coef == 0 or (rhs - const) % coef != 0:
        raise ValueError("build_example_concept_dsl: 정수 해가 되도록 coef/const/rhs를 주십시오")
    solution = (rhs - const) // coef
    return ConceptDSL(
        name=name,
        definition=(
            f"미지수 {var}에 대한 일차 조건 ${coef}{var} + {const} = {rhs}$의 해를 구하는 개념."
        ),
        examples=[
            ExampleSpec(
                statement=f"${coef}{var} + {const} = {rhs}$",
                slots={"coef": str(coef), "const": str(const), "rhs": str(rhs), "context": context},
                note=f"양변에서 {const}을 빼고 {coef}로 나눈다.",
            ),
        ],
        misconception_ids=["mc-transpose-sign"],
        relations=[RelationRef(atom_code="A1", kind="prerequisite")],
        assessment=[
            AssessmentSeed(
                conditions=[f"{coef}*{var} + {const} = {rhs}"],
                answer={var: str(solution)},
                prompt=f"조건 ${coef}{var} + {const} = {rhs}$을 만족하는 {var}의 값을 구하시오.",
            ),
        ],
    )
