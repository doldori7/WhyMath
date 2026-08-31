"""SubjectAdapter — EOS Core가 과목에 요구하는 최소 행위 계약 (EOS-66 · Subject Contract v1).

계획서 100 §3.9의 원칙: **과목마다 반드시 존재하는 능력만 계약에 넣는다.** `evaluateAnswer()`는
공통성이 높지만 `renderEquation()`은 Math 전용이므로 계약이 아니다. 이 모듈은 그 선을 코드로
긋는다 — Core는 여기 정의된 것만 알고, 수학이 어떻게 그것을 하는지는 모른다.

## 왜 `schema`에 사는가

`schema`는 import-linter 7계층 계약의 **최하위**다(어느 계층도 import하지 않는다). 계약이
`l3`/`l4`를 참조하면 Core가 다시 Adapter를 알게 되므로, 계약은 순수 타입만으로 성립해야 한다.
그래서 이 파일은 `l3.verifier.VerificationVerdict` 같은 기존 결과 타입을 **재사용하지 않고**
중립 등가물을 따로 둔다. 그 변환이 곧 어댑터의 일이다(`l4.subject_adapter_math`).

## 불투명 페이로드 원칙

`answer_kind`·`conditions`·`answer`는 **과목이 정의하고 Core는 해석하지 않는 불투명 문자열**이다.
Core가 "이 문자열은 이차방정식"임을 알게 되는 순간 경계가 무너진다(계획서 100 §3.7의
`if problem.type == "quadratic"` 금지). 반대로 문자열 자체는 과목 중립이다 — Physics 어댑터는
같은 필드에 물리 관계식을 담고 자기 방식으로 해석한다.

## ⚠️ 정본화 ≠ 집행 — 이 계약을 경유하는 서빙 코드 경로는 **현재 0개**다

이 파일이 있다고 해서 경계가 집행되는 것이 아니다. 2026-08-31 기준 실측:

- `api.coach`·`l6.blueprint.assembly`·`l3.render.adapters`·`l3.pedagogy.slot_generator`는
  여전히 `l3.verify_*`·`l3.symbolic_equivalence`를 **직접 import**한다(11건 —
  `docs/architecture/eos_core_adapter_boundary.md` §4 A분류).
- 그 11건을 이 Protocol 호출로 바꾸는 **경유 배선은 후속 태스크**이며, 이 태스크의 범위가 아니다.
- 정적 강제(Core→Adapter import 금지)는 `EOS-67`이 import-linter로 세운다.

따라서 이 계약의 존재를 근거로 "Core가 수학을 모른다"고 말하면 안 된다. 지금 성립한 것은
**"수학을 모르고도 말할 수 있는 문장이 무엇인지"의 정의**까지다.

## v1이 3메서드인 이유 (`explain` 미포함)

계획서 100 §3.9는 `explain`을 후보로 들지만, 저장소 실측 결과 **위임할 공개 진입점이 0건**이다
(`l1`~`l6` 전수 grep — 공개 `explain*` 함수 없음. 설명 생성기는 전부 스켈레톤 생성기 내부의
비공개 `_explanation()`이고, 연령별 설명 생성은 EOS-53 crosswalk가 C9 **'신규'**로 판정했다).
없는 것을 계약에 넣으면 `NotImplementedError` 좌석이 생겨 "선언≠배선"이 하나 늘 뿐이다.
v1은 **위임 대상이 실재하는 3메서드로 시작**하고, `explain`은 생성 축이 착지한 뒤 별도 태스크로
계약에 추가한다.
"""

from __future__ import annotations

from typing import Literal, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

VerificationState = Literal["pass", "fail", "unverifiable"]
"""3상태 판정 — 2상태(정답/오답)로 접으면 '측정 실패'가 '오답'으로 위장된다.

`unverifiable`은 기계가 판정하지 못했다는 뜻이지 학생이 틀렸다는 뜻이 아니다. 이 저장소의
검증 권위 서열(측정 실패를 통과·미달로 위장 금지)이 타입 수준에서 강제되는 지점이다.
"""


class ProblemStatement(BaseModel):
    """Core → Adapter 전달 봉투 — Core가 *들고 있을 수는 있으나 해석하지 않는* 문항 페이로드.

    `l3.verifier.ProblemVerifyInput`과 필드가 겹치지만 **의도적으로 별개 타입**이다. 그쪽은 L3
    (Adapter) 내부 타입이라 `schema`가 import하면 계층 역방향이 된다. 둘 사이의 변환은
    `l4.subject_adapter_math.MathSubjectAdapter`가 수행하며, 그 변환이 어댑터의 존재 이유다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_ref: str = Field(
        description="canonical 문항 식별자(slug·external_id). **DB PK를 넣지 않는다** — "
        "계획서 100 §3.11 'ID에 DB PK 의미를 넣지 말 것'.",
    )
    question_text: str = Field(description="문항 지문. Core에는 불투명 텍스트.")
    answer: str = Field(description="정답 표현. 과목이 정의하는 불투명 문자열.")
    answer_kind: str = Field(
        description="답 종류 태그 — **과목이 정의하고 Core는 값을 해석하지 않는다**. "
        "Core가 이 값으로 분기하면 경계 위반이다.",
    )
    conditions: str = Field(
        default="",
        description="정답이 만족해야 할 제약. 수학이면 수식, 물리면 물리 관계식 — Core에는 불투명.",
    )


class AnswerEvaluation(BaseModel):
    """`evaluate_answer` 결과 — 3상태 + 사유. 과목 중립."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: VerificationState = Field(description="3상태 판정.")
    reason: str | None = Field(
        default=None,
        description="fail/unverifiable 사유. **학생에게 그대로 노출하지 않는다**(진단용).",
    )
    checked_axes: tuple[str, ...] = Field(
        default_factory=tuple,
        description="실제로 닫힌 검증 축. 빈 튜플 = 아무 축도 못 닫음(작동한 비율 원칙).",
    )


class ProblemValidation(BaseModel):
    """`validate_problem` 결과 — 3상태 + 닫힌 축/잔여 축. 과목 중립.

    `residual_axes`가 비어 있지 않다는 것은 **기계가 닫지 못한 축이 남았다**는 뜻이다. 이를
    무시하고 pass로 취급하면 미검증을 검증으로 위장하게 된다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: VerificationState = Field(description="3상태 판정.")
    reason: str | None = Field(default=None, description="fail/unverifiable 사유.")
    machine_axes: tuple[str, ...] = Field(default_factory=tuple, description="기계로 닫힌 축.")
    residual_axes: tuple[str, ...] = Field(
        default_factory=tuple, description="기계가 닫지 못해 교차검증·인간 폴백이 필요한 축."
    )


class MisconceptionSignal(BaseModel):
    """`detect_misconception` 결과 1건 — 오개념 **식별자**와 신뢰도. 과목 중립.

    오개념의 *내용*(정의·반례·개입 전략)은 여기 싣지 않는다 — Core는 코드만 받고, 내용이
    필요하면 오개념 DB(L1)에서 reactive하게 조회한다(구축 플레이북: 오개념 preload 금지).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(description="오개념 정본 ID(kebab-case). 과목별 네임스페이스는 과목 책임.")
    confidence: float = Field(ge=0.0, le=1.0, description="0~1 신뢰도.")
    matched_signals: tuple[str, ...] = Field(
        default_factory=tuple, description="매칭 근거 신호(디버그·UI). 학생 원문 아님."
    )


@runtime_checkable
class SubjectAdapter(Protocol):
    """모든 과목이 EOS Core에 제공해야 하는 최소 능력 3종.

    **여기에 메서드를 추가하기 전의 질문**(계획서 100 §3.9): 이 능력이 Physics·Chemistry·
    History에도 *반드시* 존재하는가? 아니면 Math 전용인가? 후자면 계약이 아니라 어댑터
    내부 공개 API로 둔다.

    금지 예: `render_equation()`·`parse_latex()`·`simplify_expression()` — 전부 Math 전용이다.
    """

    subject_id: str
    """과목 식별자(예: "math"). canonical ID 규칙상 DB PK가 아니다."""

    def evaluate_answer(
        self, problem: ProblemStatement, answer: Mapping[str, str]
    ) -> AnswerEvaluation:
        """학생 답이 문항 조건을 만족하는지 3상태로 판정한다.

        `answer`는 변수명 → 값 문자열 치환맵이다(단일 답은 항목 1개). 값의 *의미*는 과목이
        정한다 — Core는 매핑 구조만 안다.
        """
        ...

    def detect_misconception(
        self, student_work: str, *, top_k: int = 3
    ) -> Sequence[MisconceptionSignal]:
        """학생 풀이 텍스트에서 오개념 후보를 신뢰도 내림차순으로 반환한다.

        매칭 0이면 빈 시퀀스. **없는 오개념을 지어내지 않는다** — 빈 결과가 정상 응답이다.
        """
        ...

    async def validate_problem(self, problem: ProblemStatement) -> ProblemValidation:
        """문항이 스스로 정합한지(정답이 조건을 만족하는지 등) 기계 판정한다.

        비동기인 이유: 잔여 축이 남으면 교차검증(LLM 다관점)이 붙는 구현이 있다. 동기 구현은
        그냥 즉시 반환하면 된다.
        """
        ...
