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


# --- as-found 병기 게이트(§4.5) ---


def _write_with_as_found(
    path: Path, n_ok: int, n_defect: int, *, af_n: int, af_defects: int
) -> Path:
    _write(path, n_ok, n_defect)
    body = path.read_text(encoding="utf-8")
    header = f'{{"as_found_n": {af_n}, "as_found_defects": {af_defects}}}\n'
    path.write_text(header + body, encoding="utf-8")
    return path


def test_load_audit_separates_as_found_from_labels() -> None:
    audit = ca.load_audit(
        '{"as_found_n": 240, "as_found_defects": 2}\n'
        '{"problem_id":"a","verdict":"ok"}\n'
        '{"problem_id":"b","verdict":"defect"}\n'
    )
    assert len(audit.labels) == 2
    assert audit.as_found is not None
    assert audit.as_found.as_found_n == 240 and audit.as_found.as_found_defects == 2
    # as-found 상한은 항상 값(n≥1) — 2/240은 2% 초과(FAIL이어도 병기 자체가 의무).
    ub = audit.as_found.defect_rate_upper_bound(0.95)
    assert ub > 0.02


def test_load_labels_ignores_as_found_declaration() -> None:
    # 하위호환 — load_labels는 라벨만 반환(as-found 선언 제외).
    labels = ca.load_labels(
        '{"as_found_n": 240, "as_found_defects": 2}\n{"problem_id":"x","verdict":"ok"}\n'
    )
    assert len(labels) == 1


def test_as_found_defects_exceeding_n_rejected() -> None:
    with pytest.raises(ValueError):
        ca.load_audit('{"as_found_n": 10, "as_found_defects": 11}')


def test_duplicate_as_found_declaration_rejected() -> None:
    with pytest.raises(ValueError, match="중복"):
        ca.load_audit(
            '{"as_found_n": 10, "as_found_defects": 1}\n'
            '{"as_found_n": 20, "as_found_defects": 2}\n'
        )


def test_require_as_found_pass_when_present(tmp_path: Path, capsys) -> None:
    p = _write_with_as_found(tmp_path / "af.jsonl", n_ok=200, n_defect=0, af_n=240, af_defects=2)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200", "--require-as-found"])
    assert rc == 0
    assert "as-found 병기" in capsys.readouterr().out  # 리포트에 병기 라인 노출


def test_require_as_found_fail_when_absent(tmp_path: Path) -> None:
    p = _write(tmp_path / "no_af.jsonl", n_ok=200, n_defect=0)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200", "--require-as-found"])
    assert rc == 1  # as-found 병기 선언 부재 → 게이트 미달


def test_as_found_opt_in_noop_when_flag_off(tmp_path: Path) -> None:
    # 플래그 미지정이면 병기 선언 부재여도 통과(opt-in·기존 동작 불변).
    p = _write(tmp_path / "no_af2.jsonl", n_ok=200, n_defect=0)
    rc = ca.main([str(p), "--max-defect-upper", "0.02", "--min-n", "200"])
    assert rc == 0
