"""StudentSolutionStep — 학생 풀이 step 제출의 백엔드 계약 모델(Pydantic) (EOS-46).

설계 정본: `docs/architecture/adr/ADR-002-student-solution-step-entity.md`(별도 정규 엔티티
판정·기각 대안 포함)·`docs/architecture/32_learning_history.md` §4. 정오답 최종값만으로는
"어느 단계에서 오류가 났는가"가 손실된다 — 이 모델이 학생이 제출한 풀이 단계 각 건을
정규화한다(오개념 시스템 `evidence_links`의 step 수준 증거 입력).

**명칭·책임 구분(혼동 금지 — ADR-002 3자 대조)**: 이 모델은 *학생* 데이터다.
`db/models/solution_node.py`의 `SolutionNode`는 WH-S AI 솔버의 MCTS 탐색 노드(시스템 내부
상태·학생 데이터 아님), `problem_step`(`ProblemStep`)은 문항의 저작 정본 단계(콘텐츠)다 —
`student_` 접두가 데이터 주체를 이름에 박는다.

설계 판단(근거 병기):
  - `expression` — **렌더러-중립 LaTeX 본문**(CLAUDE.md 표현≠의미 현행 정밀: 본문은 LaTeX·
    구조는 `canonical_ast`). strip 정규화 없음(EOS-32 P2 동형 — 제출 원문은 오류 분석
    증거·바이트 동일 보존).
  - `canonical_ast` — 정규화 구조(AST/JSON). 동치 판정·검산 재료의 구조 정본. None=구조화
    미수행(정직 — 날조 금지).
  - `validation` — step 검증 결과(구조 계약 `StepValidation`). **검증 권위는 SymPy 단일
    권위**(CLAUDE.md — 동치·검증·해집합): `method`는 그 판정을 낸 경로 식별자이고, LLM
    소견은 검증이 아니다 — 도구 검증을 통과하지 못한 판정을 `is_valid=True`로 적재하는 것은
    침묵 valid 위장이다. None=미검증(미검증과 무효는 다른 사실).
  - `concept_ids` — 이 step이 다루는 개념의 UC 개념 id 목록(**느슨참조** — 실측:
    `solution_paths.concept_sequence`(list[str] JSONB)·`problem_step.concept_node_id`(Text)
    전부 FK 없는 str 코드 관례). 매칭 확정분만(날조 금지) — 빈 목록=미태깅.

개인정보 메모(`answer_submission` 동형): `expression`·`canonical_ast`는 *미성년 학생 풀이
데이터*다 — 저장·동의 계층 책임(문서화만·가짜 validator 없음). privacy 3종 배선은
32_learning_history §11이 acceptance로 강제한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StepValidation(BaseModel):
    """한 step의 검증 결과 — `student_solution_step.validation` JSONB의 구조 계약.

    `is_valid`는 판정, `method`는 그 판정을 낸 검증 경로 식별자다(예: "sympy_step_check" —
    SymPy 단일 권위·CLAUDE.md). 폐쇄 어휘를 날조하지 않고 자유 문자열로 둔다(EOS-32
    `GradingResult.method` 동형). `detail`은 경로별 부가 정보(반례·불일치 식 등)다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    is_valid: bool = Field(description="검증 판정 — 이 step이 직전 상태로부터 타당한가.")
    method: str = Field(
        min_length=1,
        description="검증 경로 식별자(예 'sympy_step_check'). 빈 문자열 금지 — 검증 없는 "
        "판정을 판정으로 위장하지 않는다(SymPy 단일 권위·LLM 소견은 검증 아님).",
    )
    detail: dict[str, Any] | None = Field(
        default=None, description="검증 경로별 부가 정보(자유형 — 예: 반례·불일치 항)."
    )


class StudentSolutionStep(BaseModel):
    """학생 풀이 step 1건 — attempt 안에서 학생이 제출한 풀이 단계(`sequence_no` 순).

    한 행 = 한 attempt(`attempt_id`) 안의 `sequence_no`번째 step 제출이다(1부터·attempt 내
    유일). step을 고쳐 다시 제출하면 새 순번의 새 행이다(append-only 관행 — 32 §6·개정
    이력도 각각 사실). `answer_submission`(최종 답 제출)·`hint_usage`(힌트 사용)와 나란한
    "attempt 내 학생 행위 정규 기록" 계열이다.

    개인정보 메모(모듈 docstring 참조): `expression`·`canonical_ast`는 *미성년 풀이 데이터*.
    """

    model_config = ConfigDict(extra="forbid")

    # ===== 기본 식별 =====
    student_step_id: uuid.UUID = Field(default_factory=uuid4, description="학생 step PK (UUID)")
    attempt_id: uuid.UUID = Field(
        description="소속 시도 FK (problem_attempt 참조·required — DB는 (attempt_id, user_id) "
        "복합 FK로 소유 일치 강제·EOS-32 PR #902 P1 관례)"
    )
    user_id: uuid.UUID = Field(
        description="학생 FK (user_profile 참조·required — pseudonymous user_id만·"
        "32_learning_history §11)"
    )
    sequence_no: int = Field(
        ge=1, description="attempt 내 step 제출 순번(1부터·attempt 내 유일 — DB UNIQUE 제약)"
    )

    # ===== step 본문 (*미성년 풀이 데이터* — 표현≠의미) =====
    expression: str = Field(
        min_length=1,
        description="step 본문 — 렌더러-중립 LaTeX(빈 step 없음·strip 정규화 없음 — 원문 "
        "바이트 동일 보존·EOS-32 P2 동형)",
    )
    canonical_ast: dict[str, Any] | None = Field(
        default=None,
        description="정규화 구조(AST/JSON) — 동치 판정·검산 재료의 구조 정본(표현≠의미). "
        "None = 구조화 미수행(날조 금지)",
    )

    # ===== 검증·개념 태그 =====
    validation: StepValidation | None = Field(
        default=None,
        description="step 검증 결과(구조 계약 StepValidation·SymPy 단일 권위). "
        "None = 미검증(미검증≠무효)",
    )
    concept_ids: list[str] = Field(
        default_factory=list,
        description="이 step이 다루는 UC 개념 id 목록(느슨참조 — solution_paths."
        "concept_sequence 동형). 매칭 확정분만·빈 목록=미태깅(날조 금지)",
    )

    # ===== 시간 =====
    submitted_at: datetime | None = Field(
        default=None,
        description="step 제출 시각(서버 기준 — DB DEFAULT NOW()). None = DB가 채움",
    )


__all__ = ["StepValidation", "StudentSolutionStep"]
