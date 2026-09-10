"""오개념 진단 — `docs/prompts/misconception_diagnosis.md` "매칭 알고리즘"(L60-70).

v1.1: 규칙 기반 substring 공출현(AND) + **표기 정규화**(NFKC+공백). 학생 풀이에서 각 catalog
항목의 `signals` 부분집합이 얼마나 매칭되는지로 confidence 계산. top-K 후보 반환.

v1.1 정교화(슬 101·`concept_graph_dataset_v1.md` §5.3): 매칭 직전 양변을 `_normalize`로
정규화해 공백·유니코드 표기 변이(`a² + b²`↔`a²+b²`, 위첨자 `²`↔`2`, 전각/반각)에 의한
*거짓음성*을 제거한다. `matched_signals`·confidence는 *원본 신호* 기준이라 UI·디버그 표시 불변.

v1.2 정교화(슬 102): substring AND를 넘어 **정규식 보조 탐지 경로**(`regex_signals`, OR)를
추가한다. 헤드라인 역량은 *거짓 항등식의 수치 대입* 탐지 — 학생이 `(3+4)²=3²+4²`,
`√((-3)²)=-3`, `(2+4)/2=4`처럼 *틀린 항등식에 수를 대입한 흔적*을 잡는다. substring은
기호식(`(a+b)²=a²+b²`)은 잡지만 학생이 *구체 수치로* 계산해버린 흔적은 못 잡던 한계(§5.3·슬
101에서 문서화)를 줄인다. 정규식은 *정규화된 텍스트*에 `re.search`로 검사한다.

수치 정규식은 기호 substring 케이스와 *겹치지 않게*(disjoint) 작성해 `matched_signals` 집합·
기존 substring-only confidence를 보존한다(예: distribution 정규식은 `(3+4)²=3²+4²` *숫자*만
매치, 기호 `(a+b)²=a²+b²`엔 매치되지 않음).

v1.5 정정(MISC-22): 정규식 매치 1건 = substring 신호 **전체**와 동등한 완결 증거로 가산한다 —
`min(1.0, matched/len(signals) + matched_regex_count)`(코드는 통분해 `numerator = matched +
matched_regex*len(signals)`로 구현). v1.2의 옛 식(`min(1.0, (substr+regex)/len(signals))`)은
정규식 매치를 substring 신호 *1개*와만 동등하게 쳐서, 정규식이 disjoint 역참조로 이미
substring AND 전체에 준하는 확정 증거임에도 확신도가 0.5(수치 신호 종류가 흔히 2개)에 갇혔다 —
그 결과 `factor-sign-flip`을 비롯한 4개 v1.2 시연 채널의 "수치 대입 탐지" 헤드라인 역량이 서빙
품질 게이트(0.65)에 전혀 못 미쳐 **한 번도 학생에게 도달하지 못했다**(작동 신호 없는 알고리즘
부착 — `anchor_detection_channel_eval` 실측·MISC-22). substring만으로의 기존 confidence
(1.0/0.5)는 불변 — 이 정정은 *정규식이 매치했을 때만* 영향을 준다.

v1.3 정밀화(슬 109·라이브 FP 교정): **짧은 영숫자 signal의 경계 매칭**. `"0"` 같은 숫자-only
signal과 `"b"` 같은 단일 ASCII 문자 signal은 plain substring으로 두면 *다른 토큰 내부*에
오매칭된다 — 실증된 라이브 결함: `"분모가 10인 분수를 약분했어요"`(완전히 올바른 진술)가
`'0'∈'10'`으로 division-by-zero **풀매칭(1.0) → COUNTEREXAMPLE 개입 발화**. v1.3은 이런
signal을 영숫자 경계 정규식(`(?<![0-9A-Za-z.])sig(?![0-9A-Za-z.])`)으로 매칭해 `10`·`0.5`·
`a₀`(NFKC→`a0`)·`ab` 내부 오매칭을 차단한다. 내용성 있는 signal(한글 형태소 `"곱"`·연산자
`"√"`·복합 토큰)은 기존 substring 유지. confidence 식·분모·반환 계약은 전부 불변 —
*매칭 정밀도만* 올린다(매칭이 줄어드는 방향이라 거짓양성 감소·거짓음성 추가 없음: 정당한
사용처는 비영숫자 이웃[한글 조사·등호·괄호·쉼표]이라 계속 매칭된다).

후속(범위 밖, doc 명시): ① 풀이 단계별 파싱(PRM 활용) ② 처음 틀린 단계 식별 ③ 임베딩
유사도 매칭(text-embedding-3-large 등) ④ LLM-judged 패턴 추출. ③④는 *의미·방향* 차원
한계(방향맹)의 정본 해법이고, *어휘* 차원 거짓양성(짧은 토큰 오매칭)은 v1.3이 직접 줄인다.
잔여: 부분매칭(0.5) 자체의 정밀도 한계(예: `'분모'` 단독 0.5)는 substring 설계의 알려진
트레이드오프 — semantic/judge 계층(슬104~108)이 그 자리다.

v1.6 정정(MISC-24): MISC-22가 5개 정규식 채널(factor-sign-flip 등)의 정규식-단독 매치를
게이트 도달로 정정한 부수효과로, `extremum-value-vs-point-confused`가 `f(x₀)=x₀`인 *우연의
일치* 정답(예: 극대점 x=2에서 극댓값도 2)에도 confidence 1.0을 내 확신 오진단 위험이 있음이
드러났다 — 실은 MISC-22 이전부터 있던 사실(그 정규식이 리터럴 '극댓값'을 포함해 substring이
항상 함께 발화). 이 항목은 오개념 발화 텍스트와 우연의 일치 정답 텍스트가 **글자 그대로
동일**해 정규식으로도 반박(`refuting_regex`)으로도 원리상 구별이 불가능하다.
`ambiguous_regex_signals` 필드(models.py)로 이 항목만 예외적으로 정규식 가산을 0으로 둬
confidence가 항상 substring 신호만으로 결정되게 한다(다른 5개 채널의 MISC-22 정정은 완전히
불변).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache

from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import (
    Misconception,
    MisconceptionMatch,
)

_DEFAULT_TOP_K = 3


# MISC-17: LaTeX 표기 접기 — OCR(`OcrResult.plain_latex`)·MathLive 산출물은 계약상 LaTeX라
# `(a+b)^2`·`a^{2}`·`\left(…\right)` 형태로 온다. NFKC는 `²`→`2`만 펴고 `^`·`{}`·크기 조정
# 표식은 남겨, 인식기의 *정상* 출력이 신호 2개 중 1개(0.5)만 맞아 게이트 ①(0.65)에서 탈락하던
# 실측 결함(PR #1034 Codex P1). `^`와 `{}`를 지우면 `a^{2}`·`a^2`·`a²` 모두 정규형 `a2`로 접힌다.
# 카탈로그 `signals`·`correct_form`에는 이 문자가 0건(2026-09-07 실측)이라 양변 정규화가 일관되고,
# `regex_signals`는 *정규형 텍스트*를 겨냥하므로 패턴 내부의 `[^0-9]` 같은 메타문자와는 무관하다.
# 분수(`\frac`)·곱셈 기호(`\cdot`) 등 다른 LaTeX 명령은 접지 않는다 — 신호가 그 형태를 쓰지 않아
# 필요가 실측되지 않았고, 과도한 접기는 거짓양성 축이 된다(필요 시 실측 후 확장).
_LATEX_FOLD = re.compile(r"\\left|\\right|[\^{}]")


def _normalize(text: str) -> str:
    """매칭용 표기 정규화 — NFKC 유니코드 정규화 + 모든 공백 제거 + LaTeX 표기 접기.

    학생 표기 변이를 흡수한다: `a² + b²`·`a²+b²`·`a 2 + b 2`·`a^2+b^2`·`a^{2}+b^{2}`가 모두
    같은 정규형 `a2+b2`로, 위첨자/아래첨자·전각 숫자도 일반 숫자로(NFKC). 비교에만 쓰며,
    반환되는 신호 문자열은 원본을 유지한다(표시·텔레메트리 일관성).

    참고: NFKC는 위첨자 `²`→`2`로 펴므로 정규식은 *지수 표기를 평문으로* 작성한다
    (예: `(3+4)²=3²+4²`의 정규형은 `(3+4)2=32+42`). 정규식 패턴은 이 정규형을 겨냥한다.
    LaTeX 접기(`_LATEX_FOLD`)로 `(3+4)^2=3^2+4^2`도 같은 정규형이 된다(MISC-17).
    """
    return _LATEX_FOLD.sub("", "".join(unicodedata.normalize("NFKC", text).split()))


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    """정규식 컴파일 캐시 — 카탈로그 패턴은 고정·소수라 무한정 증가하지 않는다."""
    return re.compile(pattern)


def _signal_hit(signal: str, norm_text: str) -> bool:
    """단일 signal 매칭 — v1.3: 짧은 영숫자 signal은 경계 검사, 그 외 substring.

    숫자-only(`"0"`·`"180"`)·단일 ASCII 문자(`"b"`) signal은 다른 토큰 내부에 오매칭된다
    (`'0'∈'10'/'0.5'/'a₀'`·`'b'∈'ab'` — 올바른 진술에 풀매칭→개입 발화한 실증 라이브 결함).
    이런 signal만 영숫자·소수점 경계 정규식으로 매칭하고, 내용성 있는 signal(한글 형태소·
    연산자 기호·복합 토큰)은 기존 substring을 유지한다. 비교는 양변 정규화(`_normalize`) 후.
    """
    norm_sig = _normalize(signal)
    if norm_sig.isdigit() or (len(norm_sig) == 1 and norm_sig.isascii() and norm_sig.isalpha()):
        # 경계: 영숫자·'.'가 이웃이면 다른 수/식별자의 일부로 보고 미매칭. 정당한 사용처
        # (한글 조사·`=`·`≠`·괄호·쉼표 이웃)는 전부 비영숫자라 계속 매칭된다.
        pattern = rf"(?<![0-9A-Za-z.]){re.escape(norm_sig)}(?![0-9A-Za-z.])"
        return _compile(pattern).search(norm_text) is not None
    return norm_sig in norm_text


def is_refuted(misconception: Misconception, text: str) -> bool:
    """이 텍스트가 그 오개념을 **반박**하는가 — 반박 조건의 단일 판정처(MISC-23).

    `_match_one`(substring 경로)과 **의미(임베딩) 경로**가 같이 쓴다. 한쪽에만 걸면 다른 쪽이
    같은 오개념을 되살린다 — `combine_diagnoses`는 substring이 뺀 id를 "semantic-only"로 보고
    아래에 붙이므로, substring에서만 거부하면 semantic 후보가 그대로 노출된다(PR #1039 Codex P2).

    `combine_diagnoses`가 아니라 여기에 두는 이유: 그 함수는 원문 텍스트를 받지 않는 순수
    결합기(두 리스트 재배치·변형 0)이고, 반박은 *텍스트에 대한 판정*이라 축이 다르다.
    """
    norm_text = _normalize(text)
    return any(_compile(rx).search(norm_text) is not None for rx in misconception.refuting_regex)


def reject_refuted(candidates: Sequence[MisconceptionMatch], text: str) -> list[MisconceptionMatch]:
    """후보 목록에서 반박된 것을 제거 — 경로와 무관한 **공통 출구**용.

    substring·의미 어느 경로로 들어왔든 여기를 지나면 반박된 후보는 남지 않는다.
    """
    return [m for m in candidates if not is_refuted(m.misconception, text)]


def _match_one(misconception: Misconception, text: str) -> MisconceptionMatch | None:
    """단일 misconception 매칭 — substring 부분집합(정규형 비교) + 정규식 보조 경로(OR).

    confidence = min(1.0, substr매치/len(signals) + regex매치). 둘 다 0이면 None.
    v1.3: 개별 signal 매칭은 `_signal_hit`(짧은 영숫자 signal 경계 검사) 경유.

    MISC-22 정정(v1.5) — 정규식 매치 1건은 *전체 신호 AND*와 동등한 완결 증거로 가산한다
    (분자에 `len(signals)`를 더해 단독으로도 상한 1.0을 채운다). 카탈로그의 모든 `regex_signals`는
    명명그룹 역참조로 좌·우변이 글자 그대로 일치할 때만 매치하도록 설계돼 정답·기호식과
    *disjoint*가 이미 항목별로 증명돼 있다(각 항목 주석 참조) — 즉 규격상 "부분 신호"가 아니라
    substring AND 전체에 준하는 확정적 단서다. v1.2의 옛 가산식(정규식 매치를 substring 신호 1개와
    동등하게 취급)은 이 disjoint 보증을 과소평가해 `factor-sign-flip`(수치 입력에서 상징적
    substring이 구조적으로 0건)을 confidence 0.5에 가둬 서빙 품질 게이트(0.65)에 영원히 못 미치게
    했다(작동 신호 없는 알고리즘 부착) — 같은 결함이 `distribution-over-power`·
    `square-root-positivity`·`fraction-cancellation`·`log-distribution`의 수치 대입 탐지에도
    동일하게 있었다(실측: 4종 전부 conf 0.5). `extremum-value-vs-point-confused`는 회귀 없음 —
    그 정규식 패턴 자체가 substring 신호 `극댓값`을 리터럴로 포함해 regex 매치 시 substring도 항상
    함께 매치하므로 옛 식으로도 이미 conf 1.0이었다(실측 확인).

    MISC-23: `refuting_regex`가 하나라도 매치되면 **신호를 세기 전에** None이다. 공출현 AND는
    오개념을 *저지른* 풀이와 그것을 *설명한* 정답을 구별하지 못하므로, 반박 축이 없으면 정답에
    확신 오진단이 나간다(실측: conf 1.0으로 품질 게이트 통과).

    MISC-24: `ambiguous_regex_signals=True`인 항목은 정규식 매치가 `matched_regex_signals`
    (텔레메트리)에는 담기되 confidence 가산에는 기여하지 않는다(numerator에서 배제) —
    `extremum-value-vs-point-confused`처럼 오개념 발화와 우연의 일치 정답이 텍스트상 완전히
    동일해(`refuting_regex`로 반박할 대상 자체가 없음) 정규식 매치 자체가 확정 증거가 될 수
    없는 항목을 위한 것이다(models.py 필드 docstring 근거).
    """
    norm_text = _normalize(text)
    # 반박 조건 먼저(MISC-23) — 양성 단편을 세기 *전에* 판정한다. 나중에 감점하는 형태였다면
    # "얼마나 깎을 것인가"라는 답 없는 눈금 문제가 생기고, 깎인 후보가 하류에 약한 증거로 남는다.
    if is_refuted(misconception, text):
        return None
    matched = tuple(s for s in misconception.signals if _signal_hit(s, norm_text))
    matched_regex = tuple(
        rs for rs in misconception.regex_signals if _compile(rs).search(norm_text) is not None
    )
    if not matched and not matched_regex:
        return None
    # MISC-22(v1.5): 정규식 매치 1건 = substring 신호 전체(len(signals))와 동등한 완결 증거로
    # 가산한다 — disjoint 역참조 정규식은 substring AND 전체에 준하는 확정적 단서이기 때문이다
    # (위 docstring 근거). 분모는 substring signals 개수(>=1, 카탈로그 불변식) 유지.
    # MISC-24: 단, `ambiguous_regex_signals`가 선 항목은 정규식 가산을 0으로 둔다 — 매치된
    # 정규식이 확정 증거가 아니라 원리상 반박 불가능한 모호 신호이기 때문이다(models.py 근거).
    if misconception.ambiguous_regex_signals:
        numerator = len(matched)
    else:
        numerator = len(matched) + len(matched_regex) * len(misconception.signals)
    if numerator == 0:
        # matched_regex만 있고(ambiguous 항목이라 가산 0) matched는 비었다면 세울 증거가 없다.
        return None
    confidence = min(1.0, numerator / len(misconception.signals))
    return MisconceptionMatch(
        misconception=misconception,
        confidence=confidence,
        matched_signals=matched,
        matched_regex_signals=matched_regex,
    )


def correct_form_present(misconception: Misconception, text: str) -> bool:
    """학생 풀이에 오개념의 *정정 형태*(`correct_form`)가 나타나는지 — 정밀 반박 신호.

    `signals`와 *동일한* `_normalize`(NFKC+공백제거)로 양변을 정규화해 `correct_form`의 정규형이
    텍스트 정규형의 *부분문자열*인지 검사한다(표기 변이 흡수·신호 경로와 일관). `signals`의
    공출현(AND)·짧은 영숫자 경계 로직과 달리, 정정은 *식별 형태 1개*의 출현만으로 충분한 강한
    신호라 단일 substring 포함만 본다. `correct_form`이 None이거나 정규형이 빈 문자열(전체 매칭
    방지)이면 False(탐지 비활성·기존 약한 반박 동작 불변).

    이 함수가 True면 호출자(coach)는 그 오개념을 *강하게*(−1·강한 가중) 반박한다 — 도구 검증된
    풀이에 정정 형태가 실재하면 "학생이 그 오개념을 가졌다"는 예측과 *정밀하게* 모순되기 때문이다.
    """
    cf = misconception.correct_form
    if not cf:
        return False
    norm_cf = _normalize(cf)
    if not norm_cf:
        return False
    return norm_cf in _normalize(text)


def diagnose(student_solution: str, *, top_k: int = _DEFAULT_TOP_K) -> list[MisconceptionMatch]:
    """학생 풀이에서 오개념 후보 top-K를 confidence 내림차순으로 반환한다.

    매칭 0이면 빈 리스트. 동률은 catalog 순서(=doc 명시 순서) 안정 유지.
    """
    matches: list[MisconceptionMatch] = []
    for m in CATALOG:
        result = _match_one(m, student_solution)
        if result is not None:
            matches.append(result)
    matches.sort(key=lambda x: x.confidence, reverse=True)
    return matches[:top_k]
