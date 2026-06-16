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
    NORM_ID_PATTERN,
    SOURCE_CITATION,
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    ConceptLinkType,
    ConceptStandardLink,
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
    curriculum_revision: str
    norm_id: str


class RawLinkRecord(TypedDict, total=False):
    """개념↔성취기준 연결 raw 표현. 모든 필드 선택적(검증은 변환에서)."""

    concept_src_id: str
    norm_id: str
    link_type: str
    note: str


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
#
# 2015 개정 고교 과목 토큰 (추정 — File A 도착 시 확정):
#   수학   → 수학 (2015 공통 '수학'; 고1)
#   수학Ⅰ → 수학Ⅰ
#   수학Ⅱ → 수학Ⅱ
#   미적   → 미적분 (2015 '미적분'은 학년·맥락상 2022 미적분Ⅰ/Ⅱ와 구분; 약칭 그대로 보존)
#   확통   → 확률과 통계 (2015·2022 공용 약칭)
#   기하   → 기하 (2015·2022 공용)
#   실통   → 실용 수학 (2015) / 실용 통계(2022) — 토큰 충돌은 explicit_subject 우선으로 해소
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
    # 2015 개정 고교 과목 토큰 (로마숫자·ASCII 변형 동시 등록)
    "수학": "수학",
    "수학Ⅰ": "수학Ⅰ",
    "수학Ⅱ": "수학Ⅱ",
    "수학I": "수학Ⅰ",  # ASCII 변형
    "수학II": "수학Ⅱ",  # ASCII 변형
    "미적": "미적분",
    "미적분": "미적분",
}

# 교육과정 개정 표시 → norm_id prefix.
# (`AchievementStandard._validate_curriculum_revision`이 키를 강제하므로 안전)
_REVISION_PREFIX_MAP: Final[dict[str, str]] = {
    "2022 개정": "2022",
    "2015 개정": "2015",
}

# 로마숫자(NFC) → ASCII. norm_id 토큰은 `[가-힣A-Za-z0-9]`만 허용하므로 Ⅰ/Ⅱ를 I/II로 정규화.
# (clean의 NFC 정규화로 단일 코드포인트 Ⅰ(U+2160)·Ⅱ(U+2161) 형태가 들어온다고 가정)
_ROMAN_TO_ASCII: Final[dict[str, str]] = {
    "Ⅰ": "I",
    "Ⅱ": "II",
    "Ⅲ": "III",
    "Ⅳ": "IV",
    "Ⅴ": "V",
}

# link_type 허용 집합 (transform_raw_to_link 검증용 — ConceptLinkType Literal과 동기화)
_VALID_LINK_TYPES: Final[frozenset[str]] = frozenset({"직접", "재매핑", "준용"})


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


def _normalize_norm_id_token(grade: str, subject_token: str) -> str:
    """학년대수 + 과목토큰을 norm_id용 토큰으로 정규화.

    norm_id 토큰부는 `[가-힣A-Za-z0-9]{1,8}`만 허용하므로 로마숫자(Ⅰ/Ⅱ)를 ASCII(I/II)로
    바꾼다. 그 외 한글·숫자는 그대로 보존한다.

    예: ('2','수')→'2수' · ('10','공수1')→'10공수1' · ('12','미적Ⅰ')→'12미적I'
    """
    token = subject_token
    for roman, ascii_ in _ROMAN_TO_ASCII.items():
        token = token.replace(roman, ascii_)
    return f"{grade}{token}"


def build_norm_id(curriculum_revision: str, official_code: str) -> str:
    """(교육과정 개정, official_code) → 결정적(deterministic) norm_id 생성.

    `parse_standard_code`로 official_code를 학년·과목토큰·영역·순번으로 분해한 뒤
    `<개정연도>_<학년+과목토큰>_<영역>_<순번>` 형태로 재조립한다. 같은 입력은 항상 같은 출력.

    Args:
        curriculum_revision: '2022 개정' | '2015 개정'.
        official_code: 정규화 전/후 무관 (내부에서 normalize_code 적용).

    Returns:
        NORM_ID_PATTERN을 만족하는 norm_id.

    Raises:
        TransformError: 코드 패턴 미일치 또는 미지원 개정.

    예시:
        >>> build_norm_id("2022 개정", "[2수01-01]")
        '2022_2수_01_01'
        >>> build_norm_id("2022 개정", "[10공수1-01-01]")
        '2022_10공수1_01_01'
        >>> build_norm_id("2015 개정", "[12미적Ⅰ01-03]")
        '2015_12미적I_01_03'
    """
    if curriculum_revision not in _REVISION_PREFIX_MAP:
        raise TransformError(
            f"미지원 교육과정 개정: {curriculum_revision!r}. "
            f"지원: {sorted(_REVISION_PREFIX_MAP.keys())}"
        )
    prefix = _REVISION_PREFIX_MAP[curriculum_revision]

    code = normalize_code(official_code)
    grade, subject_token, domain_code, seq = parse_standard_code(code)
    token = _normalize_norm_id_token(grade, subject_token)

    norm_id = f"{prefix}_{token}_{domain_code}_{seq}"
    # 방어: 재조립 결과가 패턴을 만족하는지 즉시 확인 (토큰 길이 초과 등 조기 검출)
    if not NORM_ID_PATTERN.match(norm_id):
        raise TransformError(
            f"생성된 norm_id가 패턴 미일치: {norm_id!r} "
            f"(개정={curriculum_revision!r}, code={official_code!r})"
        )
    return norm_id


def transform_raw_to_standard(raw: RawStandardRecord) -> AchievementStandard:
    """raw 레코드 → 검증된 `AchievementStandard`.

    필수 필드(누락 시 예외):
      - code, statement, source_url

    선택 필드 누락 시 모델 기본값 사용. 학교급·학년군은 code에서 추론.

    norm_id 결정:
      - raw에 `norm_id`가 있으면 정규화(strip)하여 사용
      - 없으면 `build_norm_id(curriculum_revision, code)`로 파생
      - `curriculum_revision`은 raw 제공값(없으면 모델 기본 '2022 개정')

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

    # 6단계: 교육과정 개정 + norm_id 결정
    #   개정 미제공 시 모델 기본('2022 개정') 사용 → 동일 prefix로 build_norm_id에 전달.
    revision = clean_text(raw["curriculum_revision"]) if raw.get("curriculum_revision") else None
    revision_for_id = revision or "2022 개정"
    if raw.get("norm_id"):
        norm_id = normalize_norm_id(raw["norm_id"])
    else:
        norm_id = build_norm_id(revision_for_id, code)

    # 7단계: 모델 생성 (Pydantic이 추가 검증 수행)
    #   revision 미제공 시 revision_for_id가 모델 기본값('2022 개정')과 동일하다.
    return AchievementStandard(
        norm_id=norm_id,
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
        curriculum_revision=revision_for_id,
    )


def normalize_norm_id(raw: str) -> str:
    """norm_id 문자열을 정규화 — 양끝·내부 공백 제거.

    norm_id는 공백을 포함하지 않으므로 모든 공백을 제거한다(코드 정규화와 같은 방침).
    패턴 일치 여부는 검증하지 않는다(검증은 모델/검증 모듈에서).
    """
    return re.sub(r"\s+", "", raw)


def transform_raw_to_link(raw: RawLinkRecord) -> ConceptStandardLink:
    """raw 레코드 → 검증된 `ConceptStandardLink`.

    필수 필드(누락 시 예외):
      - concept_src_id, norm_id, link_type

    절차:
      1. concept_src_id 정제(strip)
      2. norm_id 정규화(공백 제거)
      3. link_type 정제 후 enum 집합('직접'·'재매핑'·'준용') 검증
      4. note 정제(선택)

    Raises:
        TransformError: 필수 필드 누락 또는 link_type 비허용 값.
    """
    if "concept_src_id" not in raw or not raw["concept_src_id"]:
        raise TransformError("'concept_src_id' 필수")
    if "norm_id" not in raw or not raw["norm_id"]:
        raise TransformError("'norm_id' 필수")
    if "link_type" not in raw or not raw["link_type"]:
        raise TransformError("'link_type' 필수")

    concept_src_id = clean_text(raw["concept_src_id"])
    norm_id = normalize_norm_id(raw["norm_id"])
    link_type_raw = clean_text(raw["link_type"])
    if link_type_raw not in _VALID_LINK_TYPES:
        raise TransformError(
            f"비허용 link_type: {link_type_raw!r}. 허용: {sorted(_VALID_LINK_TYPES)}"
        )
    # 위 검증으로 link_type_raw가 ConceptLinkType 멤버임이 보장됨
    link_type: ConceptLinkType = link_type_raw  # type: ignore[assignment]
    note = clean_text(raw["note"]) if raw.get("note") else None

    return ConceptStandardLink(
        concept_src_id=concept_src_id,
        norm_id=norm_id,
        link_type=link_type,
        note=note,
    )


# 모듈 수준 상수 — 외부 노출용 (출처 표시)
__all__ = [
    "RawLinkRecord",
    "RawStandardRecord",
    "SOURCE_CITATION",
    "TransformError",
    "build_norm_id",
    "infer_school_and_band",
    "normalize_norm_id",
    "parse_standard_code",
    "resolve_subject",
    "transform_raw_to_link",
    "transform_raw_to_standard",
]
