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
    """교육과정 버전 — §14.3 `curriculum_enum` 값 그대로(영어).

    **문항의 본질 속성 축(개정판 정합)이다 — Overlay 이관 대상 아님.** 개념 노드의
    curriculum은 Overlay(`CurriculumEntry`)로 뺐지만(rev `f3a4b5c6d7e8`·"개념은 영속·교육과정은
    Overlay"는 *개념 노드* 원칙), 문항(`Problem`)은 특정 개정판을 위해 저작된 *콘텐츠*라
    curriculum_version이 이중 진실이 아니라 문항 고유 속성이다. `Problem`이 유일 프로덕션
    소비자이며 L6 학교진도 게이트 ③(2015/2022 혼입 방지·`l6/school_progress/gating.py`)의
    살아있는 기준 — 실제로 Concept의 curriculum 제거가 안전했던 *전제*가 이 필드였다
    (게이팅이 Concept 아닌 Problem을 봄). 오등록 상환 판정 2026-07-02(MEMORY) — 제거·Overlay
    이관 기각.
    """

    REVISION_2009 = "2009_REVISION"
    REVISION_2015 = "2015_REVISION"
    REVISION_2022 = "2022_REVISION"


class Subject(str, Enum):
    """과목 — §3.1 `subject_enum` 주석(공통/미적분/확통/기하/인공지능수학).

    §14.3에 별도 `CREATE TYPE`이 없어 DDL 컬럼 주석(L139)을 정본으로 채택한다.

    **수학 교과 한정**(실체는 수능 선택과목 축) — 타 과목(물리 등) 값 ADD VALUE 금지(축 혼동
    영구화). 교과 축은 향후 `Problem.subject_area`로 별도 신설한다
    (docs/architecture/subject_expansion_readiness.md §1·§8 보류 대장, 트리거: 물리 문항 첫 적재).
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
    """문항 형식 — §3.1 `question_format_enum`(기존 4종) + P3a 10유형 체계 확장(6종 추가).

    배경(P3a): Kiki 확정 10유형 문항 체계를 도입하되, *기존 4종 PG 라벨은 그대로 보존*한다
    (기존 행 하위호환·`ALTER TYPE ... ADD VALUE`로 6종만 추가). 약어(영문)↔PG 라벨(한글)
    매핑은 아래와 같다. 약어는 *문서/코드 식별용 표기*일 뿐 enum 멤버명/값은 한글이다
    (기존 컨벤션 — Persona·SchoolType처럼 한글 값 보존, use_enum_values=True 직렬화 시
    한글 라벨 유지).

      약어    PG 라벨(=멤버명=값)   의미
      ─────   ──────────────────   ───────────────────────────────────────────
      MC      객관식               5지선다 등 표준 객관식 (기존)
      SA      단답형               단답(숫자·식 한 개) (기존)
      ST      합답형               ㄱㄴㄷ 구조화·단계형 합답 (기존·약어 ST=structured)
      EX      서술형               서술·논술형 (기존)
      MC-D    객관식진단           객관식 + 오답진단(distractor가 오개념을 진단) (신규)
      FB      빈칸형               빈칸 채우기(fill-in-the-blank) (신규)
      MN      짝짓기형             짝짓기/연결(matching) (신규)
      GR      그래프형             그래프 작도(graphing) (신규)
      PF      수행형               수행평가(performance) (신규)
      RT      재수전용형           재수(N수)전용 유형(retake-only) (신규)

    ST↔합답형 매핑 주의: 약어 ST(structured·단계형)는 한국 수능의 *합답형*(ㄱㄴㄷ 보기 중
    옳은 것의 조합을 고르는 구조화 문항)에 자연 대응한다 — 기존 라벨 '합답형'을 보존하는
    가장 적합한 매핑이다(`SignaturePattern.COMPOUND_CHOICES`(합답형 ㄱㄴㄷ)와 정합).
    """

    # ===== 기존 4종 (PG 라벨 보존 — 기존 행 하위호환) =====
    객관식 = "객관식"
    """MC — 5지선다 등 표준 객관식."""

    단답형 = "단답형"
    """SA — 단답(숫자·식 한 개)."""

    합답형 = "합답형"
    """ST — ㄱㄴㄷ 구조화·단계형 합답(약어 ST=structured)."""

    서술형 = "서술형"
    """EX — 서술·논술형."""

    # ===== P3a 신규 6종 (ALTER TYPE ADD VALUE로 추가) =====
    객관식진단 = "객관식진단"
    """MC-D — 객관식 + 오답진단(distractor가 오개념을 진단). 오답 선지가 오개념 후보를 가른다."""

    빈칸형 = "빈칸형"
    """FB — 빈칸 채우기(fill-in-the-blank)."""

    짝짓기형 = "짝짓기형"
    """MN — 짝짓기/연결(matching)."""

    그래프형 = "그래프형"
    """GR — 그래프 작도(graphing). 학생이 그래프를 직접 그려 답한다."""

    수행형 = "수행형"
    """PF — 수행평가(performance). 과정·산출물 기반 평가."""

    재수전용형 = "재수전용형"
    """RT — 재수(N수)전용 유형(retake-only). 페르소나 B·C 대상 고난도 변형."""


class AnswerFormat(str, Enum):
    """정답 형식 — §3.1 `answer_format_enum` 주석(자연수/분수/실수/식)."""

    자연수 = "자연수"
    분수 = "분수"
    실수 = "실수"
    식 = "식"


# ──────────────────────────────────────────────────────────────────────────
# Bloom 인지 수준 (P3a — 문항 메타 분류 축)
# ──────────────────────────────────────────────────────────────────────────
class BloomLevel(str, Enum):
    """Bloom 개정 분류(인지 수준) 6단계 — P3a 문항 메타 축(`Problem.bloom_level`).

    Anderson·Krathwohl(2001) 개정 Bloom taxonomy의 인지 과정 6단계(REMEMBER <
    UNDERSTAND < APPLY < ANALYZE < EVALUATE < CREATE 순의 위계). 문항이 요구하는 *인지
    수준*을 태그해 난이도 5축(diff_*)·인지 유형(`CognitiveType`)과 다른 축으로 분류한다.

    멤버명·값 모두 영어(국제 표준 분류명 — `SignaturePattern`·`CognitiveType`의 영어 값
    선례). use_enum_values=True 직렬화 시 영어 값 보존(예: bloom_level="ANALYZE").
    """

    REMEMBER = "REMEMBER"
    """기억 — 사실·용어·공식을 회상한다(가장 낮은 인지 수준)."""

    UNDERSTAND = "UNDERSTAND"
    """이해 — 개념의 의미를 설명·해석한다."""

    APPLY = "APPLY"
    """적용 — 절차·원리를 새 상황에 적용한다."""

    ANALYZE = "ANALYZE"
    """분석 — 구성요소·관계를 분해해 구조를 파악한다."""

    EVALUATE = "EVALUATE"
    """평가 — 기준에 따라 판단·비판한다."""

    CREATE = "CREATE"
    """창안 — 새 해법·구성을 만들어낸다(가장 높은 인지 수준)."""


# ──────────────────────────────────────────────────────────────────────────
# 채점 유형 (P3a — 문항 메타 분류 축)
# ──────────────────────────────────────────────────────────────────────────
class ScoringType(str, Enum):
    """채점 유형 — P3a 문항 메타 축(`Problem.scoring_type`, 한글 5종).

    문항을 *어떻게 채점하는가*를 분류한다(문항 형식 `QuestionFormat`과 다른 축 — 같은
    객관식이라도 정오답/진단 채점이 갈릴 수 있다). 한글 값(한글 식별자 그대로 — Persona·
    ScoringType 선례). use_enum_values=True 직렬화 시 한글 값 보존(예: scoring_type="루브릭").
    """

    정오답 = "정오답"
    """정오답 — 맞음/틀림 이분 채점(0/1)."""

    진단 = "진단"
    """진단 — 오답 선지로 오개념을 진단(점수보다 진단 신호가 목적)."""

    부분점수 = "부분점수"
    """부분점수 — 단계·요소별 부분 점수(서술·합답형)."""

    시간 = "시간"
    """시간 — 풀이 시간 기반 평가(속도·실전 감각)."""

    루브릭 = "루브릭"
    """루브릭 — 평가 기준표(rubric) 기반 다차원 채점(수행평가)."""


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
# 시각화 양식 (슬라이스 87: 교수학적 표현 형식 — 개념↔양식 매핑 통제 어휘)
# ──────────────────────────────────────────────────────────────────────────
class VisualizationStyle(str, Enum):
    """시각화 *양식* — 개념을 가장 잘 드러내는 *교수학적 표현 형식*.

    `VisualType`(그래프/도형/표/좌표평면 — 문제 콘텐츠 *태그*)·05 §5.2 `Visualization.type`
    (interactive_graph_2d 등 — *렌더 기술*)과는 **다른 축**. "삼각함수→단위원·확률→수형도·
    정수→수직선"처럼 개념·성취기준에 권장되는 *표상 형식*을 통제 어휘로 정의한다(슬라이스 88의
    `Concept.recommended_visual_styles` 매핑에 사용·슬라이스 87은 어휘만 도입).

    값(한글)은 슬라이스 88에서 PostgreSQL enum 타입이 되어 *추가는 쉬우나 제거는 어렵다* —
    v1은 한국 중·고 표준 표상 위주로 보수적 선정(후속 ADD VALUE로 확장).
    """

    수직선 = "수직선"
    """수직선 — 정수·유리수·절댓값·부등식 해의 위치와 순서."""

    함수그래프 = "함수그래프"
    """좌표평면 함수 그래프 — 일차·이차·다항·유리·무리·지수·로그·삼각함수의 개형."""

    단위원 = "단위원"
    """단위원 — 호도법·삼각비·삼각함수의 정의와 주기성."""

    평면도형 = "평면도형"
    """평면도형 — 작도·합동·닮음·원의 성질 등 유클리드 도형."""

    입체도형 = "입체도형"
    """입체도형·전개도 — 겉넓이·부피·정사영·단면."""

    넓이모델 = "넓이모델"
    """넓이 모델 — 분배법칙·곱셈공식·확률·정적분을 직사각형 넓이로 표상."""

    수형도 = "수형도"
    """수형도(나무 그림) — 경우의 수·조건부확률의 분기 열거."""

    부등식영역 = "부등식영역"
    """부등식 영역 — 연립부등식 해·영역·선형계획법의 색칠 영역."""

    벡터도 = "벡터도"
    """벡터 다이어그램 — 평면·공간 벡터의 합성·내적·위치 화살표."""

    점화도 = "점화도"
    """수열·점화 다이어그램 — 등차·등비·점화식의 반복 구조."""

    통계차트 = "통계차트"
    """통계 차트 — 막대·꺾은선·원그래프·히스토그램·도수분포."""

    산점도 = "산점도"
    """산점도 — 두 변량의 상관관계·회귀 직선."""

    상자그림 = "상자그림"
    """상자그림(box plot) — 사분위수·중앙값·산포·이상치."""

    분포곡선 = "분포곡선"
    """분포곡선 — 정규분포·표준화·이항분포의 정규근사."""

    접선도함수 = "접선도함수"
    """접선·도함수 시각화 — 미분계수(접선 기울기)·도함수 개형."""

    확률시뮬레이션 = "확률시뮬레이션"
    """확률 시뮬레이션 — 시행 반복·누적 상대도수(통계적 확률·대수의 법칙)."""


# ──────────────────────────────────────────────────────────────────────────
# 시각화 가능성 4분류 (구축 플레이북 Part 5 — 개념을 "어떻게/그려야 하는가"로 판별)
# ──────────────────────────────────────────────────────────────────────────
class Visualizability(str, Enum):
    """개념의 *시각화 가능성* 4분류 — 구축 플레이북 Part 5-1(직접/동적/부분/추상).

    핵심 원칙: **모든 개념이 똑같이 시각화되지 않는다**. 네 분류는 "그릴 수 있는가"가 아니라 개념이
    학생 인지에서 *어떤 방식으로 파악되는가*(인지 행동)로 나뉜다 — 어느 것도 "시각화 불가"가 아니라
    *각기 다른 시각화 전략*을 요구한다(설계 정본 `05b_visualization_classification.md`).
    억지 리터럴 시각화는 오개념을 유발하므로("그릴 수 있다 ≠ 교육적으로 좋다"), 분류가 렌더 전략을
    가른다. `VisualizationStyle`(어떤 양식)·`VisualizationType`(어떤 렌더 기술)과는 **다른 축**이다.

    **표면 표현이 아니라 인지 행동(cognitive action) 기준으로 정의한다**(플레이북 공통 문장).
    `use_enum_values=True` 모델에서 값(한글)이 그대로 직렬화된다.
    """

    직접 = "직접"
    """직접 시각화 가능 — 형태 자체가 보인다(도형·함수그래프·좌표·벡터). 정지된 한 장이 핵심 인지를
    *즉시* 드러내 조작 없이 이해가 성립한다. 렌더 전략: Geometry2D(정적)."""

    동적 = "동적"
    """동적 시각화 가능 — 변화 과정을 표현해야 한다(극한·미분·적분·함수변환). **AI 수학교육의 핵심
    영역**: 한국 학생이 가장 어려워하고 정적 그림으론 이해가 안 된다. 렌더: 애니메이션·슬라이더."""

    부분 = "부분"
    """부분 시각화 가능 — 일부 의미만 그림이 담는다(확률·벡터공간·복소수·수렴). 렌더 전략:
    AnalogyVisual(비유 시각화 + *coverage 표시* — 무엇이 안 담기는지 정직 노출)."""

    추상 = "추상"
    """추상적이라 어려움 — 구조 자체가 추상적이다(군론·위상·범주론·논리). 리터럴 그래프는 거짓
    구체성으로 오개념을 부른다. 렌더 전략: StructureGraph(구조 그래프·**메타포 중심**)."""


# ──────────────────────────────────────────────────────────────────────────
# 시각화 렌더 기술 (슬라이스 90: 05 §5.2 Visualization.type — 선언적 명세 렌더 도구 축)
# ──────────────────────────────────────────────────────────────────────────
class VisualizationType(str, Enum):
    """시각화 *렌더 기술* — 05 §5.2 `Visualization.type` 정본(4종·영문 값).

    `VisualType`(그래프/도형/표 — 문제 콘텐츠 *태그*)·`VisualizationStyle`(단위원·수형도 —
    개념 권장 *교수학적 양식*·슬라이스 87)과는 **다른 축**: 이 enum은 선언적 명세를 *어떤
    렌더 도구로 그리는가*를 규정한다(L5 ④ 국소 비상구가 type을 보고 D3/Plotly/three.js/Manim
    선택, 05 §5.2). 값은 영문(05 §5.2 표기 그대로).

    `animation_prerendered`만 기존 Manim 산출물(조작 불가)이고, 나머지 3종이 학생 파라미터
    조작이 가능한 PRD 신규 선언적 명세(05 §5.2). 슬라이스 89 "표현≠의미"의 렌더 기술 축.
    """

    interactive_graph_2d = "interactive_graph_2d"
    """2D 함수·관계 그래프 — 학생이 파라미터 조작(슬라이더·드래그). 렌더: D3.js/Plotly/Desmos."""

    interactive_surface_3d = "interactive_surface_3d"
    """3D 곡면·입체 — 회전·단면 조작. 렌더: three.js."""

    simulation_probabilistic = "simulation_probabilistic"
    """확률 시뮬레이션 — 시행 반복·누적. 렌더: D3.js/Plotly."""

    animation_prerendered = "animation_prerendered"
    """미리 렌더된 사고 과정 애니메이션(조작 불가). 렌더: Manim."""


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
# 추론 유형 (MATH DSL 진화 — 교육 추론 엔진 §2.2 · SolutionStep.reasoning_type)
# ──────────────────────────────────────────────────────────────────────────
class ReasoningType(str, Enum):
    """풀이 *스텝 단위* 추론 유형 — 폐쇄 7종(`SolutionStep.reasoning_type`).

    근거: `docs/architecture/math_dsl_evolution.md` §2.2(교육 추론 엔진 — 권장 1순위).
    불투명한 `SolutionStep.content`(자연어+LaTeX 문자열) 옆에 "이 스텝이 어떤 추론을
    수행하는가"를 태그해, "왜 이 변형이 정당한가"를 *기계가 읽게* 한다(엔진 정체성의 첫 벽돌).

    축 구분 주의: `approach_type`(SolutionPath — 풀이 *전체* 6유형: 대수/기하/조합/귀납/
    시각/역방향)과는 다른 축이다. ReasoningType은 *한 스텝*의 추론 유형이다(한 대수적 풀이
    안에서도 스텝마다 치환·사례분류·귀납이 섞일 수 있다).

    ⚠️ 폐쇄집합(6~8종) — *제거는 어렵고 추가는 신중해야* 한다(무한 추론 온톨로지 금지·
    math_dsl_evolution §2.2 금기). 유형 무한 세분화는 유지 불가·과설계다. 완전 형식논리
    증명 유형은 여기 두지 않는다(경계된 Tier3 Lean 위임·§2.9).

    멤버명·값 모두 영어(국제 인지 과정 어휘 — `BloomLevel`·`CognitiveType` 선례).
    use_enum_values=True 직렬화 시 영어 값 보존(예: reasoning_type="DEDUCTION").
    """

    DEDUCTION = "DEDUCTION"
    """연역 — 정리·정의에서 논리적으로 도출한다."""

    SUBSTITUTION = "SUBSTITUTION"
    """치환 — 변수·식을 대입해 변형한다."""

    CASE_SPLIT = "CASE_SPLIT"
    """사례분류 — 조건에 따라 경우를 나눈다(케이스 분석)."""

    INDUCTION = "INDUCTION"
    """귀납 — 패턴·수학적 귀납법으로 일반화한다."""

    TRANSFORMATION = "TRANSFORMATION"
    """동치변형 — 등식·부등식을 동치로 재작성한다(동치 판정 권위는 SymPy·§2.1)."""

    HEURISTIC = "HEURISTIC"
    """휴리스틱 — 통찰·추측으로 나아간다(검증 미완일 수 있음·정직 표시)."""

    BACKWARD = "BACKWARD"
    """역방향 — 결론에서 거꾸로 추론한다."""


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


class BehaviorArea(str, Enum):
    """행동영역(cognitive action) — SkillNode의 폐쇄 6종 축(리치 Part 2 Phase 2a·2026-07-03 확정).

    개념이 *어떻게* 작동하는지(행동)의 축으로, 개념(무엇)과 직교한다. `skill_node.behavior_area`
    (PG native `behavior_area_enum`)의 백킹이며, data-pipeline `data_pipeline.skill_graph.models
    .BehaviorArea`와 **값이 정확히 일치**한다(정합 테스트 동결). 폐쇄 6종 — 확장은 ADR 갱신 전제
    (무분별 증식 금지·`test_skill_governance` 동결).
    """

    COMPUTE = "COMPUTE"
    """계산실행 — 절차·연산 수행(예: 다항식 나눗셈)."""

    TRANSFORM = "TRANSFORM"
    """식변형 — 표현을 등가 형태로 변형(예: 인수분해)."""

    INTERPRET = "INTERPRET"
    """조건해석 — 주어진 조건·문제를 수학 구조로 해석."""

    REPRESENT = "REPRESENT"
    """표상/표현 — 그래프·도형·다중표현 전환."""

    REASON = "REASON"
    """추론 — 연역·논리적 근거 전개."""

    VERIFY = "VERIFY"
    """검증 — 결과 점검·반례·타당성 확인(Polya 반성)."""


class EdgeType(str, Enum):
    """개념 간 관계(DAG 엣지) — §4.2 `edge_type_enum`(L345-350, 영어 6종)."""

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

    TRIGGERS_DISTRACTOR = "TRIGGERS_DISTRACTOR"
    """오개념 유발 선택지 — distractor(객관식 오답 선지)가 misconception을 유발한다(슬108 어휘).

    이번 슬라이스는 *어휘만* 선언하고 `concept_edge` 적재는 하지 않는다 — `concept_edge`는
    concept→concept(UUID FK)인데 misconception은 아직 그래프 노드가 아니라 카탈로그(kebab id)다.
    노드화 전까지 distractor→misconception 매핑은 op-code 카탈로그
    (`l4/misconception/distractor.py`)가 보유한다."""


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


# 문제가 *평가하는* 개념 역할(PRIMARY·TESTED) — BKT 숙달 갱신·IRT θ 추정·약점 가중의 단일
# 대상 집합(보조 SUPPORTING·암묵 IMPLICIT 제외). L2(mastery_tracking·ability_estimation·진단)·
# L5(me)가 공유하는 단일 출처(slice 84에 분산 정의 통합).
ASSESSED_ROLES: tuple[ConceptRole, ...] = (ConceptRole.PRIMARY, ConceptRole.TESTED)


# ──────────────────────────────────────────────────────────────────────────
# 학생 학적·트랙 (§5.1 user_profile 인라인 DDL §14.3 school_type_enum — 슬라이스 4)
# ──────────────────────────────────────────────────────────────────────────
# §14.3에 `CREATE TYPE`이 있는 것은 school_type_enum 하나뿐이고(L1205-1209, 정본·완전),
# 나머지 트랙·전공·디바이스·구독·접근성 enum은 §5.1 user_profile DDL의 컬럼 인라인 주석을
# 정본으로 채택한다(slice1 ExamType/Subject가 §3.1 컬럼 주석을 정본으로 삼은 선례 동일).
# 한글 값은 한글 식별자 그대로(Persona·ConceptLevel 선례), 영어 값은 영어 그대로.
#
# ⚠️ gender_enum·region_enum은 *enum으로 만들지 않는다*. §14.3에 정의가 없고 §5.1 DDL 주석도
# 불완전하다(gender="선택 입력"으로 값 미기재, region="강남/대치/지방/..."로 명시적 미완결).
# v1.1 student_profile.schema.yaml가 region을 시도교육청 코드 문자열로 모델링한 점·미성년
# 민감정보라 닫힌 카테고리 강제가 부적절한 점을 고려해 user_profile에서 `str | None`으로
# 둔다(닫힌 enum 날조 회피). 추후 Kiki가 값을 확정하면 enum으로 승격한다.
class SchoolType(str, Enum):
    """학교 유형 — §14.3 `school_type_enum`(L1205-1209) 값 그대로(한글, 12종).

    §14.3에 유일하게 완전한 `CREATE TYPE`이 있는 학적 enum이다(자사고·대안학교는
    전국/광역·인가/비인가로 세분). use_enum_values=True 직렬화 시 한글 값 보존
    (예: school_type="일반고").
    """

    일반고 = "일반고"
    자사고_전국 = "자사고_전국"
    자사고_광역 = "자사고_광역"
    외고 = "외고"
    국제고 = "국제고"
    영재고 = "영재고"
    과학고 = "과학고"
    특성화고 = "특성화고"
    대안학교_인가 = "대안학교_인가"
    대안학교_비인가 = "대안학교_비인가"
    홈스쿨링 = "홈스쿨링"
    검정고시 = "검정고시"


class TrackType(str, Enum):
    """입시 트랙 — §5.1 `track_type_enum`(L455 주석) 값 그대로(한글 7종 + MMI 영어).

    한 학생이 여러 트랙을 병행할 수 있어 `user_profile.track_type`은 배열이다.
    """

    정시 = "정시"
    수시학종 = "수시학종"
    수시교과 = "수시교과"
    수시논술 = "수시논술"
    MMI = "MMI"
    """다중미니면접(Multiple Mini Interview) — 의대 등 면접 전형."""

    특기자 = "특기자"
    농어촌 = "농어촌"
    특례 = "특례"


class MajorCategory(str, Enum):
    """목표 전공 계열 — §5.1 `major_category_enum`(L459 주석) 값 그대로(한글 8종)."""

    의대 = "의대"
    약대 = "약대"
    치대 = "치대"
    한의대 = "한의대"
    이공계 = "이공계"
    인문계 = "인문계"
    경상계 = "경상계"
    예체능 = "예체능"


# ──────────────────────────────────────────────────────────────────────────
# 학습 환경 (§5.1 user_profile device_enum·note_app_enum)
# ──────────────────────────────────────────────────────────────────────────
class Device(str, Enum):
    """주 사용 기기 — §5.1 `device_enum`(L473 주석) 값 그대로(아이패드/iPhone/안드로이드폰/PC)."""

    아이패드 = "아이패드"
    # 멤버명이 곧 정본 값("iPhone")이라 Apple 제품명 카멜케이스를 그대로 둔다(N815 억제).
    iPhone = "iPhone"  # noqa: N815
    안드로이드폰 = "안드로이드폰"
    PC = "PC"


class NoteApp(str, Enum):
    """필기 앱 — §5.1 `note_app_enum`(L475 주석) 값 그대로(굿노트/노타빌리티/플렉슬/없음, 한글)."""

    굿노트 = "굿노트"
    노타빌리티 = "노타빌리티"
    플렉슬 = "플렉슬"
    없음 = "없음"


# ──────────────────────────────────────────────────────────────────────────
# 결제·접근성 (§5.1 user_profile subscription_tier_enum·accessibility_enum)
# ──────────────────────────────────────────────────────────────────────────
class SubscriptionTier(str, Enum):
    """구독 티어 — §5.1 `subscription_tier_enum`(L490 주석) 값 그대로(free/basic/premium, 영어)."""

    free = "free"
    basic = "basic"
    premium = "premium"


class Accessibility(str, Enum):
    """접근성 필요 — §5.1 `accessibility_enum`(L501 주석) 값 그대로(한글 5종, 특성 #47).

    한 학생이 여러 접근성 필요를 가질 수 있어 `user_profile.accessibility_needs`는 배열이다.
    """

    시각약자 = "시각약자"
    색약 = "색약"
    큰글씨 = "큰글씨"
    음성안내 = "음성안내"
    시간연장 = "시간연장"


# ──────────────────────────────────────────────────────────────────────────
# 학습 활동 (§6.1 learning_session·problem_attempt·attempt_event 인라인 DDL — 3종)
# ──────────────────────────────────────────────────────────────────────────
# §14.3에 별도 `CREATE TYPE`이 없어 §6.1 DDL의 컬럼 인라인 주석을 정본으로 채택한다
# (slice1 ExamType/Subject·slice3 ConceptLevel이 컬럼 주석을 정본으로 삼은 선례 동일).
# 세 enum 모두 한글 값(한글 식별자 그대로 — Persona·ConceptLevel 선례).
class SessionType(str, Enum):
    """학습 세션 유형 — §6.1 `session_type_enum`(L602-603, 한글 5종).

    use_enum_values=True 직렬화 시 한글 값 보존(예: session_type="자유학습").
    """

    자유학습 = "자유학습"
    실전모의고사 = "실전모의고사"
    단원집중 = "단원집중"
    약점보완 = "약점보완"
    AI추천 = "AI추천"


class AttemptMode(str, Enum):
    """문항 풀이 방식 — §6.1 `attempt_mode_enum`(L635-636, 한글 4종).

    특성 #96(used_socratic vs used_solution_view)으로 콴다 대비 차별을 측정한다.
    """

    자유풀이 = "자유풀이"
    Socratic대화 = "Socratic대화"
    힌트제공 = "힌트제공"
    풀이공개 = "풀이공개"


class EventType(str, Enum):
    """학생 풀이 단계 이벤트 — §6.1 `event_type_enum`(한글 8종 + 검산결과 + 힌트제공 + 시각화조작).

    실시간 분석용(TimescaleDB hypertable `attempt_event`)의 이벤트 종류.

    페이로드 계약(invariant ⑫): *생산되는* 6종(검산결과·힌트제공·시각화조작·막힘·힌트요청·답입력)의
    `event_data` 모양은 `schema/event_data_contract.py`(EVENT_DATA_CONTRACT)가 단일 진실원으로
    고정한다. 나머지 5종(문제읽기·조건분석·그래프그리기·계산·지움)은 생산자가 아직 0이라 계약
    면제(휴면)다. `막힘`·`힌트요청`·`답입력`은 S3-16에서 휴면→생산으로 소생됐다(신규 enum 값
    추가 아님 — 기존 3종의 생산자를 `api/coach.py`에 배선).
    """

    문제읽기 = "문제읽기"
    조건분석 = "조건분석"
    그래프그리기 = "그래프그리기"
    계산 = "계산"
    지움 = "지움"
    막힘 = "막힘"
    """WH-1 답 미루기 5회+ 막힘 임계 이벤트(S3-16 소생)·event_data={turn_count:int}.

    `l4.hint_deferral.is_stuck_turn_count`(turn_count≥5)가 True일 때만 스테이트풀 coach가
    적재한다 — `decide_hint_level`의 1번 규칙(5회+ 막힘→hint_level 최소 3)과 *같은 임계*를
    관측 신호로 노출할 뿐 결정 로직 자체는 건드리지 않는다.
    """

    힌트요청 = "힌트요청"
    """학생이 *요청*한 도움 demand 이벤트(S3-16 소생)·event_data={mode, persona}(선택 태그만).

    `l4.hint_deferral.is_answer_demand`(답 요구 토큰 포함)가 True일 때만 적재한다. `힌트제공`
    (AI가 *제공*한 supply·hint_level)과 의미가 다르다 — 지표 ⑫(도움 요청/제공 비)는 이 둘의
    개수 비다.
    """

    답입력 = "답입력"
    """학생 응답 제출의 서버 측 지연 이벤트(S3-16 소생)·event_data={server_latency_ms:int|None}.

    직전 학생 턴(server 기준 spoken_at)과 이번 제출 시각의 차 — 서버 시각 차이므로 클라 신뢰가
    불필요하고 조작 불가하다. 이전 학생 턴이 없으면(새 dialogue의 첫 턴) 기준선이 없어 적재하지
    않는다(날조 회피) — `append_turns`에서만 생산된다.
    """

    검산결과 = "검산결과"
    """WH-1 검산(verify) 결과 이벤트·event_data={passed:bool, error_kind}.

    binary 검산(3-state 아님): passed=거짓 수치관계 *미적발*(통과)·아니면 적발.
    스테이트풀 coach가 풀이 제출 턴에만 적재한다.
    """

    힌트제공 = "힌트제공"
    """WH-1 도움 감소 곡선 이벤트(지표 ⑤)·event_data={hint_level:int}(1~4·1=가장 은근/4=전체 풀이).

    *supply*(AI가 제공한 hint_level) 신호다 — `힌트요청`(학생이 *요청*한 demand)과 의미가 다르다.
    도움 감소 곡선은 AI가 *제공한* 노출량(graded 1~4)의 시간 추세이므로 supply가 정본이다.
    스테이트풀 coach가 매 응답 턴에 `decision.hint_level`을 그대로 적재한다(재계산 없음).
    `AttemptMode.힌트제공`(attempt_mode_enum·풀이 방식)과는 *다른 enum*이니 혼동 주의.
    """

    시각화조작 = "시각화조작"
    """L5 시각화의 *탐구적* 조작 이벤트(슬라이더·3D 식·확률 시뮬)·슬라이스 96-J.

    event_data={interaction, payload, concept_id, scene_id, client_at}. `그래프그리기`(그래프를
    그려 *답함*)와 구분되는 *능동 탐구·메타인지* 신호다 — 약점개념 scene의 임베드 계산기에서
    학생이 파라미터·식을 바꿔 본질을 탐색하는 행동. 둘을 한 enum으로 뭉개면 L2 행동 지표가
    오염되므로 전용 라벨로 분리한다. 약점개념 흐름엔 problem/attempt가 없어 컨텍스트는
    concept_id/scene_id(event_data)로 싣고 attempt_id/problem_id는 NULL로 둔다(거짓 연결 금지).
    """


# ──────────────────────────────────────────────────────────────────────────
# Socratic 대화 (§7.1 dialogue·dialogue_turn 인라인 DDL — 5종)
# ──────────────────────────────────────────────────────────────────────────
# §14.3에 별도 `CREATE TYPE`이 없어 §7.1 DDL의 컬럼 인라인 주석을 정본으로 채택한다
# (위 활동 도메인·slice1·slice3 선례 동일). TurnRole만 영어 값(student/assistant/system),
# 나머지 4종은 한글 값(한글 식별자 그대로 — Persona·ConceptLevel 선례).
class Resolution(str, Enum):
    """Socratic 대화 종결 결과 — §7.1 `resolution_enum`(L710-711, 한글 5종).

    학생이 스스로 풀었는지·유도로 풀었는지·결국 풀이를 봤는지·포기했는지를 가른다.
    """

    학생자력해결 = "학생자력해결"
    Socratic유도성공 = "Socratic유도성공"
    힌트필요 = "힌트필요"
    풀이공개로종결 = "풀이공개로종결"
    포기 = "포기"


class TurnRole(str, Enum):
    """대화 턴 화자 — §7.1 `turn_role_enum`(L735, 영어 3종).

    student(학생)·assistant(AI)·system(시스템 메시지). 값·식별자 모두 영어.
    """

    student = "student"
    assistant = "assistant"
    system = "system"


class ContentType(str, Enum):
    """대화 턴 콘텐츠 형식 — §7.1 `content_type_enum`(L737, 한글 4종)."""

    텍스트 = "텍스트"
    수식 = "수식"
    이미지 = "이미지"
    혼합 = "혼합"


class SocraticStrategy(str, Enum):
    """Socratic 발문 전략 — §7.1 `socratic_strategy_enum`(L740-741, 한글 6종).

    AI 응답의 교수학적 전략(특성 #8/#18 조건확인·#21 단계분해).
    """

    조건확인 = "조건확인"
    예시제시 = "예시제시"
    반례제시 = "반례제시"
    단계분해 = "단계분해"
    유사문제 = "유사문제"
    그래프그리기제안 = "그래프그리기제안"


class StudentIntent(str, Enum):
    """학생 발화 의도 — §7.1 `student_intent_enum`(L747-748, 한글 5종).

    학생 턴을 분석해 분류한 의도(답시도/질문/막힘표현/포기/이해확인).
    """

    답시도 = "답시도"
    질문 = "질문"
    막힘표현 = "막힘표현"
    포기 = "포기"
    이해확인 = "이해확인"


# ──────────────────────────────────────────────────────────────────────────
# 학습 진단 (§8.1 assessment 인라인 DDL — 2종)
# ──────────────────────────────────────────────────────────────────────────
# §14.3에 별도 `CREATE TYPE`이 없어 §8.1 DDL의 컬럼 인라인 주석을 정본으로 채택한다
# (slice1 ExamType/Subject·slice3 ConceptLevel·slice5 SessionType이 컬럼 주석을 정본으로
# 삼은 선례 동일). 두 enum 모두 한글 값(한글 식별자 그대로 — Persona·ConceptLevel 선례).
class AssessmentType(str, Enum):
    """진단 평가 유형 — §8.1 `assessment_type_enum`(L783-784, 한글 5종).

    use_enum_values=True 직렬화 시 한글 값 보존(예: assessment_type="단원진단").

    ⚠️ 식별자 주의: `D-100예측`은 하이픈이 있어 Python 식별자로 쓸 수 없다. 따라서 멤버명만
    언더스코어로 두고(`D_100예측`) *값은 하이픈 그대로*(`"D-100예측"`)다 — 값이 정본이라
    직렬화·역직렬화는 `"D-100예측"`이 오간다. 나머지 4종은 값=식별자 동일.
    """

    초기진단 = "초기진단"
    주간진단 = "주간진단"
    단원진단 = "단원진단"
    실전모의고사 = "실전모의고사"
    D_100예측 = "D-100예측"
    """D-100 합격 예측 진단(특성 #86). 식별자만 언더스코어, 값은 하이픈 그대로(정본)."""


class MentalPhase(str, Enum):
    """입시 멘탈·시간 관리 단계 — §8.1 `mental_phase_enum`(L810-811, 6종, 특성 #50).

    D-100 입시 코칭의 D-day 구간(수능 100일 전 이상 → 당일)과 평상시를 가른다. 값들이 이미
    식별자 안전(언더스코어·한글)이라 멤버명=값 동일(slice5 EventType처럼 변환 불필요).
    use_enum_values=True 직렬화 시 값 보존(예: mental_phase="D_100_50").
    """

    D_100_PLUS = "D_100_PLUS"
    """D-100 이상 — 수능 100일 전보다 더 남은 장기 구간."""

    D_100_50 = "D_100_50"
    """D-100~D-50 — 본격 실전 대비 진입."""

    D_50_30 = "D_50_30"
    """D-50~D-30 — 약점 집중 보완 구간."""

    D_30_7 = "D_30_7"
    """D-30~D-7 — 마무리·실전 감각 유지."""

    D_7_0 = "D_7_0"
    """D-7~D-day — 컨디션·멘탈 관리 최우선 구간."""

    평상시 = "평상시"
    """입시 D-day 코칭 대상이 아닌 평상시(예: 고1·고2 학기 중)."""


# ──────────────────────────────────────────────────────────────────────────
# 다국 커리큘럼 매트릭스 (v1.1 curriculum_entry.schema.yaml — 슬라이스 8a)
# ──────────────────────────────────────────────────────────────────────────
# v1.0 도메인 밖. v1.1에서 이식한 CurriculumEntry(같은 개념이 나라마다 몇 학년에·어떤
# 깊이로 다뤄지는지의 매트릭스 셀)가 *enum으로 명시한 두 필드*만 enum으로 만든다.
# YAML이 enum으로 명시한 것은 required_depth(4종)·license_id(5종)뿐이다.
#
# ⚠️ country_code·grade_band·cognitive_level 등은 enum으로 만들지 않는다. YAML이
# country_code를 ISO 3166-1 alpha-2(개방형 ~250개)+의사코드 'IMO'로 두고 "스키마는
# 풀스케일 수용"이라 명시했고(Phase 3 9~12개국 확장 대비), Phase 1 KR/US/IMO 범위
# 가드는 *데이터/파이프라인* 책임이지 모델 강제가 아니다. subject 류도 NCIC
# AchievementStandard.subject가 str인 것과 정합 → `str`로 둔다(slice4 gender/
# school_region이 닫힌 enum 날조를 회피해 str로 둔 방침과 동일).
class RequiredDepth(str, Enum):
    """국가 교육과정이 개념에 요구하는 깊이 — YAML `required_depth.enum`(영어 4종).

    awareness < procedural < conceptual < mastery 순의 깊이 위계. use_enum_values=True
    직렬화 시 영어 값 보존(예: required_depth="conceptual").
    """

    awareness = "awareness"
    """인지 — 개념을 접하고 존재를 안다(가장 얕은 깊이)."""

    procedural = "procedural"
    """절차 — 정해진 절차·계산을 수행할 수 있다."""

    conceptual = "conceptual"
    """개념 — 원리를 이해하고 맥락에 적용할 수 있다."""

    mastery = "mastery"
    """숙달 — 능숙하게 다루고 새 상황에 전이할 수 있다(가장 깊은 깊이)."""


class CurriculumLicense(str, Enum):
    """국가별 원천 자원 라이선스 매트릭스 키 — YAML `license_id.enum`(5종).

    셀 단위로 라이선스 의무를 추적한다(라이선스 미확인 국가는 셀을 만들지 않음 —
    licensing_safety.md 결정 트리).

    ⚠️ 식별자 주의: 값이 하이픈을 포함해(예 'KR-NCIC') Python 식별자로 쓸 수 없다. 따라서
    멤버명만 언더스코어로 두고(`KR_NCIC`) *값은 하이픈 그대로*(`"KR-NCIC"`)다 — 값이 정본
    이라 직렬화·역직렬화는 하이픈 값이 오간다(slice6 `AssessmentType.D_100예측` 선례 동일).
    use_enum_values=True 직렬화 시 하이픈 값 보존(예: license_id="KR-NCIC").
    """

    KR_NCIC = "KR-NCIC"
    """한국 2022 개정 교육과정 — 공공누리 1유형(상업·가공 OK, 출처 표시 필수)."""

    US_CCSS = "US-CCSS"
    """미국 Common Core — CCSSO/NGA 조건부(출처 표시·비변형 배포)."""

    INT_IMO = "INT-IMO"
    """IMO 신택터스 — 공식 표준 부재, WhyMath 자체 정리물."""

    JP_MEXT = "JP-MEXT"
    """일본 学習指導要領 — 정부 고시(Phase 3)."""

    GB_NC = "GB-NC"
    """영국 National Curriculum — OGL v3.0, CC BY 호환(Phase 3)."""


# ──────────────────────────────────────────────────────────────────────────
# 교과서 매핑 (v1.1 textbook_mapping.schema.yaml — 슬라이스 8b)
# ──────────────────────────────────────────────────────────────────────────
# v1.0 도메인 밖. v1.1에서 이식한 마지막 자산 TextbookMapping(검정 교과서 *구조*를 개념·
# NCIC 성취기준에 잇는 매핑)이 *enum으로 명시한 한 필드*만 enum으로 만든다.
# YAML이 enum으로 명시한 것은 legal_review_status(3종)뿐이다.
#
# ⚠️ subject·publisher는 enum으로 만들지 않는다. YAML이 subject를 "8과목 enum"으로,
# publisher를 enum_phase1=[미래엔, 천재교육]로 *언급*하나 값을 완전히 열거하지 않았고
# (subject는 8과목 체계를 예시로만 들고, publisher는 examples로 8종 이상을 더 든다),
# 기존 NCIC AchievementStandard.subject가 str인 것과 정합하므로 모델에서 `str`로 둔다
# (slice4 gender·slice8a country_code가 닫힌 enum 날조를 회피해 str로 둔 방침과 동일).
# Phase 1 범위 가드(미래엔/천재교육 2종·8과목)는 *데이터/파이프라인* 책임이지 모델 강제 아님.
class LegalReviewStatus(str, Enum):
    """교과서 학습목표 텍스트 변호사 검토 상태 — YAML `legal_review_status.enum`(영어 3종).

    `TextbookMapping.legal_review_status`가 `TextbookUnit.learning_objective_text`의 활성화
    여부를 결정한다 — `cleared`가 아니면 학습목표 텍스트는 null 고정(비-null 발견 시 적재
    거부). 근거: MEMORY PRD 허점 ⑥ — 한국 저작권법에 미국식 fair use 법리가 그대로 있지
    않아 교과서 저작물인 학습목표 문장을 "페어유즈" 단정으로 수집할 수 없다.

    ⚠️ 기존 `ReviewStatus`(pending/approved/rejected, §3.1 문제 검수)와 *다른* enum이다 —
    이쪽은 교과서 학습목표 *저작권* 검토 상태다(혼동 주의). use_enum_values=True 직렬화 시
    영어 값 보존(예: legal_review_status="not_required").
    """

    not_required = "not_required"
    """구조 메타데이터만 — 검토 불요(learning_objective_text는 null이어야 함)."""

    pending = "pending"
    """검토 진행 중 — learning_objective_text는 여전히 null."""

    cleared = "cleared"
    """검토 통과 — learning_objective_text 활성화 가능."""


class AuditResourceType(str, Enum):
    """slice 57: `deletion_audit.resource_type` — GDPR 삭제 감사 대상 도메인.

    값은 해당 ORM `__tablename__`과 일치(learning_session·dialogue·assessment). 삭제 *부모*
    리소스만 기록(자식은 slice 56 DB cascade로 비가시 — 개별 감사 안 함).
    """

    learning_session = "learning_session"
    """학습 세션 삭제(slice 51)."""

    dialogue = "dialogue"
    """Socratic 대화 삭제(slice 52)."""

    assessment = "assessment"
    """진단 삭제(slice 53)."""

    user_profile = "user_profile"
    """계정 전체(삭제권) 삭제 — 사용자의 *모든* 학생-연결 데이터 단일 트랜잭션 영구 삭제(R11)."""


class ConsentScope(str, Enum):
    """`parental_consent.consent_scope` — 14세 미만 법정대리인 동의가 *무엇을* 허용했는가.

    PIPA 만14세 미만 법정대리인 동의(docs/legal/pipa_data_matrix.md §3)의 *고지·동의 범위*를
    표현한다. PIPA는 동의 시 *수집 항목·이용 목적·보유 기간·제3자 제공 여부*를 명확히 고지할
    의무를 지우므로(§3.2), 동의 1건이 *무엇에 대한 동의였는지*를 감사 가능하게 기록한다.

    **현재는 `service_core`(서비스 본 기능 이용을 위한 개인정보 처리·게이트 해제) 한 값만
    둔다.** 모델 학습 활용·제3자 제공·마케팅 등 *별도 동의가 필요한 범위*는 각각 별도 동의
    레코드(별 scope)로 받아야 하며(CLAUDE.md "동의 없이 학습 사용 금지"·§5 체크리스트), 그
    값들은 **변호사 자문으로 범위·문구가 확정된 뒤** 추가한다(지금 추측으로 박지 않는다 —
    가짜 동의 범위를 만들지 않는다). 닫힌 카테고리지만 ORM은 String(32)로 두어(AuditResourceType
    선례) 범위 추가 시 마이그레이션이 enum 변경을 요구하지 않게 한다.
    """

    service_core = "service_core"
    """서비스 본 기능 이용을 위한 개인정보 처리 동의(미성년 게이트 해제) — §3.1 가입 단계."""


# ──────────────────────────────────────────────────────────────────────────
# 교수법 팩 지식 유형 (교수법 팩 + 소단원 DSL — 7유형→팩→증거)
# ──────────────────────────────────────────────────────────────────────────
# 근거: docs/reviews/260724_v2_migration_pedagogy_dsl_review.md(검토서)·
#       260724_v2_migration_pedagogy_dsl.alembic_draft.py(수정 목표 스키마).
#
# ⚠️ house style 예외(검토서 M4): 이 파일의 다른 상태/유형 축(concept_content.review_status·
# atom_node.cognitive_type 등)은 plain `sa.Text`로 두는 것이 관행이나, `knowledge_type`은
# *교수법 커널이 소유하는 과목 불변 축*(7유형이 교수법 팩과 1:1로 바인딩)이라 **PG native
# ENUM**으로 정합을 강제하는 것이 방어 가능하다(폐쇄 6종 `BehaviorArea`→`behavior_area_enum`
# native enum 선례와 동형). ORM은 이 enum을 `_pg_enum(KnowledgeType, "knowledge_type")`로
# PG native enum(타입명 `knowledge_type`)에 매핑한다. 관행 예외의 결정 근거는 MEMORY 결정
# 로그가 남긴다(검토서 §2 M4·§4 결정 필요 (1)).
class KnowledgeType(str, Enum):
    """교수법 팩 지식 유형 — 7유형 폐쇄 택소노미(커널 소유·과목 불변·PG native enum).

    각 학습목표(`learning_objective.k_type`)를 *어떤 종류의 지식*인지로 분류해 교수법 팩
    (`pedagogy_pack.k_type`)과 1:1 바인딩한다. "정답 도달"이 유형마다 다른 달성 증거를 요구
    한다는 설계 전제(개념형은 설명·표상형은 표현 전환·증명형은 논증)에서, 이 축이 팩·증거
    (`evidence_event.k_type`)를 가르는 뿌리다.

    멤버명·값 모두 영어(국제 인지 유형 어휘 — `BehaviorArea`·`CognitiveType`·`ReasoningType`
    선례). ⚠️ 폐쇄 7종 — 제거는 어렵고 추가는 신중해야 한다(native enum·거버넌스 결정 전제).
    use_enum_values=True 직렬화 시 영어 값 보존(예: k_type="CONCEPT").
    """

    CONCEPT = "CONCEPT"
    """개념·정의형 — 개념의 의미·정의를 이해·설명한다."""

    PROCEDURE = "PROCEDURE"
    """절차·알고리즘형 — 정해진 절차·계산을 정확히 수행한다."""

    REPRESENT = "REPRESENT"
    """표상연결형 — 식·그래프·도형 등 다중 표현을 잇고 전환한다."""

    PROOF = "PROOF"
    """증명·논증형 — 명제를 논리적으로 증명·정당화한다."""

    MODELING = "MODELING"
    """문제해결·모델링형 — 상황을 수학 구조로 모델링해 해결한다."""

    SPATIAL = "SPATIAL"
    """공간·시각형 — 도형·공간 관계를 시각적으로 추론한다."""

    STOCHASTIC = "STOCHASTIC"
    """데이터·불확실성형 — 확률·통계·불확실성을 다룬다."""


# ──────────────────────────────────────────────────────────────────────────
# 실행용 교수법 전략 (2단계 교수법 中 ② — 학생 학습 시점에 선택되는 전달 방식)
# ──────────────────────────────────────────────────────────────────────────
# 근거: docs/architecture/03c_content_strategy_cache.md §2.1(렌더 어댑터 축)·
#       04d_adaptive_pedagogy_engine.md §1(2단계 교수법 분리).
#
# `KnowledgeType`(설계용 축 — "무엇을 가르치나"로 교수법 팩을 가른다)과 **다른 축**이다. 이 enum은
# *같은* 교수법-중립 콘텐츠(ConceptDSL)를 학생 상태에 맞춰 *어떻게 보여줄지*를 가른다. 콘텐츠에
# 각인되지 않고 렌더 시점에 얹히므로, 저장 자산은 (중립 DSL × 전략)의 곱이 아니라 (중립 DSL +
# 어댑터 N개)의 합으로 유지된다(조합폭발 방지·"변형 열거 금지").
#
# ⚠️ house style: DB 컬럼을 두지 않는 **순수 Python 값객체 enum**이다(`ConsentScope` 선례 —
# 마이그레이션 결합을 피한다). 선택 결과를 영속해야 할 때가 오면 그때 native enum 승격을 별도
# 결정으로 판단한다(지금 추측으로 박지 않는다).
class PedagogyStrategy(str, Enum):
    """실행용 교수법 전략 — 폐쇄 10종(런타임 선택·렌더 어댑터 1:1 바인딩 축).

    선택 주체는 L4 Runtime Pedagogy Selector(04d §2)이고, 소비 주체는 L3 렌더 어댑터
    (03c §2.2)다. 각 전략은 *개념 무관* 어댑터 1개와 대응한다 — SOCRATIC 어댑터 하나가 모든
    개념에 작동하며, 개념별 어댑터를 복제하지 않는다.

    ⚠️ 폐쇄 10종 — 추가는 신중해야 한다(거버넌스 결정 전제·`test_render_governance.py`가 값집합을
    동결한다). 특히 **게임형(GAME)은 의도적으로 제외**했다: CLAUDE.md 절대 금기 "무자비한 게임화·
    중독성 설계 금지"가 정체성 축이므로, 게임형 추가는 중독성 없는 설계 명세가 확정된 뒤의 별도
    결정 사항이다(지금 넣지 않는다).

    멤버명·값 모두 영어(국제 교수법 어휘 — `KnowledgeType`·`ReasoningType` 선례).
    """

    DIRECT = "DIRECT"
    """직접교수 — 설명 중심으로 정의·원리를 제시한다."""

    SOCRATIC = "SOCRATIC"
    """소크라테스식 — 질문 중심으로 학생이 스스로 답에 도달하게 한다."""

    WORKED_EXAMPLE = "WORKED_EXAMPLE"
    """완전예제 — 풀이 과정을 끝까지 보여준다.

    ⚠️ 학생이 시도하기 *전*에 제공하면 "막혔을 때 바로 정답 제공 금지"를 어긴다(Polya 게이트).
    """

    PROBLEM_BASED = "PROBLEM_BASED"
    """문제기반 — 문제를 먼저 제시하고 필요한 개념을 뒤따라 끌어온다."""

    RETRIEVAL = "RETRIEVAL"
    """인출연습 — 기억에서 꺼내는 연습을 반복한다(계산 실수·정착 부족에 유효)."""

    SPACING = "SPACING"
    """분산복습 — 시간 간격을 두고 재노출한다(장기 파지)."""

    INTERLEAVING = "INTERLEAVING"
    """교차연습 — 유형을 섞어 제시한다(유형 변별력)."""

    SELF_EXPLANATION = "SELF_EXPLANATION"
    """자기설명 — 학생이 자기 말로 설명하게 유도한다(메타인지)."""

    ANALOGY = "ANALOGY"
    """비유 — 친숙한 상황에 빗대어 직관을 만든다(개념 이해 부족에 유효)."""

    VISUALIZATION = "VISUALIZATION"
    """시각화 — 그림·그래프 등 시각 표현을 앞세운다(렌더 intent는 L5 시각화 명세로)."""
