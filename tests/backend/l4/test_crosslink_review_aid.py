"""L4 crosslink_review_aid 단위테스트 — 검수 큐 + M-id 코퍼스 → kebab별 근거 리포트(read-only).

load_corpus(인덱싱·중복/top key 거부)·build_review_aid(kebab 그룹·코퍼스 조인·카탈로그/코퍼스
미존재 플래그·status 필터)·summarize/format(근거 집합·판정 없음·마지막 JSON 줄)·CLI. 라이브
PG/HTTP 0(순수 조인). kebab측은 실 카탈로그(CATALOG_BY_ID)로 조인해 조인이 실제 동작함을 본다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.crosslink_review import CrosslinkReviewItem
from whymath_backend.l4.misconception.crosslink_review_aid import (
    CandidateEvidence,
    MisconceptionCorpusEntry,
    ReviewAidSummary,
    build_review_aid,
    candidate_gate_checks,
    format_review_aid,
    load_corpus,
    main,
    summarize_review_aid,
)

# 실 카탈로그에 존재하는 kebab-id 2종(조인이 실제 동작함을 확인).
KEBAB_A = "distribution-over-power"
KEBAB_B = "sign-flip-in-inequality"


def _item(
    *,
    kebab_id: str,
    mis_id: str,
    link_type: str = "직접매핑",
    confidence: float | None = 0.9,
    rationale: str = "초안 근거",
    status: str = "pending",
) -> CrosslinkReviewItem:
    return CrosslinkReviewItem(
        kebab_id=kebab_id,
        mis_id=mis_id,
        link_type=link_type,  # type: ignore[arg-type]
        confidence=confidence,
        rationale=rationale,
        status=status,  # type: ignore[arg-type]
    )


def _corpus_text(*mis_ids: str) -> str:
    """주어진 M-id들로 최소 코퍼스 JSON 텍스트 생성(검수 근거 필드 포함)."""
    return json.dumps(
        {
            "misconceptions": [
                {
                    "mis_id": m,
                    "canonical_statement": f"개념-{m}",
                    "student_wrong_thinking": f"오사고-{m}",
                    "distractor_rule": f"규칙-{m}",
                    "error_type": f"유형-{m}",
                    "standard_code": "[9수02-19]",
                    "domain": "변화와 관계",
                    "extra_ignored_field": "무시됨",  # extra="ignore" 확인
                }
                for m in mis_ids
            ]
        },
        ensure_ascii=False,
    )


# ── load_corpus ──────────────────────────────────────────────────────────


def test_load_corpus_indexes_by_mis_id_and_ignores_extra() -> None:
    corpus = load_corpus(_corpus_text("M0019", "M0564"))
    assert set(corpus) == {"M0019", "M0564"}
    assert isinstance(corpus["M0019"], MisconceptionCorpusEntry)
    assert corpus["M0019"].student_wrong_thinking == "오사고-M0019"
    # extra 필드는 무시(모델에 없음).
    assert not hasattr(corpus["M0019"], "extra_ignored_field")


def test_load_corpus_rejects_missing_top_key() -> None:
    with pytest.raises(ValueError, match="misconceptions"):
        load_corpus(json.dumps({"wrong_key": []}))


def test_load_corpus_rejects_duplicate_mis_id() -> None:
    text = json.dumps({"misconceptions": [{"mis_id": "M0019"}, {"mis_id": "M0019"}]})
    with pytest.raises(ValueError, match="중복 mis_id"):
        load_corpus(text)


# ── build_review_aid ─────────────────────────────────────────────────────


def test_build_groups_by_kebab_joins_corpus_and_catalog() -> None:
    corpus = load_corpus(_corpus_text("M0019", "M0572"))
    items = [
        _item(kebab_id=KEBAB_A, mis_id="M0019", confidence=0.95),
        _item(kebab_id=KEBAB_A, mis_id="M0572", confidence=0.8),
    ]
    groups = build_review_aid(items, corpus=corpus)
    assert len(groups) == 1
    g = groups[0]
    assert g.kebab_id == KEBAB_A
    assert g.kebab_found  # 실 카탈로그 조인 성공
    assert g.kebab is not None and g.kebab.name_kr == CATALOG_BY_ID[KEBAB_A].name_kr
    # 후보 순서(큐 순서 = 초안 신뢰도 내림차순)를 보존.
    assert [c.mis_id for c in g.candidates] == ["M0019", "M0572"]
    assert g.candidates[0].corpus_found
    assert g.candidates[0].corpus is not None
    assert g.candidates[0].corpus.student_wrong_thinking == "오사고-M0019"


def test_build_sorts_groups_by_kebab_id() -> None:
    corpus = load_corpus(_corpus_text("M1", "M2"))
    # 입력은 B 먼저, A 나중 — 출력은 kebab-id 정렬(A < B).
    items = [_item(kebab_id=KEBAB_B, mis_id="M2"), _item(kebab_id=KEBAB_A, mis_id="M1")]
    groups = build_review_aid(items, corpus=corpus)
    assert [g.kebab_id for g in groups] == sorted([KEBAB_A, KEBAB_B])


def test_build_flags_kebab_not_in_catalog() -> None:
    corpus = load_corpus(_corpus_text("M0019"))
    items = [_item(kebab_id="not-a-real-kebab", mis_id="M0019")]
    groups = build_review_aid(items, corpus=corpus)
    assert len(groups) == 1
    assert not groups[0].kebab_found
    assert groups[0].kebab is None


def test_build_flags_dangling_mis_id() -> None:
    corpus = load_corpus(_corpus_text("M0019"))  # M9999 없음
    items = [_item(kebab_id=KEBAB_A, mis_id="M9999")]
    groups = build_review_aid(items, corpus=corpus)
    cand = groups[0].candidates[0]
    assert not cand.corpus_found
    assert cand.corpus is None


def test_build_status_filter_default_pending_excludes_others() -> None:
    corpus = load_corpus(_corpus_text("M1", "M2", "M3"))
    items = [
        _item(kebab_id=KEBAB_A, mis_id="M1", status="pending"),
        _item(kebab_id=KEBAB_A, mis_id="M2", status="approved"),
        _item(kebab_id=KEBAB_A, mis_id="M3", status="rejected"),
    ]
    # 기본(pending)은 미검수만.
    default_groups = build_review_aid(items, corpus=corpus)
    assert [c.mis_id for c in default_groups[0].candidates] == ["M1"]
    # 전 상태 요청 시 모두 포함.
    all_groups = build_review_aid(
        items, corpus=corpus, statuses=("pending", "approved", "rejected", "deferred")
    )
    assert [c.mis_id for c in all_groups[0].candidates] == ["M1", "M2", "M3"]


def test_build_accepts_custom_catalog() -> None:
    corpus = load_corpus(_corpus_text("M1"))
    items = [_item(kebab_id="only-here", mis_id="M1")]
    # 커스텀 카탈로그에 kebab이 없으면(빈 dict) 미존재로 플래그.
    groups = build_review_aid(items, corpus=corpus, catalog={})
    assert not groups[0].kebab_found


# ── summarize ────────────────────────────────────────────────────────────


def test_summarize_counts_and_signals() -> None:
    corpus = load_corpus(_corpus_text("M0019"))  # M9999 dangling
    items = [
        _item(kebab_id=KEBAB_A, mis_id="M0019"),
        _item(kebab_id=KEBAB_A, mis_id="M9999"),  # dangling
        _item(kebab_id="fake-kebab", mis_id="M0019"),  # not in catalog
    ]
    groups = build_review_aid(items, corpus=corpus)
    summary = summarize_review_aid(groups, statuses=("pending",))
    assert summary.kebab_groups == 2  # KEBAB_A + fake-kebab
    assert summary.candidates == 3
    assert summary.kebab_not_in_catalog == ["fake-kebab"]
    assert summary.dangling_mis_ids == ["M9999"]
    assert summary.statuses == ["pending"]


# ── gate checks (기계 전제·객관) ──────────────────────────────────────────


def _cand(
    *,
    mis_id: str = "M1",
    link_type: str = "직접매핑",
    confidence: float | None = 0.9,
    has_corpus: bool = True,
) -> CandidateEvidence:
    return CandidateEvidence(
        mis_id=mis_id,
        link_type=link_type,
        confidence=confidence,
        rationale="근거",
        status="pending",
        corpus=(MisconceptionCorpusEntry(mis_id=mis_id) if has_corpus else None),
    )


def test_gate_checks_direct_mapping_passes_when_conf_ok() -> None:
    checks = candidate_gate_checks(_cand(confidence=0.9), kebab_in_catalog=True)
    assert checks.kebab_in_catalog and checks.corpus_found and checks.direct_conf_ok
    assert checks.all_pass


def test_gate_checks_direct_mapping_blocked_below_threshold() -> None:
    # 직접매핑 conf 0.5 < 0.6 → direct_conf_ok False(promote 승격 금지 미러).
    checks = candidate_gate_checks(_cand(confidence=0.5), kebab_in_catalog=True)
    assert not checks.direct_conf_ok
    assert not checks.all_pass


def test_gate_checks_direct_mapping_none_conf_blocked() -> None:
    checks = candidate_gate_checks(_cand(confidence=None), kebab_in_catalog=True)
    assert not checks.direct_conf_ok


def test_gate_checks_non_direct_conf_not_applicable() -> None:
    # 부분매핑/개념겹침은 conf 임계값 해당 없음 → direct_conf_ok True(N/A).
    checks = candidate_gate_checks(
        _cand(link_type="부분매핑", confidence=None), kebab_in_catalog=True
    )
    assert checks.direct_conf_ok
    assert checks.all_pass


def test_gate_checks_missing_corpus_or_catalog_blocks() -> None:
    assert not candidate_gate_checks(_cand(has_corpus=False), kebab_in_catalog=True).all_pass
    assert not candidate_gate_checks(_cand(), kebab_in_catalog=False).all_pass


def test_summary_gate_blocked_lists_precondition_failures() -> None:
    corpus = load_corpus(_corpus_text("M1", "M2"))
    items = [
        _item(kebab_id=KEBAB_A, mis_id="M1", confidence=0.9),  # 통과
        _item(kebab_id=KEBAB_A, mis_id="M2", confidence=0.5),  # 직접매핑 conf 미달 → blocked
    ]
    summary = summarize_review_aid(build_review_aid(items, corpus=corpus), statuses=("pending",))
    assert summary.gate_blocked_mis_ids == ["M2"]


# ── kebab 포커스 필터 ─────────────────────────────────────────────────────


def test_build_kebab_filter_scopes_to_requested() -> None:
    corpus = load_corpus(_corpus_text("M1", "M2"))
    items = [_item(kebab_id=KEBAB_A, mis_id="M1"), _item(kebab_id=KEBAB_B, mis_id="M2")]
    groups = build_review_aid(items, corpus=corpus, kebab_filter=(KEBAB_A,))
    assert [g.kebab_id for g in groups] == [KEBAB_A]


def test_build_kebab_filter_none_includes_all() -> None:
    corpus = load_corpus(_corpus_text("M1", "M2"))
    items = [_item(kebab_id=KEBAB_A, mis_id="M1"), _item(kebab_id=KEBAB_B, mis_id="M2")]
    groups = build_review_aid(items, corpus=corpus, kebab_filter=None)
    assert {g.kebab_id for g in groups} == {KEBAB_A, KEBAB_B}


# ── format ───────────────────────────────────────────────────────────────


def test_format_contains_evidence_and_parseable_summary() -> None:
    corpus = load_corpus(_corpus_text("M0019"))
    items = [_item(kebab_id=KEBAB_A, mis_id="M0019", confidence=0.95)]
    groups = build_review_aid(items, corpus=corpus)
    report = format_review_aid(groups, statuses=("pending",))
    # kebab측·M-id측 근거가 모두 리포트에 등장.
    assert CATALOG_BY_ID[KEBAB_A].name_kr in report
    assert "오사고-M0019" in report
    assert "규칙-M0019" in report
    assert "conf=0.95" in report
    # 판정 없음: 사람이 판단·promote가 다음 단계라는 안내가 있고, 자동 승인 표기는 없다.
    assert "promote" in report
    assert "판정 없음" in report
    assert "approved" not in report  # pending 행을 승인으로 표시하지 않음
    # 마지막 줄은 ReviewAidSummary JSON(스냅샷·회귀).
    last = report.splitlines()[-1]
    parsed = ReviewAidSummary.model_validate_json(last)
    assert parsed.kebab_groups == 1
    assert parsed.candidates == 1


def test_format_flags_dangling_and_missing_kebab() -> None:
    corpus = load_corpus(_corpus_text("M0019"))
    items = [
        _item(kebab_id=KEBAB_A, mis_id="M9999"),  # dangling
        _item(kebab_id="fake-kebab", mis_id="M0019"),  # not in catalog
    ]
    groups = build_review_aid(items, corpus=corpus)
    report = format_review_aid(groups, statuses=("pending",))
    assert "코퍼스에 없음" in report  # dangling 경고
    assert "카탈로그에 없음" in report  # 전사 왜곡 경고


def test_format_empty_groups_still_has_summary_line() -> None:
    report = format_review_aid([], statuses=("pending",))
    parsed = ReviewAidSummary.model_validate_json(report.splitlines()[-1])
    assert parsed.kebab_groups == 0
    assert parsed.candidates == 0


def test_format_includes_decision_checklist_with_blank_boxes() -> None:
    corpus = load_corpus(_corpus_text("M0019"))
    items = [_item(kebab_id=KEBAB_A, mis_id="M0019", confidence=0.95)]
    report = format_review_aid(build_review_aid(items, corpus=corpus), statuses=("pending",))
    # 체크리스트: 기계 전제(객관 ✓/✗) + 교수학 판단(빈 박스).
    assert "검수 체크리스트" in report
    assert "기계 전제(promote)" in report
    assert "kebab∈카탈로그 ✓" in report and "M-id∈코퍼스 ✓" in report
    assert "직접매핑 conf≥0.6 ✓" in report
    assert "교수학 판단(Kiki)" in report
    assert "canonical·반례 타당" in report and "4지선다 귀속 타당" in report
    # 불변: 어떤 행도 승인/반려로 *표시*하지 않는다 — 박스는 전부 공란([ ]), 체크 마크 없음.
    assert "[ ] approve" in report and "[ ] reject" in report
    assert "[x]" not in report and "[X]" not in report and "☑" not in report


def test_format_checklist_flags_gate_blocked_direct_mapping() -> None:
    # 직접매핑 conf 0.5 → 기계 전제 ✗(승인해도 promote 거부)를 체크리스트가 드러낸다.
    corpus = load_corpus(_corpus_text("M0019"))
    items = [_item(kebab_id=KEBAB_A, mis_id="M0019", confidence=0.5)]
    report = format_review_aid(build_review_aid(items, corpus=corpus), statuses=("pending",))
    assert "직접매핑 conf≥0.6 ✗" in report


# ── CLI ──────────────────────────────────────────────────────────────────


def _write_queue(path: Path, items: list[CrosslinkReviewItem]) -> None:
    rows = [json.loads(i.model_dump_json()) for i in items]
    path.write_text(json.dumps({"review_queue": rows}, ensure_ascii=False), encoding="utf-8")


def test_main_cli_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    queue = tmp_path / "queue.json"
    corpus = tmp_path / "corpus.json"
    _write_queue(queue, [_item(kebab_id=KEBAB_A, mis_id="M0019", confidence=0.95)])
    corpus.write_text(_corpus_text("M0019"), encoding="utf-8")
    rc = main(["--queue", str(queue), "--corpus", str(corpus)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "오사고-M0019" in out
    ReviewAidSummary.model_validate_json(out.strip().splitlines()[-1])


def test_main_cli_missing_queue_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(_corpus_text("M0019"), encoding="utf-8")
    rc = main(["--queue", str(tmp_path / "nope.json"), "--corpus", str(corpus)])
    assert rc == 2
    assert "없음" in capsys.readouterr().out


def test_main_cli_status_all_includes_approved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    queue = tmp_path / "queue.json"
    corpus = tmp_path / "corpus.json"
    _write_queue(
        queue,
        [
            _item(kebab_id=KEBAB_A, mis_id="M1", status="pending"),
            _item(
                kebab_id=KEBAB_A,
                mis_id="M2",
                status="approved",
            ),
        ],
    )
    corpus.write_text(_corpus_text("M1", "M2"), encoding="utf-8")
    rc = main(["--queue", str(queue), "--corpus", str(corpus), "--status", "all"])
    assert rc == 0
    summary = ReviewAidSummary.model_validate_json(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary.candidates == 2


def test_main_cli_kebab_filter_scopes_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    queue = tmp_path / "queue.json"
    corpus = tmp_path / "corpus.json"
    _write_queue(
        queue,
        [_item(kebab_id=KEBAB_A, mis_id="M1"), _item(kebab_id=KEBAB_B, mis_id="M2")],
    )
    corpus.write_text(_corpus_text("M1", "M2"), encoding="utf-8")
    rc = main(["--queue", str(queue), "--corpus", str(corpus), "--kebab", KEBAB_A])
    assert rc == 0
    out = capsys.readouterr().out
    summary = ReviewAidSummary.model_validate_json(out.strip().splitlines()[-1])
    assert summary.kebab_groups == 1  # KEBAB_A만
    assert KEBAB_B not in out


def test_main_cli_rejects_bad_top_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    queue = tmp_path / "queue.json"
    corpus = tmp_path / "corpus.json"
    queue.write_text(json.dumps({"candidates": []}), encoding="utf-8")  # 오투입
    corpus.write_text(_corpus_text("M0019"), encoding="utf-8")
    rc = main(["--queue", str(queue), "--corpus", str(corpus)])
    assert rc == 1
    assert "거부" in capsys.readouterr().out


def test_real_review_queue_and_corpus_join(capsys: pytest.CaptureFixture[str]) -> None:
    """실 검수 큐 + 실 코퍼스로 리포트가 관통하는지(스모크) — 레포 루트 기준 경로."""
    repo_root = Path(__file__).resolve().parents[3]
    queue = repo_root / "docs/data/misconception_crosslink_review_queue.json"
    corpus = repo_root / "data/corpus/misconceptions_v1/misconceptions.json"
    if not queue.exists() or not corpus.exists():
        pytest.skip("실 큐/코퍼스 파일 부재")
    rc = main(["--queue", str(queue), "--corpus", str(corpus)])
    assert rc == 0
    summary = ReviewAidSummary.model_validate_json(capsys.readouterr().out.strip().splitlines()[-1])
    # 실 큐는 pending 75행 전후 — kebab 그룹·후보가 실재.
    assert summary.kebab_groups > 0
    assert summary.candidates > 0
