"""LaTeX 구조 파스 게이트 단위테스트(품질 15축 ⑩·ARCH-19) — 순수·결정론·hermetic.

`scan_latex_issue`(단일 문자열)와 `validate_problem_latex`(문항 전체 필드)를 검증한다.
정상(수식 없음·균형 잡힌 LaTeX 모두)과 4종 결함(⁠$ 불균형·중괄호 불균형·\\left\\right
불균형·미완성 이스케이프)을 변별한다 — "아무 backslash나 있으면 걸림" 오탐을 배제한다.
"""

from __future__ import annotations

from types import SimpleNamespace

from whymath_backend.l3.equivalent.latex_gate import (
    scan_latex_issue,
    validate_problem_latex,
)


class TestScanLatexIssuePlainText:
    def test_empty_or_none_is_valid(self) -> None:
        assert scan_latex_issue("") is None

    def test_plain_korean_math_text_is_valid(self) -> None:
        # 실 코퍼스의 실제 형식 — ^ 표기·수식 마크업 0건(latex_gate 모듈 docstring 정직 기록).
        assert scan_latex_issue("이차방정식 x^2 - 5x = 0 의 두 근 중 큰 근을 구하시오.") is None

    def test_set_notation_braces_balanced_is_valid(self) -> None:
        # 집합 표기 {1, 2, 3} — 중괄호가 있지만 균형이라 정상.
        assert scan_latex_issue("정의역은 {1, 2, 3}이다.") is None


class TestScanLatexIssueValidLatex:
    def test_balanced_dollar_and_frac_is_valid(self) -> None:
        assert scan_latex_issue(r"이는 $\frac{1}{2}$ 의 해다.") is None

    def test_balanced_left_right_is_valid(self) -> None:
        assert scan_latex_issue(r"$\left( x + 1 \right)$") is None

    def test_escaped_literal_brace_not_counted(self) -> None:
        # \{ \} 는 리터럴 문자(그룹 구분자 아님) — 짝이 안 맞아도 구조 위반이 아니다.
        assert scan_latex_issue(r"집합 표기 \{ 만 등장") is None

    def test_escaped_literal_dollar_not_counted(self) -> None:
        assert scan_latex_issue(r"가격은 \$5 이다.") is None


class TestScanLatexIssueBrokenLatex:
    def test_unbalanced_dollar_detected(self) -> None:
        issue = scan_latex_issue(r"이는 $\frac{1}{2} 의 해다.")
        assert issue is not None and "$" in issue

    def test_unbalanced_brace_detected(self) -> None:
        # defect_seeder._break_latex와 동일 결함 형태 — 명령 뒤 그룹 중괄호가 안 닫힘.
        issue = scan_latex_issue(r"참고: \frac{1}{2 계산 확인")
        assert issue is not None and "중괄호" in issue

    def test_command_brace_not_treated_as_escape(self) -> None:
        # \frac 의 'f'를 이스케이프로 오인하면(순진한 구현) 뒤 중괄호 불균형을 놓친다 —
        # 이 테스트가 그 회귀를 잡는다(변별력).
        issue = scan_latex_issue(r"\frac{1}{2 무언가")
        assert issue is not None and "중괄호" in issue

    def test_unbalanced_left_right_detected(self) -> None:
        issue = scan_latex_issue(r"$\left( x + 1$")
        assert issue is not None and "left" in issue

    def test_trailing_single_backslash_detected(self) -> None:
        issue = scan_latex_issue("문장이 여기서 끝\\")
        assert issue is not None and "역슬래시" in issue

    def test_trailing_double_backslash_is_valid(self) -> None:
        # 짝수 개 역슬래시(예: LaTeX 줄바꿈 \\)는 미완성 이스케이프가 아니다.
        assert scan_latex_issue("줄바꿈\\\\") is None


class TestValidateProblemLatex:
    def _problem(self, **overrides: object) -> SimpleNamespace:
        base = {
            "question_text": "정상 발문",
            "question_text_md": None,
            "answer_explanation": "정상 해설",
            "choices": None,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_all_clean_fields_no_issues(self) -> None:
        problem = self._problem(choices=["1", "2", "3", "4"])
        assert validate_problem_latex(problem) == []

    def test_broken_question_text_reported_with_field_label(self) -> None:
        problem = self._problem(question_text=r"발문 \frac{1}{2 결함")
        issues = validate_problem_latex(problem)
        assert len(issues) == 1
        assert issues[0].startswith("question_text:")

    def test_broken_choice_reported_with_index(self) -> None:
        problem = self._problem(choices=["1", r"\frac{1}{2 결함", "3", "4"])
        issues = validate_problem_latex(problem)
        assert len(issues) == 1
        assert "choices[1]" in issues[0]

    def test_multiple_broken_fields_all_reported(self) -> None:
        # 조용한 실패 금지 — 첫 결함에서 멈추지 않고 전 필드를 스캔한다.
        problem = self._problem(
            question_text=r"\frac{1}{2 결함1",
            answer_explanation=r"\left( 결함2",
        )
        issues = validate_problem_latex(problem)
        assert len(issues) == 2
