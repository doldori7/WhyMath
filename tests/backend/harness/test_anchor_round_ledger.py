"""[EOS-64 ②④] 앵커 회차 대장 — '작동한 비율'과 연속 무진전 알람의 판정 로직 동결.

이 파일이 붙드는 것은 두 가지다:
  ② **작동한 비율** — outcome 분포가 어휘 전건을 싣는가, 분모 0을 0%로 위장하지 않는가,
     Wilson 경계의 **방향**이 지표 성격과 맞는가(결함율에 하한을 쓰면 나쁜 값이 통과한다).
  ④ **연속 무진전 알람** — 대장 0행("측정 불가")과 연속 무진전("알람")이 서로 다른 색인가,
     임계 미만/이상에서 판정이 실제로 갈리는가.

각 단언은 *실패 상태에서 실제로 실패하는지*를 기준으로 골랐다(변별력 없는 검증 스텝 금지).
예: `bound_direction`만 문자열로 비교하면 방향을 뒤집어도 안 잡히므로, 경계값이 점추정보다
작은가/큰가를 함께 단언한다 — 방향이 뒤집히면 그 부등호가 깨진다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from whymath_backend.harness.anchor_round_ledger import (
    ACCEPTED_STATUSES,
    DEFAULT_STAGNATION_WINDOW,
    OUTCOME_STATUSES,
    RoundRecord,
    append_round_ledger,
    default_round_ledger_path,
    judge_stagnation,
    load_round_ledger,
    operating_rates,
)
from whymath_backend.l3.equivalent.orchestrator import GenerationOutcome


def _record(appended: int, *, run_id: str = "r", attempted: int = 5) -> RoundRecord:
    """대장 행 조립 헬퍼 — 무진전 판정 축(`appended`)만 바꿔 가며 쓴다."""
    return RoundRecord(
        run_id=run_id,
        out_path="/tmp/acc.jsonl",
        attempted=attempted,
        accepted=appended,
        appended=appended,
        outcome_counts={"accepted_stored": appended},
    )


class TestOutcomeVocabulary:
    """어휘는 오케스트레이터에서 파생된다 — 손으로 베낀 6종이 아니다."""

    def test_vocabulary_is_derived_from_orchestrator_literal(self) -> None:
        """어휘 드리프트 방지 — orchestrator가 상태를 추가하면 분포도 자동으로 따라간다."""
        expected = tuple(get_args(GenerationOutcome.model_fields["status"].annotation))
        assert OUTCOME_STATUSES == expected
        assert len(OUTCOME_STATUSES) == 6  # EOS-58 실측 어휘 — 줄면 관통 대본이 커버를 잃는다

    def test_accepted_statuses_are_the_two_stored_axes(self) -> None:
        """수용 축은 저장소 전역 규약(`_STORED_STATUSES`)과 같은 두 값이다."""
        assert ACCEPTED_STATUSES == frozenset({"accepted_stored", "accepted"})


class TestOperatingRates:
    """② 작동한 비율 — 분포·측정 가능성·경계 방향."""

    def test_all_vocabulary_present_even_when_zero(self) -> None:
        """관측 0인 상태도 count 0으로 명시된다 — '키 없음'과 '0건'은 다르다."""
        rates = operating_rates({"accepted_stored": 1}, attempted=1)
        assert set(rates["statuses"]) == set(OUTCOME_STATUSES)
        assert rates["statuses"]["generation_failed"]["count"] == 0

    def test_distribution_matches_counts(self) -> None:
        """EOS-58 관통 분포(5시도·5종 1건씩)가 그대로 실린다 — 이것이 '작동 증거'다."""
        counts = {
            "accepted_stored": 1,
            "needs_review": 1,
            "rejected_gate": 1,
            "rejected_duplicate": 1,
            "generation_failed": 1,
        }
        rates = operating_rates(counts, attempted=5)
        assert rates["measured"] is True
        assert {s: v["count"] for s, v in rates["statuses"].items()} == {
            **counts,
            "accepted": 0,
        }
        assert rates["statuses"]["accepted_stored"]["rate"] == pytest.approx(0.2)

    def test_zero_attempts_is_unmeasured_not_zero_percent(self) -> None:
        """분모 0은 '0%'가 아니라 **측정 불가** — 0.0으로 채우면 미시도가 전건 실패로 읽힌다."""
        rates = operating_rates({}, attempted=0)
        assert rates["measured"] is False
        assert rates["unmeasured_reason"] is not None
        for status in OUTCOME_STATUSES:
            assert rates["statuses"][status]["rate"] is None
            assert rates["statuses"][status]["bound"] is None

    def test_accepted_uses_lower_bound_and_is_conservative(self) -> None:
        """수용률은 '높을수록 좋은' 축 → **하한**. 하한은 점추정보다 작아야 한다(과신 방지).

        방향 문자열만 비교하면 구현에서 방향을 뒤집어도 안 잡힌다 — 부등호를 함께 건다.
        """
        rates = operating_rates({"accepted_stored": 5}, attempted=5)
        entry = rates["statuses"]["accepted_stored"]
        assert entry["bound_direction"] == "lower"
        assert entry["rate"] == pytest.approx(1.0)
        assert entry["bound"] < entry["rate"]  # 5/5=1.0의 과신을 Wilson이 깎는다
        # 단측 z=Φ⁻¹(0.95)=1.645 기준 실측값 — `harness/wilson`의 예시와 같은 값이다.
        # (그 docstring은 오래 양측 z=1.96의 "≈0.565"를 적어 왔고 2026-09-01에 정정됐다.
        #  정합은 `test_wilson.py`가 docstring을 파싱해 기계로 대조한다.)
        assert entry["bound"] == pytest.approx(0.6489, abs=1e-3)

    def test_failure_axes_use_upper_bound_and_are_conservative(self) -> None:
        """실패·비용 축은 '낮을수록 좋은' → **상한**. 상한은 점추정보다 커야 한다(보수적)."""
        rates = operating_rates({"generation_failed": 0, "accepted_stored": 5}, attempted=5)
        for status in ("generation_failed", "rejected_gate", "rejected_duplicate", "needs_review"):
            entry = rates["statuses"][status]
            assert entry["bound_direction"] == "upper", status
            # 관측 0이어도 상한 > 0 — "관측 0 = 확정 0%"로 과신하지 않는다(모르면 모른다).
            assert entry["bound"] > entry["rate"], status
            assert entry["bound"] > 0.0, status

    def test_unknown_status_is_reported_not_dropped(self) -> None:
        """어휘 밖 상태는 조용히 버리지 않는다 — 분포가 100%가 아닌 이유를 리포트가 자백한다."""
        rates = operating_rates({"accepted_stored": 1, "새로운_상태": 2}, attempted=3)
        assert rates["unknown_statuses"] == {"새로운_상태": 2}


class TestRoundLedgerMedium:
    """대장 매체 계약 — 즉시 flush·줄 번호 주입·로드 실패 사유(타입명) 보존."""

    def test_default_path_is_sidecar_of_out(self, tmp_path: Path) -> None:
        """대장은 `<out>.rounds.jsonl` 사이드카 — --out마다 하나라 회차가 섞이지 않는다."""
        assert default_round_ledger_path(tmp_path / "acc.jsonl") == tmp_path / "acc.rounds.jsonl"

    def test_append_stamps_time_and_loader_injects_line_number(self, tmp_path: Path) -> None:
        """append가 시각을 스탬프하고, 로더가 1-기반 줄 번호를 주입한다(파일은 자칭 안 함)."""
        path = tmp_path / "acc.rounds.jsonl"
        stamped = append_round_ledger(path, _record(1, run_id="a"))
        append_round_ledger(path, _record(0, run_id="b"))
        assert stamped.recorded_at is not None
        raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert "source_line" not in raw  # 매체 파생 필드는 기록하지 않는다

        records, errors = load_round_ledger(path)
        assert errors == []
        assert [r.run_id for r in records] == ["a", "b"]
        assert [r.source_line for r in records] == [1, 2]

    def test_broken_line_reports_type_name_not_silence(self, tmp_path: Path) -> None:
        """깨진 줄은 삼키지 않는다 — **예외 타입명 + 줄 번호**만 남긴다(필드 값은 안 남김)."""
        path = tmp_path / "acc.rounds.jsonl"
        append_round_ledger(path, _record(1))
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{이건 JSON이 아니다\n")
            handle.write(json.dumps({"run_id": "x"}) + "\n")  # 필수 필드 누락 → ValidationError

        records, errors = load_round_ledger(path)
        assert len(records) == 1
        assert len(errors) == 2
        assert "JSONDecodeError" in errors[0] and "line 2" in errors[0]
        assert "ValidationError" in errors[1] and "line 3" in errors[1]

    def test_missing_file_raises_rather_than_reporting_zero(self, tmp_path: Path) -> None:
        """파일 부재는 '행 0건'이 아니다 — 미측정≠0이므로 예외로 전파한다."""
        with pytest.raises(FileNotFoundError):
            load_round_ledger(tmp_path / "없는파일.jsonl")


class TestStagnationAlarm:
    """④ 연속 무진전 — 측정 불가·임계 미만·알람이 서로 다른 색인가."""

    def test_empty_ledger_is_unmeasured_not_healthy(self) -> None:
        """대장 0행은 '진전 있음'이 아니라 **측정 불가** — 안 돌린 것과 잘 도는 것은 다르다."""
        verdict = judge_stagnation([])
        assert verdict.measured is False
        assert verdict.alarm is False
        assert "측정 불가" in verdict.message

    def test_below_window_does_not_alarm(self) -> None:
        """임계 미만의 연속 무진전은 알람이 아니다(소량 n 회차의 잡음을 알람으로 만들지 않음)."""
        verdict = judge_stagnation([_record(1), _record(0), _record(0)], window=3)
        assert verdict.consecutive_zero == 2
        assert verdict.alarm is False

    def test_at_window_alarms(self) -> None:
        """임계 도달 = 알람 — 경계에서 판정이 실제로 갈린다(변별력)."""
        verdict = judge_stagnation([_record(1), _record(0), _record(0), _record(0)], window=3)
        assert verdict.consecutive_zero == 3
        assert verdict.alarm is True
        assert "연속 무진전 알람" in verdict.message

    def test_recent_progress_resets_the_streak(self) -> None:
        """최신 회차가 진전이면 연속 길이는 0 — 과거 무진전이 영구 알람이 되지 않는다."""
        verdict = judge_stagnation([_record(0), _record(0), _record(0), _record(1)], window=3)
        assert verdict.consecutive_zero == 0
        assert verdict.alarm is False

    def test_load_errors_are_disclosed_in_the_message(self) -> None:
        """대장 일부가 깨졌으면 판정을 조용히 내리지 않는다 — 근거 불완전성을 명기한다."""
        verdict = judge_stagnation(
            [_record(0), _record(0), _record(0)],
            window=3,
            load_errors=["line 2: JSONDecodeError"],
        )
        assert verdict.alarm is True
        assert "로드 실패" in verdict.message

    def test_non_positive_window_is_refused(self) -> None:
        """창 0은 알람을 상시 참으로 만든다 — 변별력 없는 게이트를 인자로 만들 수 없게 거부."""
        with pytest.raises(ValueError):
            judge_stagnation([_record(0)], window=0)

    def test_default_window_is_three(self) -> None:
        """기본 임계 동결 — 기존 관통 테스트(2회 연속 무진전 회차)가 알람에 걸리지 않는 값."""
        assert DEFAULT_STAGNATION_WINDOW == 3

    def test_to_json_carries_measurement_flags(self) -> None:
        """리포트에 실리는 형태 — alarm뿐 아니라 measured·근거 수치를 함께 낸다."""
        payload: dict[str, Any] = judge_stagnation([_record(0)], window=1).to_json()
        assert payload["alarm"] is True
        assert payload["measured"] is True
        assert payload["observed_rounds"] == 1
        assert payload["window"] == 1
