"""HTML/PDF에서 추출한 raw 레코드를 `AchievementStandard`로 정형화.

설계 메모:
  - `RawStandardRecord`: 수집기가 출력하는 *느슨한* 중간 표현
  - `transform_raw_to_standard`: raw → Pydantic 변환 + 결측 추론
  - 학년대수→학교급/학년군, 과목약칭→과목 풀네임 매핑은 *교과서적* 합의에 따름.
    NCIC 원문 변경 시 이 매핑만 갱신하면 됨 (코드 변경 최소화).
"""

from __future__ import annotations

import re
from typing import Final, TypedDict

from data_pipeline.ncic.clean import clean_text, normalize_code
from data_pipeline.ncic.models import (
    SOURCE_CITATION,
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    GradeBand,
    SchoolType,
)


class RawStandardRecord(TypedDict, total=False):
    """수집기 출력 중간 표현. 모든 필드 선택적."""

    code: str
    subject: str
    domain: str
    sub_domain: str
    statement: str
    commentary: str
    big_idea: str
    source_url: str
    source_document: str


# ──────────────────────────────────────────────────────────────────────
# 매핑 테이블 (NCIC 원문 변경 시 이 부분만 갱신)
# ──────────────────────────────────────────────────────────────────────
#
# 학년대수 → (학교급, 학년군)
# 2022 개정 교육과정 기준:
#   2  ← 초등 1~2학년군
#   4  ← 초등 3~4학년군
#   6  ← 초등 5~6학년군
#   9  ← 중학교 1~3학년군
#   10 ← 고등학교 공통과목 (공통수학1·2)
#   12 ← 고등학교 일반선택·진로선택 (대수·미적분Ⅰ·확률과 통계 등)
_GRADE_BAND_MAP: Final[dict[str, tuple[SchoolType, GradeBand]]] = {
    "2": ("초등학교", "초등학교 1~2학년군"),
    "4": ("초등학교", "초등학교 3~4학년군"),
    "6": ("초등학교", "초등학교 5~6학년군"),
    "9": ("중학교", "중학교 1~3학년군"),
    "10": ("고등학교", "고등학교"),
    "12": ("고등학교", "고등학교"),
}

# 과목 약칭 → 풀네임 (코드의 과목 부분에서 추출)
# 2022 개정 고교 과목 다양화:
#   수    → 수학 (초·중)
#   공수1 → 공통수학1
#   공수2 → 공통수학2
#   대수  → 대수
#   미적Ⅰ → 미적분Ⅰ
#   미적Ⅱ → 미적분Ⅱ
#   확통  → 확률과 통계
#   기하  → 기하
#   경수  → 경제 수학
#   인수  → 인공지능 수학
#   실통  → 실용 통계
_SUBJECT_MAP: Final[dict[str, str]] = {
    "수": "수학",
    "공수1": "공통수학1",
    "공수2": "공통수학2",
    "대수": "대수",
    "미적Ⅰ": "미적분Ⅰ",
    "미적Ⅱ": "미적분Ⅱ",
    "확통": "확률과 통계",
    "기하": "기하",
    "경수": "경제 수학",
    "인수": "인공지능 수학",
    "실통": "실용 통계",
    # 변형 표기 (PDF에서 '미적I'·'미적II'로 등장 가능)
    "미적I": "미적분Ⅰ",
    "미적II": "미적분Ⅱ",
}


class TransformError(ValueError):
    """변환 실패."""


def parse_standard_code(code: str) -> tuple[str, str, str, str]:
    """코드를 학년대수·과목약칭·영역코드·순번으로 분해.

    Args:
        code: 정규화된 성취기준 코드 (예: '[9수01-01]', '[10공수1-01-01]').

    Returns:
        (학년대수, 과목약칭, 영역코드, 순번).

        - 과목약칭은 한글 부분 + 숫자 접미사를 합친 형태 (예: '공수1', '미적Ⅰ', '수').
        - 영역 2자리, 순번 2자리.

    Raises:
        TransformError: 코드 패턴 미일치.
    """
    match = STANDARD_CODE_PATTERN.match(code)
    if not match:
        raise TransformError(f"성취기준 코드 패턴 미일치: {code!r}")
    grade = match.group(1)
    # 그룹 2(한글) + 그룹 3(숫자 접미사, 선택) = 전체 과목 약칭
    subject_token = match.group(2) + match.group(3)
    domain_code = match.group(4)
    seq = match.group(5)
    return grade, subject_token, domain_code, seq


def infer_school_and_band(grade_num: str) -> tuple[SchoolType, GradeBand]:
    """학년대수 → 학교급·학년군."""
    if grade_num not in _GRADE_BAND_MAP:
        raise TransformError(
            f"알 수 없는 학년 대수: {grade_num!r}. " f"지원: {sorted(_GRADE_BAND_MAP.keys())}"
        )
    return _GRADE_BAND_MAP[grade_num]


def resolve_subject(
    subject_token: str,
    explicit_subject: str | None = None,
) -> str:
    """코드의 과목 약칭 + 수집기에서 알려준 명시적 subject를 종합.

    원칙:
      1. explicit_subject가 있으면 *그대로 사용* (수집기가 더 정확)
      2. 없으면 _SUBJECT_MAP에서 약칭 풀이
      3. 약칭 매핑이 없으면 약칭 그대로 (보수적)
    """
    if explicit_subject:
        return clean_text(explicit_subject)
    return _SUBJECT_MAP.get(subject_token, subject_token)


def transform_raw_to_standard(raw: RawStandardRecord) -> AchievementStandard:
    """raw 레코드 → 검증된 `AchievementStandard`.

    필수 필드(누락 시 예외):
      - code, statement, source_url

    선택 필드 누락 시 모델 기본값 사용. 학교급·학년군은 code에서 추론.

    Raises:
        TransformError: 필수 필드 누락 또는 형식 오류.
    """
    # 1단계: 필수 필드 검사
    if "code" not in raw or not raw["code"]:
        raise TransformError("'code' 필수")
    if "statement" not in raw or not raw["statement"]:
        raise TransformError("'statement' 필수")
    if "source_url" not in raw or not raw["source_url"]:
        raise TransformError("'source_url' 필수 (공공누리 1유형 출처 표시)")

    # 2단계: 코드 정규화 + 분해
    code = normalize_code(raw["code"])
    grade_num, subject_token, _domain_code, _seq = parse_standard_code(code)

    # 3단계: 학교급·학년군 추론
    school_type, grade_band = infer_school_and_band(grade_num)

    # 4단계: 과목 결정
    subject = resolve_subject(subject_token, raw.get("subject"))

    # 5단계: 텍스트 정제
    statement = clean_text(raw["statement"])
    if not statement:
        raise TransformError(f"정제 후 statement가 빈 문자열: {raw['code']}")

    commentary = clean_text(raw["commentary"]) if raw.get("commentary") else None
    big_idea = clean_text(raw["big_idea"]) if raw.get("big_idea") else None
    domain = clean_text(raw.get("domain", "")) or "미지정"
    sub_domain = clean_text(raw["sub_domain"]) if raw.get("sub_domain") else None

    # 6단계: 모델 생성 (Pydantic이 추가 검증 수행)
    return AchievementStandard(
        code=code,
        grade_band=grade_band,
        school_type=school_type,
        subject=subject,
        domain=domain,
        sub_domain=sub_domain,
        statement=statement,
        commentary=commentary,
        big_idea=big_idea,
        source_url=raw["source_url"],
        source_document=raw.get("source_document"),
    )


# 모듈 수준 상수 — 외부 노출용 (출처 표시)
__all__ = [
    "RawStandardRecord",
    "SOURCE_CITATION",
    "TransformError",
    "infer_school_and_band",
    "parse_standard_code",
    "resolve_subject",
    "transform_raw_to_standard",
]


# 영역코드 사용 안 함을 명시 (mypy strict — _domain_code 미사용 경고 회피)
_ = re.compile  # 모듈 import 보장
