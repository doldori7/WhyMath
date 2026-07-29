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
    BloomLevel,
    Curriculum,
    ExamType,
    Persona,
    QuestionFormat,
    RelationType,
    ReviewStatus,
    ScoringType,
    SignaturePattern,
    SourceType,
    StepType,
    Subject,
    VisualizationType,
    VisualType,
)
from whymath_backend.schema.problem import (
    Condition,
    DistractorEntry,
    Problem,
    ProblemRelation,
    ProblemStep,
)
from whymath_backend.schema.visualization import Visualization


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
# DistractorEntry 서브모델 (P3b) — 구조 검증만(참조 무결성은 L4)
# ──────────────────────────────────────────────────────────────────────
class TestDistractorEntry:
    def test_valid_instance(self) -> None:
        """choice_index·misconception_id 필수, op_code 선택."""
        e = DistractorEntry(
            choice_index=2,
            misconception_id="distribution-over-power",
            op_code="power-distributed-no-cross-term",
        )
        assert e.choice_index == 2
        assert e.misconception_id == "distribution-over-power"
        assert e.op_code == "power-distributed-no-cross-term"

    def test_op_code_optional(self) -> None:
        """op_code는 기본 None(오개념만 매핑 가능)."""
        e = DistractorEntry(choice_index=0, misconception_id="mean-vs-median")
        assert e.op_code is None

    def test_choice_index_negative_rejected(self) -> None:
        """choice_index는 0 이상(ge=0) — 음수 → ValidationError."""
        with pytest.raises(ValidationError):
            DistractorEntry(choice_index=-1, misconception_id="mean-vs-median")

    def test_choice_index_zero_allowed(self) -> None:
        """choice_index=0은 유효(첫 선지)."""
        e = DistractorEntry(choice_index=0, misconception_id="mean-vs-median")
        assert e.choice_index == 0

    def test_empty_misconception_id_rejected(self) -> None:
        """misconception_id는 min_length=1 — 빈 문자열 → ValidationError."""
        with pytest.raises(ValidationError):
            DistractorEntry(choice_index=1, misconception_id="")

    def test_structural_only_no_catalog_check(self) -> None:
        """L1은 *구조만* 검증 — 카탈로그에 없는 id도 구조가 맞으면 생성된다(참조 무결성은 L4).

        역방향 의존 금지(CLAUDE.md): schema는 l4 카탈로그를 모른다. 미등록 id 거부는 L4
        검증자(validate_distractor_map)가 한다 — 여기선 형태만 본다.
        """
        e = DistractorEntry(choice_index=1, misconception_id="this-id-does-not-exist")
        assert e.misconception_id == "this-id-does-not-exist"

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            DistractorEntry(
                choice_index=1,
                misconception_id="mean-vs-median",
                bogus="x",  # type: ignore[call-arg]
            )

    def test_missing_required_raises(self) -> None:
        """misconception_id 누락 → ValidationError."""
        with pytest.raises(ValidationError):
            DistractorEntry(choice_index=1)  # type: ignore[call-arg]


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

    def test_visualizations_default_empty(self) -> None:
        """visualizations는 기본 빈 배열(슬라이스 91)."""
        p = _minimal_self_generated()
        assert p.visualizations == []

    def test_visualizations_from_dict(self) -> None:
        """dict로도 Visualization 강제 변환(JSONB 역직렬화 경로)·model_dump 직렬화."""
        p = _minimal_self_generated(
            visualizations=[
                {
                    "type": "interactive_graph_2d",
                    "spec": {"function": "x**2"},
                    "caption": "포물선",
                }
            ],
        )
        assert isinstance(p.visualizations[0], Visualization)
        assert p.visualizations[0].type == VisualizationType.interactive_graph_2d
        dumped = p.model_dump()
        assert dumped["visualizations"][0]["type"] == "interactive_graph_2d"
        assert dumped["visualizations"][0]["spec"]["function"] == "x**2"

    def test_visualizations_nested_invariant_propagates(self) -> None:
        """중첩 Visualization 불변식(animation_prerendered⟹조작불가)이 Problem 검증에 전파."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                visualizations=[{"type": "animation_prerendered", "interactive": True}],
            )


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
# P3a 신규 메타 8필드 — 전부 nullable·가산적(기존 구성 무회귀)
# ──────────────────────────────────────────────────────────────────────
class TestProblemP3aMetaFields:
    def test_new_fields_default_none(self) -> None:
        """P3a 8필드는 미지정 시 모두 None — 기존 Problem 구성이 그대로 유효(무회귀)."""
        p = _minimal_self_generated()
        assert p.bloom_level is None
        assert p.irt_a is None
        assert p.discrimination_D is None
        assert p.domain is None
        assert p.subunit is None
        assert p.session_position is None
        assert p.scoring_type is None
        assert p.feedback_id is None

    def test_all_new_fields_accepted(self) -> None:
        """8필드를 유효 값으로 모두 채워 생성된다(자체생성 — 본문 보유 허용)."""
        p = _minimal_self_generated(
            bloom_level=BloomLevel.ANALYZE,
            irt_a=1.35,
            discrimination_D=0.42,
            domain="CAL-DIFF",
            subunit="합성함수의 미분",
            session_position=3,
            scoring_type=ScoringType.부분점수,
            feedback_id="fb-composite-diff-01",
        )
        assert p.bloom_level == BloomLevel.ANALYZE
        assert p.irt_a == pytest.approx(1.35)
        assert p.discrimination_D == pytest.approx(0.42)
        assert p.domain == "CAL-DIFF"
        assert p.subunit == "합성함수의 미분"
        assert p.session_position == 3
        assert p.scoring_type == ScoringType.부분점수
        assert p.feedback_id == "fb-composite-diff-01"

    def test_new_enum_value_serialization(self) -> None:
        """use_enum_values=True → bloom_level(영어)·scoring_type(한글) 값 직렬화."""
        p = _minimal_self_generated(
            bloom_level=BloomLevel.CREATE,
            scoring_type=ScoringType.루브릭,
        )
        dumped = p.model_dump()
        assert dumped["bloom_level"] == "CREATE"
        assert dumped["scoring_type"] == "루브릭"

    def test_new_question_format_member_accepted(self) -> None:
        """확장된 QuestionFormat 신규 멤버(객관식진단)도 question_format에 수용된다."""
        p = _minimal_self_generated(question_format=QuestionFormat.객관식진단)
        assert p.question_format == QuestionFormat.객관식진단
        assert p.model_dump()["question_format"] == "객관식진단"

    def test_invalid_bloom_level_rejected(self) -> None:
        """bloom_level은 BloomLevel enum 값만(잘못된 값 → ValidationError)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(bloom_level="WONDER")

    def test_invalid_scoring_type_rejected(self) -> None:
        """scoring_type은 ScoringType enum 값만(잘못된 값 → ValidationError)."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(scoring_type="별점")

    def test_session_position_negative_rejected(self) -> None:
        """session_position은 0 이상(ge=0) — 음수 → ValidationError."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(session_position=-1)

    def test_session_position_zero_allowed(self) -> None:
        """session_position=0은 유효(세션 첫 번째)."""
        p = _minimal_self_generated(session_position=0)
        assert p.session_position == 0

    def test_feedback_id_max_length_rejected(self) -> None:
        """feedback_id는 max_length=64 — 초과 → ValidationError."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(feedback_id="x" * 65)


# ──────────────────────────────────────────────────────────────────────
# P3b 신규 distractor_map — nullable·rich list·가산적(기존 구성 무회귀)
# ──────────────────────────────────────────────────────────────────────
class TestProblemDistractorMap:
    def test_default_none(self) -> None:
        """distractor_map 미지정 시 None — 기존 Problem 구성이 그대로 유효(무회귀)."""
        p = _minimal_self_generated()
        assert p.distractor_map is None

    def test_rich_list_accepted(self) -> None:
        """DistractorEntry 리스트로 채워 생성된다(객관식 오답 매핑)."""
        p = _minimal_self_generated(
            distractor_map=[
                DistractorEntry(
                    choice_index=1,
                    misconception_id="distribution-over-power",
                    op_code="power-distributed-no-cross-term",
                ),
                DistractorEntry(choice_index=3, misconception_id="mean-vs-median"),
            ],
        )
        assert p.distractor_map is not None
        assert len(p.distractor_map) == 2
        assert p.distractor_map[0].choice_index == 1
        assert p.distractor_map[1].op_code is None

    def test_from_dict_coercion(self) -> None:
        """dict로도 DistractorEntry 강제 변환(JSONB 역직렬화 경로)·model_dump 직렬화."""
        p = _minimal_self_generated(
            distractor_map=[
                {"choice_index": 0, "misconception_id": "mean-vs-median", "op_code": None},
            ],
        )
        assert p.distractor_map is not None
        assert isinstance(p.distractor_map[0], DistractorEntry)
        assert p.distractor_map[0].misconception_id == "mean-vs-median"
        dumped = p.model_dump()
        assert dumped["distractor_map"][0]["choice_index"] == 0
        assert dumped["distractor_map"][0]["misconception_id"] == "mean-vs-median"

    def test_empty_list_allowed(self) -> None:
        """빈 리스트도 유효(None과 구분 — 오답 매핑이 명시적으로 없음)."""
        p = _minimal_self_generated(distractor_map=[])
        assert p.distractor_map == []

    def test_invalid_entry_rejected(self) -> None:
        """원소 구조 위반(choice_index 음수)이 Problem 검증에 전파."""
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                distractor_map=[{"choice_index": -1, "misconception_id": "mean-vs-median"}],
            )

    def test_structural_only_unknown_id_allowed(self) -> None:
        """L1은 구조만 검증 — 카탈로그 미등록 id도 Problem 생성은 통과(참조 무결성은 L4)."""
        p = _minimal_self_generated(
            distractor_map=[{"choice_index": 1, "misconception_id": "unknown-id"}],
        )
        assert p.distractor_map is not None
        assert p.distractor_map[0].misconception_id == "unknown-id"


# ──────────────────────────────────────────────────────────────────────
# 법적 교정 불변식 (MEMORY 2026-05-28) — 핵심
# ──────────────────────────────────────────────────────────────────────
class TestCopyrightInvariant:
    @pytest.mark.parametrize(
        "source",
        [SourceType.평가원, SourceType.EBS, SourceType.교과서],
    )
    def test_metadata_only_source_with_question_text_rejected(self, source: SourceType) -> None:
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
    def test_metadata_only_source_with_choices_rejected(self, source: SourceType) -> None:
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
    def test_metadata_only_source_with_conditions_parsed_rejected(self, source: SourceType) -> None:
        """평가원/EBS/교과서 + conditions_parsed 존재 → ValidationError(저작권).

        `Condition.text`는 조건 자연어 본문이라 저작권 민감 — 제한 출처는 본문 미보유여야 한다
        (P3a/P3b 신규 필드라 초기 명세에 누락됐던 갭 보정).
        """
        with pytest.raises(ValidationError):
            _minimal_self_generated(
                source_type=source,
                conditions_parsed=[Condition(label="가", text="f(x)는 미분가능", formal=None)],
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

    def test_distractor_map_allowed_for_metadata_source(self) -> None:
        """P3b: distractor_map은 *구조 메타*(본문 아님)라 메타 전용 출처에도 허용 → 통과.

        저작권 불변식의 대상 본문 필드는 question_text·answer_explanation·choices뿐이다.
        distractor_map(선지 인덱스→오개념 코드·추상 op-code)은 평가원/EBS 본문 복제가 아니므로
        signature_patterns처럼 메타 전용 출처에도 실릴 수 있다 — 불변식이 distractor_map에
        결합되지 않았음(intact)을 못 박는다.
        """
        p = _minimal_self_generated(
            source_type=SourceType.평가원,
            distractor_map=[
                DistractorEntry(choice_index=1, misconception_id="distribution-over-power"),
            ],
        )
        assert p.question_text is None  # 본문은 여전히 비어야(불변식 충족)
        assert p.distractor_map is not None
        assert p.distractor_map[0].choice_index == 1


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
