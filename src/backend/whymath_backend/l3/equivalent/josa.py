"""한국어 조사 받침 판별 헬퍼 — 동등문제 생성기 계통 결함 수정(S2-08·결정론·순수).

동등문제 생성기(S2-o 계열)는 발문·풀이 템플릿에서 조사를 **선행 수사의 받침과 무관하게 하드
코딩**해 왔다("0와 4"·"13 를 풀어"·"밑 6를"·"−3와"). 이 모듈은 선행 값(정수·한글 단어·일부
문자열)의 받침 유무를 판별해 올바른 조사를 고른다.

핵심 원칙 — **수(數)의 받침은 "표기 글자"가 아니라 "한국어 읽기(한자어·Sino-Korean)의 마지막
음절"이 지배**한다. 수학 수량은 한자어로 읽으므로(예 13=십삼·100=백), 정수의 받침은 아래
일의 자리 읽기 표 + 0으로 끝나는 자리(십·백·천·영)로 결정한다. 표기 마지막 숫자(glyph)로
판별하면 틀린다(예 13의 끝 글자 '3'=삼→받침 有가 맞지만, 10의 끝 글자 '0'은 '영'이 아니라
'십'이 지배 → 둘 다 받침 有라 우연히 맞을 뿐, 20/100은 glyph만으로 오판).

7계층: L3 지역(스켈레톤 생성기 전용 헬퍼). import는 표준 라이브러리만 — 상위 계층 참조 0(순수
함수). 표현이 아니라 값의 언어적 사실만 다룬다.
"""

from __future__ import annotations

__all__ = [
    "eul_reul",
    "eun_neun",
    "euro_ro",
    "has_batchim_hangul",
    "has_batchim_number",
    "has_batchim_text",
    "i_ga",
    "josa",
    "wa_gwa",
]

# 일의 자리 한자어 읽기의 받침 유무(有=True) — 0=영(ㅇ)·1=일(ㄹ)·2=이(無)·3=삼(ㅁ)·4=사(無)·
# 5=오(無)·6=육(ㄱ)·7=칠(ㄹ)·8=팔(ㄹ)·9=구(無). 이 표가 모든 정수 받침 판별의 단일 진실 원천.
_ONES_DIGIT_BATCHIM: dict[int, bool] = {
    0: True,
    1: True,
    2: False,
    3: True,
    4: False,
    5: False,
    6: True,
    7: True,
    8: True,
    9: False,
}

# 한글 음절 유니코드 블록 시작(가)·종성(받침) 개수 28(0=받침 없음).
_HANGUL_BASE = 0xAC00
_HANGUL_END = 0xD7A3
_JONGSEONG_COUNT = 28

# 'ㄹ' 받침 종성 인덱스 — (으)로 조사는 'ㄹ' 받침일 때 '(으)로'가 아니라 '로'를 쓴다(예외).
_JONGSEONG_RIEUL = 8


def has_batchim_number(n: int) -> bool:
    """정수 n의 한자어 읽기 마지막 음절에 받침이 있으면 True.

    규칙: 일의 자리가 0이 아니면 일의 자리 읽기(_ONES_DIGIT_BATCHIM)가 마지막 음절을 지배한다.
    일의 자리가 0이면 십·백·천·(수 0이면 영) 자리가 마지막 음절을 지배하는데, 십(ㅂ)·백(ㄱ)·
    천(ㄴ)·영(ㅇ)은 **모두 받침이 있으므로** …0으로 끝나는 정수와 0 자체는 항상 받침 有다.
    음수는 부호가 읽기의 마지막 음절을 바꾸지 않으므로(예 −3=음의 삼) 절댓값의 읽기가 지배한다.
    """
    magnitude = abs(int(n))
    ones = magnitude % 10
    if ones != 0:
        return _ONES_DIGIT_BATCHIM[ones]
    # 일의 자리 0 → 십(ㅂ)·백(ㄱ)·천(ㄴ)·영(ㅇ) 계열 지배 → 전부 받침 有.
    return True


def has_batchim_hangul(ch: str) -> bool:
    """한글 음절 문자 ch의 종성(받침) 유무 — 받침 있으면 True(가~힣 밖이면 False).

    종성 인덱스 = (코드포인트 − 0xAC00) % 28. 0이면 받침 없음(예 '가'·'노'), 그 외 받침 있음.
    """
    if not ch:
        return False
    code = ord(ch[-1])
    if not (_HANGUL_BASE <= code <= _HANGUL_END):
        return False
    return (code - _HANGUL_BASE) % _JONGSEONG_COUNT != 0


def _jongseong_index(ch: str) -> int:
    """한글 음절 ch의 종성 인덱스(0~27) — 받침 없음 0. 한글 밖이면 −1(불명)."""
    if not ch:
        return -1
    code = ord(ch[-1])
    if not (_HANGUL_BASE <= code <= _HANGUL_END):
        return -1
    return (code - _HANGUL_BASE) % _JONGSEONG_COUNT


def has_batchim_text(token: str) -> bool | None:
    """선행 토큰 token의 받침 유무 — 정수 파싱 가능하면 수 읽기 기준, 한글로 끝나면 음절 기준.

    판별 불가(무리수·분수 문자열 등 '−3±2√2'·'sqrt(11)'·'1/2')면 None을 반환한다 — 한국어
    독법(분수=분모 먼저·무리수=루트 표기)이 마지막 음절을 지배해 문자 기반 판별이 부정확하기
    때문이다. 호출부는 None일 때 안전 기본(받침 有)을 쓰거나 고정 값 매핑으로 보정한다(정직 한계).
    """
    stripped = token.strip()
    try:
        return has_batchim_number(int(stripped))
    except ValueError:
        pass
    last = stripped[-1] if stripped else ""
    if _HANGUL_BASE <= ord(last) <= _HANGUL_END if last else False:
        return has_batchim_hangul(last)
    return None


def josa(
    token: str,
    with_batchim: str,
    without_batchim: str,
    *,
    default_batchim: bool = True,
) -> str:
    """선행 token에 맞는 조사 선택 — 받침 有면 with_batchim, 無면 without_batchim.

    판별 불가(has_batchim_text=None)면 default_batchim(안전 기본 True — 을/과/은/이 계열)을
    적용한다. 저수준 선택기이며, 상위 편의 래퍼(eul_reul 등)가 이를 호출한다.
    """
    batchim = has_batchim_text(token)
    if batchim is None:
        batchim = default_batchim
    return with_batchim if batchim else without_batchim


def eul_reul(token: str) -> str:
    """목적격 조사 을/를 — 받침 有 '을'·無 '를'."""
    return josa(token, "을", "를")


def wa_gwa(token: str) -> str:
    """접속 조사 와/과 — 받침 有 '과'·無 '와'."""
    return josa(token, "과", "와")


def eun_neun(token: str) -> str:
    """보조사 은/는 — 받침 有 '은'·無 '는'."""
    return josa(token, "은", "는")


def i_ga(token: str) -> str:
    """주격 조사 이/가 — 받침 有 '이'·無 '가'."""
    return josa(token, "이", "가")


def euro_ro(token: str) -> str:
    """부사격 조사 (으)로 — 받침 無 또는 'ㄹ' 받침이면 '로', 그 외 받침이면 '으로'.

    한국어 예외: 'ㄹ' 받침 뒤에는 '으로'가 아니라 '로'를 쓴다(예 '물로'·'1(일)로'). 정수의
    'ㄹ' 받침 여부는 일의 자리 읽기(1=일·7=칠·8=팔이 ㄹ)로 판별하고, 한글 단어는 종성 인덱스가
    ㄹ(8)인지 본다. 판별 불가면 안전 기본 '으로'.
    """
    stripped = token.strip()
    # 한글 단어: 종성 ㄹ이면 '로'.
    idx = _jongseong_index(stripped[-1]) if stripped else -1
    if idx == 0:
        return "로"  # 받침 없음
    if idx == _JONGSEONG_RIEUL:
        return "로"  # ㄹ 받침 예외
    if idx > 0:
        return "으로"
    # 정수: ㄹ 받침(1·7·8)이면 '로', 그 외 받침이면 '으로', 받침 없으면 '로'.
    try:
        ones = abs(int(stripped)) % 10
    except ValueError:
        return "으로"  # 불명 — 안전 기본
    if ones == 0:
        return "으로"  # …0(십·백·천·영)은 ㄹ 받침 아님
    if ones in (1, 7, 8):  # 일·칠·팔 = ㄹ 받침 → '로'
        return "로"
    if _ONES_DIGIT_BATCHIM[ones]:  # 그 외 받침(3·6) → '으로'
        return "으로"
    return "로"  # 받침 없음(2·4·5·9)
