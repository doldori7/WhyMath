"""코퍼스 감사 CLI 테스트 — 초인간 검증 S5(순수·결정론·라이브 0).

결함율 Wilson 상한 집계·표본 부족/임계 초과 게이트·JSONL 파싱을 동결.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whymath_backend.harness import corpus_audit_eval as ca


def _write(path: Path, n_ok: int, n_defect: int, defect_class: str = "answer_error") -> Path:
    lines = []
    for i in range(n_ok):
        lines.append(f'{{"problem_id": "ok-{i}", "verdict": "ok"}}')
    for i in range(n_defect):
        lines.append(
            f'{{"problem_id": "d-{i}", "verdict": "defect", "defect_class": "{defect_class}"}}'
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_summarize_counts_and_upper_bound() -> None:
    labels = ca.load_labels(
        '{"problem_id":"a","verdict":"ok"}\n'
        '{"problem_id":"b","verdict":"defect","defect_class":"answer_error"}\n'
    )
    report = ca.summarize(labels)
    assert report.n == 2 and report.defects == 1
    assert report.defect_classes == {"answer_error": 1}
    ub = report.defect_rate_upper_bound(0.95)
    assert ub is not None and 0.5 < ub < 1.0  # 1/2 → 상한 크다(작은 표본)


def test_zero_defect_upper_bound_nonzero() -> None:
    # 결함 0/200이어도 상한>0 — 과신 금지.
    report = ca.summarize(
        ca.load_labels("\n".join(f'{{"problem_id":"p{i}","verdict":"ok"}}' for i in range(200)))
    )
    ub = report.defect_rate_upper_bound(0.95)
    assert ub is not None and 0.0 < ub < 0.02


def test_cli_gate_pass_clean_large_sample(tmp_path: Path) -> None:
    p = _write(tmp_path / "clean.jsonl", n_ok=200, n_defect=0)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200"])
    assert rc == 0


def test_cli_gate_fail_on_small_sample(tmp_path: Path) -> None:
    p = _write(tmp_path / "small.jsonl", n_ok=50, n_defect=0)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200"])
    assert rc == 1  # 표본 부족


def test_cli_gate_fail_on_high_defect_rate(tmp_path: Path) -> None:
    p = _write(tmp_path / "dirty.jsonl", n_ok=180, n_defect=20)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200"])
    assert rc == 1  # 결함율 상한 초과


def test_load_labels_skips_comments_and_blanks() -> None:
    labels = ca.load_labels('# 주석\n\n{"problem_id":"x","verdict":"ok"}\n')
    assert len(labels) == 1


def test_load_labels_reports_line_number() -> None:
    with pytest.raises(ValueError, match="line 1"):
        ca.load_labels('{"bad": true}')
