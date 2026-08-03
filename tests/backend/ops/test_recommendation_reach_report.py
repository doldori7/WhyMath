"""recommendation_reach_report 단위테스트 — hermetic(라이브 DB 0)·REC-01.

집계 코어(`build_report`)는 순수 함수라 픽스처로 경계까지 전수 단언하고,
`fetch_reach_counts`는 큐 기반 가짜 세션(FakeSession — test_me.py `_QueueSession` 관례
답습)으로 실 DB 없이 쿼리 4회의 매핑을 검증한다. 실 JOIN·DISTINCT·필터의 SQL 정확성은
FakeSession이 stmt를 무시하므로 검증하지 않는다(test_me.py 동일 관례 — 통합테스트 영역).

acceptance ③(변별력) 핵심: attempt 총계가 0→1로 바뀌면 '미도달'이 해제되고, 1→0으로
되돌리면 다시 '미도달'이 나오는지 *양방향*으로 확인한다(성공/실패가 같은 값을 내면
검증이 아니다).
"""

from __future__ import annotations

import json
from typing import Any

from whymath_backend.ops import recommendation_reach_report as rr


# ──────────────────────────────────────────────────────────────────────────
# 가짜 세션 — execute()마다 큐잉된 스칼라 값을 순서대로 반환(stmt는 무시).
# ──────────────────────────────────────────────────────────────────────────
class _FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _QueueSession:
    """`fetch_reach_counts`의 execute 4회(①attempt ②eligible ③pair ④pool)를 큐로 반환."""

    def __init__(self, values: list[int]) -> None:
        self._values = values
        self._calls = 0

    async def execute(self, _stmt: object) -> _FakeScalarResult:
        value = self._values[self._calls]
        self._calls += 1
        return _FakeScalarResult(value)


# ──────────────────────────────────────────────────────────────────────────
# fetch_reach_counts — 쿼리 4회 → ReachCounts 매핑(순서 계약).
# ──────────────────────────────────────────────────────────────────────────
async def test_fetch_reach_counts_maps_four_queries_in_order() -> None:
    session = _QueueSession([5, 3, 2, 120])
    counts = await rr.fetch_reach_counts(session)  # type: ignore[arg-type]
    assert counts == rr.ReachCounts(
        problem_attempt_total=5,
        theta_eligible_response_total=3,
        weak_concept_signal_pair_total=2,
        candidate_pool_structural_cap=120,
    )


# ──────────────────────────────────────────────────────────────────────────
# build_report — 순수 집계. count>0 ⇔ reached=True(분모 없는 0 방지 원칙).
# ──────────────────────────────────────────────────────────────────────────
def test_build_report_all_zero_marks_not_reached() -> None:
    """전 축 0행 → 전부 미도달(reached=False). candidate_pool_structural_cap은 그대로 노출."""
    report = rr.build_report(rr.ReachCounts(0, 0, 0, 0))
    assert report.problem_attempt_reached is False
    assert report.theta_eligible_reached is False
    assert report.weak_concept_signal_reached is False
    assert report.candidate_pool_structural_cap == 0
    assert report.request_counter_status == rr.REQUEST_COUNTER_STATUS


def test_build_report_positive_counts_mark_reached() -> None:
    report = rr.build_report(rr.ReachCounts(5, 3, 2, 200))
    assert report.problem_attempt_reached is True
    assert report.theta_eligible_reached is True
    assert report.weak_concept_signal_reached is True
    assert report.problem_attempt_total == 5
    assert report.theta_eligible_response_total == 3
    assert report.weak_concept_signal_pair_total == 2
    assert report.candidate_pool_structural_cap == 200


# ──────────────────────────────────────────────────────────────────────────
# acceptance ③ 변별력 — attempt 1건 주입 → 미도달 해제, 되돌리면 다시 미도달(양방향).
# ──────────────────────────────────────────────────────────────────────────
async def test_reach_toggles_bidirectionally_when_attempt_row_injected_and_removed() -> None:
    """problem_attempt 0행 ↔ 1행 왕복 — '미도달' 표시가 실제로 켜지고 꺼진다(양방향 확인)."""
    # ① 0행 — '미도달'
    zero_session = _QueueSession([0, 0, 0, 10])
    zero_report = rr.build_report(await rr.fetch_reach_counts(zero_session))  # type: ignore[arg-type]
    assert zero_report.problem_attempt_reached is False
    zero_rendered = rr.render_report(zero_report)
    assert "전체 행 수: **0** (미도달)" in zero_rendered
    assert rr.NOT_REACHED in zero_rendered

    # ② fixture row 1건 주입 — '미도달' 해제(측정됨으로 전환)
    one_session = _QueueSession([1, 1, 0, 10])
    one_report = rr.build_report(await rr.fetch_reach_counts(one_session))  # type: ignore[arg-type]
    assert one_report.problem_attempt_reached is True
    one_rendered = rr.render_report(one_report)
    assert "전체 행 수: **1** (측정됨)" in one_rendered
    assert "전체 행 수: **1** (미도달)" not in one_rendered

    # ③ fixture 제거(되돌림) — 다시 '미도달'
    back_session = _QueueSession([0, 0, 0, 10])
    back_report = rr.build_report(await rr.fetch_reach_counts(back_session))  # type: ignore[arg-type]
    assert back_report.problem_attempt_reached is False
    assert "전체 행 수: **0** (미도달)" in rr.render_report(back_report)


def test_theta_eligible_auto_not_reached_when_attempt_is_zero() -> None:
    """problem_attempt 0행이면 θ 유효 응답도 구조적으로 0 → 자동 미도달(부분집합 관계)."""
    report = rr.build_report(rr.ReachCounts(0, 0, 5, 10))
    assert report.problem_attempt_reached is False
    assert report.theta_eligible_reached is False  # count 자체가 0이라 자동


# ──────────────────────────────────────────────────────────────────────────
# 추천 요청 수 — 카운터 부재를 지어내지 않고 정직 보고(핵심 acceptance①).
# ──────────────────────────────────────────────────────────────────────────
def test_request_counter_status_reports_absence_honestly() -> None:
    """새 카운터를 지어내지 않고 '관측 불가(요청 카운터 없음)'를 명시한다."""
    assert "관측 불가" in rr.REQUEST_COUNTER_STATUS
    assert "요청 카운터 없음" in rr.REQUEST_COUNTER_STATUS
    report = rr.build_report(rr.ReachCounts(0, 0, 0, 0))
    rendered = rr.render_report(report)
    assert rr.REQUEST_COUNTER_STATUS in rendered


# ──────────────────────────────────────────────────────────────────────────
# JSON 직렬화 — report_to_json/dump_json 구조.
# ──────────────────────────────────────────────────────────────────────────
def test_report_to_json_structure() -> None:
    report = rr.build_report(rr.ReachCounts(1, 1, 0, 50))
    payload: dict[str, Any] = rr.report_to_json(report)
    assert payload["problem_attempt"] == {"total": 1, "reached": True}
    assert payload["theta_eligible_response"] == {"total": 1, "reached": True}
    assert payload["weak_concept_signal_pair"] == {"total": 0, "reached": False}
    assert payload["candidate_pool_structural_cap"] == 50
    assert payload["request_counter"]["status"] == rr.REQUEST_COUNTER_STATUS


def test_dump_json_round_trips() -> None:
    report = rr.build_report(rr.ReachCounts(2, 1, 1, 30))
    parsed = json.loads(rr.dump_json(report))
    assert parsed["problem_attempt"]["total"] == 2


# ──────────────────────────────────────────────────────────────────────────
# CLI main() — 성공/실패 exit code·stdout/stderr·--json 산출물.
# ──────────────────────────────────────────────────────────────────────────
def test_main_success_prints_report_and_returns_zero(monkeypatch: Any, capsys: Any) -> None:
    fake_report = rr.build_report(rr.ReachCounts(0, 0, 0, 10))

    async def _fake_run() -> rr.ReachReport:
        return fake_report

    monkeypatch.setattr(rr, "_run", _fake_run)
    exit_code = rr.main([])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "추천 도달 관측 리포트" in out
    assert "미도달" in out


def test_main_writes_json_when_requested(tmp_path: Any, monkeypatch: Any, capsys: Any) -> None:
    fake_report = rr.build_report(rr.ReachCounts(1, 1, 1, 5))

    async def _fake_run() -> rr.ReachReport:
        return fake_report

    monkeypatch.setattr(rr, "_run", _fake_run)
    json_path = tmp_path / "reach.json"
    exit_code = rr.main(["--json", str(json_path)])
    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["problem_attempt"] == {"total": 1, "reached": True}
    out = capsys.readouterr().out
    assert str(json_path) in out


def test_main_runtime_error_reports_exception_type_name(monkeypatch: Any, capsys: Any) -> None:
    """DB 접속 등 실행 오류 시 exit 2 + stderr에 예외 **타입명**(침묵 실패 금지)."""

    class _BoomError(Exception):
        """주입 실패용 커스텀 예외 — 타입명 로그 검증이 이 이름을 찾는다."""

    async def _fake_run_raises() -> rr.ReachReport:
        raise _BoomError("DB 접속 실패(주입)")

    monkeypatch.setattr(rr, "_run", _fake_run_raises)
    exit_code = rr.main([])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "_BoomError" in err
