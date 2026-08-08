"""OCR ④-검증 — 인식된 LaTeX의 SymPy 왕복 파싱 검증(결정론·LLM 0).

인식기가 준 LaTeX가 *SymPy로 파싱 가능한 수식인가*를 본다(왕복: LaTeX → SymPy 표현식).
파싱되면 인식이 *구문적으로 그럴듯*하다는 약한 신호이고, 파싱 불가면 인식 깨짐(예: `x ++ =`)
신호라 신뢰도를 강등한다. 이는 *답의 정오*가 아니라 *인식 품질* 검증이다(verify_answer의
Tier1 답 검산과 다른 질문) — 그래도 `l3/verify_answer.py`의 `sympy.sympify(..., convert_xor=
True)` 보수적 파싱 패턴을 그대로 재사용한다(파싱 불가는 절대 pass 위장 금지).

정직성(CLAUDE.md "모르면 모른다고"): 파싱 가능 여부만 단언한다. "파싱됨"이 "정답"을 뜻하지
않는다(약한 구문 신호일 뿐). LaTeX→SymPy 변환은 `sympy.parsing.latex`가 antlr 의존을 요구할
수 있어, 그 의존이 없으면 *가벼운 LaTeX→수식 전처리* 후 `sympify`로 보수적 왕복한다.
"""

from __future__ import annotations

import logging
import re

import sympy
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "LatexParseResult",
    "demote_confidence_if_unparseable",
    "parse_check_latex",
]

logger = logging.getLogger("whymath.l5.ocr.verify")

# 인식 신뢰도 강등 계수 — 파싱 불가 LaTeX의 신뢰도에 곱한다(0으로 죽이지 않고 *낮춘다* —
# 파싱 불가가 곧 오인식은 아니라 보수적). 0.5는 KPI 튜닝 대상(verify_answer 상수 노출 선례).
_UNPARSEABLE_CONFIDENCE_FACTOR = 0.5

# 가벼운 LaTeX→sympify 전처리 — antlr 기반 `sympy.parsing.latex` 의존이 없을 때의 폴백.
# 흔한 LaTeX 토큰을 sympify가 읽을 수 있는 형태로 바꾼다(완전하지 않음·보수적 근사).
_LATEX_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\left", ""),
    (r"\right", ""),
    (r"\cdot", "*"),
    (r"\times", "*"),
    (r"\div", "/"),
    (r"\pi", "pi"),
    (r"{", "("),
    (r"}", ")"),
)
_FRAC_RE = re.compile(r"\\frac\s*\(([^()]*)\)\s*\(([^()]*)\)")
_SQRT_RE = re.compile(r"\\sqrt\s*\(([^()]*)\)")


class LatexParseResult(BaseModel):
    """`parse_check_latex`의 결과 — 파싱 가능 여부 + 사유.

    `ok`는 SymPy 왕복 파싱 성공 여부다(약한 구문 신호·정오 아님). `reason`은 실패 사유
    (한국어·성공이면 None). frozen — 결정론 결과를 불변으로 둔다(verify_answer `AnswerVerdict`
    선례).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = Field(description="SymPy 왕복 파싱 성공 여부(약한 구문 신호·정오 아님)")
    reason: str | None = Field(default=None, description="실패 사유(한국어)·성공이면 None")


def _latex_to_sympifiable(latex: str) -> str:
    """가벼운 LaTeX→sympify 전처리(antlr 폴백) — 흔한 토큰 치환·\\frac·\\sqrt 환원(순수).

    `\\frac{a}{b}` → `((a)/(b))`, `\\sqrt{x}` → `sqrt((x))`로 바꾸고 나머지 흔한 토큰을
    치환한다. 등호는 `sympify`가 못 다루므로(파이썬 비교) 호출부가 `=`를 분리한다.
    """
    text = latex
    # \frac{a}{b} → ((a)/(b)) — 중괄호는 아래에서 (..)로 치환되므로 먼저 분수 형태를 잡는다.
    text = text.replace("{", "(").replace("}", ")")
    text = _FRAC_RE.sub(r"((\1)/(\2))", latex.replace("{", "(").replace("}", ")"))
    text = _SQRT_RE.sub(r"sqrt((\1))", text)
    for token, repl in _LATEX_REPLACEMENTS:
        text = text.replace(token, repl)
    return text


def parse_check_latex(latex: str) -> LatexParseResult:
    """인식 LaTeX의 SymPy 왕복 파싱 검증 — 파싱 가능(약한 구문 신호)이면 ok=True(결정론·LLM 0).

    절차:
      1. 빈 문자열 → ok=False(인식 실패·검증할 것 없음).
      2. `sympy.parsing.latex.parse_latex`가 가능하면 그걸로(antlr 의존). 실패/미설치면
         가벼운 전처리(`_latex_to_sympifiable`) 후 `sympy.sympify(..., convert_xor=True)`.
      3. 등호(`=`/`==`)가 있으면 양변을 각각 sympify해 둘 다 파싱되면 ok(방정식 인식).
      4. 어떤 경로로도 파싱 불가면 ok=False(보수적·verify_answer 정직성 상속·pass 위장 금지).

    "파싱됨"은 *정답*이 아니라 *구문이 그럴듯함*이다(약한 신호). 신뢰도 강등은
    `demote_confidence_if_unparseable`가 한다.
    """
    text = latex.strip()
    if not text:
        return LatexParseResult(ok=False, reason="빈 LaTeX — 인식 실패(검증할 것 없음)")

    # 등호가 있으면 양변 분리(방정식). `==`·`<=`·`>=`는 단일 식이 아니라 관계라 양변 검사.
    if "=" in text:
        sides = re.split(r"<=|>=|==|=", text)
        sides = [s for s in sides if s.strip()]
        if not sides:
            return LatexParseResult(ok=False, reason="등호만 있고 양변 비어 파싱 불가")
        for side in sides:
            if not _try_sympify(side):
                return LatexParseResult(ok=False, reason=f"등식 항 파싱 불가: {side.strip()}")
        return LatexParseResult(ok=True)

    if _try_sympify(text):
        return LatexParseResult(ok=True)
    return LatexParseResult(ok=False, reason="SymPy 왕복 파싱 불가 — 인식 깨짐 의심")


def _try_sympify(expr_text: str) -> bool:
    """한 식 문자열을 *어떤 경로로든* SymPy 표현식으로 파싱 가능한지(boolean·예외 흡수).

    우선 antlr 기반 `parse_latex`(LaTeX 정식 파서), 실패/미설치면 가벼운 전처리 후 `sympify`.
    둘 다 실패하면 False(보수적·예외 흡수). 상수 진리값(BooleanTrue 등)도 파싱 성공으로 본다.
    """
    text = expr_text.strip()
    if not text:
        return False
    # ① antlr 기반 정식 LaTeX 파서(있으면) — 가장 정확.
    try:
        from sympy.parsing.latex import parse_latex

        parsed = parse_latex(text)
        if parsed is not None:
            return True
    except Exception as exc:  # noqa: BLE001 — antlr 미설치·파싱 실패 모두 폴백으로 흡수
        # 타입명만 명시 로그(exc_info 트레이스백 미사용) — antlr/sympy 파서 예외는 메시지에 파싱
        # 시도한 원문(학생 손글씨 OCR 결과)을 그대로 담는 경우가 흔해, 트레이스백을 남기면 학생
        # 풀이 원문이 로그에 샐 위험이 있다(CLAUDE.md 미성년자 개인정보 비노출). 타입명(예:
        # ImportError=antlr 미설치·영구 열화 vs 그 외=파싱 실패·일시)만으로 CLAUDE.md 요건
        # ("예외 타입명을 로그에 포함")을 충족하면서 두 원인을 구분할 수 있다.
        logger.warning("LaTeX antlr 파서 경로 실패 — sympify 폴백으로 진행: %s", type(exc).__name__)
    # ② 폴백: 가벼운 전처리 후 sympify(verify_answer convert_xor 패턴 재사용).
    try:
        sympy.sympify(_latex_to_sympifiable(text), convert_xor=True)
        return True
    except Exception:  # noqa: BLE001 — 파싱 불가는 보수적 False(pass 위장 금지)
        return False


def demote_confidence_if_unparseable(latex: str, confidence: float) -> float:
    """수식 LaTeX가 파싱 불가면 신뢰도를 강등(× 계수)해 돌려준다 — 파싱되면 원값 유지(순수).

    조립 단계가 수식 영역마다 호출해 *인식 품질 신호*를 신뢰도에 반영한다. 강등은 0으로
    죽이지 않고 낮춘다(파싱 불가 ≠ 확정 오인식·보수적). 0~1로 클램프해 반환한다.
    """
    if parse_check_latex(latex).ok:
        return confidence
    return max(0.0, min(confidence * _UNPARSEABLE_CONFIDENCE_FACTOR, 1.0))
