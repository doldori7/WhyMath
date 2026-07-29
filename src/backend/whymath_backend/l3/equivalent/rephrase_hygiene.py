"""rephrase 발문 위생 게이트 — LLM 발문 텍스트 결함의 결정론 검출(S3-12·순수·LLM 0).

S3-09 AI 검수(720문)가 rephrased 코퍼스에서 확정한 **발문 텍스트 결함 축**을 결정론 검사로
차단한다. rephrase의 기존 불변 봉인(`rephrase.classify_invariance_failure`)은 수치·정답·선지만
검사하고 발문 텍스트 품질 게이트가 없었다 — 그 공백으로 새어 들어온 결함 4류가 이 모듈의 표적:

  ① 비한글 스크립트 주입 — CJK 한자("두解")·가나("となる") 유니코드 범위. 수식·라틴 문자·통용
     기호는 수학 표기라 허용한다(따라서 "greater" 같은 라틴 영단어 주입은 이 축이 못 잡는다 —
     정직 한계·감사 폴백).
  ② 재서술 메타 라벨 누출 — "원 발문:"·"원판"·"재서술" 등 rephrase 과정 어휘가 발문에 노출.
  ③ 비표준 용어 — "원시방정식"·"다차방정식"·"원시적"(감사 확정 폐쇄 목록. '원시함수' 같은
     정상 용어를 다치지 않게 정확 문자열만 검사).
  ④ 요구-정답 정합 — 발문이 '방법/어떨까요'를 묻는데 정답은 값인 부정합(statement_mismatch).
     스켈레톤 원 발문은 값을 물으므로 '방법'·'어떨까요'의 등장 자체가 요구 이탈 신호다.
  ⑤ 조사 오류 — S3-12 josa 판별기(`tail_reading`)가 **결정 가능한** 토큰(수·수식 꼬리)에 한해
     조사(을/를·와/과·은/는·이/가·(으)로)의 받침 정합을 검사한다. 판별 불가 토큰은 침묵
     (오탐 0 우선 — 비문·어미 파손 등 비결정 축은 사람/감사 폴백).

발문 텍스트 결함은 결정론 교정이 불가하므로(LLM 재생성 없이는 고칠 수 없다) **탈락(제거)이
정본**이다 — 적용 CLI는 `harness.rephrased_corpus_hygiene`, rephrase 수용 게이트 배선은
`rephrase.classify_invariance_failure`의 ⑤축(REASON_QUESTION_HYGIENE).

7계층: L3 지역(동일 패키지 josa만 import·표준 라이브러리 외 의존 0·순수 함수).
"""

from __future__ import annotations

import re

from whymath_backend.l3.equivalent.josa import TailReading, tail_reading

__all__ = [
    "REASON_FOREIGN_SCRIPT",
    "REASON_JOSA_ERROR",
    "REASON_META_LABEL_LEAK",
    "REASON_NONSTANDARD_TERM",
    "REASON_REQUEST_ANSWER_MISMATCH",
    "question_hygiene_violations",
]

# 위반 사유 코드 — rephrase 실패 taxonomy(REASON_*)와 같은 어휘 체계(진단 온톨로지).
REASON_FOREIGN_SCRIPT = "FOREIGN_SCRIPT"
REASON_META_LABEL_LEAK = "META_LABEL_LEAK"
REASON_NONSTANDARD_TERM = "NONSTANDARD_TERM"
REASON_REQUEST_ANSWER_MISMATCH = "REQUEST_ANSWER_MISMATCH"
REASON_JOSA_ERROR = "JOSA_ERROR"

# ① 비한글 스크립트 — CJK 한자(기본·확장A·호환)·가나(히라가나·가타카나). 한글·라틴·수식 기호는
# 검사하지 않는다(허용 목록이 아니라 금지 범위 검사 — 오탐 0 지향).
_FOREIGN_SCRIPT_RE = re.compile(
    "["
    "一-鿿"  # CJK 통합 한자
    "㐀-䶿"  # CJK 확장 A
    "豈-﫿"  # CJK 호환 한자
    "぀-ゟ"  # 히라가나
    "゠-ヿ"  # 가타카나
    "]"
)

# ② 메타 라벨 — 재서술 과정 어휘의 발문 누출(감사 확정 실사례: '원 발문:'·'원판'·'재서술').
_META_LABELS: tuple[str, ...] = ("원 발문", "원판", "재서술")

# ③ 비표준 용어 — 감사 확정 폐쇄 목록(이차방정식을 '원시방정식'·'다차방정식'으로 오명명,
# '원시적으로' 무의미 수식·'원시 방정식' 띄어쓰기 변형 실측). '원시함수'(부정적분 정상 용어)는
# 다치지 않는 정확 문자열만.
_NONSTANDARD_TERMS: tuple[str, ...] = ("원시방정식", "원시 방정식", "다차방정식", "원시적")

# ④ 요구-정답 부정합 — 값을 묻는 스켈레톤 발문에 '방법'·'어떨까요'가 등장하면 요구가 값에서
# 절차/의견으로 이탈한 것(감사 확정: '구하는 방법'·'방법은 어떨까요' — 정답은 값이라 부정합).
_REQUEST_MISMATCH_RE = re.compile(r"방법|어떨까요")

# ⑤ 조사 검사 — 수·수식 토큰(라틴·숫자·수식 기호) 뒤의 조사만 본다. 한글 낱말 뒤 조사는
# 토큰 클래스가 배제한다(한국어 일반 문장 검사가 아니라 수식-조사 정합 검사 — 오탐 0 우선).
# 경계 규칙 둘: ① 토큰 시작은 문두·공백·한글 뒤여야 한다 — √·± 등 클래스 밖 기호에 이어지는
# 부분 토큰('√3/2'의 '3/2')을 잘라 읽으면 독법이 달라질 수 있어 침묵한다(부분 캡처 금지).
# ② lookahead로 조사 뒤가 공백·문장부호·끝일 때만 매치('이다'의 이, '는데'의 는 등 오인 차단).
_JOSA_TOKEN_RE = re.compile(
    r"(?:^|(?<=[\s가-힣]))([0-9A-Za-z½²³^*/().+\-|]+)\s*"
    r"(으로|로|과|와|을|를|은|는|이|가)(?=[\s.,!?)]|$)"
)


def _expected_josa(reading: TailReading, particle: str) -> str | None:
    """받침 사실(reading)에 맞는 올바른 조사 — particle이 속한 쌍 기준. 미지원 조사면 None."""
    batchim = reading.batchim
    if particle in ("을", "를"):
        return "을" if batchim else "를"
    if particle in ("과", "와"):
        return "과" if batchim else "와"
    if particle in ("은", "는"):
        return "은" if batchim else "는"
    if particle in ("이", "가"):
        return "이" if batchim else "가"
    if particle in ("으로", "로"):
        # ㄹ 받침 예외 — 받침 없음 또는 ㄹ 받침이면 '로', 그 외 받침이면 '으로'.
        return "로" if (not batchim or reading.rieul) else "으로"
    return None


def _josa_mismatches(text: str) -> list[str]:
    """수·수식 토큰 뒤 조사의 받침 부정합 목록 — 판별 가능(tail_reading≠None) 토큰만 판정."""
    found: list[str] = []
    for match in _JOSA_TOKEN_RE.finditer(text):
        token, particle = match.group(1), match.group(2)
        reading = tail_reading(token)
        if reading is None:
            continue  # 판별 불가 — 침묵(오탐 0 우선·정직 한계)
        expected = _expected_josa(reading, particle)
        if expected is not None and expected != particle:
            found.append(f"{token} {particle}→{expected}")
    return found


def question_hygiene_violations(question_text: str) -> tuple[str, ...]:
    """발문 1건의 위생 위반 사유 코드 튜플 — 비면 통과(순수·결정론).

    사유 코드는 검사 순서대로 담기며 중복 없이 한 축당 최대 1개다. 상세(어느 토큰/용어인지)는
    사유 코드 뒤에 `:` 구분으로 병기해 사람이 탈락 근거를 재검증할 수 있게 한다(정직 산출).
    """
    violations: list[str] = []
    foreign = _FOREIGN_SCRIPT_RE.findall(question_text)
    if foreign:
        violations.append(f"{REASON_FOREIGN_SCRIPT}:{''.join(sorted(set(foreign)))}")
    leaked = [label for label in _META_LABELS if label in question_text]
    if leaked:
        violations.append(f"{REASON_META_LABEL_LEAK}:{'·'.join(leaked)}")
    terms = [term for term in _NONSTANDARD_TERMS if term in question_text]
    if terms:
        violations.append(f"{REASON_NONSTANDARD_TERM}:{'·'.join(terms)}")
    mismatch = _REQUEST_MISMATCH_RE.search(question_text)
    if mismatch is not None:
        violations.append(f"{REASON_REQUEST_ANSWER_MISMATCH}:{mismatch.group(0)}")
    josa_errors = _josa_mismatches(question_text)
    if josa_errors:
        violations.append(f"{REASON_JOSA_ERROR}:{'·'.join(josa_errors)}")
    return tuple(violations)
