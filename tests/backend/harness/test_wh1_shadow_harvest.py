"""wh1_shadow_harvest 수확·축적기 hermetic 테스트 — 라이브 0·파일은 tmp_path.

픽스처 라인은 emit 실물에서 도출한다: 레코드 페이로드는 실제 `Wh1HarnessShadowObservation.
model_dump_json()`이고, 서버-로그 스타일 라인은 실제 `record_logger`(wh1_shadow.py의 그
로거)에 표준 Formatter를 태워 만든다 — 가짜 포맷 픽스처 금지(외부 표면 시임 검증 금지 규칙의
내부 판, 로거 이름·직렬화 드리프트를 테스트가 동결).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pytest

from whymath_backend.harness import wh1_shadow_harvest as hv
from whymath_backend.harness.wh1_shadow import Wh1HarnessShadowObservation, record_logger


def _obs(
    verdict: str | None,
    *,
    status: str = "ended",
    action: str | None = "질문",
    dialogue: str | None = "d-1",
    turn: int = 1,
    observed: str = "2026-07-17T09:00:00+00:00",
) -> Wh1HarnessShadowObservation:
    """관측 픽스처 — emit 측 실물 모델로 구성(스키마 드리프트 시 여기서 즉시 깨진다)."""
    return Wh1HarnessShadowObservation(
        status=status,
        action_type=action,
        verify_verdict=verdict,
        tool_calls=3,
        hypothesis_count=1,
        dialogue_id=dialogue,
        turn_index=turn,
        problem_id=None,
        observed_at=datetime.fromisoformat(observed),
    )


def _server_log_line(obs: Wh1HarnessShadowObservation) -> str:
    """실제 record_logger에 표준 Formatter를 태워 서버-로그 스타일 라인 생성(emit 표면 실측)."""
    record = record_logger.makeRecord(
        record_logger.name, logging.INFO, __file__, 0, obs.model_dump_json(), (), None
    )
    return logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s").format(record)


# ──────────────────────────────────────────────────────────────────────────
# 로거 이름 — emit 측과 파서의 단일 진실원천 동결
# ──────────────────────────────────────────────────────────────────────────
def test_record_logger_name_matches_emitter() -> None:
    """파서가 필터하는 로거 이름 = emit 로거 이름(재타이핑 드리프트 차단)."""
    assert hv.RECORD_LOGGER_NAME == record_logger.name
    assert hv.RECORD_LOGGER_NAME == "whymath.harness.wh1_shadow.record"


# ──────────────────────────────────────────────────────────────────────────
# parse_log_text — verdict 3종+None·깨진 JSON·비해당 라인 정직 회계
# ──────────────────────────────────────────────────────────────────────────
def test_parse_mixed_server_log_accounting(caplog: pytest.LogCaptureFixture) -> None:
    """서버-로그 스타일 + 순수 JSONL 혼재 입력에서 record만 파싱하고 skip/broken을 회계한다."""
    good = [
        _obs("correct", observed="2026-07-17T09:00:01+00:00"),
        _obs("incorrect", observed="2026-07-17T09:00:02+00:00"),
        _obs("unverifiable", observed="2026-07-17T09:00:03+00:00"),
        _obs(None, observed="2026-07-17T09:00:04+00:00"),
    ]
    lines = [
        _server_log_line(good[0]),  # 서버-로그 스타일(마커 + prefix)
        _server_log_line(good[1]),
        good[2].model_dump_json(),  # 순수 JSONL 캡처 스타일(bare JSON)
        good[3].model_dump_json(),
        # 깨진 record 라인 — 마커는 있으나 JSON 절단(로테이션 컷 모사).
        _server_log_line(good[0])[:-20],
        # 비해당 라인들 — uvicorn 평문·타 로거 JSON·타 스키마 bare JSON.
        'INFO:     127.0.0.1:5000 - "POST /v1/coach/sessions HTTP/1.1" 201 Created',
        '2026-07-17 INFO whymath.l4.misconception.shadow.record {"substr_ids": []}',
        '{"other_logger": true, "not_our_schema": 1}',
        "",  # 빈 줄 — 회계 제외
    ]
    with caplog.at_level(logging.WARNING, logger=hv.logger.name):
        observations, acct = hv.parse_log_text("\n".join(lines))
    assert acct.parsed == 4
    assert [o.verify_verdict for o in observations] == [
        "correct",
        "incorrect",
        "unverifiable",
        None,
    ]
    # 비해당: 평문 1 + 타 스키마 bare JSON 1. 타 로거 마커 라인은 marker 미포함(다른 이름)이라
    # bare JSON도 아니고 평문 취급 → skip. 총 3.
    assert acct.skipped == 3
    assert acct.broken == 1
    assert acct.lines_total == 8  # 빈 줄 제외
    # 침묵 실패 금지 — 깨진 라인 경고에 예외 *타입명*이 실려야 한다.
    warnings = [r.getMessage() for r in caplog.records]
    assert any("ValidationError" in m or "JSONDecodeError" in m for m in warnings)


def test_parse_broken_bare_json_is_broken(caplog: pytest.LogCaptureFixture) -> None:
    """bare JSON 절단(로테이션 컷)은 skip이 아니라 broken — 부식을 조용히 덮지 않는다."""
    truncated = _obs("correct").model_dump_json()[:-5]
    with caplog.at_level(logging.WARNING, logger=hv.logger.name):
        observations, acct = hv.parse_log_text(truncated)
    assert observations == []
    assert acct.broken == 1
    assert acct.skipped == 0
    assert any("JSONDecodeError" in r.getMessage() for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# dedupe — (dialogue_id, turn_index, observed_at) 키
# ──────────────────────────────────────────────────────────────────────────
def test_dedupe_key_and_counts() -> None:
    """같은 키는 1건만 남고 중복 수가 회계된다. observed_at·turn이 다르면 별건이다."""
    a1 = _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:00+00:00")
    a1_dup = _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:00+00:00")
    a2 = _obs("correct", dialogue="d-1", turn=2, observed="2026-07-17T09:00:00+00:00")
    b1 = _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:05+00:00")
    unique, duplicates = hv.dedupe([a1, a1_dup, a2, b1])
    assert len(unique) == 3
    assert duplicates == 1
    # create_session 관측(dialogue_id=None·turn=1)은 observed_at으로 구분된다.
    n1 = _obs("correct", dialogue=None, observed="2026-07-17T09:01:00+00:00")
    n2 = _obs("correct", dialogue=None, observed="2026-07-17T09:01:01+00:00")
    unique2, duplicates2 = hv.dedupe([n1, n2])
    assert len(unique2) == 2 and duplicates2 == 0


# ──────────────────────────────────────────────────────────────────────────
# summarize — verdict/status/turn 분포·고유 dialogue·시각 범위
# ──────────────────────────────────────────────────────────────────────────
def test_summarize_distribution() -> None:
    """4-라벨 분포(0건 라벨 포함)·비율·turn별 분포·status·dialogue·시각 범위."""
    observations = [
        _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:00+00:00"),
        _obs("correct", dialogue="d-1", turn=2, observed="2026-07-17T09:00:10+00:00"),
        _obs("incorrect", dialogue="d-2", turn=2, observed="2026-07-17T09:00:20+00:00"),
        _obs(
            None,
            dialogue=None,
            turn=1,
            observed="2026-07-17T09:00:30+00:00",
            status="budget_exhausted",
            action=None,
        ),
    ]
    summary = hv.summarize(observations)
    assert summary.total == 4
    assert summary.verdict_counts == {"correct": 2, "incorrect": 1, "unverifiable": 0, "none": 1}
    assert summary.verdict_ratios["correct"] == pytest.approx(0.5)
    assert summary.verdict_ratios["unverifiable"] == pytest.approx(0.0)
    assert summary.status_counts == {"budget_exhausted": 1, "ended": 3}
    assert summary.turn_verdicts == {
        1: {"correct": 1, "none": 1},
        2: {"correct": 1, "incorrect": 1},
    }
    assert summary.distinct_dialogues == 2  # None은 고유 dialogue로 세지 않는다
    assert summary.observed_at_min is not None and summary.observed_at_min.second == 0
    assert summary.observed_at_max is not None and summary.observed_at_max.second == 30


def test_summarize_empty_is_honest() -> None:
    """관측 0건 — 비율은 빈 dict(0%로 위장 금지)·시각 범위 None."""
    summary = hv.summarize([])
    assert summary.total == 0
    assert summary.verdict_ratios == {}
    assert summary.verdict_counts == {"correct": 0, "incorrect": 0, "unverifiable": 0, "none": 0}
    assert summary.observed_at_min is None and summary.observed_at_max is None


# ──────────────────────────────────────────────────────────────────────────
# harvest_files + --store 원장 — 축적·중복 제거·재실행 멱등
# ──────────────────────────────────────────────────────────────────────────
def _write_log(path: Path, observations: list[Wh1HarnessShadowObservation]) -> None:
    path.write_text("\n".join(_server_log_line(o) for o in observations) + "\n", encoding="utf-8")


def test_store_accumulates_and_rerun_is_idempotent(tmp_path: Path) -> None:
    """--store: 신규만 append·같은 로그 재수확은 appended 0(멱등)·리포트는 원장 전체 기준."""
    ledger = tmp_path / "ledger.ndjson"
    log1 = tmp_path / "log1.log"
    _write_log(
        log1,
        [
            _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:00+00:00"),
            _obs("incorrect", dialogue="d-1", turn=2, observed="2026-07-17T09:00:10+00:00"),
        ],
    )
    first = hv.harvest_files([log1], store=ledger)
    assert first.appended == 2
    assert first.ledger_existing == 0
    assert first.summary.total == 2

    # 같은 로그 재수확 — 원장 불변(멱등)·리포트는 여전히 원장 전체 2건.
    second = hv.harvest_files([log1], store=ledger)
    assert second.appended == 0
    assert second.input_duplicates == 2
    assert second.ledger_existing == 2
    assert second.summary.total == 2
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2

    # 새 세션 로그(신규 1 + 기존 중복 1) — 신규만 축적돼 원장 3건.
    log2 = tmp_path / "log2.log"
    _write_log(
        log2,
        [
            _obs("correct", dialogue="d-1", turn=1, observed="2026-07-17T09:00:00+00:00"),  # 중복
            _obs("unverifiable", dialogue="d-9", turn=1, observed="2026-07-17T10:00:00+00:00"),
        ],
    )
    third = hv.harvest_files([log2], store=ledger)
    assert third.appended == 1
    assert third.input_duplicates == 1
    assert third.summary.total == 3
    assert third.summary.verdict_counts["unverifiable"] == 1


def test_ledger_broken_line_counted_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """원장 부식 1줄은 회계(ledger_broken)·경고(타입명)하되 축적 자체는 계속된다."""
    ledger = tmp_path / "ledger.ndjson"
    good = _obs("correct", observed="2026-07-17T09:00:00+00:00")
    ledger.write_text(good.model_dump_json() + "\n" + '{"broken":' + "\n", encoding="utf-8")
    log = tmp_path / "log.log"
    _write_log(log, [_obs("incorrect", turn=2, observed="2026-07-17T09:00:10+00:00")])
    with caplog.at_level(logging.WARNING, logger=hv.logger.name):
        report = hv.harvest_files([log], store=ledger)
    assert report.ledger_broken == 1
    assert report.ledger_existing == 1
    assert report.appended == 1
    assert report.summary.total == 2
    assert any("원장 라인 파싱 실패" in r.getMessage() for r in caplog.records)


def test_without_store_reports_input_only(tmp_path: Path) -> None:
    """--store 미지정 — 이번 입력(중복 제거)만 집계·원장 필드는 0/None."""
    log = tmp_path / "log.log"
    obs = _obs("correct")
    _write_log(log, [obs, obs])  # 입력 내 중복
    report = hv.harvest_files([log])
    assert report.store_path is None
    assert report.summary.total == 1
    assert report.input_duplicates == 1
    assert report.appended == 0


# ──────────────────────────────────────────────────────────────────────────
# CLI(main) — 렌더·--json·입력 오류 종료 코드
# ──────────────────────────────────────────────────────────────────────────
def test_main_renders_and_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main: 사람용 렌더(분포·회계·판정선 없음 명시) + --json 왕복."""
    log = tmp_path / "log.log"
    _write_log(
        log,
        [
            _obs("correct", observed="2026-07-17T09:00:00+00:00"),
            _obs("unverifiable", turn=2, observed="2026-07-17T09:00:10+00:00"),
        ],
    )
    ledger = tmp_path / "ledger.ndjson"
    json_out = tmp_path / "report.json"
    exit_code = hv.main([str(log), "--store", str(ledger), "--json", str(json_out)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "verify verdict" in out
    assert "판정선 없음" in out
    assert "correct" in out and "unverifiable" in out
    loaded = json.loads(json_out.read_text(encoding="utf-8"))
    assert loaded["summary"]["total"] == 2
    assert loaded["summary"]["verdict_counts"]["correct"] == 1
    assert loaded["accounting"]["parsed"] == 2
    assert loaded["appended"] == 2


def test_main_missing_file_exits_error(tmp_path: Path) -> None:
    """입력 파일 부재 — 부분 수확 리포트로 위장하지 않고 종료 코드 2."""
    assert hv.main([str(tmp_path / "없는파일.log")]) == 2
