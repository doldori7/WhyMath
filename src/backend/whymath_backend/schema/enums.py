"""Schema v1.0 도메인 ENUM 정의 (Pydantic str-Enum).

설계 정본: `schemas/v1.0/schema_v1.0.md` §14.3(ENUM 정의)·§3(도메인1 Problem DDL)·
§13.2(`license_enum`). 이 파일의 각 enum은 그 DDL의 `CREATE TYPE ... AS ENUM (...)`
값을 *그대로* 옮긴 것이 정본이다(한글 값은 한글 그대로, 영어 값은 영어 그대로).

컨벤션(`l3/models.py` 답습):
  - `class X(str, Enum)` 사용 (Literal 아님). str-Enum이므로 멤버는 그 문자열 값과
    동등 비교되어 라우터·필터 코드에서 안정적으로 쓰인다.
  - 식별자(멤버 이름)는 영어, 값(`= "..."`)은 DDL 그대로.
  - 모델에서 `use_enum_values=True`로 직렬화하면 한글 값이 그대로 보존된다
    (`str_strip_whitespace`·`ensure_ascii=False` 효과).

법적 메모(MEMORY 2026-05-28 결정 로그): `SourceType.평가원/EBS/교과서`와
`LicenseType.EBS_LICENSED`·`GenerationType.ORIGINAL`은 *본문 저장* 전제로
해석하면 저작권 가이드 v2.0(§32 단서·영리 금지)과 충돌한다. 따라서 이들
source_type은 *구조 메타데이터 참조 전용*이며, 실제 본문을 가진 문제는
`SourceType.자체생성`(license=`WHYMATH_GENERATED`)뿐이다. 이 불변식은
`problem.Problem`의 `@model_validator(mode="after")`에서 강제한다.
"""

from __future__ import annotations

from enum import Enum


# ──────────────────────────────────────────────────────────────────────────
# 출처·시험 컨텍스트 (§3.1 problem 테이블 §14.3 source_type_enum)
# ──────────────────────────────────────────────────────────────────────────
class SourceType(str, Enum):
    """콘텐츠 출처 — §14.3 `source_type_enum` 값 그대로(한글).

    법적 교정(MEMORY 2026-05-28): 평가원·EBS·교과서는 *본문 미보유*. 이 세 출처
    레코드는 구조 메타데이터(단원·코드·문항번호)만 가지며 본문 필드는 비어야 한다
    (`Problem` after-validator로 강제). 학생에게 노출되는 본문은 `자체생성`만.
    """

    평가원 = "평가원"
    """한국교육과정평가원 — 구조 메타만(본문 X, 저작권법 §32 단서·영리 금지)."""

    EBS = "EBS"
    """EBS — 구조 메타만(본문 X, 상업 영리금지 §32 단서)."""

    AIHub = "AIHub"
    """AIHub 공개 데이터셋 — 영리 명문 허용(출처표시·국외반출·재판매금지·환수)."""

    교육청학평 = "교육청학평"
    """시도교육청 학력평가 — 구조 메타 참조."""

    사설모의고사 = "사설모의고사"
    """사설 모의고사 — 제휴 시에만(THIRD_PARTY_LICENSED)."""

    자체생성 = "자체생성"
    """WhyMath 자체 생성 동등문제 — 본문 보유, license=WHYMATH_GENERATED."""

    사용자자작 = "사용자자작"
    """사용자 자작 문제 — license=USER_GENERATED."""

    교과서 = "교과서"
    """검정 교과서 — 구조 메타만(본문·문제·풀이·그림 복제 절대 금지)."""


class ExamType(str, Enum):
    """시험 유형 — §3.1 `exam_type_enum` 주석(수능/모평/학평/EBS교재/N제/자체생성).

    §14.3에 별도 `CREATE TYPE`이 없어 DDL 컬럼 주석(L127)의 값을 정본으로 채택한다.
    """

    수능 = "수능"
    모평 = "모평"
    학평 = "학평"
    EBS교재 = "EBS교재"
    N제 = "N제"
    자체생성 = "자체생성"


class Curriculum(str, Enum):
    """교육과정 버전 — §14.3 `curriculum_enum` 값 그대로(영어)."""

    REVISION_2009 = "2009_REVISION"
    REVISION_2015 = "2015_REVISION"
    REVISION_2022 = "2022_REVISION"


class Subject(str, Enum):
    """과목 — §3.1 `subject_enum` 주석(공통/미적분/확통/기하/인공지능수학).

    §14.3에 별도 `CREATE TYPE`이 없어 DDL 컬럼 주석(L139)을 정본으로 채택한다.
    """

    공통 = "공통"
    미적분 = "미적분"
    확통 = "확통"
    기하 = "기하"
    인공지능수학 = "인공지능수학"


# ──────────────────────────────────────────────────────────────────────────
# 문항 형식·정답 (§3.1 question_format_enum·answer_format_enum)
# ──────────────────────────────────────────────────────────────────────────
class QuestionFormat(str, Enum):
    """문항 형식 — §3.1 `question_format_enum` 주석(객관식/단답형/합답형/서술형)."""

    객관식 = "객관식"
    단답형 = "단답형"
    합답형 = "합답형"
    서술형 = "서술형"


class AnswerFormat(str, Enum):
    """정답 형식 — §3.1 `answer_format_enum` 주석(자연수/분수/실수/식)."""

    자연수 = "자연수"
    분수 = "분수"
    실수 = "실수"
    식 = "식"


# ──────────────────────────────────────────────────────────────────────────
# 한국 시그니처 패턴 (§14.3 signature_pattern_enum — 10종)
# ──────────────────────────────────────────────────────────────────────────
class SignaturePattern(str, Enum):
    """한국 수능 시그니처 패턴 — §14.3 `signature_pattern_enum` 값 그대로(영어, 10종)."""

    CONDITION_LIST = "CONDITION_LIST"
    """(가)(나)(다) 조건 나열 (FR-001 조건 나열형 파서)."""

    COMPOSITE_DIFFERENTIABILITY = "COMPOSITE_DIFFERENTIABILITY"
    """합성함수 미분가능성 (FR-003)."""

    INDUCTIVE_SEQUENCE = "INDUCTIVE_SEQUENCE"
    """귀납적 수열 (FR-004)."""

    DEFINED_INTEGRAL_FUNCTION = "DEFINED_INTEGRAL_FUNCTION"
    """정적분 정의 함수."""

    FUNCTION_COUNT = "FUNCTION_COUNT"
    """함수 개수 문제."""

    GRAPH_SHAPE_INFERENCE = "GRAPH_SHAPE_INFERENCE"
    """그래프 개형 추론."""

    CASE_ANALYSIS_DEEP = "CASE_ANALYSIS_DEEP"
    """깊은 케이스 분류."""

    CROSS_UNIT_FUSION = "CROSS_UNIT_FUSION"
    """단원 융합."""

    NATURAL_NUMBER_TRANSFORM = "NATURAL_NUMBER_TRANSFORM"
    """자연수 답 변환."""

    COMPOUND_CHOICES = "COMPOUND_CHOICES"
    """합답형 ㄱㄴㄷ."""


# ──────────────────────────────────────────────────────────────────────────
# 페르소나 (§14.3 persona_enum — PRD 5종)
# ──────────────────────────────────────────────────────────────────────────
class Persona(str, Enum):
    """PRD 페르소나 5종 — §14.3 `persona_enum` 값 그대로(영어+한글 혼합 식별자 표현)."""

    A_일반고고3 = "A_일반고고3"
    """A 일반고 고3 — MVP·시장 최대."""

    B_자사고N수 = "B_자사고N수"
    """B 자사고 N수 — v2.0·결제 최대."""

    C_검정고시N수 = "C_검정고시N수"
    """C 검정고시 N수 — v1.5·수학 의존 100%."""

    D_학종고2 = "D_학종고2"
    """D 학종 고2 — v1.5·세특/자유연구."""

    E_홈스쿨링영재 = "E_홈스쿨링영재"
    """E 홈스쿨링 영재 — v2.0·가치 최대."""


# ──────────────────────────────────────────────────────────────────────────
# 시각자료 (§3.1 visual_type_enum 주석: 그래프/도형/표/좌표평면)
# ──────────────────────────────────────────────────────────────────────────
class VisualType(str, Enum):
    """시각자료 유형 — §3.1 `visual_type_enum` 주석(그래프/도형/표/좌표평면)."""

    그래프 = "그래프"
    도형 = "도형"
    표 = "표"
    좌표평면 = "좌표평면"


# ──────────────────────────────────────────────────────────────────────────
# 저작권·생성 이력 (§13.2 license_enum·§10.1 generation_type_enum)
# ──────────────────────────────────────────────────────────────────────────
class LicenseType(str, Enum):
    """콘텐츠 라이선스 — §13.2 `license_enum` 값 그대로(영어).

    법적 메모: 본문을 가진 문제의 지배 license는 `WHYMATH_GENERATED`. `EBS_LICENSED`·
    (관련) `ORIGINAL`은 공식 제휴(Phase 3+) 전까지 미사용(MEMORY 2026-05-28).
    license/generation_type 강제는 ContentProvenance(슬라이스 2) 소관.
    """

    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    """공개 자료(평가원 공개 — 단, 본문 영리사용은 별도 금지)."""

    EBS_LICENSED = "EBS_LICENSED"
    """EBS 라이선스 — 공식 제휴 전까지 미사용."""

    AIHUB_OPEN = "AIHUB_OPEN"
    """AIHub 공개 데이터셋."""

    WHYMATH_GENERATED = "WHYMATH_GENERATED"
    """자체 생성 — 저작권 WhyMath. 본문 보유 문제의 지배 license."""

    USER_GENERATED = "USER_GENERATED"
    """사용자 자작."""

    THIRD_PARTY_LICENSED = "THIRD_PARTY_LICENSED"
    """사설 모의고사 협업(제휴)."""


class GenerationType(str, Enum):
    """콘텐츠 생성·변형 단계 — §10.1 `generation_type_enum` 값 그대로(영어)."""

    ORIGINAL = "ORIGINAL"
    """원본 그대로 — 본문 보유 전제이므로 공식 제휴 전까지 미사용(MEMORY 2026-05-28)."""

    VARIANT_NUMBER = "VARIANT_NUMBER"
    """숫자만 변형."""

    VARIANT_STRUCTURE = "VARIANT_STRUCTURE"
    """구조 변형."""

    VARIANT_CONTEXT = "VARIANT_CONTEXT"
    """맥락(조건) 변형."""

    COMPOSED = "COMPOSED"
    """여러 문제 결합."""

    FULLY_GENERATED = "FULLY_GENERATED"
    """AI 완전 생성."""


# ──────────────────────────────────────────────────────────────────────────
# 검수 상태 (§3.1 review_status_enum 주석: pending/approved/rejected)
# ──────────────────────────────────────────────────────────────────────────
class ReviewStatus(str, Enum):
    """검수 상태 — §3.1 `review_status_enum` 주석(pending/approved/rejected).

    §13.3: 모든 `problem`은 `review_status = approved` 후 노출.
    """

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# ──────────────────────────────────────────────────────────────────────────
# 풀이 단계·문항 관계 (§3.2 step_type_enum·relation_type_enum)
# ──────────────────────────────────────────────────────────────────────────
class StepType(str, Enum):
    """풀이 단계 유형 — §3.2 problem_step.step_type_enum.

    값: 조건해석/케이스분류/그래프스케치/계산/검산.
    """

    조건해석 = "조건해석"
    케이스분류 = "케이스분류"
    그래프스케치 = "그래프스케치"
    계산 = "계산"
    검산 = "검산"


class RelationType(str, Enum):
    """문항 간 관계 — §3.2 `problem_relation.relation_type_enum`(변형/유사/선수/심화/대조)."""

    변형 = "변형"
    유사 = "유사"
    선수 = "선수"
    심화 = "심화"
    대조 = "대조"


# ──────────────────────────────────────────────────────────────────────────
# 개념 그래프 (§4.2 concept 도메인 인라인 DDL — 4종)
# ──────────────────────────────────────────────────────────────────────────
# §14.3에 별도 `CREATE TYPE`이 없어 §4.2 DDL의 컬럼 인라인 주석을 정본으로 채택한다
# (slice1 ExamType/Subject가 §3.1 컬럼 주석을 정본으로 삼은 선례와 동일). ConceptLevel만
# 한글 값(Persona처럼 한글 식별자 허용), 나머지 3종은 영어 값.
class ConceptLevel(str, Enum):
    """개념 노드 계층 — §4.2 `concept_level_enum`(L309 주석: 단원/소단원/세부개념).

    3계층 위계(단원 > 소단원 > 세부개념). 값·식별자 모두 한글(`Persona` 선례).
    use_enum_values=True 직렬화 시 한글 값이 그대로 보존된다(예: level="단원").
    """

    단원 = "단원"
    소단원 = "소단원"
    세부개념 = "세부개념"


class CognitiveType(str, Enum):
    """개념의 인지 유형 — §4.2 `cognitive_type_enum`(L320-321, 영어 5종).

    한 개념이 여러 유형을 가질 수 있어 `concept.cognitive_type`은 배열이다.
    """

    DEFINITION = "DEFINITION"
    """정의 — 수학적 개념의 엄밀한 규정."""

    THEOREM = "THEOREM"
    """정리 — 증명되는 명제(예: 미적분학의 기본정리)."""

    TECHNIQUE = "TECHNIQUE"
    """기법 — 계산·풀이 절차(예: 부분적분)."""

    PATTERN = "PATTERN"
    """패턴 — 반복되는 문제 구조·전형."""

    VISUAL_REASONING = "VISUAL_REASONING"
    """시각적 추론 — 그래프·도형 기반 사고."""


class EdgeType(str, Enum):
    """개념 간 관계(DAG 엣지) — §4.2 `edge_type_enum`(L345-350, 영어 5종)."""

    PREREQUISITE = "PREREQUISITE"
    """선수 — A를 알아야 B를 안다(A→B)."""

    COMPOSED_OF = "COMPOSED_OF"
    """구성 — A는 B,C,D로 이루어진다."""

    ANALOGOUS_TO = "ANALOGOUS_TO"
    """유사 — A와 B는 비슷한 사고를 요구한다."""

    EXTENDS = "EXTENDS"
    """확장 — A를 일반화하면 B가 된다."""

    CONTRASTS = "CONTRASTS"
    """대조 — A와 B는 혼동하기 쉽다."""


class ConceptRole(str, Enum):
    """문제 안에서 개념의 역할 — §4.2 `concept_role_enum`(L366-370, 영어 4종)."""

    PRIMARY = "PRIMARY"
    """핵심 개념 — 이 문제의 주된 개념."""

    SUPPORTING = "SUPPORTING"
    """보조 개념 — 계산 등에 필요한 부수 개념."""

    IMPLICIT = "IMPLICIT"
    """암묵적 사용 — 학생이 의식하지 못해도 쓰이는 개념."""

    TESTED = "TESTED"
    """평가 대상 개념 — 이 문제로 이해도를 측정하는 개념."""
