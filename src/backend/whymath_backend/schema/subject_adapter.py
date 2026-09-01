"""SubjectAdapter — EOS Core가 과목에 요구하는 최소 행위 계약 (EOS-66 v1 · EOS-69 v2).

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

## 집행 — 이 계약을 경유하는 서빙 코드 경로 (EOS-69로 배선됨)

EOS-66이 이 파일을 만들었을 때 계약을 경유하는 서빙 경로는 **0개**였다(그 사실을 이 자리에
경고로 적어 두었다). `EOS-69`가 그 0을 없앴다 — 아래가 현재 이 계약을 실제로 부르는 Core
코드다(2026-09-01 실측·`docs/architecture/eos_core_adapter_boundary.md` §4 A분류의 해소):

| Core 호출부 | 계약 메서드 | 이전(직접 import) |
|---|---|---|
| `api.coach._final_answer_state` | `evaluate_final_answer` | `l3.verify_final_answer` |
| `l3.render.adapters._assessment_signal` | `evaluate_answer` | `l3.verify_answer.verify_answer` |
| `l3.render.adapters._seal_signal` | `check_content_seal` | `l3.equivalent.rephrase.*` |
| `l3.pedagogy.slot_generator` | `check_equivalence_claim` | `l3.symbolic_equivalence` |

구현체는 **조립 지점**(`whymath_backend.subject_registry`)에서만 주입된다 — 호출부는 이
Protocol 타입만 알고 `l4.subject_adapter_math`를 import하지 않는다(그것이 곧 EOS-67 계약이
잡는 위반이다). 정적 강제는 `lint-imports`, 실측은 경계 스캔 스크립트가 판정한다.

**여전히 성립하지 않는 것**: "Core가 수학을 전혀 모른다"는 아직 아니다. MIXED 34모듈·`api.ocr`
계열은 여전히 수학 페이로드를 안다(경계 문서 §4 한계). 성립한 것은 **A분류 진성 위반 경로가
계약을 경유한다**는 것까지다.

## 계약 표면의 성장 기록 — v1 3메서드 → v2 6메서드 (`explain`은 여전히 미포함)

**메서드를 늘리는 것은 비용이다.** 계약이 커질수록 새 과목 어댑터가 채워야 할
`NotImplementedError` 좌석이 늘고, "선언은 있는데 배선은 없다"가 하나씩 는다. 그래서 추가
기준을 셋으로 못 박는다 — 셋을 **전부** 통과해야 계약에 들어온다:

  (a) **과목 보편성** — Physics·Chemistry·History에도 *반드시* 존재하는 능력인가?
      (계획서 100 §3.9. `render_equation()`처럼 Math 전용이면 어댑터 내부 공개 API로 둔다.)
  (b) **실재 위임 대상** — 오늘 이 저장소에 위임할 공개 함수가 있는가? (없으면 좌석만 는다.)
  (c) **실재 Core 호출부** — 오늘 이 계약을 부를 Core 코드가 있는가? (없으면 소비처 0 추상.)

v1(EOS-66) 3메서드 — `evaluate_answer`·`detect_misconception`·`validate_problem`.
v2(EOS-69)가 더한 3메서드와 그 근거:

- **`evaluate_final_answer`** — "학생이 낸 *최종 답*이 이 문항의 정답과 같은가."
  (a) 채점이 있는 모든 과목의 가장 기본 능력이다(물리 `3.2 m/s`, 화학 균형반응식, 역사 연도).
  (b) `l3.verify_final_answer.verify_final_answer`. (c) `api.coach._final_answer_state`.
  **`evaluate_answer`와 다른 질문이다** — 저쪽은 "답이 문항의 *조건*을 만족하는가"(제약 충족),
  이쪽은 "답이 *정답 키*와 같은가"(정답 대조). 조건이 없는 문항(객관식·단답)에는 저쪽을 쓸 수
  없고, 정답 키가 없는 생성 문항에는 이쪽을 쓸 수 없다. 하나로 합치면 둘 중 하나가 거짓말이 된다.

- **`check_equivalence_claim`** — "콘텐츠가 스스로 주장하는 등가 관계가 참인가."
  (a) 자체 저작 콘텐츠를 검수하는 파이프라인은 과목을 가리지 않고 이 질문을 한다(물리 단위
  환산 주장, 화학 몰 계산 주장, 역사 "임진왜란 = 1592년"). 주장의 *표현*은 과목 것이고, 참/거짓
  판정도 과목 것이다 — Core는 묻기만 한다. (b) `l3.symbolic_equivalence.identity_status`.
  (c) `l3.pedagogy.slot_generator.verify_slot_payload`(생성 슬롯의 `sympy_verified` 표기).

- **`check_content_seal`** — "원문에서 파생된 텍스트가 과목 표기 봉인을 지켰는가."
  (a) 모든 과목에는 *변형되면 의미가 바뀌는 정형 표기*가 있다(수식·단위·화학식·연도). 렌더·
  재서술이 그것을 훼손했는지 판정할 수 있는 것은 자기 표기를 아는 과목뿐이다. (b)
  `l3.equivalent.rephrase.extract_equation` + `classify_invariance_failure`.
  (c) `l3.render.adapters._seal_signal`.

**여전히 넣지 않은 것 — `explain`**: EOS-66이 판정한 사유가 그대로 유효하다. 위임할 공개
진입점이 0건이다(`l1`~`l6` 전수 grep — 공개 `explain*` 함수 없음. 설명 생성기는 전부 스켈레톤
생성기 내부의 비공개 `_explanation()`이고, 연령별 설명 생성은 EOS-53 crosswalk가 C9 '신규'로
판정). 기준 (b)를 통과하지 못하므로 넣지 않는다 — 생성 축이 착지한 뒤 별도 태스크가 다룬다.

## 결과 *타입* 의존을 위한 중립 뷰 (EOS-69)

계약이 흡수해야 할 Core→Adapter 의존이 전부 "메서드 호출"인 것은 아니다. `l6.blueprint.
assembly.partial_credit`은 수학 함수를 *부르지 않고* `SolutionVerificationResult`를 **결과
타입으로 소비**한다(단계별 3상태를 읽어 부분점수를 매긴다). 이런 의존은 Protocol 메서드로
흡수되지 않는다 — 필요한 것은 *중립 결과 타입*이다.

그래서 이 파일은 `StepVerificationView`·`SolutionVerificationView`(구조적 Protocol)를 둔다.
**변환기가 아니라 뷰인 이유**: 변환(어댑터 타입 → 중립 모델 복사)을 넣으면 그 변환 함수가
3상태를 접을 수 있는 자리가 하나 새로 생긴다. 뷰는 같은 객체를 *덜 보는* 것뿐이라 접을 자리
자체가 없다. 선례는 이 저장소 안에 있다 — `l3.verify_final_answer.ProblemAnswerView`가 db
계층을 import하지 않으려고 쓰는 것과 같은 기법이다(구조적 타이핑).
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable

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


class ContentSealBreach(BaseModel):
    """`check_content_seal` 결과 — 봉인 위반 1건. 과목 중립.

    `reason`은 **과목이 정의하는 폐쇄 사유 코드**다(Core는 값을 해석하지 않고 로그·신호에
    실어 나르기만 한다). `derived_index`는 위반이 발견된 파생 텍스트의 인덱스로, Core가
    "어느 조각이 깨졌는지"를 자기 어휘(세그먼트 종류 등)로 되짚을 수 있게 한다 — 인덱스는
    과목 지식이 아니라 Core가 넘긴 리스트의 위치다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(description="봉인 위반 사유 코드 — 과목이 정의하는 어휘(Core에 불투명).")
    derived_index: int = Field(
        ge=0,
        description="위반이 난 파생 텍스트의 인덱스(호출 시 넘긴 순서 그대로).",
    )


STEP_STATE_CORRECT = "correct"
STEP_STATE_INCORRECT = "incorrect"
STEP_STATE_UNVERIFIABLE = "unverifiable"
"""단계 검증 3상태 어휘 — `StepVerificationView.state`가 갖는 폐쇄 값.

`VerificationState`(pass/fail/unverifiable)와 **어휘가 다른 이유**: 단계 검증이 묻는 것은
"이 변형이 동치인가"이지 "답이 맞았는가"가 아니라, 저장소가 처음부터 correct/incorrect를
써 왔다. 여기서 pass/fail로 번역하면 번역기가 하나 생기고, 번역기는 3상태를 접을 수 있는
자리다. 어휘를 그대로 두고 Core가 비교에 쓸 상수만 중립 좌석에 둔다(문자열 리터럴이 Core
코드에 흩어지는 것도 막는다).
"""


@runtime_checkable
class StepVerificationView(Protocol):
    """단계(전이) 검증 결과 1건에 대한 **중립 뷰** — Core가 볼 수 있는 최소 표면.

    Core가 알아야 하는 것은 "이 전이가 correct/incorrect/unverifiable 중 무엇인가"뿐이다.
    사유 문장·증거 가중치·단계 종류처럼 과목·검증기 내부 개념은 이 뷰에 없다 — 없으면 Core가
    그것으로 분기할 수 없다.

    `state`를 `str`로 선언한 이유: 어댑터 쪽 구현이 `str` 혼합 Enum이라(값이 곧 문자열)
    구조적으로 그대로 만족한다. 읽기 전용 property라 공변이므로 Enum 멤버가 그대로 들어온다.
    비교는 반드시 위 `STEP_STATE_*` 상수와 한다(리터럴 산포 금지).
    """

    @property
    def state(self) -> str:
        """3상태 — `STEP_STATE_CORRECT`/`_INCORRECT`/`_UNVERIFIABLE` 중 하나."""
        ...


@runtime_checkable
class SolutionVerificationView(Protocol):
    """여러 단계 연쇄 검증 집계에 대한 **중립 뷰**.

    `l6.blueprint.assembly.partial_credit`(부분점수)·`api.coach`(검산 이벤트 적재)가 소비한다.
    둘 다 수학 함수를 부르지 않고 *결과를 읽기만* 하므로, 계약이 줘야 하는 것은 메서드가 아니라
    타입이다.

    **3상태를 접지 않는 형태로 설계했다**: `n_unverifiable`과 `n_incorrect`가 별개 필드이고
    `steps[i].state`가 전이별 3상태를 그대로 들고 있다. 어느 소비자도 "검증 불가"를 "오답"으로
    합산할 수 없다 — 합치려면 두 필드를 일부러 더해야 하고, 그건 코드에 드러난다.
    """

    @property
    def steps(self) -> Sequence[StepVerificationView]:
        """전이별 결과(순서 보존·길이 == `n_transitions`)."""
        ...

    @property
    def n_correct(self) -> int:
        """correct 전이 수."""
        ...

    @property
    def n_incorrect(self) -> int:
        """incorrect 전이 수 — **검증 불가와 합치지 않는다**."""
        ...

    @property
    def n_unverifiable(self) -> int:
        """검증 불가 전이 수 — "기계가 판정 못 함"이지 "학생이 틀림"이 아니다."""
        ...

    @property
    def n_transitions(self) -> int:
        """총 전이 수. 세 카운트의 합과 같다(전이 0이면 '검증할 것이 없음'이지 실패가 아니다)."""
        ...

    @property
    def unverified_ratio(self) -> float:
        """검증 불가 비율. 전이 0이면 0.0."""
        ...

    @property
    def first_incorrect_index(self) -> int | None:
        """첫 incorrect 전이의 인덱스(없으면 None)."""
        ...

    @property
    def unverifiable_reason_counts(self) -> Mapping[str, int]:
        """검증 불가 사유 코드 → 건수(값 합 == `n_unverifiable`).

        키는 **과목이 정의하는 폐쇄 코드 문자열**이고 Core는 해석하지 않는다(집계·적재만).
        어댑터가 이미 문자열로 내주므로 Core가 Enum을 풀 일이 없다 — Core가 `code.value`를
        부르는 순간 그것은 어댑터 타입을 아는 것이다.
        """
        ...


@runtime_checkable
class ProblemAnswerKeyView(Protocol):
    """**정답 키를 보유한 문항**에 대한 중립 뷰 — `evaluate_final_answer` 입력.

    왜 `ProblemStatement`(값 봉투)가 아니라 뷰인가: 최종답 대조는 정답 본문뿐 아니라 선택지·
    문항 형식·복수 정답까지 봐야 정확하다. 이것들을 값 봉투로 복사하면 (ⓐ) 복사 누락이 곧
    판정 저하가 되고 (ⓑ) **정답이 새 봉투에 한 번 더 실린다** — 봉투는 응답·로그로 흘러갈 수
    있는 물건이라 정답 사본을 늘리는 것 자체가 노출 위험이다. 뷰는 Core가 이미 손에 쥔 객체를
    *덜 보는* 것뿐이라 사본이 생기지 않는다.

    필드는 전부 과목 중립 개념이다(정답·선택지·문항 형식·답 형식·복수 정답). 값은 과목이
    정의하고 Core는 해석하지 않는다 — 형식 enum을 `Any`로 둔 이유도 그것이다.

    ⚠️ **정답 비노출 계약**: 이 뷰를 받은 어댑터는 판정 상태와 사유만 돌려주며, 사유에
    기대정답 원문을 싣지 않는다. Core는 정답을 *넘기기만* 하고 *돌려받지 않는다*.
    """

    answer: str | None
    choices: list[str] | None
    question_format: Any
    answer_format: Any
    multiple_answers: dict[str, Any] | None


@runtime_checkable
class SubjectAdapter(Protocol):
    """모든 과목이 EOS Core에 제공해야 하는 최소 능력 6종 (v1 3종 + EOS-69 3종).

    **여기에 메서드를 추가하기 전의 질문**(계획서 100 §3.9 + 모듈 docstring의 추가 기준
    (a)(b)(c)): 이 능력이 Physics·Chemistry·History에도 *반드시* 존재하는가? 위임할 실재
    함수가 오늘 있는가? 부를 Core 코드가 오늘 있는가? 하나라도 아니면 계약이 아니라 어댑터
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

    def evaluate_final_answer(
        self, problem: ProblemAnswerKeyView, student_answer: str | None
    ) -> AnswerEvaluation:
        """학생의 *최종 답*이 문항의 정답 키와 같은지 3상태로 판정한다 (EOS-69).

        `evaluate_answer`가 "조건을 만족하는가"라면 이쪽은 "정답과 같은가"다(모듈 docstring의
        추가 근거 참조). 문항은 값 봉투가 아니라 **뷰**로 받는다 — 정답 사본을 새 객체에
        옮겨 담지 않기 위해서다.

        **정답 비노출**: 반환값에 기대정답 원문을 싣지 않는다. `reason`은 판정 사유(진단용)일
        뿐이며 정답을 반향해서는 안 된다 — 이 봉투는 Core를 거쳐 로그·이벤트로 흐를 수 있다.

        판정 불가(정답 미보유·파싱 불가·빈 입력)는 `unverifiable`이다. **`fail`로 접지
        않는다** — 서버가 채점 근거를 못 찾은 것을 "학생이 틀렸다"로 만들면 안 된다.
        """
        ...

    def check_equivalence_claim(self, left: str, right: str) -> AnswerEvaluation:
        """콘텐츠가 주장하는 "left와 right는 같다"가 참인지 3상태로 판정한다 (EOS-69).

        자체 저작 콘텐츠 검수 파이프라인이 발행 전에 던지는 질문이다 — 생성기가 payload에
        남긴 자기검증 주장을 과목이 실제로 대조한다. 두 문자열은 **과목이 정의하는 불투명
        표현**이며 Core는 내용을 해석하지 않는다.

        판정: 같음이 확정되면 `pass`, 다름이 *증명*되면 `fail`, 증명도 반증도 못 하면
        `unverifiable`. 마지막 칸이 있어야 "판정 못 했다"가 "틀렸다"로 위장되지 않는다.
        """
        ...

    def check_content_seal(
        self, source_text: str, derived_texts: Sequence[str]
    ) -> ContentSealBreach | None:
        """파생 텍스트가 원문의 과목 표기 봉인을 지켰는지 판정한다 — 통과면 None (EOS-69).

        `source_text`는 정본(원문), `derived_texts`는 그것에서 만들어진 화면·발문 조각들이다.
        원문에 봉인 대상 표기가 없으면 검사 대상이 아니므로 None(통과)이다 — "검사할 것이
        없음"과 "위반 없음"을 굳이 가르지 않는 이유는 둘 다 *차단하지 않음*이고, 어느 조각이
        왜 깨졌는지는 위반이 났을 때만 필요하기 때문이다.

        위반이면 `ContentSealBreach`(사유 코드 + 파생 텍스트 인덱스)를 돌려준다. 사유 코드
        어휘는 과목이 정의하며 Core는 그대로 실어 나르기만 한다.
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
