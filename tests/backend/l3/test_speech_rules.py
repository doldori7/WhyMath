"""L3 수식 음성화 — 고등(고3) 골든 낭독 규칙 + 모호성 해소 + SSML. 음성 슬라이스 S1.

`HIGH_SCHOOL_GOLDEN`은 WhyMath 한국어 낭독 정본의 *골든 코퍼스*다(한국어 수학 낭독 표준 부재 →
자체 정본·교사 검수로 고정). 회귀 0 단언 — 규칙을 바꾸면 이 표가 깨진다. 신규 규칙은 표에 항목을
추가해 확장한다(S4에서 카테고리별 YAML 분리·교사 검수 통과 항목만 적재).
"""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest
from whymath_backend.l3.speech import InvalidSpeechSpecError
from whymath_backend.l4.speech import speak_latex

# (latex, 기대 plain_text) — 고등 프로파일. 산술~미적분~삼각~지수로그~확통.
HIGH_SCHOOL_GOLDEN: list[tuple[str, str]] = [
    # ── 산술·부호 ──
    (r"1+2", "일 더하기 이"),
    (r"3 \times 4", "삼 곱하기 사"),
    (r"6 \div 2", "육 나누기 이"),
    (r"2 \cdot 3", "이 곱하기 삼"),
    (r"-5", "마이너스 오"),
    (r"x - y", "엑스 빼기 와이"),
    # ── 수 읽기(한자어·소수) ──
    (r"30", "삼십"),
    (r"360", "삼백육십"),
    (r"3.14", "삼 점 일 사"),
    (r"0.5", "영 점 오"),
    # ── 분수(분모 먼저) ──
    (r"\frac{1}{2}", "이 분의 일"),
    (r"\frac{x+1}{2}", "이 분의 엑스 더하기 일"),
    # ── 거듭제곱 ──
    (r"x^2", "엑스 제곱"),
    (r"x^3", "엑스 세제곱"),
    (r"x^4", "엑스 사제곱"),
    (r"2^{10}", "이 십제곱"),
    (r"\pi r^2", "파이 알 제곱"),
    (r"(x+1)^2", "엑스 더하기 일 전체의 제곱"),
    # ── 근호 ──
    (r"\sqrt{2}", "루트 이"),
    (r"\sqrt[3]{x}", "세제곱근 엑스"),
    # ── 첨자 ──
    (r"a_n", "에이 엔"),
    (r"a_{n+1}", "에이 엔 더하기 일"),
    # ── 삼각·로그 ──
    (r"\sin^2 x", "사인 제곱 엑스"),
    (r"\sin x^2", "사인 엑스 제곱"),
    (r"\cos\theta", "코사인 세타"),
    (r"\log_2 x", "로그 이 엑스"),
    (r"\ln x", "자연로그 엑스"),
    # ── 미적분 ──
    (r"\int_a^b f(x)\,dx", "에이 부터 비 까지 적분 에프 엑스 디 엑스"),
    (r"\sum_{k=1}^{n} k", "케이 는 일 부터 엔 까지의 합 케이"),
    (r"\lim_{x \to 0} f(x)", "엑스 가 영 으로 갈 때 의 극한 에프 엑스"),
    (r"f'(x)", "에프 프라임 엑스"),
    # ── 절댓값·확통 ──
    (r"|x|", "엑스 의 절댓값"),
    (r"\binom{n}{k}", "엔 콤비네이션 케이"),
    # ── 관계(한국어 후치 어순) ──
    (r"x = 3", "엑스 는 삼"),
    (r"x < 3", "엑스 는 삼 보다 작다"),
    (r"x > 3", "엑스 는 삼 보다 크다"),
    (r"x \geq 5", "엑스 는 오 보다 크거나 같다"),
    (r"x \leq 5", "엑스 는 오 보다 작거나 같다"),
    (r"x \neq y", "엑스 는 와이 와 같지 않다"),
]


@pytest.mark.parametrize(("latex", "expected"), HIGH_SCHOOL_GOLDEN)
def test_golden_high_school(latex: str, expected: str) -> None:
    """골든 코퍼스 회귀 0 — 고등 낭독이 정본과 정확히 일치."""
    spec = speak_latex(latex, "고등")
    assert spec.plain_text == expected
    assert spec.unresolved_symbols == []  # 정본 코퍼스는 미해결 기호 0


def test_golden_corpus_size_gate() -> None:
    """코퍼스가 최소 규모를 유지(슬라이스 축소 회귀 방어)."""
    assert len(HIGH_SCHOOL_GOLDEN) >= 30


# ──────────────────────────────────────────────────────────────────────────
# 모호성 해소 — 같은 surface가 구조에 따라 다르게 읽혀야 한다
# ──────────────────────────────────────────────────────────────────────────
def test_fraction_scope_disambiguation() -> None:
    """1/2x 류 세 구조가 서로 다른 낭독을 낸다(분모 경계 청각 구분)."""
    a = speak_latex(r"\frac{1}{2}x", "고등").plain_text  # (1/2)·x
    b = speak_latex(r"\frac{1}{2x}", "고등").plain_text  # 1/(2x)
    c = speak_latex(r"1/2x", "고등").plain_text  # 1 ÷ 2 · x
    assert a == "이 분의 일 엑스"
    assert b == "이 엑스 분의 일"
    assert len({a, b, c}) == 3


def test_sin_power_vs_arg_power_disambiguation() -> None:
    """sin^2 x 와 sin x^2 가 음성으로 구분된다."""
    assert (
        speak_latex(r"\sin^2 x", "고등").plain_text != speak_latex(r"\sin x^2", "고등").plain_text
    )


# ──────────────────────────────────────────────────────────────────────────
# SSML — well-formed XML + plain_text 정합
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("latex", [r"\frac{1}{2}", r"\int_a^b f(x)\,dx", r"(x+1)^2"])
def test_ssml_is_well_formed(latex: str) -> None:
    """생성 SSML이 파싱 가능한 XML이고 <speak> 루트를 가진다."""
    spec = speak_latex(latex, "고등")
    assert spec.ssml is not None
    doc = minidom.parseString(spec.ssml)
    assert doc.documentElement.tagName == "speak"


# ──────────────────────────────────────────────────────────────────────────
# 정직성 — 미지 기호는 조용히 버리지 않고 노출, 빈 낭독은 거부
# ──────────────────────────────────────────────────────────────────────────
def test_unknown_symbol_is_surfaced_not_dropped() -> None:
    """사전에 없는 기호는 unresolved_symbols에 노출된다(CLAUDE.md 침묵 금지)."""
    spec = speak_latex(r"a \heartsuit b", "고등")
    assert "\\heartsuit" in spec.unresolved_symbols
    assert "알 수 없는 기호" in spec.plain_text


def test_empty_latex_rejected() -> None:
    """빈 입력 → InvalidSpeechSpecError(읽을 원본 없음)."""
    with pytest.raises(InvalidSpeechSpecError):
        speak_latex("", "고등")


def test_only_spacing_yields_empty_read_rejected() -> None:
    """발성 토큰이 없으면(공백 명령만) 빈 낭독으로 거부된다."""
    with pytest.raises(InvalidSpeechSpecError):
        speak_latex(r"\,", "고등")
