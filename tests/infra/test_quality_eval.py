"""quality_eval.py 단위 테스트 (태스크 패밀리 인지 FAST vs MID 품질 평가 하니스).

- 실제 ollama 호출은 *반드시* 모킹. run_evaluation 의 `client` 인자로 가짜 주입.
- 모델 실행은 Phaiakes9(Ollama·GPU)에서 Kiki가 수행하고, 이 테스트/CI는 *순수
  로직만* 검증한다(이 컨테이너엔 모델·GPU 없음). 따라서 채점기·파서·집계·결정
  규칙은 모델 없이 직접 검증하고, 러너는 응답을 정해주는 가짜 클라이언트로 검증.
- 태스크 패밀리 라우팅 검증: 가짜 클라이언트의 `calls`로 NLP 항목은 nlp 모델,
  MATH 항목(산술)은 math 모델로 호출되었는지 확인한다.
- 패턴은 tests/infra/test_benchmark.py 미러링(importlib 동적 로드 + 가짜 클라이언트).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---- quality_eval 모듈 로드 (sys.path 의존 없이) ---------------------------
_QEVAL_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "phaiakes9" / "benchmark" / "quality_eval.py"
)
_SAMPLES_PATH = _QEVAL_PATH.parent / "fast_tier_eval.json"


def _import_qeval_module() -> Any:
    """quality_eval.py 를 동적 import. 테스트 격리 보장."""
    spec = importlib.util.spec_from_file_location("quality_eval_under_test", _QEVAL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def qe() -> Any:
    """quality_eval 모듈 한 번만 로드해 모듈 전체에 공유."""
    return _import_qeval_module()


# ---- 가짜 ollama 클라이언트 ------------------------------------------------
class FakeOllamaClient:
    """ollama.AsyncClient.generate/embed 를 모방하는 가짜 객체.

    Args:
        responses: 프롬프트 부분문자열 → 반환할 response 텍스트 매핑(부분 매칭).
        default: 매칭 실패 시 반환할 기본 텍스트.
        responses_by_model: (model, 프롬프트 부분문자열) 단위로 다른 답을 주고 싶을 때.
        fail_substrings: 프롬프트에 이 부분문자열이 있으면 RuntimeError 발생.
        embeddings: 정규화된 개념 문자열 → 고정 임베딩 벡터 매핑. embed가 입력 순서
            대로 이 맵을 조회해 벡터를 돌려준다(미등록 개념은 영벡터). None이면 임베딩
            테스트를 안 하는 경우(기존 테스트)로, embed 호출 시 빈 매핑처럼 동작한다.
        embed_fails: True면 embed가 RuntimeError를 던진다(임베딩 실패 → 폴백 검증용).
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default: str = "",
        responses_by_model: dict[tuple[str, str], str] | None = None,
        fail_substrings: set[str] | None = None,
        embeddings: dict[str, list[float]] | None = None,
        embed_fails: bool = False,
    ) -> None:
        self._responses = responses or {}
        self._default = default
        self._responses_by_model = responses_by_model or {}
        self._fail_substrings = fail_substrings or set()
        self._embeddings = embeddings or {}
        self._embed_fails = embed_fails
        self.calls: list[dict[str, Any]] = []
        self.embed_calls: list[dict[str, Any]] = []

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"model": model, "prompt": prompt, "stream": stream, "options": options})
        for sub in self._fail_substrings:
            if sub in prompt:
                raise RuntimeError(f"fake 실패: {sub}")
        # 모델별 우선 매칭
        for (m, sub), text in self._responses_by_model.items():
            if m == model and sub in prompt:
                return {"response": text, "done": True}
        # 프롬프트 부분 매칭
        for sub, text in self._responses.items():
            if sub in prompt:
                return {"response": text, "done": True}
        return {"response": self._default, "done": True}

    async def embed(
        self,
        model: str,
        input: list[str],  # noqa: A002 — ollama.AsyncClient.embed 시그니처 보존
    ) -> dict[str, Any]:
        """입력 순서대로 고정 임베딩 벡터를 돌려준다(실제 ollama embed와 동형).

        embeddings 맵에 없는 개념은 영벡터([0.0, 0.0])로 — 매칭되지 않음(방어적).
        embed_fails=True면 RuntimeError(러너가 정확매칭으로 폴백하는지 검증).
        """
        self.embed_calls.append({"model": model, "input": list(input)})
        if self._embed_fails:
            raise RuntimeError("fake embed 실패")
        vectors = [self._embeddings.get(c, [0.0, 0.0]) for c in input]
        return {"embeddings": vectors}


class _NoEmbedClient(FakeOllamaClient):
    """embed 메서드가 *아예 없는* 구형 클라이언트 모사(AttributeError 폴백 검증).

    embed 속성 접근 시 AttributeError를 내, 러너의 _embed_concepts가 그것을 잡고
    None을 돌려 정확매칭으로 폴백하는 경로를 탄다(메서드 미존재와 동일한 효과).
    """

    @property
    def embed(self) -> Any:
        raise AttributeError("이 가짜 클라이언트는 embed를 지원하지 않습니다")


def _matrix(qe: Any, **kw: Any) -> Any:
    """ModelMatrix 생성 헬퍼. 기본은 패밀리별로 구분 가능한 더미 모델명.

    테스트에서 'NLP 항목 → nlp-* 모델, MATH 항목 → math-* 모델' 라우팅을 calls로
    검증할 수 있도록 패밀리별로 다른 이름을 기본값으로 둔다.
    """
    base = dict(
        math_fast="math-fast",
        math_mid="math-mid",
        nlp_fast="nlp-fast",
        nlp_mid="nlp-mid",
    )
    base.update(kw)
    return qe.ModelMatrix(**base)


# ──────────────────────────────────────────────────────────────────────────
# 정규화 (normalize_form / normalize_concept)
# ──────────────────────────────────────────────────────────────────────────
def test_normalize_form_spacing_and_case(qe: Any) -> None:
    """공백·대소문자 변형이 같은 정규형으로 수렴."""
    assert qe.normalize_form("x^2+3x-4") == qe.normalize_form("x^2 + 3x - 4")
    assert qe.normalize_form("X^2 + 3X - 4") == qe.normalize_form("x^2+3x-4")
    assert qe.normalize_form("  2x + 1 < 5  ") == qe.normalize_form("2x+1<5")


def test_normalize_form_unicode_operators(qe: Any) -> None:
    """유니코드 연산자(≤·≥·×·÷·−)가 ASCII로 치환된다."""
    assert qe.normalize_form("x ≤ 3") == qe.normalize_form("x <= 3")
    assert qe.normalize_form("x ≥ -2") == qe.normalize_form("x >= -2")
    assert qe.normalize_form("2 × 3") == qe.normalize_form("2 * 3")
    assert qe.normalize_form("6 ÷ 2") == qe.normalize_form("6 / 2")
    # 유니코드 마이너스(U+2212) → 하이픈
    assert qe.normalize_form("x − 1") == qe.normalize_form("x - 1")


def test_normalize_form_strips_leading_colon_and_math_wrap(qe: Any) -> None:
    """선두 ':'·'='·수식 감싸기('$','\\(\\)')를 제거해 장식 변형을 흡수한다."""
    assert qe.normalize_form(": 45") == qe.normalize_form("45")
    assert qe.normalize_form("= x^2") == qe.normalize_form("x^2")
    assert qe.normalize_form("$45$") == qe.normalize_form("45")
    assert qe.normalize_form(r"\(x >= -2\)") == qe.normalize_form("x >= -2")


def test_normalize_form_latex_frac(qe: Any) -> None:
    r"""LaTeX '\frac{a}{b}' 가 *gold 표기* 'a/b'(괄호 없음)와 같은 정규형으로 수렴(실측 AR05)."""
    assert qe.normalize_form(r"\frac{a}{b}") == qe.normalize_form("a/b")
    assert qe.normalize_form(r"\frac{5}{6}") == qe.normalize_form("5/6")
    assert qe.normalize_form(r"\frac{1}{x}") == qe.normalize_form("1/x")
    # 다항 분자/분모는 괄호 보존(우선순위): \frac{a+b}{2} 는 '(a + b)/2' gold 와 일치
    assert qe.normalize_form(r"\frac{a+b}{2}") == qe.normalize_form("(a + b)/2")


def test_normalize_form_latex_operators_and_power(qe: Any) -> None:
    r"""'\times'/'\cdot'→'*', '\div'→'/', 'x^{2}'→'x^2', '\left'/'\right' 제거."""
    assert qe.normalize_form(r"a \times b") == qe.normalize_form("a * b")
    assert qe.normalize_form(r"a \cdot b") == qe.normalize_form("a * b")
    assert qe.normalize_form(r"6 \div 2") == qe.normalize_form("6 / 2")
    assert qe.normalize_form(r"x^{2}") == qe.normalize_form("x^2")
    assert qe.normalize_form(r"x^{10} + 1") == qe.normalize_form("x^10 + 1")
    # \left( ... \right) 의 크기 명령만 제거되고 괄호는 보존
    assert qe.normalize_form(r"\left(a + b\right)") == qe.normalize_form("(a + b)")


def test_normalize_form_latex_applies_to_both_sides_via_exact_match(qe: Any) -> None:
    r"""채점 의미 불변: 모델이 LaTeX, gold가 ASCII여도 exact_match 1.0."""
    # \frac{x}{2} 모델 출력 vs 'x/2' gold (괄호 없는 gold 표기와 일치)
    assert qe.exact_match(r"\frac{x}{2}", "x/2") == 1.0
    assert qe.exact_match(r"x^{2} + 3x - 4", "x^2 + 3x - 4") == 1.0
    assert qe.exact_match(r"2 \cdot 3", "2 * 3") == 1.0


def test_normalize_form_latex_nested_frac(qe: Any) -> None:
    r"""중첩 '\frac' 도 고정점 반복으로 안쪽부터 해소된다."""
    # \frac{1}{\frac{1}{x}} → (1)/((1)/(x))
    assert qe.normalize_form(r"\frac{1}{\frac{1}{x}}") == qe.normalize_form("(1)/((1)/(x))")


def test_normalize_concept_korean_spacing(qe: Any) -> None:
    """한국어 띄어쓰기 변형 흡수."""
    assert qe.normalize_concept("곱셈 공식") == qe.normalize_concept("곱셈공식")
    assert qe.normalize_concept(" 근의 공식 ") == qe.normalize_concept("근의공식")


# ──────────────────────────────────────────────────────────────────────────
# 답 감싸기·앞장식 strip (_strip_answer_wrapping)
# ──────────────────────────────────────────────────────────────────────────
def test_strip_wrapping_leading_colon_and_equals(qe: Any) -> None:
    """실측 ': 45' / '= x^2' 의 선두 콜론·등호를 제거한다."""
    assert qe._strip_answer_wrapping(": 45") == "45"
    assert qe._strip_answer_wrapping("= x^2") == "x^2"
    assert qe._strip_answer_wrapping("：10수학02") == "10수학02"  # 전각 콜론


def test_strip_wrapping_inline_math(qe: Any) -> None:
    """LaTeX 인라인 수식 감싸기 '$...$' / '\\(...\\)' 한 겹 제거."""
    assert qe._strip_answer_wrapping("$45$") == "45"
    assert qe._strip_answer_wrapping("$$x^2$$") == "x^2"
    assert qe._strip_answer_wrapping(r"\(x >= -2\)") == "x >= -2"


def test_strip_wrapping_markdown(qe: Any) -> None:
    """마크다운 강조 '**..**' / '*..*' / '`..`' 한 겹 제거."""
    assert qe._strip_answer_wrapping("**45**") == "45"
    assert qe._strip_answer_wrapping("*x^2*") == "x^2"
    assert qe._strip_answer_wrapping("`10수학02`") == "10수학02"


def test_strip_wrapping_nested_and_combined(qe: Any) -> None:
    """중첩 감싸기(예: '$**45**$', ': $x$')도 고정점까지 반복 제거."""
    assert qe._strip_answer_wrapping("$**45**$") == "45"
    assert qe._strip_answer_wrapping(": $x$") == "x"


def test_strip_wrapping_preserves_inner_operators(qe: Any) -> None:
    """내부 곱셈 별표·등식은 보존(감싸기만 제거, 내용 불변)."""
    assert qe._strip_answer_wrapping("x*y") == "x*y"
    assert qe._strip_answer_wrapping("y = x^2 + 1") == "y = x^2 + 1"
    # 두 개의 분리된 인라인 수식은 전체 감싸기가 아니므로 보존
    assert qe._strip_answer_wrapping("$a$ + $b$") == "$a$ + $b$"


# ──────────────────────────────────────────────────────────────────────────
# 답 구간 추출 폴백 (_extract_answer_span / _innermost_boxed / _last_label_value)
# ──────────────────────────────────────────────────────────────────────────
def test_extract_span_answer_tag_priority(qe: Any) -> None:
    """1순위: 마지막 '<ANSWER>...</ANSWER>' 내용(앞에 ####·boxed·라벨이 있어도 우선)."""
    raw = "풀이 \\boxed{99}\n#### 88\nANSWER: 77\n<ANSWER>45</ANSWER>"
    assert qe._extract_answer_span(raw) == "45"
    # 여러 개면 마지막 것
    assert qe._extract_answer_span("<ANSWER>1</ANSWER> 다시 <ANSWER>2</ANSWER>") == "2"
    # 대소문자 무관 + 여러 줄 내용 허용(개념 나열이 줄바꿈될 때)
    assert (
        qe._extract_answer_span("<answer>분배법칙,\n동류항 정리</answer>")
        == "분배법칙,\n동류항 정리"
    )
    # 태그 안이 비면 빈 문자열(폴백 안 함 — 계약을 지킨 빈 답)
    assert qe._extract_answer_span("설명\n<ANSWER></ANSWER>") == ""


def test_extract_span_hashes_priority(qe: Any) -> None:
    """2순위: '<ANSWER>' 없으면 마지막 '####' 뒤 같은 줄(앞에 boxed·라벨 있어도 #### 우선)."""
    raw = "풀이 \\boxed{99}\nANSWER: 88\n#### 45"
    assert qe._extract_answer_span(raw) == "45"
    # '####' 가 여러 번이면 마지막 것
    assert qe._extract_answer_span("#### 1\n다시\n#### 2") == "2"


def test_extract_span_boxed_fallback(qe: Any) -> None:
    """2순위: '####' 없으면 '\\boxed{}' 가장 안쪽 내용."""
    assert qe._extract_answer_span("따라서 답은 \\boxed{12} 입니다.") == "12"
    # 중첩 boxed는 가장 안쪽
    assert qe._extract_answer_span(r"\boxed{\boxed{42}}") == "42"
    # 여러 boxed면 마지막 것
    assert qe._extract_answer_span(r"\boxed{1} 그리고 \boxed{2}") == "2"


def test_extract_span_label_fallback(qe: Any) -> None:
    """3순위: '####'·boxed 없으면 라벨('ANSWER:'/'정답:'/'답:'/'정답은')."""
    assert qe._extract_answer_span("풀이...\nANSWER: x^2 + 3x - 4") == "x^2 + 3x - 4"
    assert qe._extract_answer_span("정답: 10수학02") == "10수학02"
    assert qe._extract_answer_span("답: 91") == "91"
    # 콜론 없는 한국어 라벨 '정답은'
    assert qe._extract_answer_span("정답은 45") == "45"
    # 라벨 여러 개면 마지막
    assert qe._extract_answer_span("ANSWER: 틀린값\n다시\nANSWER: 45") == "45"


def test_extract_span_last_line_fallback(qe: Any) -> None:
    """4순위: 아무 표지도 없으면 마지막 비어있지 않은 줄."""
    assert qe._extract_answer_span("계산 과정\n2x + 1 < 5") == "2x + 1 < 5"
    assert qe._extract_answer_span("") == ""
    assert qe._extract_answer_span("   \n  ") == ""


def test_innermost_boxed_none_when_absent(qe: Any) -> None:
    """boxed가 없으면 None(폴백 분기 진입 보장)."""
    assert qe._innermost_boxed("답 없음") is None


def test_innermost_boxed_unbalanced(qe: Any) -> None:
    """닫는 중괄호가 없으면 열린 지점부터 끝까지를 내용으로 본다(견고성)."""
    assert qe._innermost_boxed(r"\boxed{45") == "45"


def test_innermost_boxed_inner_braces(qe: Any) -> None:
    """내부에 일반 중괄호('\\frac{5}{6}')가 있어도 균형 스캔으로 전체 내용을 얻는다."""
    # 내부 '{','}' 깊이 추적(depth += 1 / depth==0 break) 경로를 탄다.
    assert qe._innermost_boxed(r"\boxed{\frac{5}{6}}") == r"\frac{5}{6}"
    # 단일답 파서를 통한 end-to-end(감싸기 strip은 LaTeX 명령을 보존)
    assert qe.parse_single_answer(r"답은 \boxed{\frac{5}{6}} 이다") == r"\frac{5}{6}"


# ──────────────────────────────────────────────────────────────────────────
# 출력 파서 (parse_concept_list / parse_single_answer) — 실측 qwen2-math 스타일
# ──────────────────────────────────────────────────────────────────────────
def test_parse_concept_list_answer_tag_contract(qe: Any) -> None:
    """프롬프트 계약대로 '<ANSWER>개념1, 개념2, 개념3</ANSWER>' 를 파싱."""
    raw = "이 문제는 다항식을 다룹니다.\n<ANSWER>분배법칙, 동류항 정리, 다항식의 곱셈</ANSWER>"
    assert qe.parse_concept_list(raw) == ["분배법칙", "동류항 정리", "다항식의 곱셈"]
    # 태그 안 내용이 줄바꿈으로 나뉘어도 쉼표 분할이 동작
    raw2 = "<ANSWER>이차방정식,\n인수분해</ANSWER>"
    assert qe.parse_concept_list(raw2) == ["이차방정식", "인수분해"]


def test_parse_concept_list_hash_contract(qe: Any) -> None:
    """구 계약 폴백: '<ANSWER>' 없으면 '#### 개념1, 개념2, 개념3' 한 줄을 파싱."""
    raw = "이 문제는 다항식을 다룹니다.\n#### 분배법칙, 동류항 정리, 다항식의 곱셈"
    assert qe.parse_concept_list(raw) == ["분배법칙", "동류항 정리", "다항식의 곱셈"]


def test_parse_concept_list_comma_no_marker(qe: Any) -> None:
    """표지 없는 단순 쉼표 나열(마지막 줄 폴백)."""
    assert qe.parse_concept_list("분배법칙, 동류항 정리, 다항식의 곱셈") == [
        "분배법칙",
        "동류항 정리",
        "다항식의 곱셈",
    ]


def test_parse_concept_list_label_line(qe: Any) -> None:
    """앞선 설명 줄 무시 + '개념:' 라벨 제거(개념 전용 라벨 strip)."""
    raw = "이 문제를 보면...\n다음과 같습니다.\n개념: 인수분해, 근의 공식"
    assert qe.parse_concept_list(raw) == ["인수분해", "근의 공식"]


def test_parse_concept_list_sentence_format_no_split(qe: Any) -> None:
    """문장형 응답(쉼표 없음)은 분할되지 않아 gold와 안 맞음(형식 미준수가 점수에 반영).

    실측: "이 문제는 '전개'라는 수학 개념을 다루고 있습니다." → 한 덩어리로 남아
    개념 집합과 매칭되지 않는다(set_f1 낮음). 이는 의도된 동작이다.
    """
    raw = "이 문제는 '전개'라는 수학 개념을 다루고 있습니다."
    parsed = qe.parse_concept_list(raw)
    assert parsed == ["이 문제는 '전개'라는 수학 개념을 다루고 있습니다."]


def test_parse_concept_list_middot_and_bullets(qe: Any) -> None:
    """가운뎃점 분할 + 번호/글머리표 제거."""
    assert qe.parse_concept_list("#### 1. 절댓값 · 2. 일차부등식") == ["절댓값", "일차부등식"]


def test_parse_concept_list_empty(qe: Any) -> None:
    """빈 응답은 빈 리스트."""
    assert qe.parse_concept_list("") == []
    assert qe.parse_concept_list("   \n  ") == []


def test_parse_single_answer_answer_tag_contract(qe: Any) -> None:
    """프롬프트 계약대로 '<ANSWER><답></ANSWER>' 를 파싱(앞선 풀이·#### 무시)."""
    raw = "144를 12로 나누면 12입니다.\n#### 99\n<ANSWER>12</ANSWER>"
    assert qe.parse_single_answer(raw) == "12"
    # 태그 안 식에 공백이 있어도 그대로(정규화는 채점기 몫)
    assert qe.parse_single_answer("정규화\n<ANSWER>x^2 + 3x - 4</ANSWER>") == "x^2 + 3x - 4"


def test_parse_single_answer_hash_contract(qe: Any) -> None:
    """구 계약 폴백: '<ANSWER>' 없으면 '#### <답>' 한 줄을 파싱(앞선 풀이 줄 무시)."""
    raw = "144를 12로 나누면 12입니다.\n#### 12"
    assert qe.parse_single_answer(raw) == "12"


def test_parse_single_answer_boxed(qe: Any) -> None:
    """qwen2-math 의 '\\boxed{}' 최종답 추출."""
    raw = "계산하면 \\boxed{45} 이다."
    assert qe.parse_single_answer(raw) == "45"


def test_parse_single_answer_label(qe: Any) -> None:
    """'ANSWER:' 라벨 뒤만 추출 (마지막 라벨 우선)."""
    raw = "풀이 과정...\n계산하면...\nANSWER: x^2 + 3x - 4"
    assert qe.parse_single_answer(raw) == "x^2 + 3x - 4"


def test_parse_single_answer_korean_label_and_multiple(qe: Any) -> None:
    """'정답:' 라벨도 인식하고, 라벨이 여러 개면 마지막 것."""
    raw = "ANSWER: 틀린값\n다시 계산\nANSWER: 45"
    assert qe.parse_single_answer(raw) == "45"
    assert qe.parse_single_answer("정답: 10수학02") == "10수학02"


def test_parse_single_answer_leading_colon(qe: Any) -> None:
    """실측 결과 ': 45'(앞 콜론)도 strip 되어 '45' 가 된다."""
    assert qe.parse_single_answer(": 45") == "45"
    # 마지막 줄이 ': 45' 인 경우
    assert qe.parse_single_answer("계산 과정\n: 45") == "45"


def test_parse_single_answer_no_label_last_line(qe: Any) -> None:
    """라벨이 없으면 마지막 비어있지 않은 줄."""
    raw = "계산 과정\n2x + 1 < 5"
    assert qe.parse_single_answer(raw) == "2x + 1 < 5"
    assert qe.parse_single_answer("") == ""


# ──────────────────────────────────────────────────────────────────────────
# 채점기 — exact_match
# ──────────────────────────────────────────────────────────────────────────
def test_exact_match_correct_with_spacing(qe: Any) -> None:
    """공백 변형이 있어도 정규화 후 일치 → 1.0."""
    assert qe.exact_match("x^2+3x-4", "x^2 + 3x - 4") == 1.0
    assert qe.exact_match("  45 ", "45") == 1.0


def test_exact_match_leading_colon_equiv(qe: Any) -> None:
    """실측 ': 45'(앞 콜론) 가 gold '45' 와 매칭된다(형식 불일치로 0점 되던 버그 방어)."""
    assert qe.exact_match(": 45", "45") == 1.0
    assert qe.exact_match("$45$", "45") == 1.0


def test_exact_match_incorrect(qe: Any) -> None:
    """다른 값 → 0.0."""
    assert qe.exact_match("x^2 + 3x - 5", "x^2 + 3x - 4") == 0.0
    assert qe.exact_match("46", "45") == 0.0


def test_exact_match_unicode_operator_equiv(qe: Any) -> None:
    """유니코드 연산자 차이는 동일 취급."""
    assert qe.exact_match("x ≥ -2", "x >= -2") == 1.0


# ──────────────────────────────────────────────────────────────────────────
# 채점기 — set_f1
# ──────────────────────────────────────────────────────────────────────────
def test_set_f1_perfect(qe: Any) -> None:
    """완전 일치(순서·띄어쓰기 무관) → 1.0."""
    parsed = ["동류항 정리", "분배법칙", "다항식의 곱셈"]
    gold = ["다항식의 곱셈", "분배법칙", "동류항정리"]
    assert qe.set_f1(parsed, gold) == pytest.approx(1.0)


def test_set_f1_partial(qe: Any) -> None:
    """부분 겹침 → 0<F1<1. 2개 중 1개 맞고 1개 잉여 → P=1/2,R=1/2,F1=0.5."""
    parsed = ["인수분해", "엉뚱한개념"]
    gold = ["인수분해", "근의 공식"]
    assert qe.set_f1(parsed, gold) == pytest.approx(0.5)


def test_set_f1_no_overlap(qe: Any) -> None:
    """겹침 없음 → 0.0."""
    assert qe.set_f1(["a", "b"], ["c", "d"]) == 0.0


def test_set_f1_empty_edge(qe: Any) -> None:
    """빈 집합 엣지: gold 비고 parsed도 비면 1.0, parsed만 있으면 0.0, gold만 있으면 0.0."""
    assert qe.set_f1([], []) == 1.0
    assert qe.set_f1(["a"], []) == 0.0
    assert qe.set_f1([], ["a"]) == 0.0


def test_set_f1_parts(qe: Any) -> None:
    """precision/recall/f1 분해 — 잉여 1개, 누락 0개."""
    parsed = ["a", "b", "c"]  # c는 잉여
    gold = ["a", "b"]
    p, r, f1 = qe.set_f1_parts(parsed, gold)
    assert p == pytest.approx(2 / 3)
    assert r == pytest.approx(1.0)
    assert f1 == pytest.approx(2 * (2 / 3) * 1.0 / (2 / 3 + 1.0))


def test_set_f1_parts_empty(qe: Any) -> None:
    """분해의 빈 엣지도 set_f1과 일관."""
    assert qe.set_f1_parts([], []) == (1.0, 1.0, 1.0)
    assert qe.set_f1_parts([], ["a"]) == (0.0, 0.0, 0.0)


def test_set_f1_parts_no_overlap(qe: Any) -> None:
    """겹침이 전혀 없으면 (0,0,0) — tp==0 분기."""
    assert qe.set_f1_parts(["a", "b"], ["c", "d"]) == (0.0, 0.0, 0.0)


# ──────────────────────────────────────────────────────────────────────────
# 코사인 유사도 (cosine) — extract 의미매칭 기반 (03a §H 후속8)
# ──────────────────────────────────────────────────────────────────────────
def test_cosine_identical_vectors(qe: Any) -> None:
    """동일 방향 벡터는 1.0(스케일 무관)."""
    assert qe.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    # 스케일이 달라도 방향이 같으면 1.0
    assert qe.cosine([1.0, 2.0, 2.0], [2.0, 4.0, 4.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_and_opposite(qe: Any) -> None:
    """직교 벡터는 0.0, 반대 방향은 -1.0."""
    assert qe.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert qe.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_known_value(qe: Any) -> None:
    """알려진 값: [1,1]·[1,0] = 1, 노름 √2·1 → cos = 1/√2 ≈ 0.7071."""
    assert qe.cosine([1.0, 1.0], [1.0, 0.0]) == pytest.approx(1 / 2**0.5)
    # [3,4]·[4,3] = 24, 노름 5·5=25 → 0.96
    assert qe.cosine([3.0, 4.0], [4.0, 3.0]) == pytest.approx(0.96)


def test_cosine_zero_vector_returns_zero(qe: Any) -> None:
    """영벡터는 방향이 없으므로 0.0(분모 0 방지)."""
    assert qe.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert qe.cosine([1.0, 1.0], [0.0, 0.0]) == 0.0
    assert qe.cosine([], [1.0]) == 0.0


# ──────────────────────────────────────────────────────────────────────────
# 의미매칭 집합 F1 (set_f1_semantic / set_f1_semantic_parts) — 03a §H 후속8
# ──────────────────────────────────────────────────────────────────────────
def _syn_emb() -> dict[str, list[float]]:
    """가짜 임베딩 맵(정규화된 키): 동의어는 고유사, 무관 개념은 직교.

    키는 normalize_concept 결과(공백 제거·소문자)와 같아야 한다 — 러너의 emb 키와 동일.
    '다항식의곱셈'·'다항식전개'는 거의 같은 방향(동의어), '무관개념'은 직교.
    """
    return {
        "다항식의곱셈": [1.0, 0.0],
        "다항식전개": [0.99, 0.14],  # cos ≈ 0.99 (동의어)
        "인수분해": [0.0, 1.0],  # 위 둘과 직교
        "무관개념": [0.0, 1.0],
    }


def test_set_f1_semantic_synonym_matches(qe: Any) -> None:
    """표현이 다른 동의어(고 cosine)는 매칭 → F1=1.0 ('다항식 전개' vs '다항식의 곱셈')."""
    emb = _syn_emb()
    # 정확매칭(set_f1)이라면 불일치로 0.0이었을 케이스
    assert qe.set_f1(["다항식 전개"], ["다항식의 곱셈"]) == 0.0
    # 의미매칭은 동의어로 인정 → 1.0
    assert qe.set_f1_semantic(["다항식 전개"], ["다항식의 곱셈"], emb, 0.6) == pytest.approx(1.0)


def test_set_f1_semantic_unrelated_no_match(qe: Any) -> None:
    """무관 개념(저 cosine)은 미매칭 → F1=0.0."""
    emb = _syn_emb()
    assert qe.set_f1_semantic(["무관 개념"], ["다항식의 곱셈"], emb, 0.6) == 0.0


def test_set_f1_semantic_threshold_boundary(qe: Any) -> None:
    """threshold 경계: cosine이 임계 이상이면 매칭, 미만이면 미매칭."""
    # cos([1,0],[0.6,0.8]) = 0.6 정확히
    emb = {"가": [1.0, 0.0], "나": [0.6, 0.8]}
    # threshold=0.6 → 0.6 >= 0.6 매칭
    assert qe.set_f1_semantic(["가"], ["나"], emb, 0.6) == pytest.approx(1.0)
    # threshold를 0.6보다 살짝 위로 올리면 미매칭
    assert qe.set_f1_semantic(["가"], ["나"], emb, 0.61) == 0.0


def test_set_f1_semantic_empty_edges(qe: Any) -> None:
    """빈 집합 규약은 set_f1과 동일: 둘 다 비면 1.0, 한쪽만 있으면 0.0."""
    emb = _syn_emb()
    assert qe.set_f1_semantic([], [], emb, 0.6) == 1.0
    assert qe.set_f1_semantic(["다항식의 곱셈"], [], emb, 0.6) == 0.0
    assert qe.set_f1_semantic([], ["다항식의 곱셈"], emb, 0.6) == 0.0


def test_set_f1_semantic_partial(qe: Any) -> None:
    """부분 매칭: parsed 2개 중 1개만 gold와 동의 → P=1/2, R=1/1, F1=2/3."""
    emb = _syn_emb()
    # '다항식 전개'(↔곱셈 동의), '무관 개념'(직교) vs gold ['다항식의 곱셈']
    p, r, f1 = qe.set_f1_semantic_parts(["다항식 전개", "무관 개념"], ["다항식의 곱셈"], emb, 0.6)
    assert p == pytest.approx(0.5)
    assert r == pytest.approx(1.0)
    assert f1 == pytest.approx(2 / 3)


def test_set_f1_semantic_one_to_one_matching(qe: Any) -> None:
    """그리디 1:1 이분 매칭: 한 gold가 두 parsed에 동시에 쓰이지 않는다.

    parsed=[A1, A2] 둘 다 gold=[G] 하나와만 고유사일 때, G는 한 번만 매칭되어야
    한다(중복 매칭 방지). TP=1 → P=1/2, R=1/1, F1=2/3.
    """
    emb = {"a1": [1.0, 0.0], "a2": [0.99, 0.14], "g": [1.0, 0.0]}
    p, r, f1 = qe.set_f1_semantic_parts(["a1", "a2"], ["g"], emb, 0.6)
    assert p == pytest.approx(0.5)  # 2개 중 1개만 매칭
    assert r == pytest.approx(1.0)  # gold 1개 매칭됨
    assert f1 == pytest.approx(2 / 3)


def test_set_f1_semantic_greedy_picks_best_pair(qe: Any) -> None:
    """그리디는 가장 높은 유사도 쌍부터 매칭한다(1:1 최적에 가까운 선택).

    parsed=[X, Y], gold=[Gx, Gy]에서 X↔Gx(1.0), Y↔Gy(1.0)가 최선. 교차쌍은
    유사도가 낮아야 하며, 그리디가 최고 쌍부터 잡아 둘 다 매칭 → F1=1.0.
    """
    emb = {
        "x": [1.0, 0.0],
        "gx": [1.0, 0.0],  # x와 동일(1.0)
        "y": [0.0, 1.0],
        "gy": [0.0, 1.0],  # y와 동일(1.0), x와는 직교(0.0)
    }
    assert qe.set_f1_semantic(["x", "y"], ["gx", "gy"], emb, 0.6) == pytest.approx(1.0)


def test_set_f1_semantic_dedup_normalized(qe: Any) -> None:
    """정규화 후 중복 개념은 한 번만 센다(집합 의미 유지)."""
    emb = {"다항식의곱셈": [1.0, 0.0]}
    # parsed에 '다항식의 곱셈'/'다항식의곱셈'(띄어쓰기만 다름)을 둘 다 줘도 1개로 취급
    f1 = qe.set_f1_semantic(["다항식의 곱셈", "다항식의곱셈"], ["다항식의 곱셈"], emb, 0.6)
    assert f1 == pytest.approx(1.0)


def test_set_f1_semantic_missing_emb_key_no_match(qe: Any) -> None:
    """emb 맵에 없는 개념은 영벡터로 간주 → 미매칭(방어적)."""
    emb: dict[str, list[float]] = {}  # 아무 벡터도 없음
    assert qe.set_f1_semantic(["다항식의 곱셈"], ["다항식의 곱셈"], emb, 0.6) == 0.0


def test_grade_item_absorbs_exception(qe: Any) -> None:
    """채점 중 예외(gold 타입 불일치)는 score=0·error로 흡수된다(러너 보호).

    extract 항목인데 gold가 str이면 set_f1 분기의 assert가 깨진다 →
    grade_item이 예외를 잡아 ItemScore(score=0, error!=None)을 돌려준다.
    """
    bad = _item(qe, id="BAD", call_site="extract", task_type="extract", gold="잘못된타입")
    score = qe.grade_item(bad, "ANSWER: 무엇이든")
    assert score.score == 0.0
    assert score.correct is False
    assert score.error is not None


# ──────────────────────────────────────────────────────────────────────────
# grade_item — 호출지점별 디스패치
# ──────────────────────────────────────────────────────────────────────────
def _item(qe: Any, **kw: Any) -> Any:
    """EvalItem 생성 헬퍼(필드 기본값 채움)."""
    base = dict(
        id="X",
        call_site=None,
        task_type="explain",
        difficulty="easy",
        prompt="p",
        gold="0",
    )
    base.update(kw)
    return qe.EvalItem(**base)


def test_grade_item_extract_uses_set_f1(qe: Any) -> None:
    """extract 항목은 set_f1로 채점되고 부분 점수가 나온다(<ANSWER> 계약 형식)."""
    item = _item(
        qe, id="CE", call_site="extract", task_type="extract", gold=["인수분해", "근의 공식"]
    )
    score = qe.grade_item(item, "<ANSWER>인수분해, 엉뚱</ANSWER>")
    assert score.grader == qe.GRADER_SET_F1
    assert score.score == pytest.approx(0.5)
    assert score.correct is False  # F1 != 1.0
    assert score.parsed == ["인수분해", "엉뚱"]


def test_grade_item_extract_perfect_correct(qe: Any) -> None:
    """extract 완전 일치면 correct=True(풀이 후 <ANSWER> 줄)."""
    item = _item(qe, call_site="extract", task_type="extract", gold=["분배법칙", "동류항 정리"])
    score = qe.grade_item(item, "이 문제는 다항식.\n<ANSWER>분배법칙, 동류항정리</ANSWER>")
    assert score.score == pytest.approx(1.0)
    assert score.correct is True


def test_grade_extract_semantic_synonym_correct(qe: Any) -> None:
    """grade_extract_semantic: 동의어 표현도 매칭되어 grader=set_f1_semantic·correct."""
    item = _item(qe, id="CE", call_site="extract", task_type="extract", gold=["다항식의 곱셈"])
    emb = {"다항식의곱셈": [1.0, 0.0], "다항식전개": [0.99, 0.14]}
    score = qe.grade_extract_semantic(item, "<ANSWER>다항식 전개</ANSWER>", emb, 0.6)
    assert score.grader == qe.GRADER_SET_F1_SEMANTIC
    assert score.score == pytest.approx(1.0)
    assert score.correct is True
    assert score.parsed == ["다항식 전개"]


def test_grade_extract_semantic_absorbs_exception(qe: Any) -> None:
    """gold가 str(타입 불일치)이면 assert 깨짐 → score=0·error로 흡수(grader 유지)."""
    bad = _item(qe, id="BAD", call_site="extract", task_type="extract", gold="문자열_gold")
    score = qe.grade_extract_semantic(bad, "<ANSWER>무엇이든</ANSWER>", {}, 0.6)
    assert score.score == 0.0
    assert score.correct is False
    assert score.error is not None
    assert score.grader == qe.GRADER_SET_F1_SEMANTIC


def test_grade_item_translate_exact(qe: Any) -> None:
    """translate 항목은 exact_match로 채점(<ANSWER> 계약 형식)."""
    item = _item(qe, call_site="translate", task_type="translate", gold="x^2 + 3x - 4")
    ok = qe.grade_item(item, "정규화하면\n<ANSWER>x^2+3x-4</ANSWER>")
    assert ok.grader == qe.GRADER_EXACT
    assert ok.correct is True
    bad = qe.grade_item(item, "<ANSWER>x^2+3x-5</ANSWER>")
    assert bad.correct is False


def test_grade_item_match_and_arithmetic(qe: Any) -> None:
    """match·산술(call_site=None) 모두 exact_match — <ANSWER> 계약 + 폴백(boxed/앞콜론)."""
    m = _item(qe, call_site="match", task_type="match", gold="10수학02")
    assert qe.grade_item(m, "<ANSWER>10수학02</ANSWER>").correct is True
    a = _item(qe, call_site=None, task_type="explain", gold="45")
    # <ANSWER> 계약 형식
    assert qe.grade_item(a, "계산하면\n<ANSWER>45</ANSWER>").correct is True
    # boxed 최종답(폴백)
    assert qe.grade_item(a, "계산하면 \\boxed{45}").correct is True
    # 앞 콜론 실측 케이스도 정답 처리(폴백)
    assert qe.grade_item(a, "계산 과정\n: 45").correct is True


def test_grade_item_grader_mapping(qe: Any) -> None:
    """EvalItem.grader()가 호출지점→채점기 매핑을 따른다."""
    assert _item(qe, call_site="extract").grader() == qe.GRADER_SET_F1
    assert _item(qe, call_site="translate").grader() == qe.GRADER_EXACT
    assert _item(qe, call_site="match").grader() == qe.GRADER_EXACT
    assert _item(qe, call_site=None).grader() == qe.GRADER_EXACT


# ──────────────────────────────────────────────────────────────────────────
# 태스크 패밀리 — EvalItem.family() / ModelMatrix.model_for()
# ──────────────────────────────────────────────────────────────────────────
def test_item_family_mapping(qe: Any) -> None:
    """extract/translate/match → NLP, 산술(call_site None) → MATH."""
    assert _item(qe, call_site="extract").family() == qe.FAMILY_NLP
    assert _item(qe, call_site="translate").family() == qe.FAMILY_NLP
    assert _item(qe, call_site="match").family() == qe.FAMILY_NLP
    assert _item(qe, call_site=None).family() == qe.FAMILY_MATH
    # 알 수 없는 호출지점은 보수적으로 NLP(대부분의 호출지점이 NLP)
    assert _item(qe, call_site="unknown_site").family() == qe.FAMILY_NLP


def test_model_matrix_model_for(qe: Any) -> None:
    """ModelMatrix가 (패밀리, 역할) → 모델 ID를 올바로 고른다."""
    m = qe.ModelMatrix(math_fast="mf", math_mid="mm", nlp_fast="nf", nlp_mid="nm")
    assert m.model_for(qe.FAMILY_MATH, "fast") == "mf"
    assert m.model_for(qe.FAMILY_MATH, "mid") == "mm"
    assert m.model_for(qe.FAMILY_NLP, "fast") == "nf"
    assert m.model_for(qe.FAMILY_NLP, "mid") == "nm"
    # 알 수 없는 패밀리는 NLP로 폴백
    assert m.model_for("weird", "fast") == "nf"


def test_model_matrix_defaults(qe: Any) -> None:
    """기본 매트릭스: MATH=qwen2-math, NLP=qwen2.5(일반 모델)."""
    m = qe.ModelMatrix()
    assert m.math_fast == qe.DEFAULT_MATH_FAST_MODEL == "qwen2-math:1.5b"
    assert m.math_mid == qe.DEFAULT_MATH_MID_MODEL == "qwen2-math:7b"
    # NLP는 일반 모델이어야 한다(실측 교정의 핵심).
    assert m.nlp_fast == qe.DEFAULT_NLP_FAST_MODEL == "qwen2.5:3b"
    assert m.nlp_mid == qe.DEFAULT_NLP_MID_MODEL == "qwen2.5:7b"
    assert "qwen2-math" not in m.nlp_fast and "qwen2-math" not in m.nlp_mid


# ──────────────────────────────────────────────────────────────────────────
# 집계 — aggregate_by_call_site
# ──────────────────────────────────────────────────────────────────────────
def _score(qe: Any, call_site: str | None, score: float, correct: bool, grader: str) -> Any:
    return qe.ItemScore(
        item_id="i",
        call_site=call_site,
        grader=grader,
        score=score,
        correct=correct,
        raw_response="",
        parsed="",
    )


def test_aggregate_groups_and_metrics(qe: Any) -> None:
    """호출지점별로 평균점수·정확도·에러수를 집계하고 키 정렬."""
    scores = [
        _score(qe, "extract", 1.0, True, qe.GRADER_SET_F1),
        _score(qe, "extract", 0.5, False, qe.GRADER_SET_F1),
        _score(qe, "translate", 1.0, True, qe.GRADER_EXACT),
        _score(qe, None, 0.0, False, qe.GRADER_EXACT),
    ]
    aggs = qe.aggregate_by_call_site(scores)
    by_key = {a.call_site: a for a in aggs}
    # 산술 그룹은 '__arithmetic__' 키
    assert set(by_key) == {"extract", "translate", "__arithmetic__"}
    assert by_key["extract"].n_items == 2
    assert by_key["extract"].mean_score == pytest.approx(0.75)
    assert by_key["extract"].accuracy == pytest.approx(0.5)
    assert by_key["translate"].accuracy == pytest.approx(1.0)
    assert by_key["__arithmetic__"].accuracy == pytest.approx(0.0)
    # 정렬: __arithmetic__ < extract < translate (사전순)
    assert [a.call_site for a in aggs] == ["__arithmetic__", "extract", "translate"]


def test_aggregate_counts_errors(qe: Any) -> None:
    """error 필드가 있는 항목은 n_errors에 반영."""
    s_err = qe.ItemScore(
        item_id="e",
        call_site="match",
        grader=qe.GRADER_EXACT,
        score=0.0,
        correct=False,
        raw_response="ERROR: x",
        parsed="",
        error="RuntimeError: x",
    )
    aggs = qe.aggregate_by_call_site([s_err])
    assert aggs[0].n_errors == 1


# ──────────────────────────────────────────────────────────────────────────
# 결정 규칙 — decide_call_site / build_verdicts
# ──────────────────────────────────────────────────────────────────────────
def test_decide_keep_fast_when_close_and_above_floor(qe: Any) -> None:
    """FAST가 MID에 근접(delta 이내)하고 절대 하한 이상 → FAST 유지."""
    v = qe.decide_call_site("extract", qe.GRADER_SET_F1, 0.90, 0.92, delta=0.07, abs_min=0.60)
    assert v.keep_fast is True
    assert "FAST 유지" in v.verdict


def test_decide_promote_when_gap_too_large(qe: Any) -> None:
    """FAST가 MID보다 delta 초과로 낮으면 → MID 승급 권고."""
    v = qe.decide_call_site("translate", qe.GRADER_EXACT, 0.70, 0.95, delta=0.07, abs_min=0.60)
    assert v.keep_fast is False
    assert "MID 승급 권고" in v.verdict


def test_decide_promote_when_below_abs_min(qe: Any) -> None:
    """FAST가 MID에 근접해도 둘 다 절대 하한 미만이면 → MID 승급(하한 사유)."""
    v = qe.decide_call_site("match", qe.GRADER_EXACT, 0.50, 0.52, delta=0.07, abs_min=0.60)
    assert v.keep_fast is False
    assert "절대 하한" in v.verdict


def test_decide_boundary_exactly_at_thresholds(qe: Any) -> None:
    """경계값: fast == mid - delta 이고 fast == abs_min 이면 유지(>= 비교)."""
    # mid=0.67, delta=0.07 → 임계 0.60; fast=0.60 == abs_min → 둘 다 경계 충족
    v = qe.decide_call_site("x", qe.GRADER_EXACT, 0.60, 0.67, delta=0.07, abs_min=0.60)
    assert v.keep_fast is True


def test_decide_fast_beats_mid(qe: Any) -> None:
    """FAST가 MID보다 높아도(드묾) 절대 하한만 넘으면 유지."""
    v = qe.decide_call_site("extract", qe.GRADER_SET_F1, 0.95, 0.80, delta=0.07, abs_min=0.60)
    assert v.keep_fast is True


def test_build_verdicts_pairs_call_sites(qe: Any) -> None:
    """FAST·MID 집계를 호출지점별로 짝지어 판정 목록 생성."""
    fast_aggs = [
        qe.CallSiteAggregate("extract", qe.GRADER_SET_F1, 9, 0.9, 0.9, 0),
        qe.CallSiteAggregate("translate", qe.GRADER_EXACT, 8, 0.7, 0.7, 0),
    ]
    mid_aggs = [
        qe.CallSiteAggregate("extract", qe.GRADER_SET_F1, 9, 0.92, 0.92, 0),
        qe.CallSiteAggregate("translate", qe.GRADER_EXACT, 8, 0.95, 0.95, 0),
    ]
    verdicts = qe.build_verdicts(fast_aggs, mid_aggs, delta=0.07, abs_min=0.60)
    by_key = {v.call_site: v for v in verdicts}
    assert by_key["extract"].keep_fast is True  # 0.9 vs 0.92 근접
    assert by_key["translate"].keep_fast is False  # 0.7 vs 0.95 격차 큼


def test_build_verdicts_missing_side_treated_zero(qe: Any) -> None:
    """한쪽에만 있는 호출지점은 상대 정확도 0으로 간주."""
    fast_aggs = [qe.CallSiteAggregate("match", qe.GRADER_EXACT, 8, 0.9, 0.9, 0)]
    mid_aggs: list[Any] = []
    verdicts = qe.build_verdicts(fast_aggs, mid_aggs, delta=0.07, abs_min=0.60)
    # mid=0.0이므로 fast(0.9)는 근접 조건 자동 충족 + 하한 충족 → 유지
    assert verdicts[0].keep_fast is True
    assert verdicts[0].mid_accuracy == 0.0


# ──────────────────────────────────────────────────────────────────────────
# 평가셋 로드 / 스키마
# ──────────────────────────────────────────────────────────────────────────
def test_load_items_real_file(qe: Any) -> None:
    """프로젝트의 실제 fast_tier_eval.json 이 정상 파싱되는지."""
    items = qe.load_items(_SAMPLES_PATH)
    assert len(items) >= 30, "카테고리당 ~8개 이상 → 총 30+ 기대"
    for it in items:
        assert it.id
        assert it.prompt
        # gold는 extract면 list, 그 외면 str
        if it.call_site == "extract":
            assert isinstance(it.gold, list) and it.gold
        else:
            assert isinstance(it.gold, str) and it.gold


def test_load_items_category_coverage(qe: Any) -> None:
    """4개 카테고리(extract/translate/match/산술)가 각각 충분히 있다."""
    items = qe.load_items(_SAMPLES_PATH)
    counts: dict[str, int] = {}
    for it in items:
        key = it.call_site if it.call_site is not None else "__arithmetic__"
        counts[key] = counts.get(key, 0) + 1
    for key in ("extract", "translate", "match", "__arithmetic__"):
        assert counts.get(key, 0) >= 8, f"{key} 항목이 8개 미만"


def test_load_items_grader_assignment(qe: Any) -> None:
    """로드된 항목의 grader()가 카테고리와 일치."""
    items = qe.load_items(_SAMPLES_PATH)
    for it in items:
        if it.call_site == "extract":
            assert it.grader() == qe.GRADER_SET_F1
        else:
            assert it.grader() == qe.GRADER_EXACT


def test_dataset_no_copyright_violation() -> None:
    """검정교과서·평가원·EBS 인용 방지 메타데이터 (CLAUDE.md 절대 금기)."""
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert "license" in raw
    assert "author" in raw
    assert "CC0" in raw["license"] or "원작" in raw["license"]


def test_dataset_all_prompts_use_answer_contract() -> None:
    """33문항 전부 '<ANSWER>...</ANSWER>' 출력 계약을 포함하고 '####'는 없다."""
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert len(raw["items"]) == 33
    for it in raw["items"]:
        p = it["prompt"]
        assert "<ANSWER>" in p and "</ANSWER>" in p, f"{it['id']}: <ANSWER> 계약 누락"
        assert "####" not in p, f"{it['id']}: 구 '####' 계약이 남아 있음"


def test_dataset_match_candidates_have_topic_names() -> None:
    """match 후보 목록에 코드+주제명이 들어가되 gold는 코드(10수학NN)만 유지(닫힌 PR #8 keeper)."""
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    match_items = [it for it in raw["items"] if it["call_site"] == "match"]
    assert len(match_items) == 8
    for it in match_items:
        p = it["prompt"]
        # 4개 주제명이 후보에 명시
        for topic in ("(다항식)", "(방정식과 부등식)", "(도형의 방정식)", "(함수)"):
            assert topic in p, f"{it['id']}: 후보 주제명 '{topic}' 누락"
        # gold는 코드만(주제명·괄호 없음)
        assert it["gold"].startswith("10수학")
        assert "(" not in it["gold"]


def test_dataset_extract_gold_is_list_others_str() -> None:
    """gold 형태: extract는 list, 나머지는 str (채점기 디스패치 전제)."""
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    for it in raw["items"]:
        if it["call_site"] == "extract":
            assert isinstance(it["gold"], list) and it["gold"]
        else:
            assert isinstance(it["gold"], str) and it["gold"]


def test_load_items_missing_file(qe: Any, tmp_path: Path) -> None:
    """없는 파일은 FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        qe.load_items(tmp_path / "missing.json")


# ──────────────────────────────────────────────────────────────────────────
# 러너 — run_evaluation (가짜 클라이언트 주입)
# ──────────────────────────────────────────────────────────────────────────
def _mk_items(qe: Any) -> list[Any]:
    """소형 평가셋(카테고리당 1개) — 러너 흐름 검증용.

    각 prompt에 가짜 클라이언트가 매칭하는 부분문자열(개념을 쉼표로/정규화/단원
    코드/산술 문제)을 포함시켜, 응답 매핑이 의도대로 동작하게 한다.
    """
    return [
        _item(
            qe,
            id="CE1",
            call_site="extract",
            task_type="extract",
            prompt="개념을 쉼표로 나열하시오. 문제: (x+1)(x+2)",
            gold=["분배법칙"],
        ),
        _item(
            qe,
            id="TN1",
            call_site="translate",
            task_type="translate",
            prompt="정규화하시오. 학생 입력: 엑스 제곱 더하기 1",
            gold="x^2 + 1",
        ),
        _item(
            qe,
            id="CM1",
            call_site="match",
            task_type="match",
            prompt="단원 코드를 고르시오. 개념: 이차방정식",
            gold="10수학02",
        ),
        _item(
            qe,
            id="AR1",
            call_site=None,
            task_type="explain",
            prompt="다음 산술 문제의 답: 17 + 28",
            gold="45",
        ),
    ]


@pytest.mark.asyncio
async def test_run_evaluation_fast_keeps_when_both_perfect(qe: Any) -> None:
    """FAST·MID 둘 다 만점이면 전 호출지점 FAST 유지.

    이 테스트는 *결정 규칙*(둘 다 만점 → 유지)을 본다. extract 의미매칭은 별도 테스트
    (test_run_evaluation_extract_semantic_*)에서 검증하므로, 여기서는 --no-embed로
    정확매칭을 써 extract 응답(gold와 동일 표현)을 만점 처리한다(임베딩 픽스처 불필요).
    """
    # 모든 프롬프트에 정답을 주는 가짜 클라이언트(프롬프트 부분문자열로 매칭)
    client = FakeOllamaClient(
        responses={
            "개념을 쉼표로": "<ANSWER>분배법칙</ANSWER>",
            "정규화": "<ANSWER>x^2 + 1</ANSWER>",
            "단원 코드": "<ANSWER>10수학02</ANSWER>",
            "산술 문제": "<ANSWER>45</ANSWER>",
        }
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=_mk_items(qe),
        client=client,
        embed=qe.EmbedConfig(enabled=False),  # extract도 정확매칭(결정 규칙만 검증)
    )
    assert report.overall_keep_fast is True
    assert all(v.keep_fast for v in report.verdicts)
    # FAST·MID 각각 4항목 호출 → 총 8회
    assert len(client.calls) == 8
    # 보고서는 패밀리별 매트릭스를 기록한다(단일 fast/mid 모델 아님).
    assert report.matrix["nlp_fast"] == "nlp-fast"
    assert report.matrix["math_mid"] == "math-mid"


@pytest.mark.asyncio
async def test_run_evaluation_routes_by_family(qe: Any) -> None:
    """🎯 핵심: NLP 항목은 nlp-* 모델로, MATH 항목(산술)은 math-* 모델로 호출된다.

    실측 근본 결함(수학 모델이 NLP 작업에 부적합) 교정의 검증 — 각 항목이 *패밀리에
    맞는* (fast, mid) 모델로 라우팅되는지 가짜 클라이언트 calls로 확인한다.
    """
    client = FakeOllamaClient(default="<ANSWER>x</ANSWER>")
    report = await qe.run_evaluation(matrix=_matrix(qe), items=_mk_items(qe), client=client)

    # 프롬프트별로 어떤 모델들이 호출됐는지 수집(부분문자열 기준).
    def models_for(sub: str) -> set[str]:
        return {c["model"] for c in client.calls if sub in c["prompt"]}

    # extract/translate/match(NLP) → nlp-fast, nlp-mid 두 모델만
    assert models_for("개념을 쉼표로") == {"nlp-fast", "nlp-mid"}
    assert models_for("정규화") == {"nlp-fast", "nlp-mid"}
    assert models_for("단원 코드") == {"nlp-fast", "nlp-mid"}
    # 산술(MATH) → math-fast, math-mid 두 모델만 (수학 특화 모델로!)
    assert models_for("산술 문제") == {"math-fast", "math-mid"}

    # models_used에도 패밀리별 실제 모델이 기록된다.
    assert report.fast_result.models_used == {"nlp": "nlp-fast", "math": "math-fast"}
    assert report.mid_result.models_used == {"nlp": "nlp-mid", "math": "math-mid"}


@pytest.mark.asyncio
async def test_run_evaluation_promotes_when_fast_worse(qe: Any) -> None:
    """FAST는 translate를 틀리고 MID는 맞히면 → translate에서 MID 승급 권고.

    translate는 NLP 패밀리이므로 fast=nlp-fast, mid=nlp-mid 모델 키로 응답을 지정한다.
    """
    client = FakeOllamaClient(
        responses_by_model={
            # FAST(nlp-fast): translate 틀림(나머지 정답)
            ("nlp-fast", "개념을 쉼표로"): "<ANSWER>분배법칙</ANSWER>",
            ("nlp-fast", "정규화"): "<ANSWER>완전히 틀린 식</ANSWER>",
            ("nlp-fast", "단원 코드"): "<ANSWER>10수학02</ANSWER>",
            # MID(nlp-mid): 전부 정답
            ("nlp-mid", "개념을 쉼표로"): "<ANSWER>분배법칙</ANSWER>",
            ("nlp-mid", "정규화"): "<ANSWER>x^2 + 1</ANSWER>",
            ("nlp-mid", "단원 코드"): "<ANSWER>10수학02</ANSWER>",
            # 산술(MATH): fast·mid 모두 정답
            ("math-fast", "산술 문제"): "<ANSWER>45</ANSWER>",
            ("math-mid", "산술 문제"): "<ANSWER>45</ANSWER>",
        }
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=_mk_items(qe),
        client=client,
        embed=qe.EmbedConfig(enabled=False),  # 승급 규칙만 검증 — extract는 정확매칭
    )
    by_key = {v.call_site: v for v in report.verdicts}
    # translate: FAST 0% vs MID 100% → 승급
    assert by_key["translate"].keep_fast is False
    assert by_key["translate"].fast_accuracy == pytest.approx(0.0)
    assert by_key["translate"].mid_accuracy == pytest.approx(1.0)
    # 다른 호출지점은 둘 다 만점 → 유지
    assert by_key["extract"].keep_fast is True
    # 종합은 일부 승급이므로 False
    assert report.overall_keep_fast is False


@pytest.mark.asyncio
async def test_run_evaluation_call_error_scored_zero(qe: Any) -> None:
    """ollama 호출 실패가 'ERROR:' 문자열로 흡수되어 0점 처리(러너가 죽지 않음)."""
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>분배법칙</ANSWER>"},
        fail_substrings={"정규화"},  # translate 프롬프트만 실패
        default="<ANSWER>10수학02</ANSWER>",
    )
    items = [
        _item(
            qe,
            id="CE1",
            call_site="extract",
            task_type="extract",
            prompt="개념을 쉼표로 나열하시오.",
            gold=["분배법칙"],
        ),
        _item(
            qe,
            id="TN1",
            call_site="translate",
            task_type="translate",
            prompt="정규화하시오.",
            gold="x^2 + 1",
        ),
    ]
    # 호출 실패 흡수만 검증 — extract 대조군은 정확매칭(--no-embed)으로 만점 처리.
    report = await qe.run_evaluation(
        matrix=_matrix(qe), items=items, client=client, embed=qe.EmbedConfig(enabled=False)
    )
    # translate는 호출 실패 → 'ERROR:...' → exact_match 0 → 정확도 0
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["translate"].fast_accuracy == pytest.approx(0.0)
    # extract는 정상 응답으로 정답 → 정확도 1.0 (대조군)
    assert by_key["extract"].fast_accuracy == pytest.approx(1.0)
    # 호출 실패는 _call_once가 'ERROR:' 문자열로 흡수 → raw_response에 남고 0점.
    # (채점 자체는 예외가 아니므로 ItemScore.error는 None — 신호는 raw_response.)
    fast_translate = [s for s in report.fast_result.item_scores if s.call_site == "translate"]
    assert fast_translate and fast_translate[0].raw_response.startswith("ERROR:")
    assert fast_translate[0].correct is False


@pytest.mark.asyncio
async def test_run_evaluation_empty_items_raises(qe: Any) -> None:
    """빈 평가셋은 ValueError."""
    client = FakeOllamaClient()
    with pytest.raises(ValueError, match="평가 항목"):
        await qe.run_evaluation(matrix=_matrix(qe), items=[], client=client)


@pytest.mark.asyncio
async def test_run_evaluation_passes_num_predict_and_temperature(qe: Any) -> None:
    """num_predict와 temperature=0(결정성)이 generate options로 전달되는지.

    temperature=0은 LLM 샘플링 비결정성을 제거해 재현 가능한 측정을 만든다.
    """
    client = FakeOllamaClient(default="<ANSWER>45</ANSWER>")
    items = [_item(qe, id="AR1", call_site=None, gold="45")]
    await qe.run_evaluation(matrix=_matrix(qe), items=items, client=client, num_predict=99)
    assert client.calls[0]["options"] == {"num_predict": 99, "temperature": 0}


# ──────────────────────────────────────────────────────────────────────────
# 러너 — extract 의미매칭 통합 (03a §H 후속8)
# ──────────────────────────────────────────────────────────────────────────
def _extract_only_item(qe: Any) -> Any:
    """extract 단일 항목 — 모델이 gold와 *표현이 다른* 동의어를 답하도록 구성."""
    return _item(
        qe,
        id="CE1",
        call_site="extract",
        task_type="extract",
        prompt="개념을 쉼표로 나열하시오. 문제: (x+1)(x+2)",
        gold=["다항식의 곱셈"],
    )


@pytest.mark.asyncio
async def test_run_evaluation_extract_semantic_match(qe: Any) -> None:
    """🎯 핵심: extract가 임베딩 의미매칭으로 채점된다.

    모델이 '다항식 전개'(gold '다항식의 곱셈'과 표현 다름)를 답해도, 동의어 임베딩
    (고 cosine)으로 매칭되어 F1=1.0·correct=True가 된다. 정확매칭이라면 0점이었을 케이스.
    embed_calls로 임베딩이 호출됐는지, grader가 set_f1_semantic인지 확인한다.
    """
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식 전개</ANSWER>"},
        embeddings={"다항식의곱셈": [1.0, 0.0], "다항식전개": [0.99, 0.14]},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
        embed=qe.EmbedConfig(enabled=True, model="bge-m3", threshold=0.6),
    )
    # extract 채점기가 의미매칭으로 기록된다(폴백 아님).
    assert report.extract_grader_fast == qe.GRADER_SET_F1_SEMANTIC
    assert report.extract_grader_mid == qe.GRADER_SET_F1_SEMANTIC
    assert report.embed_enabled is True
    assert report.embed_model == "bge-m3"
    assert report.embed_threshold == pytest.approx(0.6)
    # extract 항목이 의미매칭으로 만점 처리(정확매칭이면 0이었을 표현 차이).
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["extract"].fast_accuracy == pytest.approx(1.0)
    # extract item_score의 grader가 set_f1_semantic.
    fast_extract = [s for s in report.fast_result.item_scores if s.call_site == "extract"]
    assert fast_extract and fast_extract[0].grader == qe.GRADER_SET_F1_SEMANTIC
    # 임베딩이 실제로 호출됐고, 입력에 정규화된 개념(곱셈·전개)이 들어갔다.
    assert client.embed_calls
    embedded = set(client.embed_calls[0]["input"])
    assert "다항식의곱셈" in embedded and "다항식전개" in embedded
    assert client.embed_calls[0]["model"] == "bge-m3"


@pytest.mark.asyncio
async def test_run_evaluation_extract_semantic_unrelated_zero(qe: Any) -> None:
    """의미매칭이어도 무관 개념(저 cosine)은 미매칭 → extract 0점(거짓 양성 방지)."""
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>완전히 무관한 개념</ANSWER>"},
        embeddings={"다항식의곱셈": [1.0, 0.0], "완전히무관한개념": [0.0, 1.0]},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
    )
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["extract"].fast_accuracy == pytest.approx(0.0)
    assert report.extract_grader_fast == qe.GRADER_SET_F1_SEMANTIC  # 채점은 의미매칭 경로


@pytest.mark.asyncio
async def test_run_evaluation_no_embed_falls_back_to_exact(qe: Any) -> None:
    """--no-embed(embed.enabled=False): extract도 정확매칭(set_f1)으로 채점, 임베딩 미호출.

    동의어를 답해도 정확매칭이라 불일치 → 0점. embed_calls가 비어 있어야 한다.
    """
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식 전개</ANSWER>"},
        embeddings={"다항식의곱셈": [1.0, 0.0], "다항식전개": [0.99, 0.14]},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
        embed=qe.EmbedConfig(enabled=False),
    )
    assert report.embed_enabled is False
    assert report.extract_grader_fast == qe.GRADER_SET_F1  # 폴백(정확매칭)
    assert report.extract_grader_mid == qe.GRADER_SET_F1
    # 정확매칭이라 동의어는 불일치 → 0점.
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["extract"].fast_accuracy == pytest.approx(0.0)
    # 임베딩은 아예 호출되지 않음.
    assert client.embed_calls == []
    # extract item_score의 grader도 정확매칭.
    fast_extract = [s for s in report.fast_result.item_scores if s.call_site == "extract"]
    assert fast_extract and fast_extract[0].grader == qe.GRADER_SET_F1


@pytest.mark.asyncio
async def test_run_evaluation_embed_failure_falls_back_to_exact(qe: Any) -> None:
    """임베딩 호출 실패(embed_fails) 시 extract가 정확매칭으로 폴백(측정 중단 방지).

    enabled=True지만 embed가 RuntimeError → _embed_concepts가 None → grade_item(정확)
    으로 채점. 동의어를 답해도 0점이 되고, extract_grader는 set_f1(폴백)로 기록된다.
    """
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식 전개</ANSWER>"},
        embeddings={"다항식의곱셈": [1.0, 0.0], "다항식전개": [0.99, 0.14]},
        embed_fails=True,
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
    )
    assert report.extract_grader_fast == qe.GRADER_SET_F1  # 임베딩 실패 → 폴백
    # 임베딩을 *시도*는 했다(실패).
    assert client.embed_calls
    # 폴백 정확매칭이라 동의어 불일치 → 0점.
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["extract"].fast_accuracy == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_run_evaluation_embed_missing_method_falls_back(qe: Any) -> None:
    """embed 메서드가 없는 구형 클라이언트(AttributeError) → 정확매칭 폴백."""
    client = _NoEmbedClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식의 곱셈</ANSWER>"},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
    )
    assert report.extract_grader_fast == qe.GRADER_SET_F1  # 폴백
    # 정확매칭이라 동일 표현이면 매칭됨(이 케이스는 모델이 gold와 같은 표현을 답함).
    by_key = {v.call_site: v for v in report.verdicts}
    assert by_key["extract"].fast_accuracy == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_run_evaluation_embed_response_length_mismatch_falls_back(qe: Any) -> None:
    """embed 응답 개수가 입력과 안 맞으면(신뢰 불가) 정확매칭 폴백."""

    class _BadLenClient(FakeOllamaClient):
        async def embed(
            self,
            model: str,
            input: list[str],  # noqa: A002 — 시그니처 보존
        ) -> dict[str, Any]:
            self.embed_calls.append({"model": model, "input": list(input)})
            # 입력보다 적은 벡터를 돌려 길이 불일치 유발.
            return {"embeddings": [[1.0, 0.0]]}

    client = _BadLenClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식의 곱셈, 인수분해</ANSWER>"},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[
            _item(
                qe,
                id="CE1",
                call_site="extract",
                task_type="extract",
                prompt="개념을 쉼표로 나열하시오.",
                gold=["다항식의 곱셈", "인수분해"],
            )
        ],
        client=client,
    )
    assert report.extract_grader_fast == qe.GRADER_SET_F1  # 길이 불일치 → 폴백


@pytest.mark.asyncio
async def test_run_evaluation_default_embed_config(qe: Any) -> None:
    """embed 미지정 시 기본 EmbedConfig(활성·bge-m3·0.6)가 쓰인다."""
    client = FakeOllamaClient(
        responses={"개념을 쉼표로": "<ANSWER>다항식의 곱셈</ANSWER>"},
        embeddings={"다항식의곱셈": [1.0, 0.0]},
    )
    report = await qe.run_evaluation(
        matrix=_matrix(qe),
        items=[_extract_only_item(qe)],
        client=client,
    )
    assert report.embed_enabled is True
    assert report.embed_model == qe.DEFAULT_EMBED_MODEL == "bge-m3"
    assert report.embed_threshold == pytest.approx(qe.DEFAULT_EMBED_THRESHOLD)


@pytest.mark.asyncio
async def test_run_evaluation_no_extract_items_grader_default(qe: Any) -> None:
    """extract 항목이 없으면 임베딩을 호출하지 않고 extract_grader는 기본 set_f1."""
    client = FakeOllamaClient(default="<ANSWER>45</ANSWER>")
    items = [_item(qe, id="AR1", call_site=None, gold="45")]
    report = await qe.run_evaluation(matrix=_matrix(qe), items=items, client=client)
    # extract 없음 → 임베딩 미호출, 폴백 식별자(set_f1).
    assert client.embed_calls == []
    assert report.extract_grader_fast == qe.GRADER_SET_F1


@pytest.mark.asyncio
async def test_run_evaluation_extract_empty_concept_pool(qe: Any) -> None:
    """extract 개념 풀이 비면(파싱·gold 모두 빈 집합) 임베딩 호출을 생략하고 빈 맵으로 채점.

    gold=[](빈 집합)이고 모델도 빈 답이면 unique_concepts가 비어 _embed_concepts가
    빈 맵({})을 돌린다(None 아님 → 의미매칭 경로 유지). 빈 집합 규약으로 F1=1.0.
    """
    client = FakeOllamaClient(responses={"개념을 쉼표로": "<ANSWER></ANSWER>"})
    item = _item(
        qe,
        id="CE1",
        call_site="extract",
        task_type="extract",
        prompt="개념을 쉼표로 나열하시오.",
        gold=[],
    )
    report = await qe.run_evaluation(matrix=_matrix(qe), items=[item], client=client)
    # 개념 풀이 비어 임베딩은 호출되지 않는다(빈 맵 즉시 반환).
    assert client.embed_calls == []
    # 의미매칭 경로(빈 맵)로 채점됨 — 폴백 아님.
    assert report.extract_grader_fast == qe.GRADER_SET_F1_SEMANTIC
    by_key = {v.call_site: v for v in report.verdicts}
    # 빈 집합 vs 빈 집합 → F1=1.0(set_f1_semantic 빈 엣지 규약).
    assert by_key["extract"].fast_accuracy == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────
# report 직렬화 / detect_machine
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_report_to_dict_is_json_serializable(qe: Any) -> None:
    """report_to_dict 출력이 json.dumps 가능해야 함(패밀리별 매트릭스 포함)."""
    client = FakeOllamaClient(default="<ANSWER>45</ANSWER>")
    items = [_item(qe, id="AR1", call_site=None, gold="45")]
    report = await qe.run_evaluation(matrix=_matrix(qe), items=items, client=client)
    d = qe.report_to_dict(report)
    s = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(s)
    # 단일 fast/mid 모델 대신 패밀리별 매트릭스 4종을 기록한다.
    assert parsed["matrix"]["math_fast"] == "math-fast"
    assert parsed["matrix"]["nlp_mid"] == "nlp-mid"
    assert isinstance(parsed["verdicts"], list)
    assert "overall_keep_fast" in parsed
    assert isinstance(parsed["fast_result"]["item_scores"], list)
    # models_used도 직렬화된다(패밀리별 실제 모델).
    assert parsed["fast_result"]["models_used"]["math"] == "math-fast"
    # extract 의미매칭 메타데이터도 직렬화된다(03a §H 후속8).
    assert parsed["embed_enabled"] is True
    assert parsed["embed_model"] == qe.DEFAULT_EMBED_MODEL
    assert parsed["embed_threshold"] == pytest.approx(qe.DEFAULT_EMBED_THRESHOLD)
    assert "extract_grader_fast" in parsed
    assert "extract_grader_mid" in parsed


def test_detect_machine_has_platform(qe: Any) -> None:
    """machine 정보에 platform·python_version 포함."""
    info = qe.detect_machine()
    assert "platform" in info
    assert "python_version" in info


def test_build_default_client_uses_importlib(qe: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_default_client가 importlib로 ollama를 로드해 AsyncClient를 만든다.

    실제 ollama 없이 importlib.import_module를 가짜 모듈로 교체해 성공 경로
    (호스트 전달 + Protocol 캐스팅)를 검증한다.
    """
    import importlib
    import types

    captured: dict[str, Any] = {}

    class _FakeAsyncClient:
        def __init__(self, host: str) -> None:
            captured["host"] = host

        async def generate(
            self,
            model: str,
            prompt: str,
            stream: bool = False,
            options: dict[str, Any] | None = None,
        ) -> dict[str, Any]:  # pragma: no cover — 호출 안 함(생성만 검증)
            return {"response": ""}

    fake_module = types.SimpleNamespace(AsyncClient=_FakeAsyncClient)

    def _fake_import(name: str) -> Any:
        assert name == "ollama"
        return fake_module

    monkeypatch.setattr(importlib, "import_module", _fake_import)
    client = qe._build_default_client("http://example:11434")
    assert isinstance(client, _FakeAsyncClient)
    assert captured["host"] == "http://example:11434"


# ──────────────────────────────────────────────────────────────────────────
# main() 엔트리 (출력 파일 생성까지) — 동기 함수
# main() 내부에서 asyncio.run()을 호출하므로 이 그룹은 *동기* 함수.
# ──────────────────────────────────────────────────────────────────────────
def test_main_writes_output_and_returns_zero(
    qe: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """main()이 결과 JSON을 쓰고, 전부 FAST 유지면 종료 코드 0.

    실제 평가셋(fast_tier_eval.json)을 쓰되, _build_default_client를 모킹해
    모든 프롬프트에 정답을 반환하게 한다(FAST·MID 동일 → 전 호출지점 유지).
    extract 의미매칭은 별도 테스트에서 검증하므로, 여기서는 --no-embed로 정확매칭을
    써 main 흐름·출력 파일·종료 코드만 검증한다(임베딩 픽스처 불필요).
    """
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    # 각 항목 id → 정답 응답 매핑(프롬프트 전체를 키로 쓰는 가짜 클라이언트).
    # 실측 계약 형식('<ANSWER>...</ANSWER>')으로 응답해 1차 추출 경로를 그대로 탄다.
    prompt_to_answer: dict[str, str] = {}
    for it in raw["items"]:
        gold = it["gold"]
        if isinstance(gold, list):
            ans = ", ".join(gold)
        else:
            ans = str(gold)
        prompt_to_answer[it["prompt"]] = f"풀이 생략.\n<ANSWER>{ans}</ANSWER>"

    monkeypatch.setattr(
        qe,
        "_build_default_client",
        lambda host: FakeOllamaClient(responses=prompt_to_answer),
    )

    out_file = tmp_path / "qeval_out.json"
    rc = qe.main(
        [
            "--math-fast",
            "mf",
            "--math-mid",
            "mm",
            "--nlp-fast",
            "nf",
            "--nlp-mid",
            "nm",
            "--samples",
            str(_SAMPLES_PATH),
            "--out",
            str(out_file),
            "--no-embed",  # extract 정확매칭(main 흐름·출력만 검증)
        ]
    )
    assert rc == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["overall_keep_fast"] is True
    # 패밀리별 매트릭스가 CLI 인자대로 기록된다.
    assert data["matrix"]["math_fast"] == "mf"
    assert data["matrix"]["nlp_fast"] == "nf"
    # --no-embed가 보고서에 반영된다(extract 정확매칭 폴백 기록).
    assert data["embed_enabled"] is False
    assert data["extract_grader_fast"] == qe.GRADER_SET_F1


def test_main_embed_flags_flow_returns_zero(
    qe: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--embed-model/--embed-threshold가 EmbedConfig로 전달되고 의미매칭으로 채점된다.

    모델이 gold를 그대로 답하고(자기 자신과 cosine=1.0), embed가 모든 개념에 비영
    벡터를 돌려 의미매칭이 성립 → 전 호출지점 만점 → rc=0. 보고서에 임베딩 설정과
    extract=의미매칭 채점이 기록되는지 확인한다.
    """
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    prompt_to_answer: dict[str, str] = {}
    for it in raw["items"]:
        gold = it["gold"]
        ans = ", ".join(gold) if isinstance(gold, list) else str(gold)
        prompt_to_answer[it["prompt"]] = f"풀이 생략.\n<ANSWER>{ans}</ANSWER>"

    class _ConstEmbedClient(FakeOllamaClient):
        """모든 개념에 동일 비영 벡터를 돌린다(verbatim 답이라 자기매칭 1.0)."""

        async def embed(
            self,
            model: str,
            input: list[str],  # noqa: A002 — 시그니처 보존
        ) -> dict[str, Any]:
            self.embed_calls.append({"model": model, "input": list(input)})
            return {"embeddings": [[1.0, 0.0] for _ in input]}

    monkeypatch.setattr(
        qe,
        "_build_default_client",
        lambda host: _ConstEmbedClient(responses=prompt_to_answer),
    )
    out_file = tmp_path / "qeval_embed.json"
    rc = qe.main(
        [
            "--nlp-fast",
            "nf",
            "--nlp-mid",
            "nm",
            "--samples",
            str(_SAMPLES_PATH),
            "--out",
            str(out_file),
            "--embed-model",
            "my-embed",
            "--embed-threshold",
            "0.5",
        ]
    )
    assert rc == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["embed_enabled"] is True
    assert data["embed_model"] == "my-embed"
    assert data["embed_threshold"] == pytest.approx(0.5)
    # extract가 의미매칭으로 채점됐다(폴백 아님).
    assert data["extract_grader_fast"] == qe.GRADER_SET_F1_SEMANTIC
    assert data["overall_keep_fast"] is True


def test_main_returns_one_when_promotion_recommended(
    qe: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FAST가 전부 틀리고 MID가 전부 맞으면 종료 코드 1(승급 권고).

    두 패밀리의 fast를 동일 이름 'f', mid를 동일 이름 'm'으로 두어 모델별 응답을
    한 쌍으로 지정한다(패밀리 라우팅은 다른 테스트에서 검증).
    """
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    correct: dict[tuple[str, str], str] = {}
    for it in raw["items"]:
        gold = it["gold"]
        ans = ", ".join(gold) if isinstance(gold, list) else str(gold)
        # MID는 정답('<ANSWER>...</ANSWER>'), FAST는 오답
        correct[("m", it["prompt"])] = f"<ANSWER>{ans}</ANSWER>"
        correct[("f", it["prompt"])] = "<ANSWER>절대로아닌오답xyz</ANSWER>"

    monkeypatch.setattr(
        qe,
        "_build_default_client",
        lambda host: FakeOllamaClient(responses_by_model=correct),
    )
    out_file = tmp_path / "qeval_fail.json"
    rc = qe.main(
        [
            "--math-fast",
            "f",
            "--nlp-fast",
            "f",
            "--math-mid",
            "m",
            "--nlp-mid",
            "m",
            "--samples",
            str(_SAMPLES_PATH),
            "--out",
            str(out_file),
        ]
    )
    assert rc == 1
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["overall_keep_fast"] is False


def test_main_missing_samples_returns_error(qe: Any, tmp_path: Path) -> None:
    """없는 평가셋 경로 → 종료 코드 2."""
    rc = qe.main(
        [
            "--math-fast",
            "f",
            "--nlp-fast",
            "n",
            "--samples",
            str(tmp_path / "missing.json"),
            "--out",
            str(tmp_path / "x.json"),
        ]
    )
    assert rc == 2


def test_main_custom_thresholds_flow(
    qe: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--delta/--abs-min 인자가 결정 규칙에 반영된다(엄격 하한으로 승급 유발).

    모든 응답을 정답으로 주되 abs_min을 1.0 초과로 올릴 수는 없으므로,
    여기서는 abs_min=1.0(만점만 통과)으로 두고 set_f1이 1.0이라 유지됨을 확인하는
    대신, 정답이지만 set_f1<1.0이 나오도록 잉여 개념을 섞어 하한 미달을 만든다.
    """
    raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    # extract 항목에 잉여 개념을 붙여 F1<1.0 유도, 나머지는 정답
    prompt_to_answer: dict[str, str] = {}
    for it in raw["items"]:
        gold = it["gold"]
        if isinstance(gold, list):
            prompt_to_answer[it["prompt"]] = "<ANSWER>" + ", ".join(gold) + ", 잉여개념</ANSWER>"
        else:
            prompt_to_answer[it["prompt"]] = f"<ANSWER>{gold}</ANSWER>"

    monkeypatch.setattr(
        qe,
        "_build_default_client",
        lambda host: FakeOllamaClient(responses=prompt_to_answer),
    )
    out_file = tmp_path / "qeval_thresh.json"
    rc = qe.main(
        [
            "--nlp-fast",
            "nf",
            "--nlp-mid",
            "nm",
            "--samples",
            str(_SAMPLES_PATH),
            "--out",
            str(out_file),
            "--abs-min",
            "1.0",  # 만점만 통과 → extract(F1<1.0)는 승급
        ]
    )
    # extract 정확도(correct=F1==1.0)는 0 → 하한 1.0 미달 → 승급 → rc=1
    assert rc == 1
    data = json.loads(out_file.read_text(encoding="utf-8"))
    by_key = {v["call_site"]: v for v in data["verdicts"]}
    assert by_key["extract"]["keep_fast"] is False


def test_main_empty_items_returns_error(qe: Any, tmp_path: Path) -> None:
    """items가 빈 평가셋 파일 → 종료 코드 2 (로드 후 비어있음 분기)."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"license": "CC0", "author": "t", "items": []}), encoding="utf-8")
    rc = qe.main(["--samples", str(empty), "--out", str(tmp_path / "x.json")])
    assert rc == 2


def test_main_absorbs_evaluation_exception(
    qe: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_evaluation이 예외를 던지면 main은 종료 코드 2로 흡수한다.

    _build_default_client가 정상이어도 평가 도중 예외가 나는 상황을 모사하기 위해
    run_evaluation 자체를 던지도록 모킹한다.
    """

    async def _boom(**_: Any) -> Any:
        raise RuntimeError("의도된 평가 실패")

    monkeypatch.setattr(qe, "run_evaluation", _boom)
    rc = qe.main(["--samples", str(_SAMPLES_PATH), "--out", str(tmp_path / "x.json")])
    assert rc == 2


def test_default_output_path_under_results(qe: Any) -> None:
    """_default_output_path가 results/ 아래 qeval_*.json 경로를 만든다."""
    p = qe._default_output_path()
    assert p.parent.name == "results"
    assert p.name.startswith("qeval_")
    assert p.suffix == ".json"
    assert p.parent.exists()  # mkdir(parents=True) 호출됨


def test_main_default_output_path_used(
    qe: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--out 미지정 시 _default_output_path가 쓰인다 (해당 분기 커버)."""
    monkeypatch.setattr(
        qe,
        "_build_default_client",
        lambda host: FakeOllamaClient(default="ANSWER: 0"),
    )
    target = tmp_path / "auto_qeval.json"
    monkeypatch.setattr(qe, "_default_output_path", lambda: target)
    # 작은 평가셋 파일 하나로 충분
    small = tmp_path / "small.json"
    small.write_text(
        json.dumps(
            {
                "license": "CC0",
                "author": "t",
                "items": [
                    {
                        "id": "AR1",
                        "call_site": None,
                        "task_type": "explain",
                        "difficulty": "easy",
                        "prompt": "답: 0",
                        "gold": "0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = qe.main(["--samples", str(small)])  # --out 없음
    assert rc in (0, 1)
    assert target.exists()
