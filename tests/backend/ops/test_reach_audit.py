"""[OPS-17] 공급↔소비 도달 대장 — 단위 + **변별력 양방향** 검증.

이 파일의 절반은 "게이트가 실제로 실패하는가"를 본다. 성공/실패 양쪽에서 같은 값을 내는
검사는 검증이 아니라 위장이기 때문이다(CLAUDE.md — 2026-07-17 logconfig `delay:true` 사고:
사전 `Test-Path` 검사가 정상 상태에서도 항상 False라 검증 스텝 자체가 무효였다).

수용기준 ⑥이 요구하는 4종 변별력을 각각 테스트로 동결한다:
    · 더미 라우트 추가        → exit 1 (unclassified)
    · dart 호출 삭제          → exit 1 (reached 붕괴)
    · 유예를 done 태스크로    → exit 1 (expired-waiver)
    · 수집기 파손             → exit 2 (입력 오류 — "0건 통과" 위장 금지)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whymath_backend.ops import reach_audit
from whymath_backend.ops.reach_audit import (
    AXIS_CLI,
    AXIS_EVENT,
    AXIS_HTTP,
    AXIS_TIMESERIES,
    CollectorError,
    build_report,
    ci_executed_modules,
    cli_modules,
    dart_call_entries,
    normalize_dart_path,
    normalize_server_path,
    produced_event_types,
    reached_clis,
    repo_root,
    route_paths,
    timeseries_models,
    timeseries_writers,
)

_ROOT = repo_root()
_PACKAGE = _ROOT / "src" / "backend" / "whymath_backend"
_MOBILE_LIB = _ROOT / "src" / "mobile" / "lib"


# ──────────────────────────────────────────────────────────────────────
# 정규화 — 서버 `{problem_id}`와 dart `$problemId`가 한 축으로 모여야 매칭이 성립한다
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/v1/problems/{problem_id}", "/v1/problems/{param}"),
        ("/v1/coach/sessions/{dialogue_id}/turns", "/v1/coach/sessions/{param}/turns"),
        ("/v1/me/next-problem", "/v1/me/next-problem"),
    ],
)
def test_normalize_server_path(raw: str, expected: str) -> None:
    assert normalize_server_path(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/v1/problems/$problemId", "/v1/problems/{param}"),
        ("/v1/auth/$provider/callback", "/v1/auth/{param}/callback"),
        ("/v1/coach/sessions/${dialogueId}/turns", "/v1/coach/sessions/{param}/turns"),
        ("/v1/interactions", "/v1/interactions"),
    ],
)
def test_normalize_dart_path(raw: str, expected: str) -> None:
    assert normalize_dart_path(raw) == expected


def test_server_and_dart_normalization_meet() -> None:
    """두 표기가 실제로 같은 문자열로 수렴하는지 — 이게 깨지면 전 라우트가 미도달로 잡힌다."""
    assert normalize_server_path("/v1/problems/{problem_id}") == normalize_dart_path(
        "/v1/problems/$problemId"
    )


# ──────────────────────────────────────────────────────────────────────
# 수집기 — 실제 저장소에서 무엇을 얼마나 걷어오는가
# ──────────────────────────────────────────────────────────────────────


def test_route_table_includes_v1_routes() -> None:
    """FastAPI 0.140 `original_router` 재귀가 살아 있는지 — 이게 깨지면 `/v1/**`이 통째로
    사라지고 감사는 '미도달 0건'으로 조용히 통과한다(이 모듈이 막으려는 바로 그 위장)."""
    paths = route_paths()
    assert any(p.startswith("/v1/") for p in paths), "라우트 표에 /v1 경로가 없다 — 재귀 파손"
    assert "/v1/me/attempts" in paths
    assert "/health/ready" in paths


def test_dart_calls_extracted_across_multiline_form() -> None:
    """dart 호출은 `_dio.get<Map<String, dynamic>>(\\n  '/v1/…',` 형태라 개행을 넘어야 잡힌다."""
    calls = dart_call_entries(_MOBILE_LIB)
    assert ("GET", "/v1/me/next-problem") in calls
    assert ("GET", "/v1/problems/{param}") in calls  # 보간 정규화까지 함께 확인
    assert ("POST", "/v1/coach/sessions/{param}/turns") in calls
    assert len(calls) >= 10


def test_attempts_endpoint_is_not_reached_by_client() -> None:
    """반복 실수 5회차의 현장을 동결한다 — 이 사실이 바뀌면(=클라가 붙으면) 이 테스트가
    실패하며 대장의 유예를 걷으라고 알려 준다."""
    calls = dart_call_entries(_MOBILE_LIB)
    assert ("POST", "/v1/me/attempts") not in calls


def test_produced_event_types_detected_by_ast() -> None:
    produced = set(produced_event_types(_PACKAGE))
    assert {"검산결과", "힌트제공", "시각화조작"} <= produced
    assert "막힘" not in produced  # 휴면 8종 — 생산자 0


def test_timeseries_models_have_no_writer() -> None:
    """집계 hypertable 3종은 writer가 0이다(privacy 읽기·삭제 참조만) — 동명의 Pydantic
    스키마를 writer로 오인하지 않는지까지 함께 본다."""
    models = timeseries_models(_PACKAGE)
    assert set(models) == {
        "DailyLearningMetrics",
        "ProblemSolveTimeDistribution",
        "UserBehaviorMetrics",
    }
    writers = timeseries_writers(_PACKAGE, models)
    assert all(not mods for mods in writers.values()), f"예상 밖 writer 발견: {writers}"


def test_transitive_cli_reach_counts_in_process_imports() -> None:
    """`qa_pipeline`이 in-process import로 조립하는 CLI를 미도달로 세면 오탐이다(수용기준 ①).

    실제로 첫 구현이 `from whymath_backend.harness import corpus_audit_eval` 형태를 놓쳐
    이 오탐이 났다 — 그 회귀를 여기서 동결한다.
    """
    clis = cli_modules(_PACKAGE)
    roots = ci_executed_modules(_ROOT / ".github" / "workflows" / "ci.yml")
    reached = reached_clis(_PACKAGE, clis, roots)
    assert "harness.qa_pipeline" in reached  # CI가 직접 실행
    assert "harness.corpus_audit_eval" in reached  # qa_pipeline이 import → 전이 도달
    assert "harness.crosslink_demotion_eval" in reached


# ──────────────────────────────────────────────────────────────────────
# 현행 판정 — 대장이 실제 저장소에서 통과하는가
# ──────────────────────────────────────────────────────────────────────


def test_current_repository_passes() -> None:
    report = build_report(_ROOT)
    assert report.exit_code == 0, "\n".join(
        f"{v.axis} {v.key}: {v.status} — {v.note}" for v in report.violations
    )


def test_all_four_axes_present_and_populated() -> None:
    report = build_report(_ROOT)
    axes = {axis.axis: axis for axis in report.axes}
    assert set(axes) == {AXIS_HTTP, AXIS_EVENT, AXIS_TIMESERIES, AXIS_CLI}
    for axis in axes.values():
        assert axis.supplied > 0, f"{axis.axis} 공급 0 — 수집기가 비었다"


# ──────────────────────────────────────────────────────────────────────
# 변별력 (수용기준 ⑥) — 실패 상태에서 *실제로* 실패하는가
# ──────────────────────────────────────────────────────────────────────


def test_unclassified_supply_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """더미 라우트를 하나 끼워 넣으면 exit 1(unclassified)."""
    original = reach_audit.app_route_entries

    def _with_dummy() -> tuple[tuple[str, str], ...]:
        return (*original(), ("POST", "/v1/dummy-unclassified"))

    monkeypatch.setattr(reach_audit, "app_route_entries", _with_dummy)
    report = build_report(_ROOT)
    assert report.exit_code == 1
    statuses = {(v.key, v.status) for v in report.violations}
    assert ("POST /v1/dummy-unclassified", "unclassified") in statuses


def test_declaring_intent_clears_the_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    """같은 더미를 `by-design:<사유>`로 선언하면 통과 — 게이트가 *선언*으로 풀린다는 반대 방향."""
    original = reach_audit.app_route_entries

    def _with_dummy() -> tuple[tuple[str, str], ...]:
        return (*original(), ("POST", "/v1/dummy-unclassified"))

    monkeypatch.setattr(reach_audit, "app_route_entries", _with_dummy)
    monkeypatch.setitem(
        reach_audit._MANIFEST[AXIS_HTTP], "POST /v1/dummy-unclassified", "by-design:테스트 픽스처"
    )
    assert build_report(_ROOT).exit_code == 0


def test_by_design_without_reason_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """사유 없는 예외는 예외가 아니다 — 빈 사유는 거부한다."""
    original = reach_audit.app_route_entries

    def _with_dummy() -> tuple[tuple[str, str], ...]:
        return (*original(), ("POST", "/v1/dummy-unclassified"))

    monkeypatch.setattr(reach_audit, "app_route_entries", _with_dummy)
    monkeypatch.setitem(
        reach_audit._MANIFEST[AXIS_HTTP], "POST /v1/dummy-unclassified", "by-design:   "
    )
    report = build_report(_ROOT)
    assert report.exit_code == 1
    assert any(v.status == "missing-reason" for v in report.violations)


def test_losing_a_client_call_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """dart 호출이 사라지면 그 라우트가 미도달로 떨어지고, 선언이 없으므로 exit 1.

    이것이 이 게이트의 존재 이유다 — 클라가 조용히 호출을 잃는 회귀를 커밋 시점에 잡는다.
    """
    original = reach_audit.dart_call_entries

    def _without_next_problem(mobile_lib: Path) -> tuple[tuple[str, str], ...]:
        return tuple(c for c in original(mobile_lib) if c != ("GET", "/v1/me/next-problem"))

    monkeypatch.setattr(reach_audit, "dart_call_entries", _without_next_problem)
    report = build_report(_ROOT)
    assert report.exit_code == 1
    assert any(
        v.key == "GET /v1/me/next-problem" and v.status == "unclassified" for v in report.violations
    )


def test_waiver_expires_when_task_is_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """유예 근거 태스크가 done이 되면 exit 1 — 유예의 조용한 영구화를 막는다."""
    monkeypatch.setattr(reach_audit, "_task_status", lambda _tasks, _tid: "done")
    report = build_report(_ROOT)
    assert report.exit_code == 1
    assert any(v.status == "expired-waiver" for v in report.violations)


def test_waiver_expires_when_task_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """유예 근거 태스크 파일이 사라져도 exit 1 — 참조가 끊긴 유예는 유예가 아니다."""
    monkeypatch.setattr(reach_audit, "_task_status", lambda _tasks, _tid: None)
    report = build_report(_ROOT)
    assert report.exit_code == 1
    assert any(v.status == "expired-waiver" for v in report.violations)


def test_reached_item_left_in_manifest_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """도달했는데 대장에 유예가 남아 있으면 stale — 낡은 예외를 조용히 방치하지 않는다."""
    monkeypatch.setitem(
        reach_audit._MANIFEST[AXIS_HTTP],
        "GET /v1/me/next-problem",
        "pending-task:REC-01-recommendation-reach-observability",
    )
    report = build_report(_ROOT)
    assert report.exit_code == 1
    assert any(v.status == "stale-waiver" for v in report.violations)


def test_broken_collector_raises_input_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """dart 스캐너가 깨져 0건이 되면 '전부 유예라 통과'가 아니라 **입력 오류**여야 한다.

    이게 없으면 정규식 파손이 오히려 게이트를 조용히 무력화한다 — 성공/실패 양쪽에서 같은
    값(exit 0)을 내는 최악의 위장이다.
    """
    monkeypatch.setattr(reach_audit, "dart_call_entries", lambda _lib: ())
    with pytest.raises(CollectorError):
        build_report(_ROOT)


def test_cli_main_returns_input_error_code_on_broken_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI 표면에서도 exit 2로 나오는지 — 내부 예외가 exit 1(위반)로 뭉개지면 안 된다."""
    monkeypatch.setattr(reach_audit, "dart_call_entries", lambda _lib: ())
    assert reach_audit.main([]) == 2


def test_cli_main_passes_on_current_repository() -> None:
    assert reach_audit.main([]) == 0


def test_cli_writes_json_report(tmp_path: Path) -> None:
    out = tmp_path / "reach.json"
    assert reach_audit.main(["--json", str(out)]) == 0
    payload = out.read_text(encoding="utf-8")
    assert '"http_routes"' in payload
    assert '"overall"' in payload
