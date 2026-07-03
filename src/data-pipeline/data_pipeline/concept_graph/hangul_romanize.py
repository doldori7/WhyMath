"""한글 → ASCII 결정론적 로마자화 — canonical concept_id slug 생성 전용(P2d·Part 9).

정본: docs/data/concept_graph.md §2.4(ID 규약)·docs/standards/part9_id_policy_review.md.

배경(2026-07-02 P2d·Part 9 엄격 시정): canonical concept_id를 교육과정·언어 무관 의미론 형식
`math.<area>.<slug>`으로 전환하며, `<slug>`를 name_ko에서 *결정론적으로* 파생한다. Phase 1은
한국어 전용(name_en=None)이라 영어 slug 원천이 없으므로, name_ko를 국립국어원 로마자표기법에
기반한 **간이(simplified) 음역**으로 ASCII 화한다.

★ 이 음역은 *slug 생성용 간이 규칙*이다 — 자모 단위 결정론 사상만 하고, 표준 로마자표기법의
문맥 의존(자음동화·경음화·연음) 규칙은 적용하지 않는다. 목적은 언어학적 정확성이 아니라
**결정론·멱등·교육과정 독립 slug**다(같은 name_ko는 항상 같은 slug — 재실행 동일). name_en이
나중에 저작돼도 canonical_id는 불변이고 표시이름(locale)만 개선된다(§동결 정책).

외부 라이브러리 0(순수 Unicode 산식) — CLAUDE.md 의존성 최소화. 한자·미해독 문자로 slug가
비면 ValueError(시끄러운 실패 — src_id 침묵 폴백 금지, 추적성 위해 저작 개입 유도).
"""

from __future__ import annotations

import re
import unicodedata

# 한글 음절 블록(가~힣) Unicode 경계·조합 산식(§2.4).
_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3
_MEDIAL_COUNT = 21
_FINAL_COUNT = 28

# 초성 19자 → 로마자(ㅇ은 무음). 표준 로마자표기법 자음(어두) 기준.
_INITIALS: tuple[str, ...] = (
    "g",
    "kk",
    "n",
    "d",
    "tt",
    "r",
    "m",
    "b",
    "pp",
    "s",
    "ss",
    "",
    "j",
    "jj",
    "ch",
    "k",
    "t",
    "p",
    "h",
)
# 중성 21자 → 로마자(모음).
_MEDIALS: tuple[str, ...] = (
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "wo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
)
# 종성 28자 → 로마자(0=받침없음). 표준 로마자표기법 받침값(ㅅ·ㅈ·ㅊ·ㅌ·ㅎ→t 등).
_FINALS: tuple[str, ...] = (
    "",
    "k",
    "kk",
    "ks",
    "n",
    "nj",
    "nh",
    "t",
    "l",
    "lk",
    "lm",
    "lb",
    "ls",
    "lt",
    "lp",
    "lh",
    "m",
    "p",
    "ps",
    "t",
    "t",
    "ng",
    "t",
    "t",
    "k",
    "t",
    "p",
    "t",
)

# 괄호·대괄호 부기 제거(범위·단위 주석 — slug 노이즈). 전각 괄호도 포함.
_BRACKETED = re.compile(r"[（(\[][^）)\]]*[）)\]]")
# slug 허용 문자 외 → 구분자. 결과는 [a-z0-9-]만 남긴다.
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-+")


def _romanize_syllable(char: str) -> str:
    """한글 음절 1자 → 로마자(초성+중성+종성). 한글 아니면 그대로 반환(호출측이 후처리)."""
    code = ord(char)
    if not (_HANGUL_BASE <= code <= _HANGUL_LAST):
        return char
    offset = code - _HANGUL_BASE
    initial = offset // (_MEDIAL_COUNT * _FINAL_COUNT)
    medial = (offset % (_MEDIAL_COUNT * _FINAL_COUNT)) // _FINAL_COUNT
    final = offset % _FINAL_COUNT
    return _INITIALS[initial] + _MEDIALS[medial] + _FINALS[final]


def romanize(text: str) -> str:
    """name_ko 등 한글 문자열 → 결정론적 ASCII slug(`[a-z0-9]`·`-` 구분).

    처리: ① 괄호 부기 제거 ② 각 문자를 한글이면 음절 로마자화·라틴/숫자는 소문자 통과·그 외는
    구분자 ③ 비-slug 문자를 `-`로 접고 중복 `-` 축약·양끝 strip. 결과가 비면 ValueError.

    예: '수 개념과 세기(0~100)' → 'su-gaenyeomgwa-segi', '지수법칙' → 'jisu-beopchik'.
    """
    # NFC 정규화(자모 분리 입력 방어) 후 괄호 부기 제거.
    normalized = unicodedata.normalize("NFC", text)
    stripped = _BRACKETED.sub(" ", normalized)

    pieces: list[str] = []
    for char in stripped:
        if _HANGUL_BASE <= ord(char) <= _HANGUL_LAST:
            pieces.append(_romanize_syllable(char))
        elif char.isascii() and char.isalnum():
            pieces.append(char.lower())
        else:
            pieces.append(" ")  # 구분자 후보(·, 공백, 한자, 기호 등)
    joined = "".join(pieces)

    slug = _MULTI_DASH.sub("-", _NON_SLUG.sub("-", joined)).strip("-")
    if not slug:
        raise ValueError(
            f"로마자 slug를 만들 수 없음(해독 가능한 한글/영숫자 없음): {text!r}. "
            "canonical slug는 name_ko에서 파생 — 이름 확인 또는 canonical_slug override 필요."
        )
    return slug


__all__ = ["romanize"]
