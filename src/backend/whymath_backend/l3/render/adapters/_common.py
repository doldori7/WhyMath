"""어댑터 공용 순수 헬퍼 — 발문 조립·정답 유도·렌더 후 검증(개념 무관·LLM=0).

모든 헬퍼는 `AssessmentSeed`(중립 콘텐츠)만 받아 결정론 산출을 낸다 — 개념명을 하드코딩하지 않는다.
정답은 코드가 소유한다: `derive_selected_root`(근 선택 시 유도)·`verify_answer`(SymPy 검산)로
gold answer를 검증하고, `condition_dsl_violation`으로 pseudo-DSL을 렌더 경로에서도 거른다.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.l3.pregenerate.models import ValidationSignal
from whymath_backend.l3.verify_answer import derive_selected_root, verify_answer
from whymath_backend.schema.concept_dsl import AssessmentSeed


def problem_statement(seed: AssessmentSeed) -> str:
    """발문 문자열 — seed.prompt가 있으면 그대로, 없으면 조건들을 나열(개념 무관)."""
    if seed.prompt:
        return seed.prompt
    return "다음 조건을 만족하는 값을 구하시오: " + ", ".join(seed.conditions)


def gold_answer(seed: AssessmentSeed) -> dict[str, str] | None:
    """코드가 소유하는 정답 치환맵 — 근 선택이 있으면 유도, 없으면 시드 정답(유도 불가면 None).

    `selection`(largest/smallest/unique)이 있으면 `derive_selected_root`로 정답 근을 *유도*해
    LLM/저작자 정답을 신뢰하지 않는다(derive-and-verify). 단일 변수 유도라 정답 키는 시드 정답의
    첫 키를 재사용한다. 유도 불가(다변수·실근 없음 등)면 None.
    """
    if seed.selection is not None:
        derived = derive_selected_root(seed.conditions, seed.selection)
        if derived is None:
            return None
        var = next(iter(seed.answer), None)
        if var is None:
            return None
        return {var: derived}
    return dict(seed.answer)


def resolve_and_verify(
    seed: AssessmentSeed,
) -> tuple[dict[str, str] | None, ValidationSignal | None]:
    """gold answer 유도 + SymPy 검증 — (정답, None) clean 또는 (?, ValidationSignal) 실패.

    ① 닫힌-DSL 검사(pseudo-DSL이면 즉시 실패 신호) → ② 정답 유도(실패 시 신호) → ③ verify_answer
    (state!='pass'면 신호). clean이면 `(gold, None)`. 완전예제/문제형은 이 헬퍼로 렌더 전 검증한다.
    """
    for condition in seed.conditions:
        violation = condition_dsl_violation(condition)
        if violation is not None:
            return None, ValidationSignal(kind="other", reason=f"닫힌-DSL 위반: {violation}")

    gold = gold_answer(seed)
    if gold is None:
        return None, ValidationSignal(kind="solution", reason="정답 유도 불가(근 선택/다변수)")

    verdict = verify_answer(seed.conditions, gold)
    if verdict.state == "pass":
        return gold, None
    reason = f"정답 검증 {verdict.state}: {verdict.reason}"
    # fail=조건 위반 확정(solution 계열)·unverifiable=판정 불가(other). ValidationSignalKind 리터럴.
    if verdict.state == "fail":
        return gold, ValidationSignal(kind="solution", reason=reason)
    return gold, ValidationSignal(kind="other", reason=reason)


def format_answer(answer: dict[str, str]) -> str:
    """정답 치환맵을 'x = 2, y = 1' 형태 문자열로(개념 무관)."""
    return ", ".join(f"{var} = {val}" for var, val in answer.items())


__all__ = [
    "format_answer",
    "gold_answer",
    "problem_statement",
    "resolve_and_verify",
]
