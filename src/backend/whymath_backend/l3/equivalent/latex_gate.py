"""⑩ LaTeX/문법 검증 — 문항 단위 결정론 파스 게이트 (품질 15축 ⑩, ARCH-19).

정본: `docs/architecture/problem_bank_gap_review.md` §3 D5. "렌더 불가 수식·깨진 표기"를
잡는 것이 목적이므로 수식의 *의미*(정확성)가 아니라 *구조*(균형)만 본다:
  - `$`/`$$` 구분자 짝
  - 중괄호 `{`/`}` 짝(그룹 인자 — `\\frac{a}{b}`처럼 명령 뒤 그룹은 이스케이프가 아니다)
  - `\\left`/`\\right` 짝
  - 문자열이 미완성 이스케이프(단독 역슬래시)로 끝나지 않는가

sympy `parse_latex`는 antlr4-python3-runtime 의존(미보유·신규 의존성 추가 필요)이라 채택하지
않는다 — 결정론 균형 검사로 "깨진 표기" 탐지에는 충분하다(ARCH-19 결정 로그, 과공학 방지).

정직한 공백: 이 게이트를 작성하는 시점(2026-07-29) 기준 실 코퍼스 전 문항에 `$`/역슬래시
마크업이 **0건**이다(수식은 `^`·평문 표기) — 즉 지금 당장 실 코퍼스에서 이 게이트가 걸러낼
결함은 없다. 이는 게이트의 결함이 아니라 대상 부재이며, LLM 생성·rephrase가 LaTeX 마크업을
도입하기 시작하는 순간부터 즉시 작동하는 선제 인프라다. 결함 주입 강등전
(`l3/equivalent/defect_seeder.py`의 `broken_latex` 결함류)이 게이트 기전 자체의 검출력을
합성 데이터로 증명한다(무결함 코퍼스는 어차피 대상이 없어 자명하게 통과하므로).

7계층: L3 지역(수용 게이트와 동일 층). 표준 라이브러리만 — 상위 계층 참조 0(순수 함수).
"""

from __future__ import annotations

__all__ = ["scan_latex_issue", "validate_problem_latex"]


def _count_unescaped(text: str, char: str) -> int:
    """`char` 출현 중 `\\<char>` 리터럴 이스케이프가 아닌 것만 카운트.

    `\\{`·`\\}`·`\\$`만 "리터럴 문자 이스케이프"로 본다(바로 앞이 역슬래시 1개·그 앞은
    역슬래시가 아님). `\\frac{`처럼 명령 이름 뒤에 오는 그룹 중괄호는 이스케이프가 아니라
    *실제 그룹 구분자*이므로 정상 카운트된다 — 역슬래시 뒤 임의 문자를 전부 건너뛰는
    순진한 구현은 `\\frac`의 `f`를 이스케이프로 오인해 뒤 중괄호 균형을 놓친다.
    """
    count = 0
    for i, ch in enumerate(text):
        if ch != char:
            continue
        if i > 0 and text[i - 1] == "\\" and (i < 2 or text[i - 2] != "\\"):
            continue  # 리터럴 이스케이프 — 구조 문자로 세지 않음.
        count += 1
    return count


def scan_latex_issue(text: str) -> str | None:
    """단일 문자열의 LaTeX 구조 정합성 — 문제 있으면 사람 가독 사유, 없으면 None(정상)."""
    if not text:
        return None
    dollar = _count_unescaped(text, "$")
    if dollar % 2 != 0:
        return f"$ 구분자 불균형(홀수 {dollar}개)"
    open_brace = _count_unescaped(text, "{")
    close_brace = _count_unescaped(text, "}")
    if open_brace != close_brace:
        return f"중괄호 불균형(열림 {open_brace}·닫힘 {close_brace})"
    left = text.count("\\left")
    right = text.count("\\right")
    if left != right:
        return f"\\left/\\right 불균형({left}/{right})"
    trailing_backslashes = len(text) - len(text.rstrip("\\"))
    if trailing_backslashes % 2 == 1:
        return "역슬래시로 문자열이 끝남(미완성 이스케이프)"
    return None


def validate_problem_latex(problem: object) -> list[str]:
    """`Problem`의 발문·해설·선택지 전체 스캔 — 이슈 없으면 빈 리스트.

    `problem`은 `question_text`·`question_text_md`·`answer_explanation`·`choices` 속성을
    갖는 어떤 객체든 받는다(순환 import 회피 — schema.Problem을 구조적으로만 의존).
    """
    issues: list[str] = []
    fields: list[tuple[str, str]] = []
    for label in ("question_text", "question_text_md", "answer_explanation"):
        value = getattr(problem, label, None)
        if value:
            fields.append((label, value))
    choices = getattr(problem, "choices", None)
    if choices:
        for idx, choice in enumerate(choices):
            if choice:
                fields.append((f"choices[{idx}]", choice))
    for label, text in fields:
        issue = scan_latex_issue(text)
        if issue is not None:
            issues.append(f"{label}: {issue}")
    return issues
