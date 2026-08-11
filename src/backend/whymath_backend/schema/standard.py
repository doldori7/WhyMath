"""성취기준(AchievementStandard)·개념↔성취기준 링크(ConceptStandardLink) 백엔드 Pydantic 스키마.

설계 정본: L1 데이터 파이프라인의 NCIC 모델(`data_pipeline/ncic/models.py`의
`AchievementStandard`·`ConceptStandardLink`)을 *백엔드 API/계약 모델*로 옮긴 것. 이 슬라이스(P1-2)는
성취기준의 **백엔드 영속(ORM)·계약(이 Pydantic)·마이그레이션**만 세운다 — jsonl 코퍼스 로더는
*후속 슬라이스* 몫이다(코퍼스 포맷 확정 전까지 보류).

⚠️ 키 명칭 차이(로더가 메우는 seam): data-pipeline 코퍼스는 고시 원문코드를 `code` 키로 두지만,
*이 백엔드 스키마는 `official_code`*로 둔다(`code`는 백엔드 도메인2 Concept의 개념코드와 어휘가
겹쳐 혼동을 부르므로 명시적 이름을 택함). `code`(코퍼스) → `official_code`(백엔드) 매핑은
*미래 로더*가 수행하며 이 슬라이스 밖이다.

타입 매핑 판단(data-pipeline Pydantic → 백엔드 Pydantic, `schema/concept.py`·
`schema/curriculum_entry.py` 선례 그대로):
  - `norm_id`(식별 필드) → required `str`. 교육과정(2022/2015) 간 유일(PK).
  - `official_code`(고시 원문코드, 코퍼스의 `code`) → required `str`. 교육과정 간 *비유일*.
  - `curriculum_revision`·`grade_band`·`school_type`·`subject`·`domain` → required `str`.
    data-pipeline은 grade_band/school_type을 `Literal`로 좁혔으나, 백엔드 계약은 NCIC
    `subject`/`domain`이 이미 `str`인 것(slice8a `CurriculumEntry`도 동형)과 정합하게 `str`로
    둔다 — 닫힌 카테고리 강제는 *데이터/파이프라인 책임*이다(slice4 gender·slice8a
    country_code가 닫힌 enum 날조를 회피해 str로 둔 방침과 동일).
  - `sub_domain`·`commentary`·`big_idea`·`source_document` → `str | None`(선택).
  - `statement`(성취기준 본문) → required `str`. ⚠️ **NCIC 공공누리 제1유형** 자료라 본문 보유가
    *허용*되는 예외 출처다(검정교과서·EBS 본문 금지와 대비 — `licensing_safety.md` 가이드 v2.0).
  - `effective_from`(시행 시작일) → `date | None`.
  - `parent_codes`(선수 성취기준 코드) → `list[str]`(default_factory=list).
  - `source_url`(원자료 URL) → required `str`. 공공누리 1유형 *출처 표시 의무*.
  - `link_type`(개념↔성취기준 연결 의미) → `Literal["직접","재매핑","준용"]`(data-pipeline
    `ConceptLinkType` Literal과 동일 — 한글 정본 값 그대로 보존).

법적 메모(공공누리 제1유형): 성취기준 본문(`statement`)·해설(`commentary`)은 NCIC 공공누리
제1유형 자료라 *상업 이용·변경이 허용*되며 본문을 보유할 수 있다(검정교과서·EBS·평가원 본문은
자체 동등문제로 대체해야 하는 것과 *대비*). 단 모든 사용에 출처 표시가 의무이며, 이는
data-pipeline 수집기(`SOURCE_CITATION`)와 추후 노출 계층이 동봉한다.

────────────────────────────────────────────────────────────────────────────
CUR-07 확장 — 평가준거 코드·단원별 성취수준 등급 (achievement_criteria_v1 실측 근거)
────────────────────────────────────────────────────────────────────────────
`data/corpus/achievement_criteria_v1/achievement_criteria.json`(CUR-05 회수, 13 school_level×subject
세트)을 실측 근거로 두 확장을 반영한다. 코퍼스는 성격이 다른 두 필드를 갖고, **두 필드를 같은
조인 축으로 취급하지 않는다**(강제 매칭 금지 — CLAUDE.md "환경 사실의 추론 등재 금지"):

  1. `standard_criteria_coverage`(성취기준 코드 → 평가준거 코드 다건, official_code 단위) — 실측
     확인(`docs/data/achievement_criteria_v1.md` §4): 459건 전량이 `standards_v1`의 '2015 개정'
     official_code 집합과 **정확히 일치**(교집합 459/459, 페이지 경계 오귀속 우려가 실제로는
     이 코퍼스 표본에서 관측되지 않음 — 데이터 카드의 "간헐적 오귀속 가능" 경고는 유효하되 이
     코퍼스 자체엔 미발현). 그래서 `AchievementStandard`에 `evaluation_criteria_codes` 컬럼을
     *추가*한다(official_code 1건 : 평가준거 코드 다건 — `parent_codes`와 동일 배열 패턴). 매칭은
     (curriculum_revision, official_code) 대조로 로더(`l1/standards/criteria_loader.py`)가 수행.
  2. `achievement_levels_by_unit`(단원 → 등급 라벨 다건, **unit 문자열 단위**) — 실측 확인:
     `unit`(예 '(1) 다항식')은 `AchievementStandard.domain`/`sub_domain`(NCIC 표준 분류 어휘)과
     어휘가 **교집합 0**(고등학교 표준 26개 domain 대조)이고, 같은 코퍼스의 `unit_hierarchy` 최상위
     번호 매김과도 불일치(예: 공통수학의 `unit_hierarchy`는 "(1) 문자와 식"이지만
     `achievement_levels_by_unit`은 "(1) 다항식" — 같은 "(1)"이 다른 대상을 가리킴). 게다가
     "(1) 문항 개발 목록"·"(2) 예시 평가 문항" 같은 *보고서 절 제목*까지 섞여 있어 이 축은 순수
     "단원" 분류조차 아니다. 개별 성취기준(`norm_id`)에 안전하게 귀속시킬 근거가 없으므로, 별도
     테이블 `AchievementLevelUnit`(school_level·subject·unit·levels)로 두고 **개별 성취기준과의
     연결은 이 태스크 범위 밖**으로 명시한다(`docs/data/achievement_criteria_v1.md` §5 후속 항목).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────────
# 핵심: AchievementStandard (성취기준 — NCIC 단일 성취기준의 백엔드 계약 모델)
# ──────────────────────────────────────────────────────────────────────────
class AchievementStandard(BaseModel):
    """성취기준 — 백엔드 API/계약 모델(`data_pipeline/ncic` AchievementStandard 대응).

    `norm_id`는 교육과정(2022/2015) 간 유일 식별자(PK), `official_code`(고시 원문코드, 코퍼스의
    `code`)는 교육과정 간 *비유일*(예: 2022·2015에 동일 `[12미적01-01]` 동시 존재 가능)이라
    `(curriculum_revision, official_code)`가 유일성을 갖는다(ORM `UniqueConstraint`로 강제).

    필드 의미는 모듈 docstring의 타입 매핑 참조. 형식 검증(norm_id/official_code 정규식)은
    *데이터 파이프라인 수집기 책임*이며, 백엔드 계약은 NCIC가 이미 검증·정규화한 값을 받는
    전제다(slice8a `CurriculumEntry`가 cross-dataset 검증을 파이프라인에 맡긴 방침과 동형).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 계약의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값 그대로(이 모델엔 enum 없음 — 일관성 위해 둠)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 식별 — norm_id(PK) + 비유일 official_code =====
    norm_id: str = Field(
        ...,
        description="정규화 식별자(PK) — 교육과정(2022/2015) 간 유일 "
        "(예: '2022_2수_01_01', '2022_10공수1_01_01')",
    )
    official_code: str = Field(
        ...,
        description="고시 원문코드(코퍼스의 `code`) — 교육과정 간 *비유일* "
        "(예: '[9수01-01]', '[10공수1-01-01]')",
    )
    curriculum_revision: str = Field(
        ...,
        description="교육과정 개정 표시 ('2022 개정' | '2015 개정')",
    )

    # ===== 분류 (NCIC subject/domain은 str — 닫힌 enum 강제는 파이프라인 책임) =====
    grade_band: str = Field(..., description="학년군 (예: '고등학교', '중학교 1~3학년군')")
    school_type: str = Field(..., description="학교급 (예: '초등학교'·'중학교'·'고등학교')")
    subject: str = Field(
        ...,
        description="과목명 — 2022 개정 (예: '수학', '공통수학1', '대수', '미적분Ⅰ')",
    )
    domain: str = Field(
        ...,
        description="영역 (예: '수와 연산', '변화와 관계', '도형과 측정')",
    )
    sub_domain: str | None = Field(default=None, description="세부 영역 (선택)")

    # ===== 본문·해설 (공공누리 1유형 — 본문 보유 허용, 출처 표시 의무) =====
    statement: str = Field(..., description="성취기준 본문(공공누리 1유형 — 본문 보유 허용)")
    commentary: str | None = Field(default=None, description="성취기준 해설 (선택)")
    big_idea: str | None = Field(default=None, description="해당 영역의 핵심 아이디어 (선택)")

    # ===== 시점·위계·출처 =====
    effective_from: date | None = Field(
        default=None,
        description="시행 시작일 — 학년별 단계 시행 (선택)",
    )
    parent_codes: list[str] = Field(
        default_factory=list,
        description="선수 성취기준 코드 (선택, 분석 결과로 후처리 채움 가능)",
    )
    source_url: str = Field(
        ...,
        description="원자료 URL — 공공누리 1유형 출처 표시 의무",
    )
    source_document: str | None = Field(
        default=None,
        description="PDF/HWP 등 첨부 문서 식별자 (선택)",
    )

    # ===== 평가준거 코드 커버리지 (CUR-07 — achievement_criteria_v1 매칭 결과, 선택) =====
    evaluation_criteria_codes: list[str] = Field(
        default_factory=list,
        description=(
            "평가준거 코드(하위 평가기준) — achievement_criteria_v1의 standard_criteria_coverage "
            "매칭 결과(선택). (curriculum_revision, official_code) 매칭 실패 시 빈 배열 유지"
            "(조용한 날조 금지 — 매칭 통계는 로더 반환값이 정직 계상)"
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# 보조: ConceptStandardLink (개념 ↔ 성취기준 N:M 연결)
# ──────────────────────────────────────────────────────────────────────────
class ConceptStandardLink(BaseModel):
    """개념 ↔ 성취기준(norm_id) 단일 연결 — 백엔드 계약 모델.

    개념 그래프(L1)의 개념과 성취기준 사이를 잇는 *연결 레이어*. `concept_code`는 개념 식별자
    (느슨참조 — 현재 'UC.*', 후속 'ELEM-GEO-*'; 백엔드 Concept.code와 동일 어휘),
    `norm_id`는 성취기준 식별자(실 FK 대상), `link_type`은 연결 의미다.

    `link_type` 값(한글 정본): '직접'(개념이 성취기준을 곧장 다룸)·'재매핑'(2015↔2022 개정 사이
    대응 성취기준으로 옮겨 연결)·'준용'(정확히 같진 않으나 교수학적으로 준하여 적용). data-pipeline
    `ConceptLinkType` Literal과 동일하게 유지한다.
    """

    model_config = ConfigDict(
        # 추가 필드 금지 + 문자열 양끝 공백 제거(AchievementStandard와 동일)
        extra="forbid",
        str_strip_whitespace=True,
    )

    concept_code: str = Field(
        ...,
        description="개념 식별자(느슨참조 — 'UC.*'/'ELEM-GEO-*', 백엔드 Concept.code 어휘)",
    )
    norm_id: str = Field(
        ...,
        description="연결 대상 성취기준 식별자 (norm_id)",
    )
    link_type: Literal["직접", "재매핑", "준용"] = Field(
        ...,
        description="연결 의미 — '직접'(곧장)·'재매핑'(개정 간 대응)·'준용'(교수학적 준용)",
    )
    note: str | None = Field(default=None, description="연결 근거·비고 (선택)")


# ──────────────────────────────────────────────────────────────────────────
# 보조: AchievementLevelUnit (단원 단위 성취수준 등급 커버리지 — CUR-07 신규)
# ──────────────────────────────────────────────────────────────────────────
class AchievementLevelUnit(BaseModel):
    """단원 단위 성취수준 등급 커버리지 — `achievement_criteria_v1`의 `achievement_levels_by_unit`
    원소 1건의 백엔드 계약 모델.

    ⚠️ **개별 `AchievementStandard`(norm_id)와 의도적으로 연결하지 않는다**(모듈 docstring
    "CUR-07 확장" §2 실측 근거). `unit`은 KICE 평가기준 보고서 자체의 단원 편성 문자열(예
    '(1) 다항식')이며 `AchievementStandard.domain`/`sub_domain`(NCIC 표준 분류 어휘)과도, 같은
    코퍼스의 `unit_hierarchy` 최상위 번호 매김과도 어휘·번호 체계가 다르다 — 억지로 이으면 "이
    단원의 모든 성취기준이 이 등급 집합을 가진다"는 원본에 없는 주장이 된다. `school_level`도
    `AchievementStandard.school_type`과 다른 어휘다(코퍼스 출처 KICE 보고서 구분 — '고등학교'
    보고서 vs '초중학교' 보고서 — 개별 성취기준의 실제 학교급이 아니다). 그래서 이 모델은
    성취기준 식별자를 필드로 갖지 않는다(연결 없음이 설계 결정 — 우연한 누락이 아니다).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    school_level: str = Field(
        ...,
        description="출처 KICE 보고서 구분('고등학교' | '초중학교') — school_type과 다른 어휘",
    )
    subject: str = Field(
        ..., description="과목명 또는 학년군명(코퍼스 원문 그대로, 예 '심화수학Ⅰ')"
    )
    unit: str = Field(..., description="단원 라벨(코퍼스 원문 그대로, 예 '(1) 다항식') — 서술 없음")
    levels: list[str] = Field(
        default_factory=list,
        description="해당 단원에 정의된 성취수준 등급 라벨 목록(A~E 또는 A~C 단독 문자, 서술 없음)",
    )
    source_document: str | None = Field(
        default=None,
        description="출처 코퍼스 식별자(예 'achievement_criteria_v1') — 선택",
    )


__all__ = ["AchievementStandard", "AchievementLevelUnit", "ConceptStandardLink"]
