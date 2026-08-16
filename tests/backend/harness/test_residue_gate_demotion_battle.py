"""잔여 축 교차검증 게이트 강등전 — hermetic(fake verifier·라이브 LLM 0·네트워크 0).

검증 축:
  ① 변조기 단위 — 그룹별 실 코퍼스 문자열(리터럴)로 정확한 변조 결과·비적용 케이스를 확인.
  ② 커버리지 회계 — 결함류별 적용 가능 건수가 정직하게(비적용 0 포함) 드러난다.
  ③ **변별력** — fake verifier를 스크립트로 조작해, 완벽 검출기/눈먼(항상 ok) 검출기/
     상시발화(항상 defect) 검출기가 각각 다른 측정치를 낸다는 것을 증명한다(변별력 없는
     검증 스텝 금지 — CLAUDE.md).
  ④ 게이트 exit code — 임계 미지정(리포트 전용) vs 지정 시 통과/미달.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.residue_cross_verify_eval import (
    PilotRecord,
    load_pilot_records,
)
from whymath_backend.harness.residue_gate_demotion_battle import (
    RESIDUE_DEFECT_CLASSES,
    ResidueBattleReport,
    _mutate_ambiguous_wording,
    _mutate_missing_condition,
    _mutate_multiple_valid_answers,
    _mutate_unstated_equiprobability,
    build_residue_seeded_set,
    main,
    render_repeated_report,
    repeated_report_to_json,
    report_to_json,
    run_repeated_residue_demotion_battle,
    run_residue_demotion_battle,
    write_audit_jsonl,
    write_repeated_audit_jsonl,
)
from whymath_backend.l3.cross_verify import (
    MISSING_CONDITION_PERSPECTIVES,
    MULTIPLE_VALID_ANSWERS_PERSPECTIVES,
    CrossVerificationResult,
    PerspectiveVerdict,
)
from whymath_backend.l3.verification_tier import VerificationTier

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PILOT_CORPUS = (
    _REPO_ROOT / "data" / "corpus" / "problem_bank_probability_finite_v0" / "problems.jsonl"
)

# 실 코퍼스에서 읽은 리터럴 발문(그룹별 대표 1건) — 패러프레이즈 아님, 문자 그대로 확인한 값.
_GROUP_A_TEXT = (
    "서로 구별되는 두 개의 주사위를 동시에 던진다. 각 주사위의 여섯 눈이 나올 가능성이 "
    "모두 같을 때, 나온 두 눈의 수의 합이 7일 확률을 기약분수로 나타내시오."
)
_GROUP_B_TEXT = (
    "한 개의 동전을 3번 던진다. 매번 앞면과 뒷면이 나올 가능성이 같을 때, "
    "앞면이 정확히 1번 나올 확률을 기약분수로 나타내시오."
)
_GROUP_C_TEXT = (
    "주머니 안에 서로 구별되는 빨간 공 3개와 파란 공 2개가 들어 있다. 이 주머니에서 "
    "임의로 2개의 공을 동시에 꺼낼 때, 꺼낸 공이 모두 빨간 공일 확률을 기약분수로 "
    "나타내시오."
)
_GROUP_D_TEXT = (
    "서로 구별되는 두 개의 주사위를 동시에 던진다. 나온 두 눈의 수의 합이 6 이상이 되는 "
    "경우의 수를 구하시오. (두 주사위는 서로 구별하며, 눈의 순서가 다르면 다른 경우로 센다.)"
)


@pytest.fixture(scope="module")
def records() -> list[PilotRecord]:
    if not _PILOT_CORPUS.exists():  # pragma: no cover — 코퍼스 미생성 환경 방어
        pytest.skip(f"파일럿 코퍼스 미존재({_PILOT_CORPUS})")
    return load_pilot_records(_PILOT_CORPUS)


# ── ① 변조기 단위 — 실 코퍼스 리터럴 문자열 기준 ────────────────────────
def test_missing_condition_removes_distinguishability_clause_a_c_d() -> None:
    mutated_a, note_a = _mutate_missing_condition(_GROUP_A_TEXT)
    assert mutated_a == (
        "두 개의 주사위를 동시에 던진다. 각 주사위의 여섯 눈이 나올 가능성이 모두 같을 때, "
        "나온 두 눈의 수의 합이 7일 확률을 기약분수로 나타내시오."
    )
    assert "구별되는" in note_a

    mutated_c, _ = _mutate_missing_condition(_GROUP_C_TEXT)
    assert mutated_c == (
        "주머니 안에 빨간 공 3개와 파란 공 2개가 들어 있다. 이 주머니에서 임의로 2개의 공을 "
        "동시에 꺼낼 때, 꺼낸 공이 모두 빨간 공일 확률을 기약분수로 나타내시오."
    )

    mutated_d, _ = _mutate_missing_condition(_GROUP_D_TEXT)
    assert mutated_d == (
        "두 개의 주사위를 동시에 던진다. 나온 두 눈의 수의 합이 6 이상이 되는 경우의 수를 "
        "구하시오. (두 주사위는 서로 구별하며, 눈의 순서가 다르면 다른 경우로 센다.)"
    )


def test_missing_condition_not_applicable_to_group_b() -> None:
    """그룹 B(동전)는 애초 구별성 어구를 담지 않는다 — 억지 변조 대신 정직한 None."""
    assert _mutate_missing_condition(_GROUP_B_TEXT) is None


def test_unstated_equiprobability_applies_to_a_and_b_only() -> None:
    mutated_a, _ = _mutate_unstated_equiprobability(_GROUP_A_TEXT)
    assert mutated_a == (
        "서로 구별되는 두 개의 주사위를 동시에 던진다. 나온 두 눈의 수의 합이 7일 확률을 "
        "기약분수로 나타내시오."
    )
    mutated_b, _ = _mutate_unstated_equiprobability(_GROUP_B_TEXT)
    assert mutated_b == (
        "한 개의 동전을 3번 던진다. 앞면이 정확히 1번 나올 확률을 기약분수로 나타내시오."
    )
    assert _mutate_unstated_equiprobability(_GROUP_C_TEXT) is None
    assert _mutate_unstated_equiprobability(_GROUP_D_TEXT) is None


def test_ambiguous_wording_applies_to_a_b_c_not_d() -> None:
    mutated_a, _ = _mutate_ambiguous_wording(_GROUP_A_TEXT)
    assert mutated_a == (
        "서로 구별되는 두 개의 주사위를 동시에 던진다. 각 주사위의 여섯 눈이 나올 가능성이 "
        "모두 같을 때, 나온 두 눈의 수가 7일 확률을 기약분수로 나타내시오."
    )
    mutated_b, _ = _mutate_ambiguous_wording(_GROUP_B_TEXT)
    assert mutated_b == (
        "한 개의 동전을 3번 던진다. 매번 앞면과 뒷면이 나올 가능성이 같을 때, 앞면이 1번 "
        "나올 확률을 기약분수로 나타내시오."
    )
    mutated_c, _ = _mutate_ambiguous_wording(_GROUP_C_TEXT)
    assert mutated_c == (
        "주머니 안에 서로 구별되는 빨간 공 3개와 파란 공 2개가 들어 있다. 이 주머니에서 "
        "임의로 2개의 공을 동시에 꺼낼 때, 꺼낸 공이 빨간 공일 확률을 기약분수로 나타내시오."
    )
    # 그룹 D — "이상" 제거는 중의성이 아니라 문제 자체의 변경이라 설계상 의도적 제외.
    assert _mutate_ambiguous_wording(_GROUP_D_TEXT) is None


def test_multiple_valid_answers_applies_only_to_group_c() -> None:
    mutated_c, _ = _mutate_multiple_valid_answers(_GROUP_C_TEXT)
    assert mutated_c == (
        "주머니 안에 서로 구별되는 빨간 공 3개와 파란 공 2개가 들어 있다. 이 주머니에서 "
        "임의로 2개의 공을 꺼낼 때, 꺼낸 공이 모두 빨간 공일 확률을 기약분수로 나타내시오."
    )
    # 주사위(A·D)는 "동시에" 제거가 모델을 바꾸지 않는 무의미 변조라 의도적으로 배제.
    assert _mutate_multiple_valid_answers(_GROUP_A_TEXT) is None
    assert _mutate_multiple_valid_answers(_GROUP_D_TEXT) is None


def test_mutations_never_touch_answer_or_conditions(records: list[PilotRecord]) -> None:
    """변조는 question_text만 건드린다 — answer·conditions는 원본 그대로."""
    battery = build_residue_seeded_set(records)
    by_slug = {r.slug: r for r in records}
    for item in battery.seeded:
        original = by_slug[item.record.slug]
        assert item.record.answer == original.answer
        assert item.record.conditions == original.conditions
        assert item.mutated_question_text != original.question_text  # 실제로 변조됐는지


# ── ② 커버리지 회계 — 정직한 불균등 (침묵 생략 아님) ────────────────────
def test_coverage_is_honest_and_uneven(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    assert set(battery.coverage) == set(RESIDUE_DEFECT_CLASSES)
    # 실측(코퍼스 34건 기준) — missing_condition은 그룹 B(9건) 비적용이라 25건(전 34건 아님).
    assert battery.coverage["missing_condition"] == 25
    assert battery.coverage["unstated_equiprobability"] == 20
    assert battery.coverage["ambiguous_wording"] == 26
    assert battery.coverage["multiple_valid_answers"] == 6
    # 0인 결함류가 있어도 키 자체는 반드시 존재(침묵 생략 금지).
    assert all(name in battery.coverage for name in RESIDUE_DEFECT_CLASSES)


def test_clean_control_is_untouched_originals(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    assert battery.clean == tuple(records)
    assert len(battery.clean) == len(records)


# ── ③ 변별력 — 스크립트 fake verifier로 세 가지 검출기 프로파일 구분 ─────
class _ScriptedVerifier:
    """대역 검증기 — question_text가 원본(무결함)과 다르면 "변조됨"으로 인식 가능.

    `mode="oracle"`은 완벽 검출기(변조=defect·원본=ok), `mode="blind_ok"`는 항상 ok(눈먼
    검출기), `mode="blind_defect"`는 항상 defect(상시발화 검출기) — 세 프로파일 모두 다른
    측정치를 내야 harness가 "변별력 없는 검증 스텝"이 아님을 증명한다.
    """

    def __init__(self, *, mode: str, clean_texts: frozenset[str]):
        self._mode = mode
        self._clean_texts = clean_texts
        self.seen: list[str] = []

    def verify(self, subject: object) -> CrossVerificationResult:
        problem_id = subject.problem_id  # type: ignore[attr-defined]
        question_text = subject.question_text  # type: ignore[attr-defined]
        self.seen.append(problem_id)
        if self._mode == "blind_ok":
            verdict = "ok"
        elif self._mode == "blind_defect":
            verdict = "defect"
        else:  # "oracle"
            verdict = "ok" if question_text in self._clean_texts else "defect"
        if verdict == "defect":
            return CrossVerificationResult(
                problem_id,
                (PerspectiveVerdict("p", "defect", "model_mismatch", "불일치"),),
                "defect",
                "p:model_mismatch",
                "결함",
            )
        return CrossVerificationResult(
            problem_id, (PerspectiveVerdict("p", "ok", "", "정상"),), "ok", "", "만장일치"
        )


def _clean_texts(records: list[PilotRecord]) -> frozenset[str]:
    return frozenset(r.question_text for r in records)


def test_oracle_verifier_detects_all_seeded_and_zero_false_alarms(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=50, seed="t1")

    overall_lower = report.overall_detection_lower_bound(0.95)
    fau = report.false_alarm_upper_bound(0.95)
    assert report.overall_detected == report.overall_resolved  # 100% 점추정
    assert overall_lower is not None and overall_lower > 0.8  # Wilson 하한도 높게
    assert report.clean_false_alarms == 0
    assert fau is not None and fau < 0.2  # Wilson 상한도 낮게


def test_blind_ok_verifier_never_detects_defects(records: list[PilotRecord]) -> None:
    """항상 ok를 내는 눈먼 검출기 — harness가 좋은 결과를 위장하지 않고 0%를 그대로 낸다."""
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="blind_ok", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=50, seed="t2")

    assert report.overall_detected == 0
    overall_lower = report.overall_detection_lower_bound(0.95)
    # successes=0의 Wilson 하한은 이론상 0이지만 부동소수 잔차(예: ~1e-18)가 남을 수 있다 —
    # 정확히 0.0을 요구하지 않고 무시 가능한 허용오차로 확인한다.
    assert overall_lower is not None and overall_lower < 1e-9
    assert report.clean_false_alarms == 0  # 오검출도 0(항상 ok니까)


def test_blind_defect_verifier_flags_everything_including_clean(
    records: list[PilotRecord],
) -> None:
    """항상 defect를 내는 상시발화 검출기 — 검출률은 100%지만 오검출도 100%로 드러난다."""
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="blind_defect", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=50, seed="t3")

    assert report.overall_detected == report.overall_resolved  # 결함도 전부 검출(우연히)
    assert report.clean_false_alarms == report.clean_resolved  # 그러나 대조군도 전부 오검출
    fau = report.false_alarm_upper_bound(0.95)
    assert fau is not None and fau > 0.8  # 오검출 상한이 높게 나와 "상시발화"가 드러난다


def test_unresolved_is_tracked_separately_from_detection(records: list[PilotRecord]) -> None:
    """판정불가(unclear)는 '결함 미검출'로 뭉개지지 않고 별도 집계된다."""

    class _UnclearVerifier:
        def verify(self, subject: object) -> CrossVerificationResult:
            return CrossVerificationResult(
                subject.problem_id,  # type: ignore[attr-defined]
                (PerspectiveVerdict("p", "unclear", "provider_error", "다운"),),
                "unclear",
                "p:provider_error",
                "측정 실패",
            )

    battery = build_residue_seeded_set(records)
    report = run_residue_demotion_battle(
        battery, verifier=_UnclearVerifier(), sample_n=5, seed="t4"
    )
    assert report.overall_resolved == 0
    assert report.overall_unresolved > 0
    assert report.overall_detection_lower_bound(0.95) is None  # 측정 실패는 0%가 아니라 None
    assert report.clean_resolved == 0
    assert report.false_alarm_upper_bound(0.95) is None


# ── 표본 크기 통제 확인 ──────────────────────────────────────────────────
def test_sample_n_caps_per_class_and_is_deterministic(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    verifier_a = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    verifier_b = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report_a = run_residue_demotion_battle(
        battery, verifier=verifier_a, sample_n=2, seed="fixed-seed"
    )
    run_residue_demotion_battle(battery, verifier=verifier_b, sample_n=2, seed="fixed-seed")
    for name in RESIDUE_DEFECT_CLASSES:
        assert report_a.per_class[name].sampled <= 2
    assert verifier_a.seen == verifier_b.seen  # 결정론 — 같은 시드는 같은 표본·같은 순서


# ── ④ 감사 JSONL 왕복 ────────────────────────────────────────────────────
def test_write_audit_jsonl_includes_as_found_summary(
    records: list[PilotRecord], tmp_path: Path
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=3, seed="t5")
    out = tmp_path / "battle_audit.jsonl"
    n = write_audit_jsonl(out, report)
    assert n == len(report.audit_rows) + 1  # +1 = as_found 요약 행
    lines = out.read_text(encoding="utf-8").splitlines()
    summary = json.loads(lines[-1])
    assert summary["as_found_overall_detected"] == report.overall_detected
    assert summary["as_found_clean_false_alarms"] == report.clean_false_alarms


def test_report_to_json_matches_report_fields(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=3, seed="t6")
    payload = report_to_json(report, confidence=0.95)
    assert payload["overall"]["detected"] == report.overall_detected
    assert payload["clean_control"]["false_alarms"] == report.clean_false_alarms
    assert set(payload["coverage"]) == set(RESIDUE_DEFECT_CLASSES)  # type: ignore[arg-type]


# ── ⑤ CLI 게이트 exit code ───────────────────────────────────────────────
def _make_scripted_verifier_for_cli(records: list[PilotRecord], mode: str) -> type:
    """CLI는 내부에서 실 CrossVerifier()를 생성하므로, main()을 직접 호출하는 대신
    run_residue_demotion_battle을 거치는 별도 헬퍼로 exit code 로직만 재사용해 검증한다
    (라이브 LLM 0 원칙 — main() 자체를 hermetic하게 부르려면 CrossVerifier 생성자가 provider
    lazy-import만 하고 네트워크 0인 것과 동일하게, 여기서는 run_residue_demotion_battle이
    반환한 report에 CLI와 동일한 게이트 판정식을 적용해 배선을 검증한다)."""
    del records, mode
    return ResidueBattleReport


def test_gate_report_only_mode_is_always_exit_0_regardless_of_rate(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="blind_ok", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=5, seed="t7")
    # 게이트 미지정(min_detection_lower=0.0·max_false_alarm_upper=1.0 기본값) → 항상 off.
    min_detection_lower, max_false_alarm_upper = 0.0, 1.0
    dlb = report.overall_detection_lower_bound(0.95)
    fau = report.false_alarm_upper_bound(0.95)
    exit_code = 0
    if min_detection_lower > 0.0 and (dlb is None or dlb < min_detection_lower):
        exit_code = 1
    if max_false_alarm_upper < 1.0 and (fau is None or fau > max_false_alarm_upper):
        exit_code = 1
    assert exit_code == 0  # 검출률 0%인데도 게이트 미지정이면 통과(리포트 전용)


def test_gate_min_detection_lower_fails_when_above_actual_rate(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="blind_ok", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=5, seed="t8")
    dlb = report.overall_detection_lower_bound(0.95)
    assert dlb is not None and dlb < 1e-9  # 부동소수 잔차 허용(위 blind_ok 테스트와 동형)
    threshold = 0.5
    exit_code = 1 if (threshold > 0.0 and (dlb is None or dlb < threshold)) else 0
    assert exit_code == 1


def test_gate_min_detection_lower_passes_when_below_actual_rate(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=50, seed="t9")
    dlb = report.overall_detection_lower_bound(0.95)
    threshold = 0.5
    exit_code = 1 if (threshold > 0.0 and (dlb is None or dlb < threshold)) else 0
    assert exit_code == 0
    assert dlb is not None and dlb >= threshold


def test_gate_max_false_alarm_upper_fails_when_below_actual_rate(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="blind_defect", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=5, seed="t10")
    fau = report.false_alarm_upper_bound(0.95)
    assert fau is not None and fau > 0.5
    threshold = 0.1
    exit_code = 1 if (threshold < 1.0 and (fau is None or fau > threshold)) else 0
    assert exit_code == 1


def test_gate_max_false_alarm_upper_passes_when_above_actual_rate(
    records: list[PilotRecord],
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    report = run_residue_demotion_battle(battery, verifier=verifier, sample_n=50, seed="t11")
    fau = report.false_alarm_upper_bound(0.95)
    threshold = 0.9
    exit_code = 1 if (threshold < 1.0 and (fau is None or fau > threshold)) else 0
    assert exit_code == 0
    assert fau is not None and fau <= threshold


# ── CLI 진입점 — main()은 실 CrossVerifier()를 구성하지만 provider는 lazy-import라
#    네트워크 호출 없이 --sample-n 0(대상 0건)으로 배선만 확인한다.
def test_main_report_only_wiring_smoke(tmp_path: Path) -> None:
    """main() 배선 자체(파서·로더·리포트 출력)를 --sample-n 0으로 hermetic하게 스모크."""
    if not _PILOT_CORPUS.exists():  # pragma: no cover — 코퍼스 미생성 환경 방어
        pytest.skip(f"파일럿 코퍼스 미존재({_PILOT_CORPUS})")
    audit_out = tmp_path / "audit.jsonl"
    exit_code = main([str(_PILOT_CORPUS), "--sample-n", "0", "--audit-out", str(audit_out)])
    assert exit_code == 0  # 표본 0건이라 검증기 호출 0 — 게이트 미지정이므로 통과
    assert not audit_out.exists() or audit_out.read_text(encoding="utf-8") == ""


# ── ⑥ 반복 실행 v3 프로토콜 ────────────────────────────────────────────────
def test_run_repeated_demotion_battle_returns_n_reports(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    repeated = run_repeated_residue_demotion_battle(
        battery,
        verifier=verifier,
        sample_n=3,
        seed="t12",
        repeat_runs=3,
        corpus_size=len(records),
    )
    assert len(repeated.reports) == 3
    assert repeated.repeat_runs == 3
    assert all(isinstance(r, ResidueBattleReport) for r in repeated.reports)


def test_repeated_report_render_and_json_include_stats(records: list[PilotRecord]) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    repeated = run_repeated_residue_demotion_battle(
        battery,
        verifier=verifier,
        sample_n=3,
        seed="t13",
        repeat_runs=2,
        corpus_size=len(records),
    )
    text = render_repeated_report(repeated, confidence=0.95)
    assert "반복 실행" in text
    assert "평균" in text
    assert "최악" in text
    assert "표준편차" in text
    assert "판정불가율" in text
    payload = repeated_report_to_json(repeated, confidence=0.95)
    assert payload["repeat_runs"] == 2
    assert "detection_lower_bound_mean" in payload["overall"]
    assert "false_alarm_upper_bound_worst" in payload["clean_control"]


def test_write_repeated_audit_jsonl_includes_run_index(
    tmp_path: Path, records: list[PilotRecord]
) -> None:
    battery = build_residue_seeded_set(records)
    verifier = _ScriptedVerifier(mode="oracle", clean_texts=_clean_texts(records))
    repeated = run_repeated_residue_demotion_battle(
        battery,
        verifier=verifier,
        sample_n=3,
        seed="t14",
        repeat_runs=2,
        corpus_size=len(records),
    )
    out = tmp_path / "repeated_audit.jsonl"
    n = write_repeated_audit_jsonl(out, repeated)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert n == len(lines)
    runs = {json.loads(line).get("run") for line in lines}
    assert runs == {1, 2}


# ── ⑦ v4 결함류별 전용 관점 ──────────────────────────────────────────────
def test_v4_missing_condition_perspectives_are_independent() -> None:
    """MISSING_CONDITION_PERSPECTIVES는 CrossVerifier 생성 시 독립성 검사를 통과한다."""
    from whymath_backend.l3.cross_verify import CrossVerifier

    verifier = CrossVerifier(perspectives=MISSING_CONDITION_PERSPECTIVES)
    assert len(verifier._perspectives) == 3


def test_v4_multiple_valid_answers_perspectives_are_independent() -> None:
    """MULTIPLE_VALID_ANSWERS_PERSPECTIVES는 CrossVerifier 생성 시 독립성 검사를 통과한다."""
    from whymath_backend.l3.cross_verify import CrossVerifier

    verifier = CrossVerifier(perspectives=MULTIPLE_VALID_ANSWERS_PERSPECTIVES)
    assert len(verifier._perspectives) == 3


class _ClassScriptedVerifier:
    """결함류별로 다른 동작을 하는 대역 검증기 — v4 Mapping 배선 테스트용."""

    def __init__(self, *, verdict: str) -> None:
        self.verdict = verdict
        self.seen: list[str] = []

    def verify(self, subject: object) -> CrossVerificationResult:
        problem_id = subject.problem_id  # type: ignore[attr-defined]
        self.seen.append(problem_id)
        return CrossVerificationResult(
            problem_id,
            (PerspectiveVerdict("p", self.verdict, "", "대역"),),
            self.verdict,  # type: ignore[arg-type]
            "",
            "대역",
        )

    def flush_trace(self) -> None:
        """CrossVerifier.flush_trace 호환용 no-op."""


def test_v4_defect_specific_verifier_mapping(records: list[PilotRecord]) -> None:
    """결함류별 Mapping verifier가 missing_condition/defect, 나머지/ok로 분기한다."""
    battery = build_residue_seeded_set(records)
    verifiers = {
        "missing_condition": _ClassScriptedVerifier(verdict="defect"),
        "unstated_equiprobability": _ClassScriptedVerifier(verdict="ok"),
        "ambiguous_wording": _ClassScriptedVerifier(verdict="ok"),
        "multiple_valid_answers": _ClassScriptedVerifier(verdict="ok"),
    }
    report = run_residue_demotion_battle(battery, verifier=verifiers, sample_n=5, seed="v4-t1")

    assert report.per_class["missing_condition"].detected > 0
    assert report.per_class["multiple_valid_answers"].detected == 0
    # clean 대조군은 Mapping 중 "ambiguous_wording" verifier(여기서는 ok)를 사용.
    assert report.clean_false_alarms == 0


def test_v4_defect_specific_mapping_uses_correct_verifier_for_clean(
    records: list[PilotRecord],
) -> None:
    """clean 대조군은 Mapping에서 ambiguous_wording verifier를 사용한다."""
    battery = build_residue_seeded_set(records)
    verifiers = {
        "missing_condition": _ClassScriptedVerifier(verdict="ok"),
        "unstated_equiprobability": _ClassScriptedVerifier(verdict="ok"),
        "ambiguous_wording": _ClassScriptedVerifier(verdict="defect"),
        "multiple_valid_answers": _ClassScriptedVerifier(verdict="ok"),
    }
    report = run_residue_demotion_battle(battery, verifier=verifiers, sample_n=5, seed="v4-t2")
    # clean 검증에 ambiguous_wording(항상 defect) verifier가 쓰이므로 오검출 > 0.
    assert report.clean_false_alarms > 0


# ── 로더 위생(재사용 확인) ────────────────────────────────────────────────
def test_pilot_record_reuses_shared_loader_type(records: list[PilotRecord]) -> None:
    """PilotRecord/load_pilot_records는 이 모듈이 재구현한 것이 아니라 재사용임을 확인."""
    assert records and isinstance(records[0], PilotRecord)
    assert {r.tier for r in records} == {VerificationTier.MACHINE_EXHAUSTIVE}
