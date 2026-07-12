"""발문-수식 정합 독립 감사 — 초인간 검증 §3 "생성자 ≠ 검증자"(순수·결정론·LLM 0).

정본: `docs/standards/superhuman_verification_standard.md` §2(S3 독립 다관점)·§3.1(⑥
statement_mismatch). **자기 채점 금지의 실체**: 수용 게이트(`acceptance.py`)의 동등성
4성분은 후보가 *스스로 신고한* 메타데이터(성취기준·오개념 태그)를 스펙과 비교할 뿐,
학생이 읽는 **발문의 수식**이 검증기가 검산하는 **조건식**과 일치하는지는 아무도 보지
않는다(acceptance.py §419-426의 구멍). 생성기가 발문과 조건을 따로 만들면(또는 발문만
변조되면) 검산은 조건에 대해 통과하지만 학생은 다른 문제를 본다.

`StatementConsistencyAuditor`는 그 교차를 **독립적으로** 검사한다:
  1. 발문 텍스트에서 방정식을 추출(정규식).
  2. 표시 표기(`^`·`5x` 병치)를 조건 DSL(`**`·`5*x`)로 정규화.
  3. `canonical_signature`(기존 재사용)로 발문 수식과 조건식을 각각 접어 대조 —
     서로 다른 구조면 **불일치**(⑥ 검출).
  4. 선택 문구("큰/작은/유일 근")를 `answer_selection`과 교차 검사.

정직성: 발문에서 방정식을 못 뽑거나 정규화가 불가하면 *불일치로 단정하지 않고*
`consistency_ok=True`(감사 불가는 통과 — 이 감사기는 *반증기*이지 필수 게이트가 아님).
확정적 불일치만 False를 낸다(오탐으로 정상 문항을 막지 않는다).

7계층: L3 지역. schema·동일 패키지(canonicalize)만 import. DB 0·네트워크 0·LLM 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.schema.problem import Problem

__all__ = [
    "AuditVerdict",
    "StatementConsistencyAuditor",
    "TagAuditor",
]

# 발문에서 방정식을 뽑는 정규식 — 수식 문자(숫자·x·^·괄호·연산자·공백·=)의 최대 런.
# 한국어는 문자클래스 밖이라 방정식 양끝에서 자연히 끊긴다("이차방정식 <EQ> 의 …").
_EQ_PATTERN = re.compile(r"[0-9xX\^\(\)][0-9xX\^\(\)\s\+\-\*/]*=[\s]*[0-9xX\^\(\)\s\+\-\*/]+")

# 선택 문구 → answer_selection 매핑(발문 어휘). 판별 불가는 None(교차 검사 생략).
_SELECTION_WORDS: tuple[tuple[str, str], ...] = (
    ("중근", "unique"),
    ("유일", "unique"),
    ("큰 근", "largest"),
    ("작은 근", "smallest"),
)


@dataclass(slots=True, frozen=True)
class AuditVerdict:
    """감사 결과 — 정합 여부 + 사유. `consistency_ok=False`만 확정적 불일치."""

    consistency_ok: bool
    reason: str | None = None


@runtime_checkable
class TagAuditor(Protocol):
    """발문-태그 정합 감사기 좌석 — 후보를 받아 정합 여부를 낸다(생성자와 독립 주체).

    수용 게이트가 이 좌석에 감사기를 주입받아 `accepted &= consistency_ok`로 결합한다.
    미주입이면 기존 동작과 비트동일(감사 없음). 프로덕션=StatementConsistencyAuditor·
    테스트=가짜 감사기.
    """

    def audit(self, candidate: Problem, *, answer_selection: str | None) -> AuditVerdict: ...


def _display_to_dsl(display: str) -> str:
    """표시 수식('2x^2 + 11x + 12 = 0')을 조건 DSL('2*x**2 + 11*x + 12 = 0')로 정규화.

    `^`→`**`, 숫자-변수/괄호 병치에 `*` 삽입(`5x`→`5*x`·`2(`→`2*(`), `)`-후행 병치에
    `*` 삽입(`)x`→`)*x`). canonical_condition은 병치를 파싱 못 하므로 이 정규화가 전제다.
    """
    text = display.replace("^", "**")
    text = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", text)
    text = re.sub(r"(\))\s*([a-zA-Z0-9(])", r"\1*\2", text)
    return text


def _selection_from_words(question_text: str) -> str | None:
    """발문 어휘에서 근 선택을 추론 — 판별 불가면 None(교차 검사 생략)."""
    for word, selection in _SELECTION_WORDS:
        if word in question_text:
            return selection
    return None


class StatementConsistencyAuditor:
    """발문 수식 ↔ 검산 조건식 정합을 독립 검사(TagAuditor 구현).

    `Problem.question_text`(학생이 읽는 것)와 검산에 쓰이는 `conditions`가 같은 구조인지
    canonical_signature로 대조한다. conditions는 게이트가 answer_map과 함께 받는 값이라
    감사기에는 별도로 주입된다(생성자가 신고한 태그가 아니라 검산 재료 그 자체).
    """

    def __init__(self, *, conditions: str | list[str]) -> None:
        # 검산 조건(발문과 대조할 진실축) — 게이트 호출부가 주입한다.
        self._conditions = conditions

    def audit(self, candidate: Problem, *, answer_selection: str | None) -> AuditVerdict:
        """발문-조건 구조 대조 + 선택 문구 교차 검사. 확정 불일치만 False."""
        question = candidate.question_text or ""

        # ① 선택 문구 교차 검사 — 발문이 "큰 근"인데 selection=smallest 등.
        worded = _selection_from_words(question)
        if worded is not None and answer_selection is not None and worded != answer_selection:
            return AuditVerdict(
                False,
                f"발문 선택 문구({worded})와 answer_selection({answer_selection}) 불일치.",
            )

        # ② 발문 수식 ↔ 조건식 구조 대조. 연립 조건은 발문 단일 수식과 대조 불가 → 통과.
        if not isinstance(self._conditions, str):
            return AuditVerdict(True)
        match = _EQ_PATTERN.search(question)
        if match is None:
            return AuditVerdict(True)  # 발문에서 방정식 추출 불가 — 감사 불가는 통과(반증기).
        display_dsl = _display_to_dsl(match.group(0).strip())
        sig_statement = canonical_signature(display_dsl, answer_selection)
        sig_condition = canonical_signature(self._conditions, answer_selection)
        if sig_statement is None or sig_condition is None:
            return AuditVerdict(True)  # 정규화 불가 — 단정하지 않음(모르면 모른다).
        if sig_statement != sig_condition:
            return AuditVerdict(
                False,
                f"발문 수식 {match.group(0).strip()!r}이 검산 조건 {self._conditions!r}과 "
                "구조가 다름(학생 노출 수식 ≠ 검증 대상).",
            )
        return AuditVerdict(True)
