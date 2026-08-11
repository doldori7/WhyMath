"""SolutionPath/SolutionStep/Justification Pydantic 실체화 — S4-09 (D1).

설계 정본: `schemas/v1.1/solution_path.schema.yaml`(필드·validation_invariants 정본)·
`docs/architecture/solution_module_gap_review.md` §3 D1·`03_content_generation.md`(SolutionPath
정의 정본). 유보 해제 근거: 03 문서의 "Phase 2 — 다중 풀이 소비처가 설 때"가 S4-10(D2)으로
성립했고, WH-S 620문 실가동 출력(`verified_solutions.solution_path` 평문 JSONB)의 *스키마 승격*
좌석이 필요하다(신규 데이터 창조가 아니라 이미 흐르는 데이터의 구조화 — dead code 아님).

축 구분(yaml 경계 명시 그대로):
  - `approach_type` — 풀이 *전체*의 6유형(대수/기하/조합/귀납/시각/역방향). **Enum 클래스를
    신설하지 않고 Literal로 둔다** — 단일 좌석(`schema/enums.py` `ApproachType`) 승격은 후속
    S4-10 몫이다(`tests/backend/l1/test_strategy_governance.py` 리터럴 6값과 동일 집합).
  - `reasoning_type` — *스텝 단위* 추론 유형. 기존 단일 좌석 `schema/enums.py::ReasoningType`
    (폐쇄 7종)을 **소비만** 한다(신설 금지 — S4-09 acceptance).

검증 책임 경계(어디까지 Pydantic인가):
  - 본 모듈(Pydantic)이 강제하는 invariant: ① steps order가 1부터 연속(중복·건너뜀·역순 거부)
    ② justification.prior_step_orders 각 값 < 현재 order(전방참조·자기참조 금지·비순환)
    ③ reasoning_type 폐쇄 7종 밖 거부(enum이 자연 거부) ④ approach_type 6종 밖 거부(Literal이
    자연 거부).
  - **참조 실재**(problem_id가 실재하는 Problem인지·concept_node_id/justification의 각 ID가
    실재하는 Concept 노드인지 — cross-dataset)는 Pydantic이 아니라 *적재 시점* 책임이다:
    `whs/path_promotion.py`(승격 어댑터)의 존재 확인 + DB FK(`solution_paths.problem_id`)가
    강제한다. Pydantic은 DB를 모른다(hermetic 검증 가능·계층 위생).

표현≠의미(CLAUDE.md): `content`는 렌더러-중립 표현식/LaTeX *문자열 그대로* 담는다 — AST화
시도·공백 정규화를 하지 않는다(byte-exact 보존·`str_strip_whitespace` 미적용 이유).

경계(S4-09): `embedding` 필드는 **넣지 않는다** — 소비처(군집·D4)가 서는 S4-12에서 판정
(acceptance 명시·임베딩 네임스페이스 거버넌스 연동).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import ReasoningType

__all__ = [
    "APPROACH_TYPES",
    "ApproachType",
    "Justification",
    "SolutionPath",
    "SolutionStep",
]

# 풀이 전체 접근유형 6종 — yaml `approach_type` enum과 1:1. Enum 클래스 신설 금지(S4-09):
# schema/enums.py `ApproachType` 단일 좌석 승격은 S4-10에서 수행 예정(그때 이 Literal을 좌석
# 참조로 교체·`test_strategy_governance.py`의 하드코딩 6값도 좌석 참조로 승격).
ApproachType = Literal["algebraic", "geometric", "combinatorial", "inductive", "visual", "backward"]

# 폐쇄 6값 튜플(리포트·매핑 테이블용) — Literal 정의에서 파생(이중 정의 방지·단일 진실 원천).
APPROACH_TYPES: tuple[str, ...] = get_args(ApproachType)


class Justification(BaseModel):
    """스텝의 정당화 근거 참조 — 얇은 참조 3종 묶음(증명 트리 아님·yaml `Justification`).

    정리(`theorem_concept_ids`)·개념노드(`concept_node_ids`)·이전 스텝(`prior_step_orders`)을
    *ID/order로만* 가리킨다 — 자체 정리증명기·형식논리 증명 트리는 만들지 않는다(경계된 Tier3
    위임·`math_dsl_evolution.md` §2.2·§2.9 금기). 그래프 엣지·ORM 테이블로 승격하지 않고 스텝
    내부 인라인 JSONB로만 영속한다(yaml 경계 그대로).

    전방/자기참조 금지(`prior_step_orders` 각 값 < 현재 스텝 order)는 order를 아는
    `SolutionStep` 검증기가 강제한다(본 모델은 자기 order를 모른다). ID 실재 검증은 적재 시점
    책임(모듈 docstring 경계).
    """

    model_config = ConfigDict(extra="forbid")

    theorem_concept_ids: list[str] = Field(
        default_factory=list,
        description=(
            "근거 *정리* 개념노드 ID(cognitive_type=THEOREM/DEFINITION). 실재 검증은 적재 시점."
        ),
    )
    concept_node_ids: list[str] = Field(
        default_factory=list,
        description="근거 *개념* 노드 ID(정리 외 일반 개념). 실재 검증은 적재 시점.",
    )
    prior_step_orders: list[int] = Field(
        default_factory=list,
        description=(
            "의존하는 *이전 스텝* order(같은 SolutionPath 내). 각 값 < 현재 order — "
            "전방참조·자기참조 금지(SolutionStep 검증기가 강제)."
        ),
    )


class SolutionStep(BaseModel):
    """풀이 한 단계 — 내용 + 힌트 원천 + 흔한 오류 + 추론 태그 + 검증 표시(yaml `SolutionStep`).

    `content`는 자연어+LaTeX/표현식 *문자열 그대로*(렌더러-중립·AST화 금지). `hint`는 L4 graded
    Hint의 *원천 텍스트*일 뿐(구조화는 `hint.schema.yaml` — L4 몫). `reasoning_type`·
    `justification`은 *선택* — 미지정 스텝도 유효하다(yaml 하위호환 invariant·strict superset).

    `concept_node_id` required 재량 이탈(정직 명시): yaml은 required지만 본 구현은 `None`을
    허용한다 — 개념 ID 매칭은 L3 LLM 5개 핵심 호출지점 중 4번("개념 ID 매칭")이고, S4-09 승격
    어댑터는 LLM 0·결정론이라 매칭을 시도하지 않고 **전건 사람 검수 큐**로 보낸다(AI 자기승인
    금지). None = "매칭 검수 대기"이며 DB 좌석(`problem_step.concept_node_id`)도 같은 이유로
    nullable이다. 검수 완료 후 채워진 값의 실재 검증은 적재 시점 책임.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    order: int = Field(ge=1, description="단계 순서(1부터). SolutionPath가 연속성을 강제.")
    content: str = Field(
        description="단계 내용(자연어+LaTeX/표현식) — 렌더러-중립 문자열 그대로(표현≠의미)."
    )
    concept_node_id: str | None = Field(
        default=None,
        description=(
            "이 단계가 통과하는 L1 개념 노드 ID. None=매칭 검수 대기(사람 검수 큐 — "
            "클래스 docstring 재량 이탈 명시). 실재 검증은 적재 시점."
        ),
    )
    hint: str | None = Field(
        default=None,
        description="막힌 학생용 힌트 *원천 텍스트*(L4 Hint 엔티티가 graded 척도로 구조화).",
    )
    common_errors: list[str] = Field(
        default_factory=list,
        description="이 단계의 흔한 오류 — 오개념 카탈로그 코드 또는 오류 패턴 서술.",
    )
    reasoning_type: ReasoningType | None = Field(
        default=None,
        description=(
            "스텝 추론 유형 — 기존 단일 좌석 `schema/enums.py::ReasoningType`(폐쇄 7종) 소비. "
            "폐쇄집합 밖은 enum이 자연 거부. None=미태깅(하위호환)."
        ),
    )
    justification: Justification | None = Field(
        default=None,
        description="정당화 근거 참조(얇은 3종 묶음). None=근거 미명시(하위호환).",
    )
    sympy_verified: bool = Field(
        default=False,
        description=(
            "SymPy 자동 검증 통과 여부(환각 방어 ② — 수치·수식 검증은 LLM이 아니라 SymPy). "
            "WH-S 승계 시 *직전 스텝→이 스텝 전이*가 Tier2 correct였는지를 뜻한다."
        ),
    )
    lean_verified: bool | None = Field(
        default=None,
        description="형식 증명 단계의 Lean 검증 여부. 증명 단계가 아니면 None(Phase 3+).",
    )

    @model_validator(mode="after")
    def _justification_refs_prior_steps_only(self) -> SolutionStep:
        """justification.prior_step_orders 각 값 ∈ [1, order-1] — 전방·자기참조 금지(비순환).

        yaml invariant "각 값 < 해당 스텝 order" 그대로. 하한 1은 "이전 *스텝*의 order" 정의에서
        따라온다(order는 1부터 — 0 이하는 어떤 스텝도 가리키지 않는 무의미 참조라 함께 거부).
        order가 1..n 연속(SolutionPath invariant)이므로 [1, order-1] 안의 값은 반드시 실재한다.
        """
        if self.justification is None:
            return self
        invalid = [o for o in self.justification.prior_step_orders if not 1 <= o < self.order]
        if invalid:
            raise ValueError(
                f"justification.prior_step_orders 위반: 스텝 order={self.order}에서 "
                f"이전 스텝([1, {self.order - 1}])만 참조할 수 있다 — 전방참조·자기참조 금지"
                f"(비순환). 위반 값: {invalid}"
            )
        return self


class SolutionPath(BaseModel):
    """풀이 경로 — 문제 1개에 대한 풀이 1개를 *개념 노드 통과 시퀀스*로 인코딩(yaml 1:1).

    `concept_sequence`가 풀이의 골격(비교·검색·분류 기준)이고, 자연어/표현식 본문은
    `steps[].content`에 남는다. 한 문제에 여러 SolutionPath(6가지 접근의 인스턴스)가 올 수
    있다(N:1).

    🚨 동치성 정직 경계(yaml 그대로): `concept_sequence`는 두 풀이 동치성의 *필요조건도
    충분조건도 아니다*. `equivalence_cluster_id`가 채워져 있어도 "확정 동치"가 아니라 "검수
    거친 동치 후보 군집"이다 — 학생 노출 전 반드시 사람 검수(CLAUDE.md "확실하지 않을 때
    자신 있게 말함 금지"). 군집 판정 자체는 S4-12(D4) 몫.

    `embedding` 필드 부재는 의도(모듈 docstring — S4-12에서 판정).
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    solution_path_id: str = Field(description="PK. 풀이 경로 식별자.")
    problem_id: str = Field(
        description="이 풀이가 푸는 문제 ID(N:1). 실재 검증은 적재 시점(DB FK)."
    )
    approach_type: ApproachType = Field(
        description=(
            "6가지 solution_approaches 중 하나(풀이 *전체* 유형·스텝 단위 reasoning_type과 "
            "직교). 6종 밖은 Literal이 자연 거부."
        )
    )
    concept_sequence: list[str] = Field(
        description=(
            "풀이가 통과하는 개념 노드 ID *순서열*(골격·set 아님). 매칭 확정분만 담는다 — "
            "매칭 실패 스텝은 시퀀스에서 제외하고 검수 큐에 기록(날조 금지). "
            "실재 검증은 적재 시점."
        )
    )
    steps: list[SolutionStep] = Field(description="단계별 상세 — order 1부터 연속(검증기 강제).")
    verified_by_human: bool = Field(
        default=False,
        description="사람 검수 통과 여부(환각 방어 ④ — 상시 10% 표본+저신뢰+신고분 검수 큐).",
    )
    equivalence_cluster_id: str | None = Field(
        default=None,
        description=(
            "동치 풀이 군집 식별자 — 값이 있어도 '확정 동치'가 아니라 '검수 거친 동치 후보 "
            "군집'(클래스 docstring 정직 경계)."
        ),
    )
    created_at: datetime = Field(description="풀이 경로 생성 시각.")

    @model_validator(mode="after")
    def _steps_order_consecutive_from_one(self) -> SolutionPath:
        """steps의 order가 리스트 순서대로 정확히 1..n — yaml invariant "1부터 연속".

        중복 order·건너뜀(gap)·역순 모두 여기서 거부된다(정규형 강제). 빈 steps는 자명하게
        통과한다(yaml에 비어있음 금지 invariant 없음 — 승격 어댑터가 빈 steps를 별도 스킵).
        """
        orders = [step.order for step in self.steps]
        expected = list(range(1, len(self.steps) + 1))
        if orders != expected:
            raise ValueError(
                f"steps order 위반: 1부터 연속(리스트 순서대로 {expected})이어야 한다 — "
                f"실제 {orders} (중복·건너뜀·역순 금지)"
            )
        return self
