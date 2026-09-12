"""조립 세트 시행 귀속 관측 리포트 테스트 — 결정론·정직 회계(hermetic).

대상: `whymath_backend.harness.assessment_set_attribution_report`(ASM-10 acceptance②).
`build_report`는 순수 함수라 실 DB 없이 합성 `TestSetCollection`으로 검증한다. DB를 실제로 여는
델타 통합테스트는 `tests/backend/db/test_assessment_set_attribution_report_integration.py`
(acceptance⑤ 변별력)에 별도로 있다.

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"): 세트 문항에 대한 시도가 있을 때와 없을 때
`unattributable_attempt_count`가 실제로 다른 값을 내는지가 이 파일의 핵심 검증 대상이다(절대값
0을 assert하는 것만으로는 "판별 불가 축이 죽어 있어도 항상 0"인 상태와 구분되지 않는다 —
반드시 델타로 확인한다).
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from whymath_backend.harness import assessment_set_attribution_report as asar

# tests/backend/harness/ → tests/backend → tests → repo root → src/backend
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "src" / "backend"


def _row(
    *,
    assessment_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    completed_at: datetime | None = None,
    pattern_diagnosis: list[dict] | None = None,
    concept_diagnosis: list[dict] | None = None,
    recommended_path: list[dict] | None = None,
    strong_points: list[dict] | None = None,
) -> asar.RawTestSetRow:
    return asar.RawTestSetRow(
        assessment_id=assessment_id or uuid.uuid4(),
        user_id=user_id,
        completed_at=completed_at,
        pattern_diagnosis=pattern_diagnosis if pattern_diagnosis is not None else [],
        concept_diagnosis=concept_diagnosis if concept_diagnosis is not None else [],
        recommended_path=recommended_path if recommended_path is not None else [],
        strong_points=strong_points if strong_points is not None else [],
    )


def _header(selected_item_count: int = 2) -> dict:
    return {"kind": "blueprint_test_set", "selected_item_count": selected_item_count}


def _item(problem_id: uuid.UUID) -> dict:
    return {"kind": "blueprint_item", "problem_id": str(problem_id), "position": 0}


def _seat(report: asar.TestSetAttributionReport, assessment_id: uuid.UUID) -> asar.TestSetSeat:
    return next(s for s in report.seats if s.assessment_id == assessment_id)


# ──────────────────────────────────────────────────────────────────────────
# 1. 세트 수·문항 수 정합
# ──────────────────────────────────────────────────────────────────────────
def test_total_sets_reflects_row_count() -> None:
    rows = (_row(), _row(), _row())
    report = asar.build_report(asar.TestSetCollection(rows=rows, attempted_pairs=frozenset()))
    assert report.total_sets == 3


def test_declared_and_observed_item_counts_from_header_and_items() -> None:
    aid = uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    row = _row(
        assessment_id=aid,
        pattern_diagnosis=[_header(selected_item_count=2), _item(p1), _item(p2)],
    )
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    seat = _seat(report, aid)
    assert seat.declared_item_count == 2
    assert seat.observed_item_count == 2


def test_declared_and_observed_can_disagree_when_header_and_items_mismatch() -> None:
    """헤더가 3개라 선언해도 실제 항목이 1개뿐이면 그대로 어긋난 값을 낸다(조용한 보정 금지)."""
    aid = uuid.uuid4()
    row = _row(
        assessment_id=aid, pattern_diagnosis=[_header(selected_item_count=3), _item(uuid.uuid4())]
    )
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    seat = _seat(report, aid)
    assert seat.declared_item_count == 3
    assert seat.observed_item_count == 1


# ──────────────────────────────────────────────────────────────────────────
# 2. 헤더 형태 이상(malformed) — 조용히 버리지 않고 별도 계상
# ──────────────────────────────────────────────────────────────────────────
def test_missing_header_is_flagged_malformed_not_silently_dropped() -> None:
    aid = uuid.uuid4()
    row = _row(assessment_id=aid, pattern_diagnosis=[_item(uuid.uuid4())])  # 헤더 없음
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    seat = _seat(report, aid)
    assert seat.malformed_pattern_diagnosis is True
    assert seat.declared_item_count is None
    assert report.malformed_count == 1


def test_well_formed_header_is_not_flagged_malformed() -> None:
    row = _row(pattern_diagnosis=[_header()])
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    assert report.malformed_count == 0


def test_non_dict_entries_in_pattern_diagnosis_are_ignored_not_crashed() -> None:
    """방어적 파싱 — 문자열 등 딕셔너리가 아닌 항목이 섞여도 예외 없이 무시한다."""
    row = _row(pattern_diagnosis=["not-a-dict", _header(), 42])
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    assert report.malformed_count == 0
    assert report.total_sets == 1


# ──────────────────────────────────────────────────────────────────────────
# 3. 귀속 판별 불가 시도 — 핵심 변별력(델타 패턴)
# ──────────────────────────────────────────────────────────────────────────
def test_unattributable_count_increases_when_attempt_pair_present() -> None:
    """합성 세트 + 합성 시도 추가 → 카운터가 실제로 오른다(acceptance⑤)."""
    uid = uuid.uuid4()
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    row = _row(assessment_id=aid, user_id=uid, pattern_diagnosis=[_header(1), _item(pid)])

    without_attempt = asar.build_report(
        asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset())
    )
    with_attempt = asar.build_report(
        asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset({(uid, pid)}))
    )
    assert without_attempt.total_unattributable_attempts == 0
    assert with_attempt.total_unattributable_attempts == 1
    assert _seat(with_attempt, aid).unattributable_attempt_count == 1


def test_unattributable_count_restores_to_zero_when_attempt_pair_removed() -> None:
    """추가했던 합성 시도를 제거하면 카운터가 원래 값으로 복원된다(델타 왕복)."""
    uid, pid, aid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    row = _row(assessment_id=aid, user_id=uid, pattern_diagnosis=[_header(1), _item(pid)])
    baseline = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    bumped = asar.build_report(
        asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset({(uid, pid)}))
    )
    restored = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    assert baseline.total_unattributable_attempts == 0
    assert bumped.total_unattributable_attempts == 1
    assert restored.total_unattributable_attempts == baseline.total_unattributable_attempts


def test_attempt_for_problem_not_in_any_set_does_not_count() -> None:
    """세트에 없는 문항의 시도는 카운터에 잡히지 않는다(acceptance⑤ 후반)."""
    uid, pid_in_set, pid_outside = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    row = _row(user_id=uid, pattern_diagnosis=[_header(1), _item(pid_in_set)])
    # attempted_pairs에 세트 밖 문항의 (uid, pid_outside)만 있는 상황을 가정.
    report = asar.build_report(
        asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset({(uid, pid_outside)}))
    )
    assert report.total_unattributable_attempts == 0


def test_attempt_by_different_user_for_same_problem_does_not_count() -> None:
    """다른 사용자의 시도는 이 세트 소유자의 귀속 판정에 영향을 주지 않는다."""
    owner, other_user, pid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    row = _row(user_id=owner, pattern_diagnosis=[_header(1), _item(pid)])
    report = asar.build_report(
        asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset({(other_user, pid)}))
    )
    assert report.total_unattributable_attempts == 0


# ──────────────────────────────────────────────────────────────────────────
# 4. 빈 완료 세트
# ──────────────────────────────────────────────────────────────────────────
def test_completed_with_no_result_artifacts_is_empty_completion() -> None:
    aid = uuid.uuid4()
    row = _row(assessment_id=aid, completed_at=datetime(2026, 1, 1, tzinfo=UTC))
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    seat = _seat(report, aid)
    assert seat.completed is True
    assert seat.empty_completion is True
    assert report.empty_completion_count == 1


def test_completed_with_any_result_artifact_is_not_empty_completion() -> None:
    aid = uuid.uuid4()
    row = _row(
        assessment_id=aid,
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        concept_diagnosis=[{"concept_id": "x"}],
    )
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    assert _seat(report, aid).empty_completion is False
    assert report.empty_completion_count == 0


def test_incomplete_set_is_never_counted_as_empty_completion() -> None:
    """completed_at이 None이면 결과가 비어도 '빈 완료'가 아니다(아직 완료 자체가 안 된 것)."""
    row = _row(completed_at=None)
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    assert report.empty_completion_count == 0


# ──────────────────────────────────────────────────────────────────────────
# 5. 중복 청사진 세트
# ──────────────────────────────────────────────────────────────────────────
def test_same_user_same_item_set_twice_is_one_duplicate_group() -> None:
    uid = uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    row_a = _row(user_id=uid, pattern_diagnosis=[_header(2), _item(p1), _item(p2)])
    row_b = _row(user_id=uid, pattern_diagnosis=[_header(2), _item(p1), _item(p2)])
    report = asar.build_report(
        asar.TestSetCollection(rows=(row_a, row_b), attempted_pairs=frozenset())
    )
    assert report.duplicate_blueprint_group_count == 1
    assert report.duplicate_blueprint_extra_row_count == 1


def test_different_item_sets_are_not_duplicates() -> None:
    uid = uuid.uuid4()
    row_a = _row(user_id=uid, pattern_diagnosis=[_header(1), _item(uuid.uuid4())])
    row_b = _row(user_id=uid, pattern_diagnosis=[_header(1), _item(uuid.uuid4())])
    report = asar.build_report(
        asar.TestSetCollection(rows=(row_a, row_b), attempted_pairs=frozenset())
    )
    assert report.duplicate_blueprint_group_count == 0


def test_same_item_set_different_users_is_not_a_duplicate() -> None:
    pid = uuid.uuid4()
    row_a = _row(user_id=uuid.uuid4(), pattern_diagnosis=[_header(1), _item(pid)])
    row_b = _row(user_id=uuid.uuid4(), pattern_diagnosis=[_header(1), _item(pid)])
    report = asar.build_report(
        asar.TestSetCollection(rows=(row_a, row_b), attempted_pairs=frozenset())
    )
    assert report.duplicate_blueprint_group_count == 0


def test_no_result_gating_fields_appear_in_json_output() -> None:
    """게임화 금기(acceptance④) — 점수·등급 등은 애초에 이 리포트 데이터 모델에 없다."""
    report = asar.build_report(asar.TestSetCollection(rows=(), attempted_pairs=frozenset()))
    payload = asar.report_to_json(report)
    dumped = json.dumps(payload)
    for forbidden in (
        "estimated_grade",
        "estimated_score",
        "estimated_percentile",
        "admission_probability",
    ):
        assert forbidden not in dumped


# ──────────────────────────────────────────────────────────────────────────
# 6. JSON 직렬화·렌더링 결정론성
# ──────────────────────────────────────────────────────────────────────────
def test_report_to_json_roundtrips_through_json_dumps_loads() -> None:
    row = _row(pattern_diagnosis=[_header(1), _item(uuid.uuid4())])
    report = asar.build_report(asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset()))
    payload = asar.report_to_json(report)
    roundtripped = json.loads(json.dumps(payload, ensure_ascii=False))
    assert roundtripped == payload
    assert roundtripped["total_sets"] == 1


def test_dump_json_produces_valid_json_with_sorted_keys() -> None:
    report = asar.build_report(asar.TestSetCollection(rows=(), attempted_pairs=frozenset()))
    dumped = asar.dump_json(report)
    parsed = json.loads(dumped)
    assert parsed["total_sets"] == 0


def test_render_report_is_deterministic_across_repeated_calls() -> None:
    row = _row(pattern_diagnosis=[_header(1), _item(uuid.uuid4())])
    collection = asar.TestSetCollection(rows=(row,), attempted_pairs=frozenset())
    r1 = asar.render_report(asar.build_report(collection))
    r2 = asar.render_report(asar.build_report(collection))
    assert r1 == r2


# ──────────────────────────────────────────────────────────────────────────
# 7. CLI — DB 오류 시 exit 2·예외 타입명 stderr 포함(침묵 실패 금지)
# ──────────────────────────────────────────────────────────────────────────
def test_main_returns_exit_2_and_logs_exception_type_on_db_failure(capsys) -> None:
    with patch.object(asar, "_run", new=AsyncMock(side_effect=RuntimeError("접속 실패"))):
        exit_code = asar.main([])
    assert exit_code == asar._EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err


def test_main_cli_smoke_help_exits_zero_without_db() -> None:
    """`--help`는 DB 접속 없이 exit 0이어야 한다(argparse 표준 동작 회귀 감시)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whymath_backend.harness.assessment_set_attribution_report",
            "--help",
        ],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0
    assert "assessment" in result.stdout.lower() or "귀속" in result.stdout
