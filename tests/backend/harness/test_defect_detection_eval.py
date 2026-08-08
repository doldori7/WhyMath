"""강등전 하니스 hermetic 테스트 — 결함 주입기·기계 검출·Wilson·CLI(라이브 0).

`defect_seeder`가 결정론으로 시험지를 만들고, 현 스택이 결함 ①~⑤·⑦을 검출·⑥을 미검출
(정직한 공백)·무결함을 통과시킴을 동결한다. Wilson 경계는 손계산과 대조한다. ⑦(broken_latex)은
ARCH-19(품질 15축 ⑩) 확장 — 감사기 무관 결정론 100% 검출(구조 파스라 항상 걸림).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from whymath_backend.harness import defect_detection_eval as dd
from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.equivalent.acceptance import evaluate_equivalent_candidate
from whymath_backend.l3.equivalent.defect_seeder import (
    DEFECT_CLASSES,
    build_defect_seeded_set,
)

# ──────────────────────────────────────────────────────────────────────────
# Wilson 공용 부품 — 손계산 대조(l4/step_shadow_eval와 산술 동일).
# ──────────────────────────────────────────────────────────────────────────


def test_wilson_lower_bound_small_sample_penalized() -> None:
    # 5/5=1.0이라도 하한은 크게 깎인다(작은 표본 과신 방지·슬68 정본·≈0.65).
    lb = wilson_lower_bound(5, 5, 0.95)
    assert 0.60 < lb < 0.70  # ≈0.649
    assert wilson_lower_bound(0, 10, 0.95) == 0.0  # 성공 0 → 하한 0


def test_wilson_upper_bound_zero_observed_not_zero() -> None:
    # 관측 0이어도 상한>0 — "0 관측 = 확정 0"으로 과신하지 않는다(모르면 모른다).
    ub = wilson_upper_bound(0, 60, 0.95)
    assert 0.0 < ub < 0.05  # ≈0.043


def test_wilson_bounds_bracket_point_estimate() -> None:
    lb = wilson_lower_bound(45, 50, 0.95)
    ub = wilson_upper_bound(45, 50, 0.95)
    assert lb < 0.90 < ub  # 점추정 0.90을 구간이 감싼다


# ──────────────────────────────────────────────────────────────────────────
# 결함 주입기 — 결정론·구성.
# ──────────────────────────────────────────────────────────────────────────


def test_seeder_deterministic_same_seed() -> None:
    a = build_defect_seeded_set(n_defective=30, n_clean=30, seed=42)
    b = build_defect_seeded_set(n_defective=30, n_clean=30, seed=42)
    assert [i.candidate.problem.slug for i in a] == [j.candidate.problem.slug for j in b]
    assert [i.defect_class for i in a] == [j.defect_class for j in b]


def test_seeder_composition_counts() -> None:
    items = build_defect_seeded_set(n_defective=70, n_clean=70, seed=7)
    assert len(items) == 140
    assert sum(1 for i in items if i.defect_class) == 70
    assert sum(1 for i in items if not i.defect_class) == 70
    # 7종 결함이 균형 배정(70/7=10)된다.
    from collections import Counter

    counts = Counter(i.defect_class for i in items if i.defect_class)
    assert all(counts[k] == 10 for k in DEFECT_CLASSES)


def test_clean_items_pass_gate() -> None:
    # 무결함 문항은 전부 수용 게이트를 통과해야 한다(구성상 참).
    items = build_defect_seeded_set(n_defective=0, n_clean=24, seed=1)
    for item in items:
        c = item.candidate
        verdict = evaluate_equivalent_candidate(
            item.spec,
            c.problem,
            provenance=c.provenance,
            conditions=c.conditions,
            answer_map=c.answer_map,
            answer_selection=c.answer_selection,
        )
        assert verdict.accepted, f"무결함이 거부됨: {c.problem.slug} — {verdict.reasons}"


# ──────────────────────────────────────────────────────────────────────────
# 기계 검출 baseline — ①~⑤·⑦ 검출·⑥ 미검출 동결(감사기 도입 시 반전할 앵커).
# ──────────────────────────────────────────────────────────────────────────


def test_baseline_detection_per_class() -> None:
    items = build_defect_seeded_set(n_defective=70, n_clean=70, seed=20260708)
    report = dd.summarize(dd._run_machine(items))
    for name in (
        "answer_error",
        "explanation_slip",
        "condition_mismatch",
        "standard_tag_error",
        "broken_latex",
    ):
        detected, total = report.per_class[name]
        assert detected == total == 10, f"{name} 검출 실패"
    d_mc, t_mc = report.per_class["distractor_misattribution"]
    assert d_mc == t_mc == 10
    # ⑥ statement_mismatch — 현 스택 미검출(정직한 공백·retag 감사기의 대상).
    d6, t6 = report.per_class["statement_mismatch"]
    assert t6 == 10 and d6 == 0
    # 무결함 오검출 0.
    assert report.false_alarm == 0 and report.clean_total == 70


def test_report_wilson_bounds_present() -> None:
    items = build_defect_seeded_set(n_defective=70, n_clean=70, seed=20260708)
    report = dd.summarize(dd._run_machine(items))
    # 60/70 검출(⑥만 미검출) → 하한 ≈0.775.
    lb = report.detection_lower_bound(0.95)
    assert lb is not None and 0.74 < lb < 0.80
    ub = report.false_alarm_upper_bound(0.95)
    assert ub is not None and ub < 0.05


def test_with_auditor_detects_all_seven_classes() -> None:
    # 감사기 배선 시 statement_mismatch까지 검출 → 7종 전부 70/70, 오검출 0.
    items = build_defect_seeded_set(n_defective=70, n_clean=70, seed=20260708)
    report = dd.summarize(dd._run_machine(items, with_auditor=True))
    for name in DEFECT_CLASSES:
        detected, total = report.per_class[name]
        assert detected == total == 10, f"{name}: {detected}/{total}"
    assert report.false_alarm == 0
    # 140/140 검출 → 하한이 baseline(~0.775)보다 크게 상승(≈0.96+).
    lb = report.detection_lower_bound(0.95)
    assert lb is not None and lb > 0.95


def test_cli_with_auditor_passes_high_gate() -> None:
    # --with-auditor면 검출률 하한이 0.95 게이트를 통과한다.
    rc = dd.main(
        [
            "--n-defective",
            "120",
            "--n-clean",
            "120",
            "--seed",
            "20260708",
            "--with-auditor",
            "--min-detection-lower",
            "0.95",
        ]
    )
    assert rc == 0


# ──────────────────────────────────────────────────────────────────────────
# CLI — 기계 측정·블라인드 발행·강등 판정·게이트 exit code.
# ──────────────────────────────────────────────────────────────────────────


def test_cli_machine_measurement_exit_ok() -> None:
    rc = dd.main(["--n-defective", "12", "--n-clean", "12", "--seed", "3"])
    assert rc == 0


def test_cli_gate_fails_on_high_detection_threshold() -> None:
    # ⑥ 미검출 때문에 전체 검출률 하한(52/60·~0.78)은 0.95를 못 넘는다 → 게이트 exit 1.
    rc = dd.main(
        [
            "--n-defective",
            "60",
            "--n-clean",
            "60",
            "--seed",
            "20260708",
            "--min-detection-lower",
            "0.95",
        ]
    )
    assert rc == 1


def test_cli_false_alarm_gate_passes() -> None:
    # 오검출 0 → 상한 ≈0.043 < 0.05 게이트 통과.
    rc = dd.main(
        ["--n-defective", "30", "--n-clean", "60", "--seed", "5", "--max-false-alarm-upper", "0.05"]
    )
    assert rc == 0


def test_cli_emit_blind_and_key(tmp_path: Any) -> None:
    blind = tmp_path / "blind.jsonl"
    key = tmp_path / "key.jsonl"
    rc = dd.main(
        [
            "--n-defective",
            "6",
            "--n-clean",
            "6",
            "--seed",
            "9",
            "--emit-blind",
            str(blind),
            "--answer-key",
            str(key),
        ]
    )
    assert rc == 0
    blind_rows = [json.loads(x) for x in blind.read_text(encoding="utf-8").splitlines()]
    key_rows = [json.loads(x) for x in key.read_text(encoding="utf-8").splitlines()]
    assert len(blind_rows) == len(key_rows) == 12
    # 블라인드에는 정답지(defect_class)가 없다.
    assert all("defect_class" not in r for r in blind_rows)
    assert all("defect_class" in r for r in key_rows)
    # slug 정렬이 두 파일에서 일치(같은 문항).
    assert [r["slug"] for r in blind_rows] == [r["slug"] for r in key_rows]


def test_cli_demotion_verdict_with_human_labels(tmp_path: Path) -> None:
    # 사람이 결함의 60%만 잡았다고 라벨 → 기계 하한(~0.74) > 0.60 → 강등 성립.
    items = build_defect_seeded_set(n_defective=10, n_clean=10, seed=11)
    labels = tmp_path / "human.jsonl"
    with labels.open("w", encoding="utf-8") as fh:
        defect_seen = 0
        for item in items:
            is_defect = item.defect_class is not None
            human = "ok"
            if is_defect:
                defect_seen += 1
                human = "defect" if defect_seen % 10 < 6 else "ok"  # 대략 60% 검출
            fh.write(
                json.dumps(
                    {
                        "slug": item.candidate.problem.slug,
                        "is_defect": is_defect,
                        "human_label": human,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    rate = dd._human_detection_rate(labels)
    assert 0.0 <= rate <= 1.0
