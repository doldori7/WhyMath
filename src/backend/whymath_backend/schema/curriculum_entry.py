"""Schema v1.1 다국 커리큘럼 매트릭스 셀(CurriculumEntry) 모델 (Pydantic) — 슬라이스 8a.

설계 정본: `schemas/v1.1/curriculum_entry.schema.yaml`(`fields:` 31필드·`validation_invariants`·
`license`). v1.0 8개 도메인(슬라이스 1~7) *밖*의 v1.1 이식 자산이다 — 같은 수학 개념이
나라마다 *몇 학년에·어떤 깊이로* 다뤄지는지를 담는 매트릭스의 한 셀((concept_id × country_code
× subject) 3-튜플). 기존 NCIC 성취기준(AchievementStandard)이 이 매트릭스의 "한국(KR) 열"이며,
KR 셀은 그 크롤러 산출물(standards.json)에서 *파생*된다(새 한국 크롤러를 만드는 게 아님). 소유
7계층은 L1(데이터 기반), 매트릭스를 소비하는 자동 커리큘럼 정렬 엔진은 L6 소관(YAML 헤더).

subject 축 (과목 확장 S1 — subject_expansion_readiness.md §9):
  `subject`는 **교과** 레벨 과목 축('수학'·'물리')이다 — 같은 개념('벡터')이 같은 나라의 수학·
  물리 양쪽 교육과정에 등장할 수 있어 복합 의미키가 (concept_id, country_code, subject)
  3-튜플로 확장됐다. 과목 스코핑의 정본은 개념 노드가 아니라 이 Overlay다(rev f3a4b5c6d7e8이
  Concept에서 subject를 제거 — "노드는 의미만"). ⚠️ granularity 교차 명기: NCIC
  `AchievementStandard.subject`는 **과목** 레벨('공통수학1'·'미적분Ⅰ' — 교과 내 편제 단위)로
  이름만 같고 축이 다르다. country_code 선례 그대로 개방 str(enum 아님·default '수학') —
  Phase 1 산출물 '수학' 외 금지 범위 가드는 파이프라인 책임.

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수 Pydantic
모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1~7 동일 패턴). 스키마는 9~12개국
풀스케일을 *미리 수용*하되(필드는 개방형) 데이터는 Phase 1 범위(KR + 참고용 US·IMO 3축)다.

컨벤션(`problem.py`·`concept.py`·`user.py`·`assessment.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`(Literal 아님 — schema 패키지 컨벤션). 이 모델은
    `RequiredDepth`(4종)·`CurriculumLicense`(5종, 하이픈 값) 신규 enum을 쓴다.
  - 불변식은 `@model_validator(mode="after")`(슬라이스 1 `ProblemRelation._no_self_relation`·
    슬라이스 3 `ConceptEdge._no_self_edge` 패턴).
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(YAML `type:` → Pydantic, 슬라이스 1~7 선례 그대로):
  - `string`(required:true) → required `str`(`Field(...)`)
  - `string`(required:false) → `str | None`
  - `integer | null` → `int | None`(예: introduced_grade)
  - `date | null` → `datetime.date | None`(예: effective_from — TIMESTAMPTZ 아닌 날짜만,
    슬라이스 4 `target_exam_date` 선례)
  - `datetime`(required:true) → required `datetime`(예: created_at·updated_at — YAML이
    *required:true로 명시*하므로 슬라이스 1~7의 Optional created_at과 달리 required로 둔다.
    슬라이스 4 `UserPersonaHistory.detected_at`·슬라이스 6 `ConceptMasteryHistory.measured_at`이
    required `datetime`을 둔 선례)
  - `float`(required, range[0.0,1.0]) → `float = Field(..., ge=0.0, le=1.0)`(confidence —
    범위는 Field ge/le로 강제하고 validator는 두지 않는다, 슬라이스 1~7 척도 필드 방식)
  - `list<string>` → `list[str] = Field(default_factory=list)`
  - `enum`(required:false) → `Enum | None`(required_depth → `RequiredDepth | None`)
  - `enum`(required:true) → required `Enum`(license_id → `CurriculumLicense`)

⚠️ str로 둔 필드(enum 날조 회피 — slice4 gender/school_region 방침):
  YAML이 enum으로 *명시한 것*은 required_depth·license_id 둘뿐이다. country_code는 ISO 3166-1
  alpha-2(개방형 ~250개)+의사코드 'IMO'이고 YAML이 "스키마는 풀스케일 수용"이라 명시했으므로
  `str`로 둔다(Phase 1 KR/US/IMO 범위 가드는 *데이터/파이프라인* 책임이지 모델 강제 아님).
  grade_band·cognitive_level·domain_label 등 라벨류도 닫힌 카테고리가 YAML에 없어 `str`로
  둔다(NCIC `AchievementStandard.subject`가 str인 것과 정합).

법적 메모(YAML `license` 섹션·CLAUDE.md 절대 금기):
  이 모델은 국가 교육과정의 *구조*(몇 학년에·어떤 깊이로)와 *표준 코드*만 담으며 해설 *본문*은
  담지 않는다(YAML key_principle: "본문"과 "구조"를 구분). 국가별 원천 라이선스 의무는
  `license_id`로 셀 단위 추적하고, 라이선스 미확인 국가는 셀을 만들지 않는다(licensing_safety.md
  결정 트리 — 모델이 아니라 파이프라인 게이트). statement 상당 텍스트의 수집 범위가
  license_id별로 다른 점도 *수집(파이프라인) 단계* 책임이며, 자유 서술 텍스트라 구조 신호가
  없으므로 모델 validator로 강제하지 않는다(슬라이스 3 `concept.py` 법적 메모 방침: 문서화만,
  가짜 validator 금지).

cross-dataset 메모(YAML `validation_invariants` 중 모델 단독 강제 불가 항목):
  YAML invariant 중 *다른 데이터셋이 있어야 검증 가능한 것*은 모델이 강제하지 않는다 —
  ① concept_id가 개념 그래프(concept.schema.yaml) 노드에 실재(키 공간 정합), ② KR 셀의
  national_standard_codes가 NCIC standards.json에 실재, ③ (concept_id, country_code, subject)
  셀 중복 없음(복합키 유일성 — 단일 인스턴스로는 검증 불가, DB/파이프라인 레벨), ④ Phase 1
  산출물에 KR·US·IMO 외 국가 코드 없음(범위 가드), ⑤ Phase 1 산출물에 '수학' 외 subject
  없음(범위 가드 — ④와 동형). 이들은 *파이프라인 책임*이다(슬라이스 3 `ConceptEdge`의 복합
  UNIQUE가 DB 제약이라 모델 레벨에서 표현 안 한 선례와 동일). subject *비공백*만 모델이
  강제한다(Field min_length=1 — 구조 신호가 모델 안에 있으므로). *모델 내부로 강제 가능한*
  invariant만 아래 validator 2개로 구현한다.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import (
    CurriculumLicense,
    RequiredDepth,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: CurriculumEntry (curriculum_entry.schema.yaml — 매트릭스 셀, 31필드)
# ──────────────────────────────────────────────────────────────────────────
class CurriculumEntry(BaseModel):
    """다국 커리큘럼 매트릭스 셀 — YAML `CurriculumEntry`(31필드). 같은 개념이 나라마다 몇
    학년에·어떤 깊이로 다뤄지는지를 담는 (concept_id × country_code × subject) 3-튜플 레코드.

    복합키 `(concept_id, country_code, subject)`가 셀 PK이고, `entry_id`는 그 복합키와 1:1
    대응하는 표면 식별자다 — subject 외 셋은 YAML required:true이므로 required `str`로 두고
    (슬라이스 6 `ConceptMasteryHistory`가 복합 PK 구성요소를 모두 required로 둔 선례),
    subject는 YAML default '수학'이라 default 부여로 기존 호출부·payload를 깨지 않는다(S1).
    복합키 유일성 검증은 단일 인스턴스로 불가하므로 DB/파이프라인 책임이다(모듈 docstring
    cross-dataset 메모).

    required는 9개다 — 식별 3종(concept_id·country_code·entry_id) + source_name + license_id
    + is_present + confidence + created_at + updated_at. 나머지 22개(subject 포함)는
    nullable/기본값이라 `is_present=false`(그 나라에 개념 없음)인 *시점·깊이 필드가 빈* 셀도
    표현할 수 있다.

    불변식(`@model_validator(mode="after")`, 모델 내부로 강제 가능한 invariant만 — 모듈
    docstring cross-dataset 메모):
      1. `is_present is True`이면 `source_url`이 비어있지 않아야(None·"" 금지). 존재한다고
         주장하려면 근거 출처가 있어야 한다(YAML: "is_present=true인데 비면 ValidationError").
      2. `country_code == "IMO"`이면 `confidence <= 0.7`. IMO는 공식 표준이 부재한 관례라
         표준만큼 확정적이지 않다(YAML: "IMO 셀 confidence ≤ 0.7"). country_code는 str이므로
         use_enum_values와 무관하게 그대로 문자열 비교한다.
    `confidence ∈ [0.0, 1.0]`은 validator가 아니라 Field ge/le로 강제한다(슬라이스 1~7 방식).

    법적 메모(모듈 docstring·YAML license): 이 모델은 교육과정의 *구조·코드*만 담고 본문은
    담지 않는다. 국가별 라이선스 의무는 `license_id`로 셀 단위 추적(가짜 validator 없이 문서화).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(license_id="KR-NCIC"·required_depth="conceptual" 보존)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 그룹 1: 식별 (4) — 복합키 (concept_id, country_code, subject) + 표면키 entry_id =====
    concept_id: str = Field(
        ...,
        description="Universal Concept ID(복합키 구성요소). concept.schema.yaml의 concept_id와 "
        "동일 키 공간 — 개념 그래프 노드 실재 검증은 cross-dataset(파이프라인 책임).",
    )
    country_code: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 국가 코드(복합키 구성요소). IMO는 국가가 아니라 의사 "
        "코드 'IMO'. 개방형(~250개)+IMO이라 enum 아닌 str — Phase 1 KR/US/IMO 범위 가드는 "
        "파이프라인 책임.",
    )
    subject: str = Field(
        default="수학",
        min_length=1,
        description="**교과** 레벨 과목 축(복합키 구성요소·예: '수학'·'물리') — 과목 확장 S1"
        "(subject_expansion_readiness.md §9). ⚠️ NCIC AchievementStandard.subject(**과목** "
        "레벨 — '공통수학1'·'미적분Ⅰ')와 이름만 같고 granularity가 다르다(교차 명기). "
        "country_code 선례 그대로 개방 str(enum 아님) — Phase 1 산출물 '수학' 외 금지 범위 "
        "가드는 파이프라인 책임, 비공백만 모델 강제(min_length=1).",
    )
    entry_id: str = Field(
        ...,
        description="셀의 표면 식별자 — (concept_id, country_code, subject) 복합키와 1:1 대응하는 "
        "단일 키. 규약(S1): 수학 셀은 '{concept_id}:{country_code}' 무접미 불변(데이터 churn 0), "
        "비수학 셀만 ':{subject}' 접미(미래 규약).",
    )

    # ===== 그룹 2: 출처 (5) — 국가별 교육과정 표준 =====
    source_name: str = Field(
        ...,
        description="국가별 교육과정 표준 명칭(예: '2022 개정 교육과정 — 수학과 교육과정').",
    )
    source_code: str | None = Field(
        default=None,
        description="표준 문서 식별 코드(예: '교육부 고시 제2022-33호 [별책 8]').",
    )
    source_url: str | None = Field(
        default=None,
        description="출처 URL — 출처 표시 의무. YAML은 required:true이나 invariant가 "
        "is_present=false일 때 빈 값을 허용함을 함의하므로 str|None으로 두고, is_present=true일 "
        "때만 비어있지 않도록 아래 validator로 조건부 강제한다.",
    )
    source_document: str | None = Field(
        default=None,
        description="PDF/HWP 등 첨부 원문 문서 식별자.",
    )
    license_id: CurriculumLicense = Field(
        ...,
        description="국가별 원천 자원 라이선스 매트릭스 키 — KR-NCIC/US-CCSS/INT-IMO/JP-MEXT/"
        "GB-NC(셀 단위 라이선스 의무 추적, required).",
    )

    # ===== 그룹 3: 시점 (4) =====
    introduced_grade: int | None = Field(
        default=None,
        description="그 나라에서 이 개념이 처음 도입되는 학년(국가 내 학년 정수). 학제 차이는 "
        "clean 단계에서 정규화. is_present=false면 null.",
    )
    grade_band: str | None = Field(
        default=None,
        description="WhyMath 공통 학년대(개념 그래프 grade_band_hint·NCIC grade_band 어휘와 "
        "정렬). 닫힌 카테고리가 YAML에 없어 enum 아닌 str.",
    )
    effective_from: date | None = Field(
        default=None,
        description="해당 교육과정의 시행 시작일 — DATE 타입(TIMESTAMPTZ 아님, 날짜만).",
    )
    curriculum_revision: str | None = Field(
        default=None,
        description=(
            "교육과정 개정 표시(예: '2022 개정'). "
            "⚠️ CUR-10: framework_id 기반 연결 권장, 본 필드는 하위호환·레이블용"
        ),
    )
    framework_id: str | None = Field(
        default=None,
        description=(
            "소속 교육과정 프레임워크 식별자 "
            "(CurriculumFramework.framework_id, CUR-10). null이면 미분류"
        ),
    )

    # ===== 그룹 4: 맥락 (3) =====
    introduced_context: str | None = Field(
        default=None,
        description="이 개념이 어떤 맥락/단원에서 처음 등장하는지.",
    )
    domain_label: str | None = Field(
        default=None,
        description="그 나라 교육과정의 영역명. 한국은 NCIC domain에서 직접 매핑.",
    )
    sub_domain_label: str | None = Field(
        default=None,
        description="세부 영역명.",
    )

    # ===== 그룹 5: 깊이 (4) =====
    required_depth: RequiredDepth | None = Field(
        default=None,
        description="그 나라 교육과정이 이 개념에 요구하는 깊이 — awareness/procedural/"
        "conceptual/mastery.",
    )
    cognitive_level: str | None = Field(
        default=None,
        description="인지 수준(블룸 분류 등 — 국가별 원문 기준). 국가별 어휘가 달라 enum 아닌 str.",
    )
    is_assessed: bool | None = Field(
        default=None,
        description="그 나라의 국가 단위 평가에서 이 개념이 다뤄지는가(미응답=None 구분).",
    )
    assessment_format: str | None = Field(
        default=None,
        description="평가 형식(지필·서술형·수행 등).",
    )

    # ===== 그룹 6: 표기 (3) =====
    notation_local: str | None = Field(
        default=None,
        description="그 나라에서 쓰는 수학 표기.",
    )
    terminology_local: str | None = Field(
        default=None,
        description="그 나라의 용어(현지어 명칭).",
    )
    notation_variants: list[str] = Field(
        default_factory=list,
        description="같은 개념의 표기 변형들(Concept/Edge의 notation_variant 관계와 정합).",
    )

    # ===== 그룹 7: 위계 (2) — 그 나라 교육과정 내 =====
    prerequisite_concept_ids: list[str] = Field(
        default_factory=list,
        description="그 나라 교육과정 *내에서의* 선수개념. concept.schema.yaml의 전역 "
        "prerequisite와 다를 수 있음(나라마다 위계가 다름). concept_id 실재는 cross-dataset.",
    )
    followup_concept_ids: list[str] = Field(
        default_factory=list,
        description="그 나라 교육과정 내에서의 후속 개념.",
    )

    # ===== 그룹 8: 매핑 (2) =====
    national_standard_codes: list[str] = Field(
        default_factory=list,
        description="국가 표준 코드 목록. KR 셀의 경우 NCIC AchievementStandard.code를 가리킨다"
        "('한국 열 = NCIC 성취기준'의 연결 지점). NCIC standards.json 실재는 cross-dataset.",
    )
    textbook_unit_refs: list[str] = Field(
        default_factory=list,
        description="교과서 단원 참조(TextbookUnit.unit_id — textbook_mapping.schema.yaml).",
    )

    # ===== 그룹 9: 상태 (5) =====
    is_present: bool = Field(
        ...,
        description="그 나라 교육과정에 이 개념이 존재하는가(required). false면 시점·깊이 필드가 "
        "null. true인데 source_url이 비면 ValidationError(아래 validator).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="이 셀 데이터의 신뢰도(required, [0.0,1.0] — Field ge/le 강제). INT-IMO "
        "열은 보수적으로 ≤0.7(관례는 표준만큼 확정적이지 않음 — 아래 validator).",
    )
    verified_by: str | None = Field(
        default=None,
        description="사람 검수자 식별자.",
    )
    created_at: datetime = Field(
        ...,
        description="셀 생성 시각(YAML required:true → required datetime).",
    )
    updated_at: datetime = Field(
        ...,
        description="셀 최종 수정 시각(YAML required:true → required datetime).",
    )

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _present_requires_source_url(self) -> CurriculumEntry:
        """is_present=true이면 source_url이 비어있지 않아야 한다(None·"" 금지).

        존재한다고 주장하려면 근거 출처가 있어야 한다(YAML: "is_present=true인데 비면
        ValidationError"). is_present=false면 source_url이 빈 값이어도 정당하다.
        """
        if self.is_present and not (self.source_url and self.source_url.strip()):
            raise ValueError(
                "커리큘럼 셀 위반: is_present=true이면 source_url이 비어있을 수 없다 "
                "(존재 주장에는 근거 출처가 필요함)"
            )
        return self

    @model_validator(mode="after")
    def _imo_confidence_cap(self) -> CurriculumEntry:
        """country_code='IMO' 셀의 confidence는 ≤ 0.7이어야 한다.

        IMO는 공식 표준이 부재한 관례라 표준만큼 확정적이지 않다(YAML: "IMO 셀
        confidence ≤ 0.7"). country_code는 str이므로 use_enum_values와 무관하게 그대로 비교.
        """
        if self.country_code == "IMO" and self.confidence > 0.7:
            raise ValueError(
                "커리큘럼 셀 위반: country_code='IMO' 셀의 confidence는 0.7을 초과할 수 없다 "
                "(관례는 공식 표준만큼 확정적이지 않음)"
            )
        return self
