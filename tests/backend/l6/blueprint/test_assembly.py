"""L6 평가 청사진 조립 단위테스트 — 선언 명세 충족·2축 게이트·정직 회계·변별력.

검증(ASM-04 acceptance 대응):
  ① 선언 명세 충족 — 성취기준×난이도 밴드×유형·문항 수를 만족하는 세트 조립.
  ② 두 게이트 **각각** 독립 — `is_exposable`(저작권) 실패와 `is_review_cleared`(검수) 실패가
     *따로* 후보를 탈락시킨다(뮤테이션 실측 — acceptance ⑤).
  ③ CAT vs blueprint 경계 동결 — `/next-problem` 핸들러가 이 모듈을 참조하지 않음을 소스로 확인.
  ④ 배점 정직 회계 — `points=NULL`이 섞이면 실측 총점은 `None` + 미부여 건수 보고(0 접기 금지).
  ⑤ 시험시간 — 선언값 *보존만*. 문항별 소요시간 추정 필드가 결과 어디에도 없다.
  ⑥ 변별력 — 요구 문항 수 > 적격 후보 수면 `satisfied=False` + 부족 명세(조용한 부분 세트 금지).
  ⑦ 부분점수 — 기존 `verify_solution` 결과 재사용·판정 불가와 0점을 구분.

합성 픽스처만(실데이터 0·DB 0). `_problem(**over)` 빌더는 다른 L6 테스트 패턴을 답습한다.

레이어(CLAUDE.md): 이 테스트는 L1(`schema.*`)·L3(`l3.verify_*`)·L6(`l6.blueprint`)만 import한다
(③의 CAT 경계 확인만 `api.me` 소스를 *문자열로* 읽는다 — 호출이 아니라 정적 확인).
"""

from __future__ import annotations

import inspect
import uuid

import pytest

from whymath_backend.l3.verify_solution import SolutionVerificationResult
from whymath_backend.l3.verify_step import VerifyStepResult, VerifyStepState
from whymath_backend.l6.blueprint import (
    BLUEPRINT_USE_CASE,
    DIFFICULTY_BAND_BOUNDS,
    BlueprintCell,
    ExamBlueprint,
    assemble_test_set,
    blueprint_priority,
    difficulty_band_of,
    is_blueprint_eligible,
    matches_cell,
    partial_credit,
)
from whymath_backend.schema.enums import (
    Curriculum,
    QuestionFormat,
    ReviewStatus,
    SourceType,
    StepType,
    Subject,
)
from whymath_backend.schema.problem import Problem

_STANDARD_A = "[10공수1-02-02]"
_STANDARD_B = "[10공수1-03-01]"


def _problem(**over: object) -> Problem:
    """두 게이트를 기본 통과하는 최소 자체생성 Problem 빌더(합성 픽스처).

    기본값은 `source_type=자체생성`(저작권 게이트 통과) + `review_status=approved`(검수 게이트
    통과)라, 테스트가 오버라이드로 *한 축씩* 깨뜨려 각 게이트의 독립성을 확인할 수 있다.
    """
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "review_status": ReviewStatus.approved,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.공통,
        "unit_codes": ["ALG-EQ-QUAD"],
        "difficulty_overall": 3.0,
        "question_format": QuestionFormat.객관식,
        "achievement_standard_codes": [_STANDARD_A],
    }
    kwargs.update(over)
    return Problem(**kwargs)  # type: ignore[arg-type]


def _cell(**over: object) -> BlueprintCell:
    """기본 1문항 셀(무제약) 빌더 — 필요한 축만 오버라이드."""
    kwargs: dict[str, object] = {"count": 1}
    kwargs.update(over)
    return BlueprintCell(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 용도 동결(D4-2) — blueprint는 CAT을 대체하지 않는다
# ──────────────────────────────────────────────────────────────────────
class TestUseCaseFreeze:
    def test_use_case_is_unit_closure_only(self) -> None:
        """허용 용도는 '단원 마감 측정' 단 하나 — 값이 바뀌면 이 테스트가 먼저 깨진다."""
        assert BLUEPRINT_USE_CASE == "unit_closure_measurement"

    def test_assembled_set_carries_use_case(self) -> None:
        """조립 결과가 용도를 스스로 들고 다닌다(하류가 용도를 잃지 않게)."""
        result = assemble_test_set(ExamBlueprint(title="단원 마감", cells=[_cell()]), [_problem()])
        assert result.use_case == BLUEPRINT_USE_CASE

    def test_next_problem_handler_does_not_use_blueprint(self) -> None:
        """CAT 단건(`/next-problem`) 핸들러가 blueprint 조립을 참조하지 않는다(경계 동결).

        학습 중 노출 정본은 CAT이고 blueprint는 단원 마감 예외다. 누군가 `/next-problem`에서
        세트 조립을 부르기 시작하면(=CAT 대체 표류) 이 테스트가 깨진다.
        """
        from whymath_backend.api import me as me_module

        source = inspect.getsource(me_module.recommend_next_problem)
        assert "assemble_test_set" not in source
        assert "blueprint" not in source.lower()


# ──────────────────────────────────────────────────────────────────────
# 난이도 밴드
# ──────────────────────────────────────────────────────────────────────
class TestDifficultyBand:
    @pytest.mark.parametrize(
        ("difficulty", "expected"),
        [(1.0, "하"), (2.4, "하"), (2.5, "중"), (3.7, "중"), (3.75, "상"), (5.0, "상")],
    )
    def test_band_boundaries(self, difficulty: float, expected: str) -> None:
        """경계값 포함 관계 — `[하한, 상한)`이고 마지막 밴드만 상한 포함(5.0에 구멍 없음)."""
        assert difficulty_band_of(_problem(difficulty_overall=difficulty)) == expected

    def test_bands_cover_full_scale_without_gap(self) -> None:
        """세 밴드가 1.0~5.0 전 구간을 빈틈없이 덮는다(상수 자체의 무결성)."""
        bounds = sorted(DIFFICULTY_BAND_BOUNDS.values())
        assert bounds[0][0] == 1.0
        assert bounds[-1][1] == 5.0
        for (_, high), (next_low, _) in zip(bounds, bounds[1:], strict=False):
            assert high == next_low

    def test_missing_difficulty_is_unbanded_not_middle(self) -> None:
        """난이도 미평가는 '중'으로 날조되지 않고 미판정(None)이다."""
        assert difficulty_band_of(_problem(difficulty_overall=None)) is None

    def test_unbanded_problem_fails_band_constrained_cell(self) -> None:
        """밴드를 지정한 칸에서 난이도 미평가 문항은 후보에서 빠진다(fail-closed)."""
        problem = _problem(difficulty_overall=None)
        assert matches_cell(problem, _cell(difficulty_band="중")) is False
        # 밴드 무제약 칸에는 그대로 들어간다.
        assert matches_cell(problem, _cell()) is True


# ──────────────────────────────────────────────────────────────────────
# 두 게이트 — 각각 독립(PB-03) · acceptance ⑤ 뮤테이션 실측
# ──────────────────────────────────────────────────────────────────────
class TestTwoIndependentGates:
    def test_baseline_problem_is_eligible(self) -> None:
        """두 축 모두 통과하는 기준 문항은 적격."""
        assert is_blueprint_eligible(_problem()) is True

    @pytest.mark.parametrize("source", [SourceType.평가원, SourceType.EBS, SourceType.교과서])
    def test_copyright_axis_alone_blocks(self, source: SourceType) -> None:
        """저작권 축만 깨뜨려도 탈락 — 검수는 approved 그대로다(축 분리 실측)."""
        # 본문 미보유 출처는 본문 필드를 못 가지므로 발문 없이 구성(스키마 불변식).
        problem = _problem(source_type=source, review_status=ReviewStatus.approved)
        assert is_blueprint_eligible(problem) is False

    @pytest.mark.parametrize("status", [None, ReviewStatus.pending, ReviewStatus.rejected])
    def test_review_axis_alone_blocks(self, status: ReviewStatus | None) -> None:
        """검수 축만 깨뜨려도 탈락 — 출처는 자체생성(저작권 통과) 그대로다(축 분리 실측)."""
        problem = _problem(source_type=SourceType.자체생성, review_status=status)
        assert is_blueprint_eligible(problem) is False

    def test_each_axis_removes_candidates_from_assembly(self) -> None:
        """조립 파이프라인에서 두 축이 *각각* 후보를 실제로 줄인다(뮤테이션 → 원복).

        acceptance ⑤의 "게이트 각각을 뮤테이션해 실제로 후보가 빠지는지 확인"에 대응한다.
        기준 상태에서 3문항이 조립되고, 한 문항의 저작권 축 / 검수 축을 각각 깨면 그때마다
        후보가 하나씩 줄어 조립이 실패한다. 뮤테이션 후에는 원복해 기준 상태를 되돌린다.
        """
        blueprint = ExamBlueprint(title="3문항", cells=[_cell(count=3)])
        problems = [_problem() for _ in range(3)]

        baseline = assemble_test_set(blueprint, problems)
        assert baseline.satisfied is True
        assert baseline.selected_item_count == 3

        # ① 저작권 축 뮤테이션 — 한 문항을 본문 미보유 출처로.
        original_source = problems[0].source_type
        problems[0].source_type = SourceType.평가원
        mutated_copyright = assemble_test_set(blueprint, problems)
        assert mutated_copyright.satisfied is False
        assert mutated_copyright.cells[0].eligible_count == 2
        problems[0].source_type = original_source  # 원복
        assert assemble_test_set(blueprint, problems).satisfied is True

        # ② 검수 축 뮤테이션 — 한 문항을 pending으로.
        original_status = problems[1].review_status
        problems[1].review_status = ReviewStatus.pending
        mutated_review = assemble_test_set(blueprint, problems)
        assert mutated_review.satisfied is False
        assert mutated_review.cells[0].eligible_count == 2
        problems[1].review_status = original_status  # 원복
        assert assemble_test_set(blueprint, problems).satisfied is True


# ──────────────────────────────────────────────────────────────────────
# 선언 명세 충족(acceptance ①)
# ──────────────────────────────────────────────────────────────────────
class TestSpecSatisfaction:
    def test_assembles_by_standard_band_and_format(self) -> None:
        """성취기준×난이도 밴드×유형 세 축을 동시에 만족하는 문항만 담긴다."""
        target = _problem(
            achievement_standard_codes=[_STANDARD_A],
            difficulty_overall=4.5,
            question_format=QuestionFormat.단답형,
        )
        wrong_standard = _problem(achievement_standard_codes=[_STANDARD_B])
        wrong_band = _problem(difficulty_overall=1.5, question_format=QuestionFormat.단답형)
        wrong_format = _problem(difficulty_overall=4.5, question_format=QuestionFormat.객관식)

        blueprint = ExamBlueprint(
            title="단원 마감 — 상 난이도 단답형",
            cells=[
                _cell(
                    standard_code=_STANDARD_A,
                    difficulty_band="상",
                    question_format=QuestionFormat.단답형,
                    count=1,
                )
            ],
        )
        result = assemble_test_set(blueprint, [wrong_standard, wrong_band, wrong_format, target])
        assert result.satisfied is True
        assert result.problem_ids == [target.problem_id]

    def test_cells_do_not_share_problems(self) -> None:
        """한 문항이 두 칸에 중복으로 들어가지 않는다(세트 내 유일)."""
        problems = [_problem() for _ in range(2)]
        blueprint = ExamBlueprint(title="두 칸", cells=[_cell(count=1), _cell(count=1)])
        result = assemble_test_set(blueprint, problems)
        assert result.satisfied is True
        assert len(set(result.problem_ids)) == 2

    def test_selection_is_deterministic_and_stable(self) -> None:
        """같은 입력 → 같은 결과(결정론). 동률은 입력 순서를 보존한다(안정정렬)."""
        problems = [_problem() for _ in range(5)]
        blueprint = ExamBlueprint(title="상위 3", cells=[_cell(count=3)])
        first = assemble_test_set(blueprint, problems)
        second = assemble_test_set(blueprint, problems)
        assert first.problem_ids == second.problem_ids
        # 전부 동률(가중치 0.0)이라 입력 순서 앞 3개가 그대로 선택된다.
        assert first.problem_ids == [p.problem_id for p in problems[:3]]

    def test_priority_prefers_pointed_and_reviewed(self) -> None:
        """우선순위 — 배점 보유(+2.0)가 검수 점수(+0~1.0)보다 앞선다."""
        pointed = _problem(points=4)
        high_review = _problem(review_score=5.0)
        assert blueprint_priority(pointed) > blueprint_priority(high_review)
        assert blueprint_priority(_problem()) == 0.0


# ──────────────────────────────────────────────────────────────────────
# 변별력(acceptance ⑤) — 부족은 조용히 넘어가지 않는다
# ──────────────────────────────────────────────────────────────────────
class TestShortfallIsExplicit:
    def test_insufficient_candidates_fail_loudly(self) -> None:
        """요구 문항 수 > 적격 후보 수 → `satisfied=False` + 칸별 부족 + 사유 문자열."""
        blueprint = ExamBlueprint(title="5문항", cells=[_cell(count=5)])
        result = assemble_test_set(blueprint, [_problem(), _problem()])

        assert result.satisfied is False
        assert result.requested_item_count == 5
        assert result.selected_item_count == 2
        assert result.cells[0].shortfall == 3
        assert result.cells[0].eligible_count == 2
        assert len(result.unsatisfied_reasons) == 1
        assert "부족" in result.unsatisfied_reasons[0]

    def test_satisfying_and_failing_corpora_differ(self) -> None:
        """제약을 만족하는 코퍼스와 못 하는 코퍼스가 *서로 다른 결과*를 낸다(변별력 본체)."""
        blueprint = ExamBlueprint(
            title="상 난이도 2문항", cells=[_cell(difficulty_band="상", count=2)]
        )
        satisfying = [_problem(difficulty_overall=4.5) for _ in range(2)]
        failing = [_problem(difficulty_overall=2.0) for _ in range(2)]

        assert assemble_test_set(blueprint, satisfying).satisfied is True
        failed = assemble_test_set(blueprint, failing)
        assert failed.satisfied is False
        assert failed.selected_item_count == 0

    def test_empty_corpus_fails_with_zero_eligible(self) -> None:
        """후보가 아예 없으면 0건 적격으로 명시 실패(빈 세트를 성공이라 하지 않는다)."""
        result = assemble_test_set(ExamBlueprint(title="빈", cells=[_cell()]), [])
        assert result.satisfied is False
        assert result.cells[0].eligible_count == 0


# ──────────────────────────────────────────────────────────────────────
# 배점 정직 회계(acceptance ③)
# ──────────────────────────────────────────────────────────────────────
class TestPointsHonestAccounting:
    def test_null_points_yield_none_total_not_zero(self) -> None:
        """코퍼스 배점이 전량 NULL(현 실측 상태)이면 실측 총점은 `None` — 0이 아니다."""
        result = assemble_test_set(
            ExamBlueprint(title="2문항", cells=[_cell(count=2)]),
            [_problem(points=None), _problem(points=None)],
        )
        assert result.satisfied is True
        assert result.corpus_total_points is None
        assert result.points_missing_count == 2

    def test_partial_null_points_still_none(self) -> None:
        """일부만 NULL이어도 총점은 None — 부여분만 더해 '총점'이라 부르지 않는다."""
        result = assemble_test_set(
            ExamBlueprint(title="2문항", cells=[_cell(count=2)]),
            [_problem(points=4), _problem(points=None)],
        )
        assert result.corpus_total_points is None
        assert result.points_missing_count == 1

    def test_all_pointed_yields_real_total(self) -> None:
        """전 문항 배점이 채워지면 실측 총점이 실제로 합산된다(첫 `points` 소비처)."""
        result = assemble_test_set(
            ExamBlueprint(title="2문항", cells=[_cell(count=2)]),
            [_problem(points=4), _problem(points=3)],
        )
        assert result.corpus_total_points == 7
        assert result.points_missing_count == 0

    def test_declared_total_is_separate_axis(self) -> None:
        """선언 총점은 청사진 축 — 코퍼스가 전량 NULL이어도 따로 계산된다(두 축 분리)."""
        blueprint = ExamBlueprint(
            title="선언 배점",
            cells=[_cell(count=2, points_per_item=4), _cell(count=1, points_per_item=3)],
        )
        result = assemble_test_set(blueprint, [_problem() for _ in range(3)])
        assert result.declared_total_points == 11
        assert result.declared_points_missing_cells == 0
        assert result.corpus_total_points is None

    def test_declared_total_none_when_any_cell_undeclared(self) -> None:
        """배점 미선언 칸이 하나라도 있으면 선언 총점도 None + 미선언 칸 수 보고."""
        blueprint = ExamBlueprint(
            title="일부 미선언",
            cells=[_cell(count=1, points_per_item=4), _cell(count=1)],
        )
        result = assemble_test_set(blueprint, [_problem() for _ in range(2)])
        assert result.declared_total_points is None
        assert result.declared_points_missing_cells == 1


# ──────────────────────────────────────────────────────────────────────
# 시험시간(acceptance ④) — 선언 보존만·문항별 추정 없음
# ──────────────────────────────────────────────────────────────────────
class TestTimeLimitPreservedOnly:
    def test_declared_time_is_preserved_verbatim(self) -> None:
        """청사진이 선언한 총 시험시간이 그대로 결과에 보존된다."""
        blueprint = ExamBlueprint(title="50분", cells=[_cell()], time_limit_minutes=50)
        assert assemble_test_set(blueprint, [_problem()]).time_limit_minutes == 50

    def test_no_time_declared_stays_none(self) -> None:
        """선언이 없으면 None — 문항 수로 시험시간을 추정해 채우지 않는다."""
        blueprint = ExamBlueprint(title="무선언", cells=[_cell(count=1)])
        assert assemble_test_set(blueprint, [_problem()]).time_limit_minutes is None

    def test_result_has_no_per_item_time_field(self) -> None:
        """결과 스키마에 문항별 소요시간 필드가 존재하지 않는다(`Problem`에 원천이 없음)."""
        blueprint = ExamBlueprint(title="검사", cells=[_cell()], time_limit_minutes=30)
        result = assemble_test_set(blueprint, [_problem()])
        field_names = set(type(result).model_fields) | set(type(result.cells[0]).model_fields)
        assert not any("time" in name for name in field_names if name != "time_limit_minutes")
        assert not any("duration" in name or "elapsed" in name for name in field_names)


# ──────────────────────────────────────────────────────────────────────
# 부분점수(acceptance ③ 후단) — 신규 채점기 0
# ──────────────────────────────────────────────────────────────────────
def _verification(states: list[VerifyStepState]) -> SolutionVerificationResult:
    """전이 상태 목록으로 `SolutionVerificationResult`를 합성한다(합성 픽스처)."""
    steps = [
        VerifyStepResult(state=s, step_type=StepType.계산, evidence_weight=1.0) for s in states
    ]
    first_incorrect = next(
        (i for i, s in enumerate(states) if s == VerifyStepState.incorrect), None
    )
    n_unverifiable = sum(1 for s in states if s == VerifyStepState.unverifiable)
    return SolutionVerificationResult(
        steps=steps,
        n_correct=sum(1 for s in states if s == VerifyStepState.correct),
        n_incorrect=sum(1 for s in states if s == VerifyStepState.incorrect),
        n_unverifiable=n_unverifiable,
        n_transitions=len(states),
        unverified_ratio=(n_unverifiable / len(states)) if states else 0.0,
        first_incorrect_index=first_incorrect,
        has_incorrect=first_incorrect is not None,
    )


class TestPartialCredit:
    def test_no_points_is_not_zero(self) -> None:
        """배점 미부여는 0점이 아니라 판정 불가 — 사유가 그 사실을 말한다."""
        credit = partial_credit(None, _verification([VerifyStepState.correct]))
        assert credit.awarded_points is None
        assert credit.reason == "no_points_declared"

    def test_no_transitions_is_undecided(self) -> None:
        """검증할 전이가 0이면 판정 불가(에러가 아니라 정직한 미판정)."""
        credit = partial_credit(4, _verification([]))
        assert credit.awarded_points is None
        assert credit.reason == "no_transitions"

    def test_all_correct_gets_full_points(self) -> None:
        """오류 없음 → 전액."""
        credit = partial_credit(4, _verification([VerifyStepState.correct] * 3))
        assert credit.awarded_points == 4
        assert credit.credited_ratio == 1.0
        assert credit.reason == "credited_full"

    def test_first_incorrect_index_drives_partial(self) -> None:
        """첫 오류 직전까지만 인정 — `first_incorrect_index` 재사용(신규 채점기 0)."""
        states = [
            VerifyStepState.correct,
            VerifyStepState.correct,
            VerifyStepState.incorrect,
            VerifyStepState.correct,
        ]
        credit = partial_credit(4, _verification(states))
        assert credit.reason == "credited_partial"
        assert credit.credited_ratio == 0.5
        assert credit.awarded_points == 2

    def test_unverifiable_prefix_blocks_credit(self) -> None:
        """인정 구간에 검증 불가가 섞이면 점수를 만들지 않는다(허위 확언 금지)."""
        states = [
            VerifyStepState.unverifiable,
            VerifyStepState.correct,
            VerifyStepState.incorrect,
        ]
        credit = partial_credit(4, _verification(states))
        assert credit.awarded_points is None
        assert credit.reason == "unverifiable_prefix"

    def test_partial_credit_rounds_down(self) -> None:
        """비율→점수는 내림 — 검증되지 않은 부분을 점수로 바꾸지 않는다."""
        states = [
            VerifyStepState.correct,
            VerifyStepState.incorrect,
            VerifyStepState.correct,
        ]
        credit = partial_credit(4, _verification(states))
        assert credit.credited_ratio == pytest.approx(1 / 3)
        assert credit.awarded_points == 1


# ──────────────────────────────────────────────────────────────────────
# 반-스코프 동결(acceptance ⑥)
# ──────────────────────────────────────────────────────────────────────
class TestAntiScopeFreeze:
    def test_no_metadata_only_source_can_enter_a_set(self) -> None:
        """평가원·EBS·교과서 문항은 어떤 청사진으로도 세트에 들어갈 수 없다(본문 0)."""
        blocked = [
            _problem(source_type=SourceType.평가원),
            _problem(source_type=SourceType.EBS),
            _problem(source_type=SourceType.교과서),
        ]
        result = assemble_test_set(
            ExamBlueprint(title="무제약 3문항", cells=[_cell(count=3)]), blocked
        )
        assert result.satisfied is False
        assert result.problem_ids == []

    def test_result_carries_no_grade_or_percentile(self) -> None:
        """조립 결과에 등급·점수·백분위·합격확률 필드가 없다(게임화 금기 승계)."""
        result = assemble_test_set(ExamBlueprint(title="검사", cells=[_cell()]), [_problem()])
        names = set(type(result).model_fields)
        for banned in ("grade", "percentile", "rank", "admission", "score"):
            assert not any(banned in name for name in names)

    def test_problem_ids_only_no_body(self) -> None:
        """세트는 문항 *id*만 담는다 — 발문·해설 본문을 복제하지 않는다."""
        result = assemble_test_set(
            ExamBlueprint(title="검사", cells=[_cell()]),
            [_problem(question_text="x^2+1=0의 해를 구하시오.")],
        )
        assert all(isinstance(pid, uuid.UUID) for pid in result.problem_ids)
        assert "question_text" not in set(type(result.cells[0]).model_fields)
