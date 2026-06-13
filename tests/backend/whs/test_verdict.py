"""Tier1+2 판정 combiner `final_verdict` 단위테스트 — WH-S S0 슬라이스 1(§4·§3·hermetic).

verified(answer pass + 전부 correct)·failed(answer fail / 단계 incorrect)·unverified(answer
unverifiable / 단계 unverifiable·incorrect 없음)·§4 판정 규칙·§3 격리(R-S2 보상 해킹 차단).

canned AnswerVerdict·SolutionVerificationResult를 직접 주입한다(verify_answer/verify_solution
재실행 없이 combiner 로직만 격리 테스트).
"""

from __future__ import annotations

from whymath_backend.l3.verify_answer import AnswerVerdict, verify_answer
from whymath_backend.l3.verify_solution import SolutionVerificationResult
from whymath_backend.whs import WhsVerdict, final_verdict


def _answer(state: str) -> AnswerVerdict:
    """canned AnswerVerdict — state만 지정."""
    return AnswerVerdict(
        state=state,  # type: ignore[arg-type]
        reason=None if state == "pass" else f"{state} 사유",
        samples_checked=4,
    )


def _steps(
    *,
    n_correct: int = 0,
    n_incorrect: int = 0,
    n_unverifiable: int = 0,
) -> SolutionVerificationResult:
    """canned SolutionVerificationResult — 카운트만 주입(steps 리스트는 비움·집계 필드로 충분)."""
    n_transitions = n_correct + n_incorrect + n_unverifiable
    return SolutionVerificationResult(
        steps=[],
        n_correct=n_correct,
        n_incorrect=n_incorrect,
        n_unverifiable=n_unverifiable,
        n_transitions=n_transitions,
        unverified_ratio=(n_unverifiable / n_transitions if n_transitions else 0.0),
        first_incorrect_index=0 if n_incorrect else None,
        has_incorrect=n_incorrect > 0,
    )


class TestVerified:
    """verified — Tier1 pass AND 모든 단계 correct(incorrect 0·unverifiable 0)."""

    def test_pass_and_all_correct_is_verified(self) -> None:
        result = final_verdict(_answer("pass"), _steps(n_correct=3))
        assert result.grade == "verified"
        assert result.answer_state == "pass"
        assert result.has_incorrect is False
        assert result.n_unverifiable_steps == 0

    def test_pass_with_no_steps_is_verified(self) -> None:
        # 전이 0개(단계 검증 없음)이라도 incorrect/unverifiable 0이면 Tier1 pass로 verified.
        result = final_verdict(_answer("pass"), _steps())
        assert result.grade == "verified"


class TestFailed:
    """failed — Tier1 fail 또는 어느 단계든 incorrect(틀린 과정·답 무관)."""

    def test_answer_fail_is_failed(self) -> None:
        result = final_verdict(_answer("fail"), _steps(n_correct=3))
        assert result.grade == "failed"

    def test_incorrect_step_is_failed_even_if_answer_pass(self) -> None:
        # 핵심 §4 이중 체크 — 답이 맞아도(pass) 과정에 incorrect가 있으면 failed.
        result = final_verdict(_answer("pass"), _steps(n_correct=2, n_incorrect=1))
        assert result.grade == "failed"
        assert result.has_incorrect is True

    def test_incorrect_step_with_answer_unverifiable_is_failed(self) -> None:
        # incorrect는 unverifiable보다 우선 — 틀린 과정은 무조건 차단.
        result = final_verdict(_answer("unverifiable"), _steps(n_incorrect=1))
        assert result.grade == "failed"


class TestUnverifiedIsolation:
    """unverified — 판정 불가 격리 등급(학습 배제·§3·R-S2). incorrect는 없음."""

    def test_answer_unverifiable_is_unverified(self) -> None:
        result = final_verdict(_answer("unverifiable"), _steps(n_correct=3))
        assert result.grade == "unverified"
        assert "학습 배제" in result.reason or "격리" in result.reason

    def test_step_unverifiable_is_unverified(self) -> None:
        # 답은 pass지만 단계에 unverifiable 존재 → verified 아님·격리(verify 없는 통과 거부).
        result = final_verdict(_answer("pass"), _steps(n_correct=2, n_unverifiable=1))
        assert result.grade == "unverified"
        assert result.n_unverifiable_steps == 1

    def test_unverified_not_verified_guard(self) -> None:
        # 정직성 가드(R-S2) — Tier1 단독 pass + 검증 안 된 단계는 절대 verified 아님.
        result = final_verdict(_answer("pass"), _steps(n_unverifiable=3))
        assert result.grade != "verified"
        assert result.grade == "unverified"


class TestVerdictShape:
    """`WhsVerdict` 필드·frozen·근거 전파."""

    def test_returns_whs_verdict(self) -> None:
        result = final_verdict(_answer("pass"), _steps(n_correct=1))
        assert isinstance(result, WhsVerdict)
        assert result.reason

    def test_frozen(self) -> None:
        result = final_verdict(_answer("pass"), _steps(n_correct=1))
        try:
            result.grade = "failed"  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:
            raise AssertionError("frozen이어야 한다")

    def test_evidence_fields_propagated(self) -> None:
        result = final_verdict(_answer("pass"), _steps(n_correct=2, n_unverifiable=1))
        assert result.answer_state == "pass"
        assert result.n_unverifiable_steps == 1
        assert result.has_incorrect is False


class TestInequalityAndSystemIntegration:
    """부등식·연립 AnswerVerdict → final_verdict 등급 일관(combiner 불변·자동 호환).

    `final_verdict`는 AnswerVerdict.state만 보므로 부등식·연립도 변경 없이 호환된다 —
    실제 `verify_answer` 출력을 주입해 등급이 일관됨을 회귀로 못박는다(combiner 변경 0 확인).
    """

    def test_inequality_pass_verifies(self) -> None:
        # 부등식 pass(x>0·x=3) + 전 단계 correct → verified.
        answer = verify_answer("x > 0", {"x": "3"})
        assert answer.state == "pass"
        result = final_verdict(answer, _steps(n_correct=2))
        assert result.grade == "verified"

    def test_inequality_fail_is_failed(self) -> None:
        # 부등식 fail(x>0·x=-1) → 단계 무관 failed.
        answer = verify_answer("x > 0", {"x": "-1"})
        assert answer.state == "fail"
        result = final_verdict(answer, _steps(n_correct=2))
        assert result.grade == "failed"

    def test_strict_boundary_unverifiable_is_unverified(self) -> None:
        # 엄격 경계(x>2·x=2) unverifiable → 격리(unverified).
        answer = verify_answer("x > 2", {"x": "2"})
        assert answer.state == "unverifiable"
        result = final_verdict(answer, _steps(n_correct=2))
        assert result.grade == "unverified"

    def test_system_pass_verifies(self) -> None:
        # 연립 pass + 전 단계 correct → verified.
        answer = verify_answer(["x + y = 3", "x - y = 1"], {"x": "2", "y": "1"})
        assert answer.state == "pass"
        result = final_verdict(answer, _steps(n_correct=3))
        assert result.grade == "verified"

    def test_system_fail_is_failed(self) -> None:
        # 연립 한 조건 위반 → failed.
        answer = verify_answer(["x + y = 3", "x - y = 5"], {"x": "2", "y": "1"})
        assert answer.state == "fail"
        result = final_verdict(answer, _steps(n_correct=3))
        assert result.grade == "failed"
