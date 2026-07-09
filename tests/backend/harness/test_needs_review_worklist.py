"""S2 비수용 후보 워크리스트 — 순수 단위테스트(hermetic·DB/파일 무관).

`build_worklist`(필터·우선순위 정렬)와 `render_worklist_markdown`(카운트·항목·체크박스)만
검증한다. 구성한 `GenerationOutcome`(다양 status)로 결정론 동작을 본다.

핵심 불변: 수용(accepted_stored·accepted)은 워크리스트에서 제외·나머지 4종만 항목화·needs_review
가 최상위 우선순위·"판정 안 함"(needs_review만 사람 체크박스)·모든 사유 보존(조용한 실패 금지).
"""

from __future__ import annotations

from whymath_backend.harness.needs_review_worklist import (
    build_worklist,
    render_worklist_markdown,
)
from whymath_backend.l3.equivalent.acceptance import AcceptanceVerdict
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.orchestrator import GenerationOutcome
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem
from whymath_backend.schema.provenance import ContentProvenance


def _problem(slug: str) -> Problem:
    # test_orchestrator._problem 미러(전 게이트 통과 기준 유효 후보).
    return Problem(
        slug=slug,
        source_type=SourceType.자체생성,
        curriculum_version=Curriculum.REVISION_2022,
        valid_from_year=2022,
        subject=Subject.미적분,
        unit_codes=["CAL-INT-DEF"],
        difficulty_overall=3.0,
        answer_format=AnswerFormat.자연수,
        achievement_standard_codes=["[12미적01-01]"],
        question_text="주어진 이차식의 자연수 근을 구하시오.",
        answer="3",
        answer_explanation="주어진 조건을 풀면 정답은 자연수 세 입니다.",
    )


def _candidate(slug: str) -> CandidateProblem:
    return CandidateProblem(
        problem=_problem(slug),
        provenance=ContentProvenance(
            generation_type=GenerationType.FULLY_GENERATED,
            license=LicenseType.WHYMATH_GENERATED,
        ),
        conditions="x**2 - 5*x + 6 = 0",
        answer_map={"x": "3"},
        answer_selection="largest",
    )


def _verdict(score: float, reasons: list[str]) -> AcceptanceVerdict:
    return AcceptanceVerdict(
        accepted=False,
        copyright_ok=True,
        verification="verified",
        hygiene_ok=True,
        equivalence="검수필요",
        equivalence_score=score,
        reasons=reasons,
    )


def _outcome(
    status: str,
    *,
    slug: str | None = None,
    score: float | None = None,
    reasons: list[str] | None = None,
) -> GenerationOutcome:
    return GenerationOutcome(
        status=status,  # type: ignore[arg-type]  # 테스트가 6종 Literal 값을 문자열로 구성
        candidate=_candidate(slug) if slug is not None else None,
        acceptance=_verdict(score, reasons or []) if score is not None else None,
        reasons=reasons or [],
    )


class TestBuildWorklist:
    def test_excludes_accepted(self) -> None:
        """accepted_stored·accepted는 워크리스트에서 제외(비수용만 항목화)."""
        outcomes = [
            _outcome("accepted_stored", slug="a"),
            _outcome("accepted", slug="b"),
            _outcome("needs_review", slug="c", score=0.7, reasons=["경계 점수"]),
        ]
        items = build_worklist(outcomes)
        assert len(items) == 1
        assert items[0].status == "needs_review"
        assert items[0].slug == "c"

    def test_priority_order_needs_review_first(self) -> None:
        """정렬 우선순위 — needs_review < rejected_gate < rejected_duplicate < generation_failed."""
        outcomes = [
            _outcome("generation_failed"),
            _outcome("rejected_duplicate", slug="d", score=0.9),
            _outcome("rejected_gate", slug="g", score=0.5),
            _outcome("needs_review", slug="n", score=0.7),
        ]
        items = build_worklist(outcomes)
        assert [it.status for it in items] == [
            "needs_review",
            "rejected_gate",
            "rejected_duplicate",
            "generation_failed",
        ]

    def test_same_status_sorted_by_score_desc(self) -> None:
        """같은 상태는 동등성 점수 내림차순(수용에 가까운 후보 먼저)."""
        outcomes = [
            _outcome("needs_review", slug="low", score=0.4),
            _outcome("needs_review", slug="high", score=0.8),
        ]
        items = build_worklist(outcomes)
        assert [it.slug for it in items] == ["high", "low"]

    def test_reasons_preserved(self) -> None:
        """모든 사유 보존(조용한 실패 금지)."""
        item = build_worklist([_outcome("rejected_gate", slug="x", score=0.3, reasons=["a", "b"])])[
            0
        ]
        assert item.reasons == ["a", "b"]

    def test_generation_failed_no_candidate_no_score(self) -> None:
        """생성 실패는 후보·점수 없음 → slug/score None."""
        item = build_worklist([_outcome("generation_failed", reasons=["생성 실패"])])[0]
        assert item.slug is None
        assert item.equivalence_score is None

    def test_empty(self) -> None:
        assert build_worklist([]) == []


class TestRenderWorklist:
    def test_header_counts(self) -> None:
        items = build_worklist(
            [
                _outcome("needs_review", slug="n", score=0.7),
                _outcome("rejected_gate", slug="g", score=0.5),
                _outcome("rejected_duplicate", slug="d", score=0.9),
                _outcome("generation_failed"),
            ]
        )
        md = render_worklist_markdown(items, total_outcomes=10)
        assert "총 생성 outcome: 10 · 비수용(워크리스트) 4" in md
        assert "검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1" in md

    def test_needs_review_has_checkbox_others_not(self) -> None:
        """needs_review 항목만 사람 판단 체크박스(판정 안 함 규약)."""
        md = render_worklist_markdown(
            build_worklist(
                [
                    _outcome("needs_review", slug="n", score=0.7),
                    _outcome("rejected_gate", slug="g", score=0.5, reasons=["부호 오류"]),
                ]
            ),
            total_outcomes=2,
        )
        assert "사람 판단(검수자 체크)" in md
        assert "[ ] 수용(코퍼스 편입)" in md
        # rejected_gate 사유는 렌더되나 체크박스는 needs_review에만.
        assert "부호 오류" in md

    def test_empty_worklist_renders_header(self) -> None:
        md = render_worklist_markdown([], total_outcomes=5)
        assert "비수용(워크리스트) 0" in md
