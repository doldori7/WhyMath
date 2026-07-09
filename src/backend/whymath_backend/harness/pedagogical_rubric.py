"""교수학 평가 루브릭 — answer-leakage(정답 유출) 결정론 부정지표(순수).

배경: CLAUDE.md **최상위 교수학 금기**는 "학생이 막혔을 때 바로 정답 제공 금지"다. WH-1은
`wh1_loop._end_turn_utterance`의 **verdict 기반** 정답 억제 백스톱(오답·미검증 턴이면 정책 명시
발화를 버리고 소크라테스 발화로 파생)만 갖는다 — *발화 내용*이 실제로 정답 값을 흘리는지 판정하는
결정론 탐지기는 없다. SSM 스캔(`docs/standards/ssm_scan_2026-Q3.md` 게이트 큐 #12)이 이를
"교수학 평가 루브릭(answer-leakage 부정지표) → 즉시 우월성 계측·저위험"으로 명시한 후속이다.

본 모듈은 **튜터 발화가 정답을 유출하는지**를 응답·정답 값만으로 판정하는 순수·결정론 탐지기와
소형 교수학 루브릭을 낸다. verdict 억제(구조)와 상보하는 *내용* 방어축이며, 회귀 게이트로 최상위
금기를 코드 봉인한다. 라이브 LLM 키 불요(문자열 검사)·런타임 경로 무변경·순수(DB/파일 무관).

정직성 규약(`verify_answer` 미러): **판정 불가는 가짜 판정하지 않고 undecidable**로 둔다 — 너무
짧거나(≤1자) 모호한 정답은 오탐을 낼 수 있어 보수적으로 undecidable. 수치 정답은 단어 경계로만
매칭해 "3"이 "13"·"30"·"3.5"에 오탐 나지 않게 한다(오탐 금지 우선).
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "LeakageVerdict",
    "RubricScore",
    "detect_answer_leakage",
    "score_tutoring_response",
]

# 정답이 이보다 짧으면(정규화 후) 오탐 위험이 커 판정을 유보한다(보수·undecidable).
_MIN_DECIDABLE_LEN = 2

# 정규화 후에도 흔해서 우연 일치가 잦은 토큰 — 노출돼도 정답 유출로 단정 못 함(undecidable).
_AMBIGUOUS_TOKENS: frozenset[str] = frozenset(
    {"true", "false", "yes", "no", "참", "거짓", "없음", "정답", "해", "근"}
)

# 소크라테스 발문 신호 — 물음표 또는 학생에게 사고를 되묻는 발문어(발화 유형 판정용·최소 집합).
_SOCRATIC_MARKERS: tuple[str, ...] = (
    "?",
    "？",
    "무엇",
    "무슨",
    "왜",
    "어떻게",
    "어떤",
    "근거",
    "설명",
    "말해줄래",
    "볼까",
    "해볼래",
    "생각해",
)

# LaTeX 명령(백슬래시 워드) 제거용 — 값 매칭 전 마크업을 벗긴다.
_LATEX_COMMANDS = re.compile(r"\\[a-zA-Z]+")
# 구조 문자(수식 구분자·중괄호·공백) 제거용 — 표현 차이를 값 비교에서 흡수한다.
_STRUCTURAL_CHARS = re.compile(r"[$\\{}()\s,]")
# 순수 정수·소수 판정(부호 허용) — 수치 정답은 단어 경계 매칭 경로로 보낸다.
_NUMERIC = re.compile(r"-?\d+(?:\.\d+)?")


def _normalize(text: str) -> str:
    """정규화 — NFKC·소문자·LaTeX 명령·구조 문자 제거(표현 차이 흡수·순수).

    표현(마크업·공백·전각)이 아니라 *값*으로 비교하기 위한 canonicalization이다. 개념 무관하게
    문자열만 다루므로 그래프·DB를 건드리지 않는다.
    """
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _LATEX_COMMANDS.sub("", normalized)
    return _STRUCTURAL_CHARS.sub("", normalized)


class LeakageVerdict(str, Enum):
    """정답 유출 3-state — 확신 매치만 leaked·판정 불가는 undecidable(보수·가짜 판정 금지)."""

    leaked = "leaked"  # 응답에 정답 값이 확신 노출됨(최상위 금기 위반)
    clean = "clean"  # 정답 값 미노출(확신)
    undecidable = "undecidable"  # 판정 불가(짧음·모호·오탐 위험) — 유보


def detect_answer_leakage(response: str, answer: str) -> LeakageVerdict:
    """튜터 응답이 정답 값을 유출하는지 판정한다(순수·결정론·보수).

    정규화(NFKC·마크업/공백 제거·소문자) 후 정답 값이 응답에 노출됐는지 검사한다. 수치 정답은
    **단어 경계**로 매칭해 부분 숫자 오탐(“3”이 “13”·“3.5”)을 차단하고, **너무 짧거나(≤1자) 흔한
    정답**은 오탐 위험이 커 `undecidable`로 유보한다(오탐 금지 우선). 확신 매치만 `leaked`.
    """
    norm_answer = _normalize(answer)
    if len(norm_answer) < _MIN_DECIDABLE_LEN or norm_answer in _AMBIGUOUS_TOKENS:
        return LeakageVerdict.undecidable
    norm_response = _normalize(response)
    if _NUMERIC.fullmatch(norm_answer):
        # 수치는 단어 경계 매칭 — 앞뒤로 숫자·소수점이 붙으면 다른 수이므로 유출 아님.
        pattern = rf"(?<![\d.]){re.escape(norm_answer)}(?![\d.])"
        matched = re.search(pattern, norm_response) is not None
    else:
        matched = norm_answer in norm_response
    return LeakageVerdict.leaked if matched else LeakageVerdict.clean


class RubricScore(BaseModel):
    """튜터 발화 1건의 교수학 준거 채점 — 근거만 모으고 통과/실패만 낸다(reviewer 규약 톤)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool = Field(description="전 준거 통과 여부(정답 미유출 AND 소크라테스 발문 존재).")
    no_answer_leak: bool = Field(
        description="핵심 부정지표 — 정답 유출 없음(leaked가 아니면 통과·undecidable도 보수 통과)."
    )
    leakage: LeakageVerdict = Field(description="정답 유출 판정(leaked·clean·undecidable).")
    has_socratic_prompt: bool = Field(description="소크라테스 발문 신호(물음표·발문어) 존재 여부.")
    reasons: list[str] = Field(
        default_factory=list, description="판정 근거 누적(학생 비노출·조용한 실패 금지)."
    )


def _has_socratic_prompt(response: str) -> bool:
    """소크라테스 발문 신호 유무 — 물음표 또는 되묻는 발문어(정규화 없이 원문 검사)."""
    return any(marker in response for marker in _SOCRATIC_MARKERS)


def score_tutoring_response(response: str, *, answer: str) -> RubricScore:
    """튜터 발화를 결정론 교수학 준거로 채점한다(순수·판정 근거만).

    준거 소집합: ① **정답 미유출**(핵심 부정지표·`detect_answer_leakage`, undecidable은 보수 통과)
    ② 소크라테스 발문 존재. 두 준거를 모두 만족해야 `passed`. 근거 문자열을 남겨(조용한 실패 금지)
    회귀·검수에 그대로 쓴다.
    """
    leakage = detect_answer_leakage(response, answer)
    no_answer_leak = leakage is not LeakageVerdict.leaked
    has_socratic = _has_socratic_prompt(response)

    reasons: list[str] = []
    if leakage is LeakageVerdict.leaked:
        reasons.append("정답 값이 발화에 노출됨 — 최상위 교수학 금기 위반.")
    elif leakage is LeakageVerdict.undecidable:
        reasons.append("정답 유출 판정 불가(짧음·모호) — 보수적으로 미유출 처리.")
    else:
        reasons.append("정답 값 미노출(clean).")
    reasons.append("소크라테스 발문 신호 존재." if has_socratic else "소크라테스 발문 신호 없음.")

    return RubricScore(
        passed=no_answer_leak and has_socratic,
        no_answer_leak=no_answer_leak,
        leakage=leakage,
        has_socratic_prompt=has_socratic,
        reasons=reasons,
    )
