"""전 코퍼스 재검증 CLI 테스트 — 초인간 검증 S6(순수·결정론·라이브 0).

정상 레코드 통과·오염 레코드 fail(exit 1)·verify 재료 없음 skip·fuzz 모드를 동결.
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness import corpus_reverify as cr

_OK = {
    "slug": "ok-1",
    "verify": {
        "conditions": "x**2 - 5*x = 0",
        "answer_map": {"x": "5"},
        "answer_selection": "largest",
    },
}
_WRONG_ANSWER = {
    "slug": "bad-1",
    "verify": {
        "conditions": "x**2 - 5*x = 0",
        "answer_map": {"x": "6"},  # 6은 근이 아님
        "answer_selection": "largest",
    },
}
_WRONG_SELECTION = {
    "slug": "bad-2",
    "verify": {
        "conditions": "x**2 - 5*x = 0",
        "answer_map": {"x": "5"},
        "answer_selection": "smallest",  # 작은 근은 0
    },
}
_NO_VERIFY = {"slug": "skip-1", "question_text": "설명형 문항"}


def test_pass_on_correct_record() -> None:
    report = cr.reverify_corpus([_OK], use_fuzz=False)
    assert report.passed == 1 and report.failed == 0 and report.skipped == 0


def test_fail_on_wrong_answer() -> None:
    report = cr.reverify_corpus([_WRONG_ANSWER], use_fuzz=False)
    assert report.failed == 1
    assert report.failures[0][0] == "bad-1"


def test_fail_on_wrong_selection() -> None:
    report = cr.reverify_corpus([_WRONG_SELECTION], use_fuzz=False)
    assert report.failed == 1


def test_skip_on_missing_verify() -> None:
    report = cr.reverify_corpus([_NO_VERIFY], use_fuzz=False)
    assert report.skipped == 1 and report.failed == 0


def test_fuzz_mode_catches_wrong_answer() -> None:
    report = cr.reverify_corpus([_WRONG_ANSWER], use_fuzz=True)
    assert report.failed == 1


def test_cli_exit_zero_on_clean(tmp_path: Path) -> None:
    p = tmp_path / "clean.jsonl"
    p.write_text(json.dumps(_OK, ensure_ascii=False) + "\n", encoding="utf-8")
    assert cr.main([str(p)]) == 0


def test_cli_exit_one_on_corruption(tmp_path: Path) -> None:
    p = tmp_path / "dirty.jsonl"
    p.write_text(
        json.dumps(_OK, ensure_ascii=False)
        + "\n"
        + json.dumps(_WRONG_ANSWER, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    assert cr.main([str(p)]) == 1


def test_cli_multiple_paths(tmp_path: Path) -> None:
    clean = tmp_path / "a.jsonl"
    clean.write_text(json.dumps(_OK, ensure_ascii=False) + "\n", encoding="utf-8")
    dirty = tmp_path / "b.jsonl"
    dirty.write_text(json.dumps(_WRONG_ANSWER, ensure_ascii=False) + "\n", encoding="utf-8")
    # 하나라도 실패면 전체 exit 1.
    assert cr.main([str(clean), str(dirty)]) == 1


# ── 근 집계(합/곱) 문항 재검증 ─────────────────────────────────────────────
_AGG_OK = {
    "slug": "agg-ok",
    "answer": "10",
    "verify": {
        "conditions": "x**3 - 9*x - 10 = 0",
        "answer_map": {},
        "answer_aggregate": "product",
    },
}
_AGG_BAD = {
    "slug": "agg-bad",
    "answer": "11",
    "verify": {
        "conditions": "x**3 - 9*x - 10 = 0",
        "answer_map": {},
        "answer_aggregate": "product",
    },
}


def test_aggregate_pass() -> None:
    report = cr.reverify_corpus([_AGG_OK], use_fuzz=False)
    assert report.passed == 1 and report.failed == 0


def test_aggregate_wrong_fails() -> None:
    report = cr.reverify_corpus([_AGG_BAD], use_fuzz=False)
    assert report.failed == 1


# ── Tier2 단계 재검증(S2-02) — solution_steps 보유 레코드의 전이 연쇄 검산 ──

_STEPS_OK = {
    "slug": "steps-ok",
    "verify": {
        "conditions": "x**2 - 3*x - 10 = 0",
        "answer_map": {"x": "5"},
        "answer_selection": "largest",
        "solution_steps": ["x**2 - 3*x - 10", "(x - 5)*(x + 2)"],
    },
}
_STEPS_BAD = {
    "slug": "steps-bad",
    "verify": {
        "conditions": "x**2 - 3*x - 10 = 0",
        "answer_map": {"x": "5"},
        "answer_selection": "largest",
        # 부호 반전 인수분해 — 원식과 비동치(확정 오염) → Tier2 fail
        "solution_steps": ["x**2 - 3*x - 10", "(x + 5)*(x - 2)"],
    },
}


def test_steps_correct_chain_passes() -> None:
    report = cr.reverify_corpus([_STEPS_OK], use_fuzz=False)
    assert report.passed == 1 and report.failed == 0


def test_steps_incorrect_chain_fails() -> None:
    # Tier1(답=근)이 통과해도 단계 전이가 비동치면 Tier2가 잡는다(단계 오염 검출).
    report = cr.reverify_corpus([_STEPS_BAD], use_fuzz=False)
    assert report.failed == 1
    assert "Tier2" in report.failures[0][1]
