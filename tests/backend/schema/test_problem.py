"""Schema v1.0 Problem 모델 단위 테스트 — 생성·extra forbid·필수필드·법적 교정 불변식.

설계 정본: `schemas/v1.0/schema_v1.0.md` §3.1(problem)·§3.2(problem_step·problem_relation).
법적 교정 근거: MEMORY 2026-05-28 (평가원·EBS·교과서 본문 미보유, 저작권 가이드 v2.0).
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    ExamType,
    Persona,
    QuestionFormat,
    RelationType,
    ReviewStatus,
    SignaturePattern,
    SourceType,
    StepType,
    Subject,
    VisualType,
)
from whymath_backend.schema.problem import (
    Condition,
    Problem,
    ProblemRelation,
    ProblemStep,
)


def _minimal_self_generated(**overrides: object) -> Problem:
    """본문 보유가 허용되는 최소 자체생성 Problem(테스트 헬퍼)."""
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
    }
    kwargs.update(overrides)
    return Problem(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# Condition 서브모델
# ──────────────────────────────────────────────────────────────────────
class TestCondition:
    def test_valid_instance(self) -> None:
        """label·text 필수, formal 선택."""
        c = Condition(
            label="가",
            text="f(x)는 실수 전체에서 미분가능",
            formal="differentiable(f, R)",
        )
        assert c.label == "가"
        assert c.formal == "differentiable(f, R)"

    def test_formal_optional(self) -> None:
        """formal은 기본 None."""
        c = Condition(label="나", text="f(0)=1")
        assert c.formal is None

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            Condition(label="가", text="t", bogus="x")  # type: ignore[call-arg]

    def test_missing_required_raises(self) -> None:
        """text 누락 → ValidationError."""
        with pytest.raises(ValidationError):
            Condition(label="가")  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────
# Problem — 생성·기본값
# ──────────────────────────────────────────────────────────────────────
class TestProblemCreation:
    def test_minimal_self_generated_valid(self) -> None:
        """필수 필드만으로 자체생성 문제 생성 — UUID 자동 생성·기본값 확인."""
        p = _minimal_self_generated()
        assert isinstance(p.problem_id, uuid.UUID)
        assert p.source_type == SourceType.자체생성
        assert p.unit_codes == ["CAL-INT-DEF"]
        # 기본값
        assert p.has_condition_list is False
        assert p.signature_patterns == []
        assert p.persona_fit == {}
        assert p.is_published is False
        assert p.question_text is None

    def test_full_self_generated_with_body(self) -> None:
        """자체생성은 본문(question_text·choices·answer_explanation) 보유 허용."""
        p = _minimal_self_generated(
            exam_type=ExamType.자체생성,
            exam_year=2026,
            exam_month=11,
            problem_number=30,
            exam_authority_weight=1.0,
            question_format=QuestionFormat.객관식,
            answer_format=AnswerFormat.자연수,
            points=4,
            question_text="다음 조건을 만족시키는 함수 f(x)에 대하여...",
            choices=["①", "②", "③", "④", "⑤"],
            answer="16",
            answer_explanation="합성함수의 미분가능성에 의해...",
            signature_patterns=[SignaturePattern.COMPOSITE_DIFFERENTIABILITY],
            visual_type=[VisualType.그래프],
            visual_complexity=4,
            difficulty_overall=4.5,
            diff_calculation=3.0,
            historical_correct_rate=0.0822,
            persona_fit={Persona.A_일반고고3: 0.9},
            review_status=ReviewStatus.approved,
        )
        assert p.question_text is not None
        assert p.choices == ["①", "②", "③", "④", "⑤"]
        assert p.persona_fit[Persona.A_일반고고3] == pytest.approx(0.9)
        assert p.signature_patterns == [SignaturePattern.COMPOSITE_DIFFERENTIABILITY]

    def test_conditions_parsed_submodel(self) -> None:
        """conditions_parsed는 Condition 서브모델 리스트."""
        p = _minimal_self_generated(
            has_condition_list=True,
            condition_count=2,
            conditions_parsed=[
                Condition(label="가", text="f는 미분가능"),
                Condition(label="나", text="f(0)=1"),
            ],
        )
        assert len(p.conditions_parsed) == 2
        assert p.conditions_parsed[0].label == "가"

    def test_conditions_parsed_from_dict(self) -> None:
        """dict로도 Condition 강제 변환(JSONB 역직렬화 경로)."""
        p = _minimal_self_generated(
            conditions_parsed=[{"label": "가", "text": "조건", "formal": "x>0"}],
        )
        assert isinstance(p.conditions_parsed[0], Condition)
        assert p.conditions_parsed[0].formal == "x>0"

    def test_jsonb_freeform_dicts(self) -> None:
        """source_detail·answer_constraint·answer_transform·ebs_source는 자유형 dict."""
        p = _minimal_self_generated(
            source_detail={"publisher": "WhyMath", "year": 2026},
            answer_constraint={"min": 1, "max": 999, "is_natural": True},
            answer_transform={"type": "p_plus_q", "p": 3, "q": 5},
            cross_unit_pairs=[["수열", "극한"], ["미분", "함수"]],
        )
        assert p.source_detail == {"publisher": "WhyMath", "year": 2026}
        assert p.answer_constraint["is_natural"] is True  # type: ignore[index]
        assert p.cross_unit_pairs == [["수열", "극한"], ["미분", "함수"]]


# ──────────────────────────────────────────────────────────────────────
# Problem — extra forbid·필수필드·범위 검증
# ──────────────────────────────────────────────────────────────────────
class TestProblemValidation:
    def test_extra_field_rejected(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(unknown_field="x")

    def test_missing_required_source_type(self) -> None:
        """source_type 누락 → ValidationError."""
        with pytest.raises(ValidationError):
            Problem(  # type: ignore[call-arg]
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
            )

    def test_missing_required_unit_codes(self) -> None:
        """unit_codes 누락 → ValidationError(NOT NULL)."""
        with pytest.raises(ValidationError):
            Problem(  # type: ignore[call-arg]
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
            )

    def test_empty_unit_codes_rejected(self) -> None:
        """unit_codes는 최소 1개(min_length=1)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(unit_codes=[])

    def test_difficulty_range_rejected(self) -> None:
        """difficulty_overall은 1.0-5.0 범위."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(difficulty_overall=5.5)

    def test_correct_rate_range_rejected(self) -> None:
        """historical_correct_rate는 0.0-1.0 범위."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(historical_correct_rate=1.5)

    def test_exam_month_range_rejected(self) -> None:
        """exam_month는 1-12."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(exam_month=13)

    def test_invalid_enum_value_rejected(self) -> None:
        """source_type은 SourceType enum 값만."""
        with pytest.raises(ValidationError):
            Problem(  # type: ignore[arg-type]
                source_type="존재하지않는출처",
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
            )

    def test_use_enum_values_serialization(self) -> None:
        """use_enum_values=True → enum 필드가 문자열 값으로 저장(한글 보존)."""
        p = _minimal_self_generated()
        dumped = p.model_dump()
        assert dumped["source_type"] == "자체생성"
        assert dumped["curriculum_version"] == "2022_REVISION"
        assert dumped["subject"] == "미적분"


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 (MEMORY 2026-05-28) — 핵심
# ──────────────────────────────────────────────────────────────────────
class TestCopyrightInvariant:
    @pytest.mark.parametrize(
        "source",
        [SourceType.평가원, SourceType.EBS, SourceType.교과서],
    )
    def test_metadata_only_source_with_question_text_rejected(
        self, source: SourceType
    ) -> None:
        """평가원/EBS/교과서 + question_text 존재 → ValidationError(저작권)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                source_type=source,
                question_text="평가원 발문 본문...",
            )

    @pytest.mark.parametrize(
        "source",
        [SourceType.평가원, SourceType.EBS, SourceType.교과서],
    )
    def test_metadata_only_source_with_answer_explanation_rejected(
        self, source: SourceType
    ) -> None:
        """평가원/EBS/교과서 + answer_explanation 존재 → ValidationError(저작권)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                source_type=source,
                answer_explanation="평가원 공식 해설...",
            )

    @pytest.mark.parametrize(
        "source",
        [SourceType.평가원, SourceType.EBS, SourceType.교과서],
    )
    def test_metadata_only_source_with_choices_rejected(
        self, source: SourceType
    ) -> None:
        """평가원/EBS/교과서 + choices 존재 → ValidationError(저작권)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                source_type=source,
                choices=["①", "②", "③"],
            )

    @pytest.mark.parametrize(
        "source",
        [SourceType.평가원, SourceType.EBS, SourceType.교과서],
    )
    def test_metadata_only_source_meta_only_passes(self, source: SourceType) -> None:
        """평가원/EBS/교과서 + 구조 메타만(본문 없음) → 통과."""
        p = _minimal_self_generated(
            source_type=source,
            external_id="2026-SUNEUNG-30",
            source_detail={
                "exam": "2026학년도_수능",
                "subject": "미적분",
                "number": 30,
            },
            ebs_source={"book": "수능특강", "chapter": 3, "page": 47},
            exam_year=2026,
            problem_number=30,
        )
        assert p.question_text is None
        assert p.answer_explanation is None
        assert p.choices is None
        assert p.source_detail is not None

    def test_self_generated_with_body_passes(self) -> None:
        """자체생성 + 본문(question_text·choices·answer_explanation) → 통과."""
        p = _minimal_self_generated(
            question_text="WhyMath 자체 동등문제 발문...",
            choices=["①", "②", "③", "④", "⑤"],
            answer_explanation="자체 해설...",
            answer="16",
        )
        assert p.question_text is not None
        assert p.choices is not None

    def test_aihub_with_body_passes(self) -> None:
        """AIHub(영리 허용) + 본문 → 통과(메타 전용 대상 아님)."""
        p = _minimal_self_generated(
            source_type=SourceType.AIHub,
            question_text="AIHub 데이터셋 문항...",
        )
        assert p.question_text is not None

    def test_user_generated_with_body_passes(self) -> None:
        """사용자자작 + 본문 → 통과(메타 전용 대상 아님)."""
        p = _minimal_self_generated(
            source_type=SourceType.사용자자작,
            question_text="사용자가 만든 문제...",
        )
        assert p.question_text is not None

    def test_metadata_source_with_string_value_enforced(self) -> None:
        """source_type을 문자열 값('평가원')로 줘도 불변식이 작동(use_enum_values 정규화)."""
        with pytest.raises(ValidationError):
            Problem(  # type: ignore[arg-type]
                source_type="평가원",
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.미적분,
                unit_codes=["CAL-INT-DEF"],
                question_text="본문",
            )

    def test_empty_string_body_is_allowed_for_metadata_source(self) -> None:
        """빈 문자열/빈 리스트 본문은 '비어 있음'으로 간주 → 통과."""
        p = _minimal_self_generated(
            source_type=SourceType.평가원,
            question_text="",
            answer_explanation="",
            choices=[],
        )
        # str_strip_whitespace + falsy → 위반 아님
        assert not p.question_text
        assert not p.choices


# ──────────────────────────────────────────────────────────────────────
# ProblemStep (§3.2)
# ──────────────────────────────────────────────────────────────────────
class TestProblemStep:
    def test_valid_instance(self) -> None:
        """필수: problem_id·step_order. step_id 자동 생성."""
        pid = uuid.uuid4()
        s = ProblemStep(
            problem_id=pid,
            step_order=1,
            step_type=StepType.조건해석,
            step_title="조건 (가) 해석",
            socratic_prompt="조건 (가)를 수식으로 표현해보세요",
            expected_answer="differentiable(f, R)",
            common_mistakes=[{"error": "정의역 누락", "hint": "실수 전체 확인"}],
        )
        assert s.problem_id == pid
        assert isinstance(s.step_id, uuid.UUID)
        assert s.step_type == StepType.조건해석

    def test_step_order_min(self) -> None:
        """step_order는 1 이상."""
        with pytest.raises(ValidationError):
            ProblemStep(problem_id=uuid.uuid4(), step_order=0)

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            ProblemStep(
                problem_id=uuid.uuid4(),
                step_order=1,
                bogus="x",  # type: ignore[call-arg]
            )

    def test_missing_problem_id(self) -> None:
        """problem_id 누락 → ValidationError."""
        with pytest.raises(ValidationError):
            ProblemStep(step_order=1)  # type: ignore[call-arg]

    def test_step_type_enum_value_serialization(self) -> None:
        """use_enum_values → step_type 문자열 저장."""
        s = ProblemStep(
            problem_id=uuid.uuid4(),
            step_order=2,
            step_type=StepType.케이스분류,
        )
        assert s.model_dump()["step_type"] == "케이스분류"


# ──────────────────────────────────────────────────────────────────────
# ProblemRelation (§3.2)
# ──────────────────────────────────────────────────────────────────────
class TestProblemRelation:
    def test_valid_instance(self) -> None:
        """필수: parent·related·relation_type."""
        parent = uuid.uuid4()
        related = uuid.uuid4()
        r = ProblemRelation(
            parent_problem_id=parent,
            related_problem_id=related,
            relation_type=RelationType.변형,
            similarity_score=0.85,
        )
        assert r.relation_type == RelationType.변형
        assert r.similarity_score == pytest.approx(0.85)

    def test_self_relation_rejected(self) -> None:
        """자기 자신과의 관계 금지(parent == related) → ValidationError."""
        same = uuid.uuid4()
        with pytest.raises(ValidationError):
            ProblemRelation(
                parent_problem_id=same,
                related_problem_id=same,
                relation_type=RelationType.유사,
            )

    def test_similarity_range(self) -> None:
        """similarity_score는 0.0-1.0."""
        with pytest.raises(ValidationError):
            ProblemRelation(
                parent_problem_id=uuid.uuid4(),
                related_problem_id=uuid.uuid4(),
                relation_type=RelationType.심화,
                similarity_score=1.5,
            )

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            ProblemRelation(
                parent_problem_id=uuid.uuid4(),
                related_problem_id=uuid.uuid4(),
                relation_type=RelationType.대조,
                bogus="x",  # type: ignore[call-arg]
            )

    def test_relation_type_enum_value_serialization(self) -> None:
        """use_enum_values → relation_type 문자열 저장."""
        r = ProblemRelation(
            parent_problem_id=uuid.uuid4(),
            related_problem_id=uuid.uuid4(),
            relation_type=RelationType.선수,
        )
        assert r.model_dump()["relation_type"] == "선수"
