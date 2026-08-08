"""학생 최종답 3상태 검증 — S3-32 "learning-loop-closure" L3 primitive.

지금까지 코치 대화 흐름은 학생이 최종 답에 도달해도 그걸 *서버가 검증하지 않았다* — 정답
여부 판정이 클라이언트 자가보고(`api/me.py::submit_attempt`의 `is_correct`)에만 의존했다.
본 모듈은 학생의 최종답(`student_answer`)과 문항 기대정답(`expected_answer`)을 비교해
**3상태**(`correct`/`incorrect`/`unverifiable`)로 판정하는 순수·결정론·DB 0 primitive다.

**재사용(재구현 금지)** — `l3/verify_step.py`(풀이 *한 단계* 3상태 검증)와 *같은* 재료를
쓰되 용도가 다르다: `verify_step`은 "before→after 전이가 올바른 변형인가"를 묻고, 본 모듈은
"학생의 최종답 ≡ 기대정답인가"라는 *동치* 질문을 묻는다. 계산 자체는 동일 primitive로 충분:
  - `l3/solution_set.py`의 `read_equation_step`·`equation_solution_set`(내부 호출)·
    `solset_transition_status` — 양쪽이 *둘 다* 등식 형태(`x=2` 등)면 해집합 보존 동치로 비교.
  - `l3/symbolic_equivalence.py`의 `identity_status` — 등식 형태가 아니면(순수 값·식) SymPy
    항등 비교로 직접 동치 판정.

**환각 금지 원칙(CLAUDE.md "확실하지 않으면 모른다")**: 판정 불가(다변수·비다항·복소·파싱
불가·이질 형태 등)를 *절대* `correct`로 낙관 판정하지 않는다 — 애매하면 `unverifiable`로
정직하게 반환한다. 이 계약은 `l3/solution_set.py`/`l3/symbolic_equivalence.py`가 이미 4상태
(`IdentityVerdict`)로 보장하는 보수성을 그대로 물려받는다(재구현 0 — 새 보수화 규칙을
여기서 발명하지 않는다).

**정답 비노출 원칙**: `VerifyFinalAnswerResult`는 판정 *결과*(3상태)만 담고 `expected_answer`
값 자체를 어떤 필드에도 싣지 않는다 — `verify_step.VerifyStepResult.reason`과 달리(그쪽은
학생 자신이 제출한 두 조각을 반향할 뿐 비밀이 없다), 여기서는 `expected_answer`가 *정답
그 자체*라 사유 문구에 값을 넣으면 정답이 API 응답 경로로 새어나갈 위험이 있다(CLAUDE.md
"정답을 학생에게 노출 금지"). 그래서 이 모듈은 사유 문자열을 아예 반환하지 않는다.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.solution_set import read_equation_step, solset_transition_status
from whymath_backend.l3.symbolic_equivalence import IdentityVerdict, identity_status

__all__ = [
    "VerifyFinalAnswerResult",
    "VerifyFinalAnswerState",
    "verify_final_answer",
]


class VerifyFinalAnswerState(str, Enum):
    """학생 최종답 검증 3상태 — §S3-32.

    `str, Enum`이라 멤버가 문자열 값과 동등 비교된다(`verify_step.VerifyStepState`·
    `schema/enums.py` 컨벤션 답습).
    """

    correct = "correct"
    """학생 최종답이 기대정답과 *동치*로 확정 — 해집합 보존 또는 SymPy 항등."""

    incorrect = "incorrect"
    """학생 최종답이 기대정답과 *동치가 아님*이 확정(0-아님 확정 또는 해집합 비보존)."""

    unverifiable = "unverifiable"
    """판정 불가 — 다변수·비다항·복소·파싱 불가·이질 형태(방정식↔값)·빈 입력. 낙관 판정 금지."""


def _map_verdict(verdict: IdentityVerdict) -> VerifyFinalAnswerState:
    """동치 권위 4상태(`IdentityVerdict`) → 최종답 검증 3상태 매핑(`verify_step` 매핑과 동형)."""
    if verdict is IdentityVerdict.identity:
        return VerifyFinalAnswerState.correct
    if verdict is IdentityVerdict.not_identity:
        return VerifyFinalAnswerState.incorrect
    # undecidable/parse_error — 위장 없이 unverifiable(정직).
    return VerifyFinalAnswerState.unverifiable


class VerifyFinalAnswerResult(BaseModel):
    """`verify_final_answer`의 결과 — 3상태 판정만 담는다(정답 비노출 원칙, 모듈 docstring).

    `verify_step.VerifyStepResult`와 달리 `reason`·`evidence_weight`가 없다 — 사유 문구에
    학생 제출 조각을 반향하면(예: "≠ {expected_answer}") 정답이 그대로 노출되므로, 이 결과는
    *상태 하나*만 반환해 호출자가 정답 노출 없이 안전하게 취급하도록 강제한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: VerifyFinalAnswerState = Field(
        description="3상태 판정 — correct(동치 확정)·incorrect(비동치 확정)·unverifiable(판정불가)."
    )


def _result(state: VerifyFinalAnswerState) -> VerifyFinalAnswerResult:
    return VerifyFinalAnswerResult(state=state)


def verify_final_answer(student_answer: str, expected_answer: str) -> VerifyFinalAnswerResult:
    """학생 최종답(`student_answer`)이 기대정답(`expected_answer`)과 동치인지 3상태로 판정한다.

    순수·결정론·DB 0. 입력은 이미 추출된 *최종답 문자열* 한 쌍이다(대화 텍스트에서 최종답을
    뽑아내는 추출 로직은 호출자 책임 — 이 함수는 이미 분리된 두 문자열만 비교한다).

    판정 로직(재사용 집계 — 새 SymPy 관용구를 발명하지 않는다):
      1. **빈 입력**(둘 중 하나라도 공백뿐) → 동치 판정 불가 → `unverifiable`(정직 회피).
      2. **양쪽 다 등식 형태**(`read_equation_step`이 둘 다 None이 아님 — 단일 등식·연쇄 등식
         정규화·근 나열 통합, `l3/solution_set.py` §S3-06/§S3-08 확장 그대로 재사용) →
         `solset_transition_status(expected, student)`(해집합 보존 동치)로 판정. 학생 제출이
         내부 모순 연쇄 등식(예: `x=(1+3)/2=3`의 `(1+3)/2≠3`)이면 그 자체로 `incorrect`(학생
         진술의 내적 오류 — 기대정답과 무관하게 승격 안전). 기대정답 쪽이 내부 모순이면(코퍼스
         데이터 이상) 학생 탓이 아니므로 `unverifiable`로 보수 처리한다.
      3. **한쪽만 등식 형태**(방정식↔순수 값 혼합) → 비교 대상이 어긋나므로 `unverifiable`
         (`verify_step`의 "혼합 단계" 처리와 동형 — 거짓 incorrect 회피).
      4. **양쪽 다 비등식**(순수 값·식) → `identity_status(student_answer, expected_answer)`
         (SymPy 항등 비교, 자유변수 OK)로 직접 판정.

    정직성(CLAUDE.md "확실하지 않으면 모른다"): 판정 불가·파싱 불가·예외·빈 입력은 *절대*
    `correct`로 위장하지 않고 보수적으로 `unverifiable`로 떨어뜨린다. 반환값은 정답 자체를
    담지 않는다(모듈 docstring 정답 비노출 원칙).
    """
    if not student_answer.strip() or not expected_answer.strip():
        return _result(VerifyFinalAnswerState.unverifiable)

    student_reading = read_equation_step(student_answer)
    expected_reading = read_equation_step(expected_answer)

    if student_reading is not None and student_reading.violation is not None:
        # 학생 제출 자체의 연쇄 등식 내부 모순 — 기대정답과 무관하게 학생 진술이 거짓으로
        # *증명*됨(verify_step의 동형 처리·S3-06 ①). incorrect 승격이 안전하다.
        return _result(VerifyFinalAnswerState.incorrect)

    if expected_reading is not None and expected_reading.violation is not None:
        # 기대정답 데이터 자체가 내부 모순 연쇄(코퍼스 이상) — 학생 탓이 아니므로 보수 회피.
        return _result(VerifyFinalAnswerState.unverifiable)

    if student_reading is not None and expected_reading is not None:
        verdict = solset_transition_status(expected_reading.solset, student_reading.solset)
        return _result(_map_verdict(verdict))

    if student_reading is not None or expected_reading is not None:
        # 한쪽만 등식 형태(방정식↔값 혼합) — 비교 대상 불일치, 안전 회피(verify_step 동형).
        return _result(VerifyFinalAnswerState.unverifiable)

    # 양쪽 다 등식이 아님(순수 값·식) — 동치 권위 primitive(SymPy)로 직접 비교.
    verdict = identity_status(student_answer, expected_answer)
    return _result(_map_verdict(verdict))
