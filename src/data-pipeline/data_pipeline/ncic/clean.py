"""NCIC 추출 텍스트 정제.

NCIC HTML/PDF에서 추출된 문자열은 종종 다음 문제를 가진다:
  - 비표준 공백 (NBSP·전각 공백·여러 공백)
  - 줄바꿈 잘림 (PDF 한 행의 단어 끝 hyphen)
  - 한자 병기 (예: "수학(數學)") — 그대로 보존하되 검색용 컬럼에서 제거할 수도
  - HTML 엔티티 잔여 (&nbsp; · &amp; 등)
  - Zero-width characters (ZWSP·ZWNJ 등)

이 모듈은 *최소 침습 정제* 원칙:
  - 의미를 바꾸는 변형 금지
  - 공백·제어문자만 정규화
  - 한자·괄호·문장부호는 그대로 보존
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Final

# 모든 종류의 유니코드 공백을 일반 스페이스로 매핑할 정규식
#      NBSP
#      Ogham space
#    -   in-quad spaces
#      Narrow NBSP
#      Medium Mathematical Space
#   　  IDEOGRAPHIC SPACE (전각 공백)
_UNICODE_SPACES: Final[re.Pattern[str]] = re.compile(r"[   -   　]")

# Zero-width 문자: ZWSP·ZWNJ·ZWJ·BOM (제거 대상)
_ZERO_WIDTH: Final[re.Pattern[str]] = re.compile(r"[​-‍﻿]")

# 제어문자 (개행·탭은 제외)
_CONTROL_CHARS: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# 연속 공백 (개행 제외)
_MULTI_SPACES: Final[re.Pattern[str]] = re.compile(r"[ \t]{2,}")

# 연속 개행 (3+ → 2)
_MULTI_NEWLINES: Final[re.Pattern[str]] = re.compile(r"\n{3,}")

# PDF에서 자주 발생: 줄바꿈 직전 하이픈
#   "소인수분-\n해" → "소인수분해" — 한국어에서는 거의 없지만 영문 혼용 시 발생
_LINE_BREAK_HYPHEN: Final[re.Pattern[str]] = re.compile(r"([A-Za-z])-\n([a-z])")


def clean_text(raw: str) -> str:
    """원문 텍스트를 정제.

    절차 (순서 중요):
      1. None/빈 문자열 처리
      2. HTML 엔티티 디코드 (&nbsp; → NBSP 등)
      3. 유니코드 정규화 NFC (한자·합성 한글 정규형)
      4. Zero-width 문자 제거
      5. 제어문자 제거
      6. PDF 줄바꿈 하이픈 결합
      7. 모든 유니코드 공백을 일반 스페이스로
      8. 연속 공백·연속 개행 축약
      9. 양끝 공백 제거

    Args:
        raw: 정제 전 원문.

    Returns:
        정제 후 문자열. 입력이 빈 문자열이면 빈 문자열 반환.

    예시:
        >>> clean_text("소인수분해의  뜻을  알고")
        '소인수분해의 뜻을 알고'
        >>> clean_text("&nbsp;자연수를&nbsp;소인수분해")
        '자연수를 소인수분해'
    """
    if not raw:
        return ""

    # 1단계: HTML 엔티티 디코드
    text = html.unescape(raw)

    # 2단계: 유니코드 정규화 (NFC) — 한자·한글 자모 결합형 정규화
    text = unicodedata.normalize("NFC", text)

    # 3단계: Zero-width 문자 제거
    text = _ZERO_WIDTH.sub("", text)

    # 4단계: 제어문자 제거 (개행·탭은 보존)
    text = _CONTROL_CHARS.sub("", text)

    # 5단계: PDF 줄바꿈 하이픈 결합
    text = _LINE_BREAK_HYPHEN.sub(r"\1\2", text)

    # 6단계: 유니코드 공백을 일반 스페이스로
    text = _UNICODE_SPACES.sub(" ", text)

    # 7단계: 연속 스페이스 축약
    text = _MULTI_SPACES.sub(" ", text)

    # 8단계: 연속 개행 축약 (3+ → 2, 단락 구분만 보존)
    text = _MULTI_NEWLINES.sub("\n\n", text)

    # 9단계: 줄별 양끝 공백 제거 + 전체 양끝 공백 제거
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def normalize_code(raw: str) -> str:
    """성취기준 코드 문자열을 정규화.

    NCIC PDF·HTML에서는 코드가 다양한 형태로 등장:
      - "[9수01-01]"   ← 표준
      - "[ 9수 01-01 ]" ← 공백 삽입
      - "[9수01–01]"   ← em-dash (U+2013)
      - "[9수01—01]"   ← em-dash (U+2014)

    이 함수는 공백 제거 + dash 통일을 수행.

    Args:
        raw: 정규화 전 코드 문자열.

    Returns:
        정규화된 코드. 패턴 일치 여부는 검증하지 않음(검증은 모델에서).
    """
    # 모든 공백 제거
    text = re.sub(r"\s+", "", raw)
    # em-dash·en-dash·hyphen-minus 변형 → ASCII '-'
    # mypy 호환: 키를 ord(int)로 변환해 표준 translation table 형식
    dash_map: dict[int, str] = {
        ord("‐"): "-",  # HYPHEN
        ord("‑"): "-",  # NON-BREAKING HYPHEN
        ord("‒"): "-",  # FIGURE DASH
        ord("–"): "-",  # EN DASH
        ord("—"): "-",  # EM DASH
        ord("―"): "-",  # HORIZONTAL BAR
        ord("−"): "-",  # MINUS SIGN
    }
    return text.translate(dash_map)
