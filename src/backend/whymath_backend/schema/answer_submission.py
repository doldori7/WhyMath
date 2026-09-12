"""AnswerSubmission — attempt 내 다회 제출 시퀀스의 백엔드 계약 모델(Pydantic) (EOS-32).

설계 정본: `docs/architecture/32_learning_history.md` §4("AnswerSubmission 분리의 근거")·§9·§11.
학생은 한 문제에 답을 여러 번 제출할 수 있다(오답 → 오답 → 정답). `problem_attempt.student_answer`
는 *최종값 1개*만 담아 "두 번째 오답이 어떤 오개념을 시사하는가"가 손실된다 — 이 모델이 그 제출
시퀀스를 1급 데이터로 정규화한다. 분리된 시퀀스는 오개념 시스템(`evidence_links`)의 핵심 입력이다.

이 Pydantic 모델은 검증·API 계약이고, 영속 매핑은 `db/models/answer_submission.py`(ORM)가 별도로
세운다 — `from_schema`/`to_schema` 변환 헬퍼가 둘을 잇는다(`dialogue.py`·`activity.py` 동일 패턴).

설계 판단(근거 병기):
  - `response_type` — 32_learning_history §9(subject-neutral: "response_type + payload"로 일반화)
    의 착지. 제출 *양식*의 폐쇄 4종만 Literal로 강제한다(DB 컬럼은 String — 닫힌 어휘는 schema
    몫·DB는 값만 담는다는 `misconception_relation.relation_type` 선례). 과목 확장 시 Literal
    확장으로 대응(핵심 스키마에 수학 전용 필드를 박지 않는다 — §9 설계 제약).
  - `raw_response` vs `latex` — raw는 *제출된 그대로*(자유 텍스트·선택지 id·OCR 전사 등),
    latex는 수식 정규 표현(해당 시에만·MathLive/OCR 경유). 표현≠의미 원칙(CLAUDE.md)의 구조
    좌석은 `canonical_ast`(동치 판정·검산 재료)다 — 본문은 렌더러-중립 LaTeX(현행 정밀 방침).
  - `suspected_misconception_ids` — kebab-case 오개념 카탈로그 id의 *느슨참조* 목록
    (`evidence_link.misconception_id`·`misconception_hypothesis.misconception_id` 동형 — FK가
    아니라 적재/소비 시점 카탈로그 대조가 참조 무결성을 강제한다).
  - `grading_result.method` — 자유 문자열(채점 경로 식별자). 채점 경로의 폐쇄 어휘는 아직
    확정되지 않았으므로 닫힌 집합을 날조하지 않는다(정직 경계) — SymPy 단일 권위 등 검증 계약은
    채점 *구현* 계층 몫이다.

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `activity.py` 방침과 동일):
  `raw_response`·`latex`·`canonical_ast`는 *미성년 학생 풀이 데이터*다. 평문 저장 금지·동의 없는
  학습 사용 금지는 *저장·동의 계층*(암호화·미들웨어·검수) 책임이며, 모델 필드는 그 사실을
  상기시키되 가짜 validator를 두지 않는다(`problem_attempt.student_answer` 동형 방침 — 문서화만).
  privacy 3종 배선(삭제권 `_ERASURE_PLAN`·보존 `_RETENTION_PLAN`·반출 `_EXPORT_PLAN`)은
  32_learning_history §11이 acceptance로 강제한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# 폐쇄 4종 — 제출 *양식*(modality)만 가른다(내용 아님·subject-neutral). 확장은 이 Literal 확장으로.
#   latex: MathLive 수식 입력 / text: 자유 서술 / choice: 선택지 / handwriting: 손글씨(OCR 경유).
AnswerResponseType = Literal["latex", "text", "choice", "handwriting"]


class GradingResult(BaseModel):
    """한 제출의 채점 결과 — `answer_submission.grading_result` JSONB의 구조 계약.

    `is_correct`는 판정, `method`는 그 판정을 낸 채점 경로 식별자다(예: "sympy_equivalence").
    폐쇄 어휘를 날조하지 않고 자유 문자열로 둔다 — 검증 계약(SymPy 단일 권위·학생 제공 전 검증)은
    채점 구현 계층이 지킨다. `detail`은 경로별 부가 정보(자유형·채점 근거)다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    is_correct: bool = Field(description="채점 판정 — 정답 여부.")
    method: str = Field(
        min_length=1,
        description="채점 경로 식별자(예 'sympy_equivalence'·'exact_match'). 빈 문자열 금지 — "
        "검증 없는 판정을 판정으로 위장하지 않는다.",
    )
    detail: dict[str, Any] | None = Field(
        default=None, description="채점 경로별 부가 정보(자유형 — 예: 동치 판정 근거)."
    )


class ErrorAnalysis(BaseModel):
    """한 제출의 오류 분석 — `answer_submission.error_analysis` JSONB의 구조 계약.

    `suspected_misconception_ids`는 kebab-case 오개념 카탈로그 id의 *느슨참조* 목록이다
    (FK 아님 — `evidence_link.misconception_id` 동형·카탈로그 대조는 적재/소비 시점 책임).
    이 목록이 오개념 시스템(`evidence_links`)으로 흘러가는 1급 입력이다(EOS-32 목적).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    suspected_misconception_ids: list[str] = Field(
        default_factory=list,
        description="의심 오개념 카탈로그 id 목록(kebab-case·느슨참조 — 예 "
        "'distribution-over-power'). 빈 목록 = 의심 오개념 없음.",
    )
    detail: dict[str, Any] | None = Field(
        default=None, description="분석 부가 정보(자유형 — 예: 오류 위치·추론 근거)."
    )


class AnswerSubmission(BaseModel):
    """답 제출 1건 — attempt 내 시퀀스(`sequence_no`)로 정렬되는 다회 제출의 정규 기록.

    한 행 = 한 attempt(`attempt_id`) 안의 `sequence_no`번째 제출이다(1부터 시작·attempt 내 유일).
    `problem_attempt.student_answer`(최종값)와 병행 기록되며, 시퀀스의 정본은 이 모델이다
    (병행 전략은 `docs/architecture/32_learning_history.md` §4 이관·병행 전략 참조).

    개인정보 메모(모듈 docstring 참조): `raw_response`·`latex`·`canonical_ast`는 *미성년 풀이
    데이터*다 — 저장·동의 계층 책임(문서화만·가짜 validator 없음).

    **str_strip_whitespace 미적용(PR #902 P2)**: 이 모델의 str 필드는 `raw_response`·`latex`
    둘뿐이고, 둘 다 계약이 "제출된 그대로"다 — 앞뒤 공백도 오류 분석 증거(입력 습관·OCR 전사
    특성)라 조용한 strip 정규화는 증거 유실이다. 바이트 동일 보존을 테스트가 동결한다
    (`test_raw_response_and_latex_preserve_whitespace_verbatim`). 식별자 성격 필드의 strip은
    서브모델(GradingResult.method 등)이 각자 유지한다.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    # ===== 기본 식별 =====
    submission_id: uuid.UUID = Field(default_factory=uuid4, description="제출 PK (UUID)")
    attempt_id: uuid.UUID = Field(
        description="소속 시도 FK (problem_attempt 참조·required — attempt 없는 제출은 없다)"
    )
    user_id: uuid.UUID = Field(
        description="학생 FK (user_profile 참조·required — pseudonymous user_id만, "
        "PII 직접 컬럼 금지·32_learning_history §11)"
    )
    sequence_no: int = Field(
        ge=1, description="attempt 내 제출 순번(1부터·attempt 내 유일 — DB UNIQUE 제약)"
    )

    # ===== 응답 본문 (*미성년 풀이 데이터*) =====
    response_type: AnswerResponseType = Field(
        description="제출 양식 폐쇄 4종(latex/text/choice/handwriting) — subject-neutral·"
        "닫힌 어휘는 이 Literal이 강제(DB는 String 좌석만)"
    )
    raw_response: str | None = Field(
        default=None,
        description="제출된 그대로의 응답(자유 텍스트·선택지 id·OCR 전사 등) — *미성년 풀이 "
        "데이터*(평문 저장 금지는 저장계층 책임·모듈 docstring)",
    )
    latex: str | None = Field(
        default=None,
        description="수식 정규 LaTeX 표현(해당 시에만 — MathLive/OCR 경유). 본문은 렌더러-중립 "
        "LaTeX 저장(CLAUDE.md 표현≠의미 현행 정밀)",
    )
    canonical_ast: dict[str, Any] | None = Field(
        default=None,
        description="정규화 구조(AST/JSON) — 동치 판정·검산 재료의 구조 정본(표현≠의미). "
        "None = 구조화 미수행(정직 — 날조 금지)",
    )

    # ===== 채점·오류 분석 =====
    grading_result: GradingResult | None = Field(
        default=None, description="채점 결과(구조 계약 GradingResult). None = 미채점"
    )
    error_analysis: ErrorAnalysis | None = Field(
        default=None,
        description="오류 분석(suspected_misconception_ids 포함 — evidence_links 1급 입력). "
        "None = 분석 미수행",
    )

    # ===== 시간 =====
    submitted_at: datetime | None = Field(
        default=None,
        description="제출 시각(서버 기준 — DB DEFAULT NOW()). None = DB가 채움",
    )


__all__ = [
    "AnswerResponseType",
    "AnswerSubmission",
    "ErrorAnalysis",
    "GradingResult",
]
