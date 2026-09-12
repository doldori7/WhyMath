"""S2 비수용 후보 워크리스트 — 단위테스트(hermetic).

구계층(`build_worklist`·`render_worklist_markdown` — 회차 메모리 뷰·batch 경로 소비)과
신계층(내구 검수 큐 — `ReviewQueueEntry`·`entry_from_outcome`·append/load JSONL·
`render_review_queue_markdown` 누적 뷰·EOS-58 codex 상환)을 함께 검증한다.

핵심 불변: 수용(accepted_stored·accepted)은 워크리스트/큐에서 제외·나머지 4종만 항목화·
needs_review가 최상위 우선순위·"판정 안 함"(needs_review만 사람 체크박스)·모든 사유 보존
(조용한 실패 금지)·큐 행은 후보 본문 전문 동반(P1-1)·append 즉시 flush(P2)·로드 실패 행은
타입명+줄 번호로 수집(침묵 실패 금지).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.needs_review_worklist import (
    ReviewQueueEntry,
    append_review_queue_jsonl,
    build_worklist,
    entry_from_outcome,
    load_review_queue_jsonl,
    render_review_queue_markdown,
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


# ══════════════════════════════════════════════════════════════════════════
# 내구 검수 큐(EOS-58 codex 상환) — 행 조립·JSONL 계약·누적 렌더 뷰
# ══════════════════════════════════════════════════════════════════════════
_PAYLOAD = {
    "question_text": "이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오.",
    "answer": "11",
    "answer_explanation": "x^2 = 121 에서 x 는 11 또는 -11 이고, 자연수는 11이다.",
    "verify": {"conditions": "x**2 - 121 = 0"},
}


def _entry(
    status: str = "needs_review",
    *,
    run_id: str = "run-1",
    payload: dict[str, object] | None = None,
    slug: str | None = "wm-q",
    score: float | None = 0.9,
    reasons: list[str] | None = None,
) -> ReviewQueueEntry:
    return entry_from_outcome(
        _outcome(status, slug=slug, score=score, reasons=reasons or ["경계 점수"]),
        run_id=run_id,
        candidate_payload=payload if payload is not None else dict(_PAYLOAD),
    )


class TestEntryFromOutcome:
    def test_rejects_accepted_statuses(self) -> None:
        """수용 상태는 큐 대상이 아니다 — 조용한 오적재 대신 ValueError."""
        for status in ("accepted_stored", "accepted"):
            with pytest.raises(ValueError, match="검수 큐 대상이 아닙니다"):
                entry_from_outcome(_outcome(status, slug="a"), run_id="r", candidate_payload=None)

    def test_maps_outcome_fields_and_payload_sha(self) -> None:
        entry = _entry("needs_review", slug="wm-q", score=0.7, reasons=["사유1", "사유2"])
        assert entry.status == "needs_review"
        assert entry.slug == "wm-q"
        assert entry.equivalence_score == 0.7
        assert entry.reasons == ["사유1", "사유2"]
        assert entry.candidate_payload == _PAYLOAD
        assert entry.payload_sha256 is not None and len(entry.payload_sha256) == 64

    def test_payload_sha_is_key_order_independent(self) -> None:
        """canonical 직렬화 — 키 순서가 달라도 같은 payload는 같은 sha(재출현 묶기 키)."""
        reordered = dict(reversed(list(_PAYLOAD.items())))
        assert (
            _entry(payload=dict(_PAYLOAD)).payload_sha256
            == _entry(payload=reordered).payload_sha256
        )

    def test_no_payload_records_none_honestly(self) -> None:
        """후보 없는 outcome(생성 실패) — payload·sha 모두 None(본문 날조 금지)."""
        entry = entry_from_outcome(
            _outcome("generation_failed", reasons=["생성 실패"]),
            run_id="r",
            candidate_payload=None,
        )
        assert entry.candidate_payload is None
        assert entry.payload_sha256 is None
        assert entry.slug is None


class TestReviewQueueJsonl:
    def test_append_stamps_recorded_at_and_omits_source_line(self, tmp_path: Path) -> None:
        """append는 recorded_at을 스탬프하고, 매체 파생 필드 source_line은 기록하지 않는다."""
        path = tmp_path / "q.review.jsonl"
        stamped = append_review_queue_jsonl(path, _entry())
        assert stamped.recorded_at is not None  # 반환본 = 기록된 그대로의 사본
        raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert raw["recorded_at"] is not None
        assert "source_line" not in raw  # 파일이 줄 번호를 자칭하지 않음(로더 주입)

    def test_load_injects_actual_line_numbers(self, tmp_path: Path) -> None:
        path = tmp_path / "q.review.jsonl"
        append_review_queue_jsonl(path, _entry(run_id="run-1"))
        append_review_queue_jsonl(path, _entry(run_id="run-2"))
        entries, errors = load_review_queue_jsonl(path)
        assert errors == []
        assert [entry.source_line for entry in entries] == [1, 2]
        assert [entry.run_id for entry in entries] == ["run-1", "run-2"]

    def test_broken_line_collected_with_type_name_and_line_no(self, tmp_path: Path) -> None:
        """깨진 행은 조용히 사라지지 않는다 — 타입명+줄 번호 수집·유효 행은 그대로 로드."""
        path = tmp_path / "q.review.jsonl"
        append_review_queue_jsonl(path, _entry())
        with path.open("a", encoding="utf-8") as fh:
            fh.write("json 아님)))\n")
            fh.write('{"status": 12345}\n')  # 스키마 위반(ValidationError 경로)
        entries, errors = load_review_queue_jsonl(path)
        assert len(entries) == 1  # 유효 1행은 생존
        assert len(errors) == 2
        assert errors[0].startswith("line 2: JSONDecodeError")
        assert errors[1].startswith("line 3: ValidationError")

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """파일 부재는 FileNotFoundError 전파 — '파일 없음'≠'행 0건'(미측정≠0)."""
        with pytest.raises(FileNotFoundError):
            load_review_queue_jsonl(tmp_path / "없는파일.jsonl")


class TestRenderReviewQueue:
    def _loaded(self, tmp_path: Path, entries: list[ReviewQueueEntry]) -> list[ReviewQueueEntry]:
        """append→load 라운드트립 — 렌더 입력을 실제 매체 경유로 만든다(source_line 주입)."""
        path = tmp_path / "q.review.jsonl"
        for entry in entries:
            append_review_queue_jsonl(path, entry)
        loaded, errors = load_review_queue_jsonl(path)
        assert errors == []
        return loaded

    def test_same_payload_grouped_with_occurrence_and_row_refs(self, tmp_path: Path) -> None:
        loaded = self._loaded(tmp_path, [_entry(run_id="run-1"), _entry(run_id="run-2")])
        md = render_review_queue_markdown(loaded, queue_display_path="q.review.jsonl")
        assert "누적 행 2 · 항목(묶음) 1 · 로드 실패 0" in md
        assert "출현 2회" in md
        assert "- 행 참조: #1, #2" in md
        assert "run: run-1 · run-2" in md  # 재출현 회차가 전부 보인다

    def test_item_carries_candidate_body(self, tmp_path: Path) -> None:
        """항목에 문항·정답·해설·검산 조건이 실린다(P1-1 — slug만으로는 검수 불가였던 공백)."""
        md = render_review_queue_markdown(
            self._loaded(tmp_path, [_entry()]), queue_display_path="q.review.jsonl"
        )
        assert "- 문항: 이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오." in md
        assert "- 정답: 11" in md
        assert "- 해설: x^2 = 121 에서" in md
        assert "- 검산 조건: x**2 - 121 = 0" in md
        assert "- [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상" in md

    def test_multiline_question_folded_for_view(self, tmp_path: Path) -> None:
        """개행 포함 발문은 뷰에서 ' / '로 접는다 — 전문은 JSONL 행이 정본(요약 명시)."""
        payload = {"question_text": "(가) 조건 하나\n(나) 조건 둘", "answer": "3"}
        md = render_review_queue_markdown(
            self._loaded(tmp_path, [_entry(payload=payload)]),
            queue_display_path="q.review.jsonl",
        )
        assert "- 문항: (가) 조건 하나 / (나) 조건 둘" in md

    def test_payload_less_entry_says_so_honestly(self, tmp_path: Path) -> None:
        entry = entry_from_outcome(
            _outcome("generation_failed", reasons=["생성 실패"]),
            run_id="r",
            candidate_payload=None,
        )
        md = render_review_queue_markdown(
            self._loaded(tmp_path, [entry]), queue_display_path="q.review.jsonl"
        )
        assert "- 본문: (payload 없음 — 후보 미조립·사유만 기록)" in md
        assert "생성실패 1" in md

    def test_load_errors_surfaced_in_header(self) -> None:
        """로드 실패 사유는 뷰 헤더에 노출 — 깨진 행이 조용히 사라지지 않는다."""
        md = render_review_queue_markdown(
            [],
            queue_display_path="q.review.jsonl",
            load_errors=["line 3: JSONDecodeError"],
        )
        assert "로드 실패 1" in md
        assert "- ⚠ 로드 실패 행: line 3: JSONDecodeError" in md

    def test_priority_order_needs_review_first(self, tmp_path: Path) -> None:
        """묶음 정렬도 구뷰와 동일 축 — needs_review 최상단."""
        entries = [
            entry_from_outcome(
                _outcome("generation_failed", reasons=["실패"]),
                run_id="r",
                candidate_payload=None,
            ),
            _entry("rejected_gate", payload={"question_text": "게이트 거부 문항", "answer": "1"}),
            _entry("needs_review"),
        ]
        md = render_review_queue_markdown(
            self._loaded(tmp_path, entries), queue_display_path="q.review.jsonl"
        )
        first = md.split("## 1. ")[1].splitlines()[0]
        assert "[needs_review]" in first
