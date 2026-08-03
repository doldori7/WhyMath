"""잔여 축 강등전 CLI hermetic 테스트(S4-16 — 라이브 LLM 0).

`harness/defect_detection_eval.py` 테스트의 확률 도메인 형제. `l3/finite_probability_defect_seeder`
가 만든 시험지를 `CrossVerifier`(또는 그 대역)에 태워 검출표를 낸다. 검증 축:
  ① `_build_subject` — 시더 항목 → `ResidueSubject` 조립(공용 조립기 재사용 확인).
  ② `_run_battle`/`summarize` — 실 `CrossVerifier(ScriptedProvider([...]))`로 결함
     3관점 전부 defect → aggregate=="defect", 무결함 3관점 전부 ok → 오검출 0.
  ③ **변별력** — provider 예외/파싱 실패로 나온 unclear가 분모(resolved)에서 빠지고
     unclear 카운트에만 잡힌다(측정 실패 ≠ 미검출).
  ④ CLI `main()` — `--min-detection-lower`/`--max-false-alarm-upper` 미지정이면 exit 0
     (리포트만), 지정하고 미충족이면 exit 1, 충족하면 exit 0. `--help`는 라이브 호출 없이
     정상 종료한다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whymath_backend.harness import residue_gate_demotion_battle as rgdb
from whymath_backend.l3.cross_verify import (
    CrossVerificationResult,
    CrossVerifier,
    PerspectiveVerdict,
    ResidueSubject,
)
from whymath_backend.l3.finite_probability import enumerate_model, parse_finite_model
from whymath_backend.l3.finite_probability_defect_seeder import (
    DEFECT_CLASSES,
    build_defect_seeded_residue_set,
)
from whymath_backend.l3.models import GenerationResult, RoutingDecision

# ──────────────────────────────────────────────────────────────────────────
# provider/verifier 대역 — tests/backend/l3/test_cross_verify.py의 ScriptedProvider 패턴을
# 그대로 가져온다(라이브 호출 0). RaisingProvider도 동형.
# ──────────────────────────────────────────────────────────────────────────


class ScriptedProvider:
    """관점 순서대로 응답을 방출하는 provider 대역 — LLMProvider 충족(네트워크 0)."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        self.calls.append((prompt, system))
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return GenerationResult(out)
        return GenerationResult("응답 없음")


class RaisingProvider:
    """항상 예외를 던지는 provider 대역 — 측정 실패가 통과/미검출로 위장되지 않는지 본다."""

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        raise RuntimeError("provider 다운(테스트)")


class RecordingSink:
    """관측 싱크 대역 — Langfuse 미사용."""

    def record(self, fields: dict[str, object]) -> None:
        pass

    def flush(self) -> None:
        pass


class StubVerifier:
    """`CrossVerifier.verify(subject)` 표면만 충족하는 대역 — 게이트/집계/CLI 배선 테스트용.

    실 검증기의 라우터·프롬프트 경로는 위 `ScriptedProvider` 기반 테스트가 따로 본다.
    """

    def __init__(
        self,
        *,
        defects: frozenset[str] = frozenset(),
        unclear: frozenset[str] = frozenset(),
    ) -> None:
        self._defects = defects
        self._unclear = unclear
        self.seen: list[str] = []

    def verify(self, subject: ResidueSubject) -> CrossVerificationResult:
        problem_id = subject.problem_id
        self.seen.append(problem_id)
        if problem_id in self._unclear:
            return CrossVerificationResult(
                problem_id,
                (PerspectiveVerdict("p", "unclear", "provider_error", "다운"),),
                "unclear",
                "p:provider_error",
                "측정 실패",
            )
        if problem_id in self._defects:
            return CrossVerificationResult(
                problem_id,
                (PerspectiveVerdict("p", "defect", "model_mismatch", "불일치"),),
                "defect",
                "p:model_mismatch",
                "결함",
            )
        return CrossVerificationResult(
            problem_id,
            (PerspectiveVerdict("p", "ok", "", "정상"),),
            "ok",
            "",
            "만장일치",
        )

    def flush_trace(self) -> None:
        pass


def _label_json(verdict: str, *, defect_class: str = "ambiguous_condition") -> str:
    if verdict == "ok":
        return json.dumps({"verdict": "ok", "reason": "문제 없음"}, ensure_ascii=False)
    return json.dumps(
        {
            "verdict": "defect",
            "defect_class": defect_class,
            "reason": "발문-모델 불일치",
        },
        ensure_ascii=False,
    )


# ──────────────────────────────────────────────────────────────────────────
# ① _build_subject — 공용 조립기 재사용 확인
# ──────────────────────────────────────────────────────────────────────────


def test_build_subject_reuses_shared_assembler() -> None:
    items = build_defect_seeded_residue_set(n_per_class=1, n_clean=1, seed="rgdb-1")
    item = items[0]
    subject = rgdb._build_subject(item)
    assert not isinstance(subject, str)
    model = parse_finite_model(item.conditions)
    result = enumerate_model(model)
    assert subject.machine_total == result.total
    assert subject.machine_favorable == result.favorable
    assert subject.authored_by == item.authored_by == "harness:residue_demotion_battle"
    assert subject.question_text == item.question_text  # 변조된 발문이 그대로 실린다


# ──────────────────────────────────────────────────────────────────────────
# ② 실 CrossVerifier(ScriptedProvider) — 결함 3관점 전부 defect·무결함 3관점 전부 ok
# ──────────────────────────────────────────────────────────────────────────


def test_defective_item_all_defect_responses_aggregates_defect() -> None:
    items = build_defect_seeded_residue_set(n_per_class=1, n_clean=0, seed="rgdb-2")
    item = next(i for i in items if i.defect_class == "equal_probability_unstated")
    model = parse_finite_model(item.conditions)
    result = enumerate_model(model)
    # ① 독립 재구성 관점도 기계값과 다른 수를 내 defect로 잡히게 한다(가장 흔한 실패 모드).
    wrong_reconstruction = json.dumps(
        {"total": result.total, "favorable": max(0, result.favorable - 1)}
    )
    provider = ScriptedProvider(
        [wrong_reconstruction, _label_json("defect"), _label_json("defect")]
    )
    verifier = CrossVerifier(provider, trace=RecordingSink())
    outcomes = rgdb._run_battle([item], verifier=verifier)
    assert len(outcomes) == 1
    assert outcomes[0].aggregate == "defect"
    assert outcomes[0].defect_class == "equal_probability_unstated"


def test_clean_item_all_ok_responses_aggregates_ok() -> None:
    items = build_defect_seeded_residue_set(n_per_class=0, n_clean=1, seed="rgdb-3")
    item = items[0]
    model = parse_finite_model(item.conditions)
    result = enumerate_model(model)
    correct_reconstruction = json.dumps({"total": result.total, "favorable": result.favorable})
    provider = ScriptedProvider([correct_reconstruction, _label_json("ok"), _label_json("ok")])
    verifier = CrossVerifier(provider, trace=RecordingSink())
    outcomes = rgdb._run_battle([item], verifier=verifier)
    assert outcomes[0].aggregate == "ok"
    assert outcomes[0].defect_class is None


# ──────────────────────────────────────────────────────────────────────────
# ③ 변별력 — provider 예외는 unclear로 잡히고 분모에서 빠진다
# ──────────────────────────────────────────────────────────────────────────


def test_provider_failure_is_unclear_and_excluded_from_resolved_denominator() -> None:
    items = build_defect_seeded_residue_set(n_per_class=1, n_clean=1, seed="rgdb-4")
    verifier = CrossVerifier(RaisingProvider(), trace=RecordingSink())
    outcomes = rgdb._run_battle(items, verifier=verifier)
    assert all(o.aggregate == "unclear" for o in outcomes)
    report = rgdb.summarize(outcomes)
    # unclear는 detected(defect)도 false_alarm도 아니다 — 그냥 판정불가로만 잡힌다.
    assert report.defect_detected == 0 and report.clean_false_alarm == 0
    assert report.defect_unclear == 4  # DEFECT_CLASSES 4종 × n_per_class=1
    assert report.clean_unclear == 1
    assert report.defect_resolved == 0 and report.clean_resolved == 0
    # 분모 0 → 경계는 계산 불가(None), "0% 검출" 같은 거짓 확정이 아니다.
    assert report.detection_lower_bound() is None
    assert report.false_alarm_upper_bound() is None


def test_summarize_separates_unclear_from_miss_within_same_class() -> None:
    """같은 결함류 안에서 detected·unclear·(ok=미검출)가 섞여도 분모가 정확히 분리된다."""
    items = build_defect_seeded_residue_set(n_per_class=3, n_clean=0, seed="rgdb-5")
    target_class = "condition_missing"
    class_items = [i for i in items if i.defect_class == target_class]
    assert len(class_items) == 3
    verifier = StubVerifier(
        defects=frozenset({class_items[0].slug}),
        unclear=frozenset({class_items[1].slug}),
    )
    # class_items[2]는 defects/unclear 어디에도 없으므로 StubVerifier가 "ok"(=미검출)를 낸다.
    outcomes = rgdb._run_battle(items, verifier=verifier)
    report = rgdb.summarize(outcomes)
    detected, unclear, total = report.per_class[target_class]
    assert (detected, unclear, total) == (1, 1, 3)
    # resolved = 3 - 1 = 2, 그중 1건 detected → 미검출(ok) 1건이 정확히 반영된다.


# ──────────────────────────────────────────────────────────────────────────
# 집계·리포트 — 구성만으로 정확히 회계되는지(대량 결정론 시나리오)
# ──────────────────────────────────────────────────────────────────────────


def test_full_battle_all_detected_no_false_alarm_high_lower_bound() -> None:
    items = build_defect_seeded_residue_set(n_per_class=2, n_clean=2, seed="rgdb-6")
    defect_slugs = frozenset(i.slug for i in items if i.defect_class is not None)
    verifier = StubVerifier(defects=defect_slugs)
    report, outcomes = rgdb.run_residue_gate_demotion_battle(
        verifier=verifier, n_per_class=2, n_clean=2, seed="rgdb-6"
    )
    assert report.defect_detected == report.defect_total == 8
    assert report.clean_false_alarm == 0 and report.clean_total == 2
    dlb = report.detection_lower_bound()
    fau = report.false_alarm_upper_bound()
    assert dlb is not None and 0.70 < dlb < 0.80
    assert fau is not None and fau < 0.60
    for name in DEFECT_CLASSES:
        detected, unclear, total = report.per_class[name]
        assert (detected, unclear, total) == (2, 0, 2)


def test_format_report_contains_all_defect_class_rows() -> None:
    items = build_defect_seeded_residue_set(n_per_class=1, n_clean=1, seed="rgdb-7")
    verifier = StubVerifier()
    outcomes = rgdb._run_battle(items, verifier=verifier)
    report = rgdb.summarize(outcomes)
    text = rgdb.format_report(report, confidence=0.95)
    for name in DEFECT_CLASSES:
        assert name in text
    assert "전체" in text


# ──────────────────────────────────────────────────────────────────────────
# ④ CLI — argparse·opt-in 게이트 exit code
# ──────────────────────────────────────────────────────────────────────────


def test_cli_help_exits_zero_without_touching_verifier() -> None:
    with pytest.raises(SystemExit) as exc_info:
        rgdb.main(["--help"])
    assert exc_info.value.code == 0


def test_cli_no_gate_flags_reports_only_exit_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rgdb, "CrossVerifier", lambda: StubVerifier())
    rc = rgdb.main(["--n-per-class", "2", "--n-clean", "2", "--seed", "rgdb-cli-1"])
    assert rc == 0


def test_cli_gate_fails_when_detection_threshold_not_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # StubVerifier() 기본값은 전부 ok → 결함 검출 0/8, 하한 0.0 → 임계 0.5 미달.
    monkeypatch.setattr(rgdb, "CrossVerifier", lambda: StubVerifier())
    rc = rgdb.main(
        [
            "--n-per-class",
            "2",
            "--n-clean",
            "2",
            "--seed",
            "rgdb-cli-2",
            "--min-detection-lower",
            "0.5",
        ]
    )
    assert rc == 1


def test_cli_gate_passes_when_thresholds_met(monkeypatch: pytest.MonkeyPatch) -> None:
    seed = "rgdb-cli-3"
    items = build_defect_seeded_residue_set(n_per_class=2, n_clean=2, seed=seed)
    defect_slugs = frozenset(i.slug for i in items if i.defect_class is not None)
    monkeypatch.setattr(rgdb, "CrossVerifier", lambda: StubVerifier(defects=defect_slugs))
    rc = rgdb.main(
        [
            "--n-per-class",
            "2",
            "--n-clean",
            "2",
            "--seed",
            seed,
            "--min-detection-lower",
            "0.5",
            "--max-false-alarm-upper",
            "0.6",
        ]
    )
    assert rc == 0


def test_cli_false_alarm_gate_fails_when_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = "rgdb-cli-4"
    items = build_defect_seeded_residue_set(n_per_class=2, n_clean=2, seed=seed)
    clean_slugs = frozenset(i.slug for i in items if i.defect_class is None)
    # 무결함 항목을 전부 defect로 오검출하게 만들어 상한 게이트가 실제로 실패하는지 본다.
    monkeypatch.setattr(rgdb, "CrossVerifier", lambda: StubVerifier(defects=clean_slugs))
    rc = rgdb.main(
        [
            "--n-per-class",
            "2",
            "--n-clean",
            "2",
            "--seed",
            seed,
            "--max-false-alarm-upper",
            "0.1",
        ]
    )
    assert rc == 1


def test_cli_writes_audit_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rgdb, "CrossVerifier", lambda: StubVerifier())
    out = tmp_path / "audit.jsonl"
    rc = rgdb.main(
        [
            "--n-per-class",
            "1",
            "--n-clean",
            "1",
            "--seed",
            "rgdb-cli-5",
            "--audit-out",
            str(out),
        ]
    )
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 * 1 + 1
    assert all({"slug", "defect_class", "aggregate", "reason"} <= set(r) for r in rows)
