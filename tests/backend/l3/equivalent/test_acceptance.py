"""동등문제 수용 게이트 테스트 — S2-a `evaluate_equivalent_candidate`(hermetic·순수).

각 게이트(저작권·정확성·위생·동등성 분류)와 최종 accepted 진리표를 커버한다. DB·LLM·네트워크
0 — 모두 결정론 순수 함수다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l3.equivalent.acceptance import (
    AcceptanceVerdict,
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem
from whymath_backend.schema.provenance import ContentProvenance

# ──────────────────────────────────────────────────────────────────────
# 테스트 헬퍼 — 전 게이트 통과하는 기준 후보/명세/이력.
# ──────────────────────────────────────────────────────────────────────
_STANDARD = "[12미적01-01]"
_MISCONCEPTION = "distribution-over-power"


def _valid_candidate(**overrides: object) -> Problem:
    """전 게이트 통과 기준의 자체생성 동등문제 후보."""
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
        "difficulty_overall": 3.0,
        "answer_format": AnswerFormat.자연수,
        "achievement_standard_codes": [_STANDARD],
        "distractor_map": [
            DistractorEntry(choice_index=1, misconception_id=_MISCONCEPTION),
        ],
        "question_text": "주어진 이차식의 자연수 근을 구하시오.",
        "answer": "3",
        "answer_explanation": "주어진 조건을 풀면 정답은 자연수 세 입니다.",
    }
    kwargs.update(overrides)
    return Problem(**kwargs)  # type: ignore[arg-type]


def _valid_provenance(**overrides: object) -> ContentProvenance:
    """전 게이트 통과 기준의 저작권 이력(변형/생성류·WHYMATH_GENERATED)."""
    kwargs: dict[str, object] = {
        "generation_type": GenerationType.FULLY_GENERATED,
        "license": LicenseType.WHYMATH_GENERATED,
    }
    kwargs.update(overrides)
    return ContentProvenance(**kwargs)  # type: ignore[arg-type]


def _spec(**overrides: object) -> EquivalenceSpec:
    """후보와 완전 대응하는 기준 명세."""
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset({_MISCONCEPTION}),
        "difficulty_overall": 3.0,
        "answer_format": AnswerFormat.자연수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


_CONDITIONS = "x**2 - 5*x + 6 = 0"
_ANSWER_MAP = {"x": "3"}


def _evaluate(**overrides: object) -> AcceptanceVerdict:
    """기준 인자로 게이트 평가(overrides로 한 축만 바꿔 검증)."""
    kwargs: dict[str, object] = {
        "spec": _spec(),
        "candidate": _valid_candidate(),
        "provenance": _valid_provenance(),
        "conditions": _CONDITIONS,
        "answer_map": _ANSWER_MAP,
    }
    kwargs.update(overrides)
    return evaluate_equivalent_candidate(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# Happy path — 전 게이트 통과·동치후보·accepted.
# ──────────────────────────────────────────────────────────────────────
class TestAcceptHappyPath:
    def test_all_gates_pass_accepted(self) -> None:
        """전 게이트 통과 → accepted·동치후보·verified."""
        verdict = _evaluate()
        assert verdict.accepted is True
        assert verdict.equivalence == "동치후보"
        assert verdict.copyright_ok is True
        assert verdict.verification == "verified"
        assert verdict.hygiene_ok is True
        assert verdict.equivalence_score == pytest.approx(1.0)
        assert verdict.reasons == []

    def test_verified_with_correct_steps(self) -> None:
        """정답 + 단계 전부 correct → verified·accepted."""
        verdict = _evaluate(solution_steps=["2*x + 3", "3 + 2*x"])
        assert verdict.verification == "verified"
        assert verdict.accepted is True


# ──────────────────────────────────────────────────────────────────────
# 저작권 게이트.
# ──────────────────────────────────────────────────────────────────────
class TestCopyrightGate:
    def test_original_generation_type_rejected_at_provenance_creation(self) -> None:
        """generation_type=ORIGINAL은 ContentProvenance 생성 자체가 거부(A 불변식)."""
        with pytest.raises(ValidationError):
            ContentProvenance(
                generation_type=GenerationType.ORIGINAL,  # type: ignore[arg-type]
                license=LicenseType.WHYMATH_GENERATED,
            )

    def test_license_mismatch_copyright_not_ok(self) -> None:
        """license가 WHYMATH_GENERATED가 아니면 copyright_ok=False·미수용."""
        prov = _valid_provenance(license=LicenseType.USER_GENERATED)
        verdict = _evaluate(provenance=prov)
        assert verdict.copyright_ok is False
        assert verdict.accepted is False
        assert any("license" in reason for reason in verdict.reasons)

    def test_non_self_generated_source_copyright_not_ok(self) -> None:
        """source_type이 자체생성이 아니면 copyright_ok=False."""
        candidate = _valid_candidate(source_type=SourceType.AIHub)
        verdict = _evaluate(candidate=candidate)
        assert verdict.copyright_ok is False
        assert verdict.accepted is False


# ──────────────────────────────────────────────────────────────────────
# 정확성 게이트.
# ──────────────────────────────────────────────────────────────────────
class TestVerificationGate:
    def test_wrong_answer_failed(self) -> None:
        """답이 조건을 위반(verify_answer fail) → failed·미수용."""
        verdict = _evaluate(answer_map={"x": "4"})
        assert verdict.verification == "failed"
        assert verdict.accepted is False

    def test_incorrect_step_failed(self) -> None:
        """단계 중 incorrect(틀린 과정) → failed(답 무관 차단)."""
        verdict = _evaluate(solution_steps=["2*x + 3", "2*x + 4"])
        assert verdict.verification == "failed"
        assert verdict.accepted is False

    def test_unverifiable_step_unverified_review(self) -> None:
        """단계 판정 불가(미검증) → unverified → 검수필요."""
        verdict = _evaluate(solution_steps=["f(x)", "g(x)"])
        assert verdict.verification == "unverified"
        assert verdict.equivalence == "검수필요"
        assert verdict.accepted is False

    def test_unparseable_condition_unverified(self) -> None:
        """Tier1 답 검산 판정 불가 → unverified → 검수필요."""
        verdict = _evaluate(conditions="이 조건은 파싱 불가")
        assert verdict.verification == "unverified"
        assert verdict.equivalence == "검수필요"
        assert verdict.accepted is False


# ──────────────────────────────────────────────────────────────────────
# 위생 게이트.
# ──────────────────────────────────────────────────────────────────────
class TestHygieneGate:
    def test_false_equation_in_explanation_hygiene_not_ok(self) -> None:
        """answer_explanation에 거짓 수치 등식 → hygiene_ok=False·미수용."""
        candidate = _valid_candidate(
            answer_explanation="계산하면 3 × 4 = 11 이므로 정답은 3.",
        )
        verdict = _evaluate(candidate=candidate)
        assert verdict.hygiene_ok is False
        assert verdict.accepted is False
        assert any("위생" in reason for reason in verdict.reasons)

    def test_clean_explanation_hygiene_ok(self) -> None:
        """거짓 등식 없는 본문 → hygiene_ok=True."""
        verdict = _evaluate()
        assert verdict.hygiene_ok is True


# ──────────────────────────────────────────────────────────────────────
# 동등성 분류.
# ──────────────────────────────────────────────────────────────────────
class TestEquivalenceClassification:
    def test_standard_mismatch_lowers_score_to_review(self) -> None:
        """성취기준 불일치 → 점수 하락·경계 구간 검수필요."""
        candidate = _valid_candidate(achievement_standard_codes=[])
        verdict = _evaluate(candidate=candidate)
        assert verdict.equivalence_score < 1.0
        assert verdict.equivalence == "검수필요"
        assert verdict.accepted is False

    def test_misconception_mismatch_lowers_score(self) -> None:
        """오개념 불일치 → Jaccard 0 → 점수 하락."""
        candidate = _valid_candidate(
            distractor_map=[DistractorEntry(choice_index=1, misconception_id="other-misc")],
        )
        verdict = _evaluate(candidate=candidate)
        assert verdict.equivalence_score < 1.0
        assert verdict.equivalence == "검수필요"

    def test_difficulty_gap_lowers_score(self) -> None:
        """난이도 큰 격차 → 선형 감쇠로 점수 하락·비동치."""
        candidate = _valid_candidate(difficulty_overall=5.0)
        spec = _spec(difficulty_overall=1.0)
        verdict = _evaluate(candidate=candidate, spec=spec)
        assert verdict.equivalence_score < 1.0
        assert verdict.equivalence != "동치후보"

    def test_difficulty_within_tolerance_full(self) -> None:
        """난이도 격차 ≤ tol → 만점(동치후보 유지)."""
        candidate = _valid_candidate(difficulty_overall=3.4)
        verdict = _evaluate(candidate=candidate)  # spec 3.0·tol 0.5 → gap 0.4
        assert verdict.equivalence == "동치후보"

    def test_answer_format_mismatch_lowers_score(self) -> None:
        """답 형태 불일치 → 점수 하락(가중치 0.1)."""
        candidate = _valid_candidate(answer_format=AnswerFormat.식)
        verdict = _evaluate(candidate=candidate)
        assert verdict.equivalence_score < 1.0

    def test_spec_no_requirement_full_score(self) -> None:
        """빈 명세(요구 없음) + 후보도 오개념 없음 → 각 축 만점 → 동치후보."""
        spec = _spec(
            achievement_standard_codes=frozenset(),
            target_misconception_ids=frozenset(),
            answer_format=None,
        )
        # 오개념 Jaccard가 만점이려면 후보 distractor 오개념도 비어야 한다(둘 다 공집합→1.0).
        candidate = _valid_candidate(distractor_map=[])
        verdict = _evaluate(spec=spec, candidate=candidate)
        assert verdict.equivalence == "동치후보"
        assert verdict.equivalence_score == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────
# accepted 종합 진리표 — 하나라도 실패하면 accepted=False.
# ──────────────────────────────────────────────────────────────────────
class TestAcceptedTruthTable:
    def test_copyright_fail_blocks_accept(self) -> None:
        verdict = _evaluate(provenance=_valid_provenance(license=LicenseType.USER_GENERATED))
        assert verdict.accepted is False

    def test_verification_fail_blocks_accept(self) -> None:
        verdict = _evaluate(answer_map={"x": "4"})
        assert verdict.accepted is False

    def test_hygiene_fail_blocks_accept(self) -> None:
        candidate = _valid_candidate(answer_explanation="틀린 식 5 < 3 이다.")
        verdict = _evaluate(candidate=candidate)
        assert verdict.hygiene_ok is False
        assert verdict.accepted is False

    def test_equivalence_review_blocks_accept(self) -> None:
        candidate = _valid_candidate(achievement_standard_codes=[])
        verdict = _evaluate(candidate=candidate)
        assert verdict.equivalence != "동치후보"
        assert verdict.accepted is False

    def test_reasons_recorded_on_rejection(self) -> None:
        """거부 시 사유가 조용히 사라지지 않고 reasons에 기록된다."""
        verdict = _evaluate(answer_map={"x": "4"})
        assert len(verdict.reasons) >= 1
