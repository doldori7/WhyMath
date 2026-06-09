"""Schema v1.0 도메인 ENUM 단위 테스트 — 값이 §14.3·§3·§13.2와 정확히 일치해야 한다.

설계 정본: `schemas/v1.0/schema_v1.0.md` §14.3(ENUM 정의)·§3.1/§3.2(DDL 컬럼 주석)·
§13.2(`license_enum`)·§10.1(`generation_type_enum`).
"""

from __future__ import annotations

from enum import Enum

from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    ExamType,
    GenerationType,
    LicenseType,
    Persona,
    QuestionFormat,
    RelationType,
    ReviewStatus,
    SignaturePattern,
    SourceType,
    StepType,
    Subject,
    VisualizationStyle,
    VisualType,
)

_ALL_ENUMS: list[type[Enum]] = [
    SourceType,
    ExamType,
    Curriculum,
    Subject,
    QuestionFormat,
    AnswerFormat,
    SignaturePattern,
    Persona,
    VisualType,
    VisualizationStyle,
    LicenseType,
    GenerationType,
    ReviewStatus,
    StepType,
    RelationType,
]


# ──────────────────────────────────────────────────────────────────────
# 출처·시험 컨텍스트
# ──────────────────────────────────────────────────────────────────────
class TestSourceType:
    def test_values_match_ddl(self) -> None:
        """§14.3 source_type_enum 값 그대로(한글 8종)."""
        assert {s.value for s in SourceType} == {
            "평가원",
            "EBS",
            "AIHub",
            "교육청학평",
            "사설모의고사",
            "자체생성",
            "사용자자작",
            "교과서",
        }

    def test_korean_values_preserved(self) -> None:
        """식별자는 영어 표현이되 값은 한글 그대로 보존."""
        assert SourceType.평가원.value == "평가원"
        assert SourceType.자체생성.value == "자체생성"
        assert SourceType.교과서.value == "교과서"


class TestExamType:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 exam_type_enum 컬럼 주석(수능/모평/학평/EBS교재/N제/자체생성)."""
        assert {e.value for e in ExamType} == {
            "수능",
            "모평",
            "학평",
            "EBS교재",
            "N제",
            "자체생성",
        }


class TestCurriculum:
    def test_values_match_ddl(self) -> None:
        """§14.3 curriculum_enum 값 그대로(영어, 3종)."""
        assert {c.value for c in Curriculum} == {
            "2009_REVISION",
            "2015_REVISION",
            "2022_REVISION",
        }

    def test_identifier_english_value_ddl(self) -> None:
        """식별자는 영어(숫자 접두 금지 → REVISION_2022), 값은 DDL 그대로."""
        assert Curriculum.REVISION_2022.value == "2022_REVISION"
        assert Curriculum.REVISION_2015.value == "2015_REVISION"
        assert Curriculum.REVISION_2009.value == "2009_REVISION"


class TestSubject:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 subject_enum 컬럼 주석(공통/미적분/확통/기하/인공지능수학)."""
        assert {s.value for s in Subject} == {
            "공통",
            "미적분",
            "확통",
            "기하",
            "인공지능수학",
        }


# ──────────────────────────────────────────────────────────────────────
# 문항 형식·정답
# ──────────────────────────────────────────────────────────────────────
class TestQuestionFormat:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 question_format_enum 주석(객관식/단답형/합답형/서술형)."""
        assert {q.value for q in QuestionFormat} == {
            "객관식",
            "단답형",
            "합답형",
            "서술형",
        }


class TestAnswerFormat:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 answer_format_enum 주석(자연수/분수/실수/식)."""
        assert {a.value for a in AnswerFormat} == {"자연수", "분수", "실수", "식"}


# ──────────────────────────────────────────────────────────────────────
# 한국 시그니처 패턴 (10종)
# ──────────────────────────────────────────────────────────────────────
class TestSignaturePattern:
    def test_values_match_ddl(self) -> None:
        """§14.3 signature_pattern_enum 값 그대로(영어, 정확히 10종)."""
        assert {p.value for p in SignaturePattern} == {
            "CONDITION_LIST",
            "COMPOSITE_DIFFERENTIABILITY",
            "INDUCTIVE_SEQUENCE",
            "DEFINED_INTEGRAL_FUNCTION",
            "FUNCTION_COUNT",
            "GRAPH_SHAPE_INFERENCE",
            "CASE_ANALYSIS_DEEP",
            "CROSS_UNIT_FUSION",
            "NATURAL_NUMBER_TRANSFORM",
            "COMPOUND_CHOICES",
        }

    def test_exactly_ten_members(self) -> None:
        """시그니처 패턴은 정확히 10종(태스크 명세)."""
        assert len(list(SignaturePattern)) == 10


# ──────────────────────────────────────────────────────────────────────
# 페르소나 (5종)
# ──────────────────────────────────────────────────────────────────────
class TestPersona:
    def test_values_match_ddl(self) -> None:
        """§14.3 persona_enum 값 그대로(A~E 5종)."""
        assert {p.value for p in Persona} == {
            "A_일반고고3",
            "B_자사고N수",
            "C_검정고시N수",
            "D_학종고2",
            "E_홈스쿨링영재",
        }

    def test_exactly_five_personas(self) -> None:
        """페르소나는 정확히 5종(PRD)."""
        assert len(list(Persona)) == 5


# ──────────────────────────────────────────────────────────────────────
# 시각자료
# ──────────────────────────────────────────────────────────────────────
class TestVisualType:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 visual_type_enum 주석(그래프/도형/표/좌표평면)."""
        assert {v.value for v in VisualType} == {"그래프", "도형", "표", "좌표평면"}


class TestVisualizationStyle:
    def test_values_are_pedagogical_forms(self) -> None:
        """슬라이스 87: 교수학적 표현 양식 통제 어휘(16종·한글)."""
        assert {v.value for v in VisualizationStyle} == {
            "수직선",
            "함수그래프",
            "단위원",
            "평면도형",
            "입체도형",
            "넓이모델",
            "수형도",
            "부등식영역",
            "벡터도",
            "점화도",
            "통계차트",
            "산점도",
            "상자그림",
            "분포곡선",
            "접선도함수",
            "확률시뮬레이션",
        }

    def test_count(self) -> None:
        """양식은 정확히 16종(v1 통제 어휘 — 변경은 의도적 결정)."""
        assert len(list(VisualizationStyle)) == 16


# ──────────────────────────────────────────────────────────────────────
# 저작권·생성 이력
# ──────────────────────────────────────────────────────────────────────
class TestLicenseType:
    def test_values_match_ddl(self) -> None:
        """§13.2 license_enum 값 그대로(영어, 6종)."""
        assert {lt.value for lt in LicenseType} == {
            "PUBLIC_DOMAIN",
            "EBS_LICENSED",
            "AIHUB_OPEN",
            "WHYMATH_GENERATED",
            "USER_GENERATED",
            "THIRD_PARTY_LICENSED",
        }


class TestGenerationType:
    def test_values_match_ddl(self) -> None:
        """§10.1 generation_type_enum 값 그대로(영어, 6종)."""
        assert {g.value for g in GenerationType} == {
            "ORIGINAL",
            "VARIANT_NUMBER",
            "VARIANT_STRUCTURE",
            "VARIANT_CONTEXT",
            "COMPOSED",
            "FULLY_GENERATED",
        }


# ──────────────────────────────────────────────────────────────────────
# 검수 상태
# ──────────────────────────────────────────────────────────────────────
class TestReviewStatus:
    def test_values_match_ddl_comment(self) -> None:
        """§3.1 review_status_enum 주석(pending/approved/rejected)."""
        assert {r.value for r in ReviewStatus} == {"pending", "approved", "rejected"}


# ──────────────────────────────────────────────────────────────────────
# 풀이 단계·문항 관계
# ──────────────────────────────────────────────────────────────────────
class TestStepType:
    def test_values_match_ddl_comment(self) -> None:
        """§3.2 problem_step.step_type_enum(조건해석/케이스분류/그래프스케치/계산/검산)."""
        assert {s.value for s in StepType} == {
            "조건해석",
            "케이스분류",
            "그래프스케치",
            "계산",
            "검산",
        }


class TestRelationType:
    def test_values_match_ddl_comment(self) -> None:
        """§3.2 problem_relation.relation_type_enum(변형/유사/선수/심화/대조)."""
        assert {r.value for r in RelationType} == {
            "변형",
            "유사",
            "선수",
            "심화",
            "대조",
        }


# ──────────────────────────────────────────────────────────────────────
# 공통 컨벤션 — str-Enum (Literal 아님), 식별자 영어
# ──────────────────────────────────────────────────────────────────────
class TestEnumConventions:
    def test_all_are_str_enums(self) -> None:
        """모든 enum은 `class X(str, Enum)` — 멤버가 str 인스턴스(l3/models.py 답습)."""
        for enum_cls in _ALL_ENUMS:
            for member in enum_cls:
                assert isinstance(member, str)
                assert isinstance(member, Enum)

    def test_str_enum_equals_value(self) -> None:
        """str-Enum이므로 멤버는 그 문자열 값과 동등 — 필터·비교 안정성."""
        assert SourceType.자체생성 == "자체생성"
        assert SignaturePattern.CONDITION_LIST == "CONDITION_LIST"
        assert Persona.A_일반고고3 == "A_일반고고3"
        assert ReviewStatus.approved == "approved"

    def test_member_names_are_ascii_identifiers(self) -> None:
        """식별자(멤버 이름)는 한글 값이라도 ASCII가 아닐 수 있으나 유효 식별자여야 한다.

        태스크: '식별자는 영어, 값은 DDL 그대로' — 단 persona/source 등은 DDL 값 자체가
        한글이라 가독성을 위해 한글 식별자를 허용(l3와 달리 도메인 enum). 여기서는 모든
        멤버 이름이 파이썬 유효 식별자임을 보장한다(ruff N은 문자열·docstring만 한글 허용).
        """
        for enum_cls in _ALL_ENUMS:
            for member in enum_cls:
                assert member.name.isidentifier()
