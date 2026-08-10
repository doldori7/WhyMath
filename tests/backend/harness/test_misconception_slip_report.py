"""root/symptom·slip 판별 관측 리포트 테스트(MISC-05) — acceptance①~⑦ 대응.

구성:
  - `classify_pair` 단위 테스트(5-way 분류 완전성 — slip-like/지속오개념-like/불일치 2종/잔여)
  - `build_report` 집계 테스트(분모 완전성·스냅샷-이력 불일치 정직 회계·confidence 근사·judge
    상태 반영)
  - render/json 정직 회계 문구 테스트(데이터없음 vs 0건 구분·개인정보 비노출)
  - 결정론 테스트(동일 입력 → 동일 바이트, 입력 순서 비의존)
  - CLI 테스트(exit 0 성공·exit 2 DB 오류 — exit 1 없음 확인)

전부 hermetic(DB 0) — `build_report`는 순수 함수라 dataclass를 직접 구성해 검증한다
(`attempt_grading_shadow_report`/`recommendation_outcome_report` 테스트 관례 답습).
"""

from __future__ import annotations

import inspect
import json
import uuid
from datetime import datetime, timezone

import pytest

import whymath_backend.db.session as db_session_module
from whymath_backend.harness import misconception_slip_report as mod
from whymath_backend.harness.misconception_slip_report import (
    EvidenceRecord,
    HypothesisSnapshotRecord,
    build_report,
    classify_pair,
    dump_json,
    render_report,
    report_to_json,
)

pytestmark = pytest.mark.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼 — 최소 레코드 구성
# ──────────────────────────────────────────────────────────────────────────
def _snap(
    *,
    student_id: uuid.UUID | None,
    misconception_id: str = "m-test",
    evidence_count: int,
    is_active: bool,
) -> HypothesisSnapshotRecord:
    return HypothesisSnapshotRecord(
        student_id=student_id,
        misconception_id=misconception_id,
        evidence_count=evidence_count,
        is_active=is_active,
    )


def _ev(
    *,
    student_id: uuid.UUID,
    misconception_id: str = "m-test",
    polarity: int = 1,
    weight: float | None = None,
    created_at: datetime | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        student_id=student_id,
        misconception_id=misconception_id,
        polarity=polarity,
        weight=weight,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────────────
# classify_pair — 5-way 분류(3분류 + 잔여) 완전성
# ──────────────────────────────────────────────────────────────────────────
class TestClassifyPair:
    def test_slip_like(self) -> None:
        snap = _snap(student_id=uuid.uuid4(), evidence_count=1, is_active=False)
        assert classify_pair(snap, 1) == "slip_like"

    def test_persistent_like(self) -> None:
        snap = _snap(student_id=uuid.uuid4(), evidence_count=2, is_active=True)
        assert classify_pair(snap, 2) == "persistent_like"

    def test_persistent_like_higher_count(self) -> None:
        snap = _snap(student_id=uuid.uuid4(), evidence_count=5, is_active=True)
        assert classify_pair(snap, 5) == "persistent_like"

    def test_mismatch_absent_when_no_snapshot(self) -> None:
        assert classify_pair(None, 3) == "mismatch_absent"

    def test_mismatch_disagreement_when_counts_differ(self) -> None:
        """태스크가 명시한 예시 — 이력(강화 횟수)이 스냅샷 evidence_count와 다르면 불일치."""
        snap = _snap(student_id=uuid.uuid4(), evidence_count=1, is_active=False)
        assert classify_pair(snap, 2) == "mismatch_disagreement"

    def test_undetermined_single_evidence_still_active(self) -> None:
        """1회·아직 활성 — slip-like도 지속오개념-like도 아닌 잔여(강제분류 금지)."""
        snap = _snap(student_id=uuid.uuid4(), evidence_count=1, is_active=True)
        assert classify_pair(snap, 1) == "undetermined"

    def test_undetermined_multi_evidence_but_inactive(self) -> None:
        """≥2회 강화됐으나 비활성(반박·장기방치 감쇠 등) — 지속오개념-like로 강제분류 안 함."""
        snap = _snap(student_id=uuid.uuid4(), evidence_count=3, is_active=False)
        assert classify_pair(snap, 3) == "undetermined"

    def test_mismatch_checked_before_behavioral_pattern(self) -> None:
        """카운트 불일치가 우연히 slip-like 패턴(1·비활성)이어도 불일치 판정이 우선한다."""
        snap = _snap(student_id=uuid.uuid4(), evidence_count=1, is_active=False)
        assert classify_pair(snap, 3) == "mismatch_disagreement"


# ──────────────────────────────────────────────────────────────────────────
# build_report — 분류 집계 + 분모 완전성(acceptance①②③)
# ──────────────────────────────────────────────────────────────────────────
class TestBuildReportClassification:
    def test_denominator_completeness_across_all_buckets(self) -> None:
        """6쌍을 5-way(3주분류+잔여+불일치2종)에 정확히 하나씩 배분 — 분모 완전성 불변식."""
        sid = [uuid.uuid4() for _ in range(6)]
        snapshots = [
            _snap(student_id=sid[0], misconception_id="m1", evidence_count=1, is_active=False),
            _snap(student_id=sid[1], misconception_id="m2", evidence_count=2, is_active=True),
            _snap(student_id=sid[2], misconception_id="m3", evidence_count=1, is_active=True),
            _snap(student_id=sid[3], misconception_id="m4", evidence_count=5, is_active=False),
            _snap(student_id=sid[4], misconception_id="m5", evidence_count=9, is_active=True),
        ]
        evidence = [
            _ev(student_id=sid[0], misconception_id="m1", weight=0.6),
            _ev(student_id=sid[1], misconception_id="m2", weight=0.4),
            _ev(student_id=sid[1], misconception_id="m2", weight=0.7),
            _ev(student_id=sid[2], misconception_id="m3", weight=0.3),
            *[_ev(student_id=sid[3], misconception_id="m4") for _ in range(5)],
            _ev(student_id=sid[4], misconception_id="m5"),  # 스냅샷은 9인데 이력은 1건뿐
            _ev(student_id=sid[5], misconception_id="m6", weight=0.9),  # 스냅샷 자체가 없음
        ]
        report = build_report(snapshots, evidence, judge_enabled=False)

        assert report.total_pairs == 6
        assert report.slip_like_count == 1  # m1
        assert report.persistent_like_count == 1  # m2
        assert report.undetermined_count == 2  # m3(1회·활성) · m4(5회·비활성)
        assert report.mismatch_disagreement_count == 1  # m5
        assert report.mismatch_snapshot_absent_count == 1  # m6
        assert report.mismatch_count == 2
        assert (
            report.total_pairs
            == report.slip_like_count
            + report.persistent_like_count
            + report.undetermined_count
            + report.mismatch_count
        )

    def test_refutation_evidence_does_not_count_toward_reinforcement(self) -> None:
        """polarity=-1(반박)은 04e §3의 '강화 횟수'가 아니다 — 카운트·confidence 근사 모두 제외."""
        sid = uuid.uuid4()
        snapshots = [_snap(student_id=sid, evidence_count=1, is_active=False)]
        evidence = [
            _ev(student_id=sid, polarity=-1, weight=0.99),  # 반박 — 무시돼야 함
            _ev(student_id=sid, polarity=1, weight=0.3),  # 유일한 강화
        ]
        report = build_report(snapshots, evidence, judge_enabled=False)
        assert report.slip_like_count == 1  # -1이 카운트에 섞였으면 evidence_count(1)과
        # 불일치(hist=2)해 mismatch로 샜을 것 — slip_like로 남았다는 것 자체가 반박 제외 증거.
        assert report.slip_like_high_confidence_count == 0  # 0.3<0.5(0.99가 섞이지 않았다는 증거)


# ──────────────────────────────────────────────────────────────────────────
# judge_enabled 상태 반영(acceptance④)
# ──────────────────────────────────────────────────────────────────────────
class TestJudgeEnabledReflection:
    def test_judge_enabled_true_reflected_in_report_and_render(self) -> None:
        report = build_report([], [], judge_enabled=True)
        assert report.judge_enabled is True
        assert "misconception_judge_enabled` = **True**" in render_report(report)

    def test_judge_enabled_false_reflected_in_report_and_render(self) -> None:
        report = build_report([], [], judge_enabled=False)
        assert report.judge_enabled is False
        assert "misconception_judge_enabled` = **False**" in render_report(report)

    def test_judge_gap_note_present_regardless_of_flag(self) -> None:
        for flag in (True, False):
            report = build_report([], [], judge_enabled=flag)
            assert "EXPRESSES" in report.judge_gap_note
            assert "간접 전제" in report.judge_gap_note

    def test_judge_docstring_stale_note_present(self) -> None:
        report = build_report([], [], judge_enabled=False)
        assert "config.py" in report.judge_docstring_stale_note
        assert "stale" in report.judge_docstring_stale_note


# ──────────────────────────────────────────────────────────────────────────
# 개입 임계 근사 초과 비율(acceptance⑤, §4)
# ──────────────────────────────────────────────────────────────────────────
class TestInterventionConfidenceApproximation:
    def test_high_confidence_slip_counted(self) -> None:
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=1, is_active=False)],
            [_ev(student_id=sid, weight=0.9)],
            judge_enabled=False,
        )
        assert report.slip_like_high_confidence_count == 1
        assert report.slip_like_high_confidence_rate == pytest.approx(1.0)

    def test_low_confidence_slip_not_counted(self) -> None:
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=1, is_active=False)],
            [_ev(student_id=sid, weight=0.2)],
            judge_enabled=False,
        )
        assert report.slip_like_high_confidence_count == 0
        assert report.slip_like_high_confidence_rate == pytest.approx(0.0)

    def test_threshold_boundary_is_inclusive(self) -> None:
        """정확히 0.5(개입 임계 그 자체)는 초과 근사에 포함된다(>=)."""
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=1, is_active=False)],
            [_ev(student_id=sid, weight=0.5)],
            judge_enabled=False,
        )
        assert report.slip_like_high_confidence_count == 1

    def test_unknown_confidence_excluded_from_denominator(self) -> None:
        """weight 전무(None)면 판정 불가로 별도 집계 — 분모(known)에서 제외, 0%로 위장 안 함."""
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=1, is_active=False)],
            [_ev(student_id=sid, weight=None)],
            judge_enabled=False,
        )
        assert report.slip_like_count == 1
        assert report.slip_like_unknown_confidence_count == 1
        assert report.slip_like_confidence_known_count == 0
        assert report.slip_like_high_confidence_rate is None

    def test_rate_computed_over_multiple_slip_like_pairs(self) -> None:
        """3개 slip-like 중 2개가 임계 이상 → 비율 정확히 2/3."""
        sids = [uuid.uuid4() for _ in range(3)]
        snapshots = [
            _snap(student_id=sids[i], misconception_id=f"m{i}", evidence_count=1, is_active=False)
            for i in range(3)
        ]
        weights = [0.9, 0.7, 0.1]
        evidence = [
            _ev(student_id=sids[i], misconception_id=f"m{i}", weight=weights[i]) for i in range(3)
        ]
        report = build_report(snapshots, evidence, judge_enabled=False)
        assert report.slip_like_count == 3
        assert report.slip_like_high_confidence_count == 2
        assert report.slip_like_high_confidence_rate == pytest.approx(2 / 3)

    def test_persistent_like_pairs_do_not_affect_slip_confidence_metric(self) -> None:
        """지속오개념-like 쌍의 weight는 slip 전용 지표에 섞이지 않는다."""
        sid_slip, sid_persist = uuid.uuid4(), uuid.uuid4()
        snapshots = [
            _snap(
                student_id=sid_slip, misconception_id="m-slip", evidence_count=1, is_active=False
            ),
            _snap(
                student_id=sid_persist,
                misconception_id="m-persist",
                evidence_count=2,
                is_active=True,
            ),
        ]
        evidence = [
            _ev(student_id=sid_slip, misconception_id="m-slip", weight=0.2),
            _ev(student_id=sid_persist, misconception_id="m-persist", weight=0.99),
            _ev(student_id=sid_persist, misconception_id="m-persist", weight=0.99),
        ]
        report = build_report(snapshots, evidence, judge_enabled=False)
        assert report.slip_like_count == 1
        assert report.slip_like_high_confidence_count == 0  # 0.99짜리 persistent가 안 섞임


# ──────────────────────────────────────────────────────────────────────────
# 빈 입력 — "데이터없음" vs "0건" 구분(acceptance⑥)
# ──────────────────────────────────────────────────────────────────────────
class TestEmptyInputHonestAccounting:
    def test_fully_empty_input_renders_as_data_absent(self) -> None:
        report = build_report([], [], judge_enabled=False)
        assert report.total_pairs == 0
        rendered = render_report(report)
        assert "데이터없음" in rendered
        assert "관측된 것이 0건인 게 아니라" in rendered

    def test_nonzero_total_but_zero_slip_like_is_not_data_absent(self) -> None:
        """total_pairs>0인데 slip-like만 0건 — '0건 관측'이지 '데이터없음'이 아니다."""
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=2, is_active=True)],
            [_ev(student_id=sid, weight=0.9), _ev(student_id=sid, weight=0.9)],
            judge_enabled=False,
        )
        assert report.total_pairs == 1
        assert report.slip_like_count == 0
        rendered = render_report(report)
        assert "총 1쌍" in rendered
        assert "slip-like로 분류된 쌍: **0건**(관측은 이뤄졌음" in rendered
        assert "트리거 지표 계산 대상이 없다" in rendered
        # 상단 총량 섹션은 "데이터없음" 분기를 타지 않는다.
        assert "데이터없음(가설 스냅샷" not in rendered

    def test_anonymous_snapshot_rows_counted_not_silently_dropped(self) -> None:
        """user_id=NULL 스냅샷 행은 조용히 드롭되지 않고 정직하게 집계·표기된다."""
        known_sid = uuid.uuid4()
        snapshots = [
            _snap(student_id=None, misconception_id="m-orphan", evidence_count=1, is_active=False),
            _snap(student_id=known_sid, misconception_id="m-ok", evidence_count=1, is_active=False),
        ]
        evidence = [_ev(student_id=known_sid, misconception_id="m-ok", weight=0.9)]
        report = build_report(snapshots, evidence, judge_enabled=False)
        assert report.snapshot_anonymous_rows_skipped == 1
        assert report.total_pairs == 1
        assert "1건" in render_report(report)


# ──────────────────────────────────────────────────────────────────────────
# 결정론(acceptance⑦) — 같은 입력 → 같은 바이트
# ──────────────────────────────────────────────────────────────────────────
class TestDeterminism:
    @staticmethod
    def _sample() -> tuple[list[HypothesisSnapshotRecord], list[EvidenceRecord]]:
        sid1, sid2 = uuid.uuid4(), uuid.uuid4()
        snapshots = [
            _snap(student_id=sid1, misconception_id="m1", evidence_count=1, is_active=False),
            _snap(student_id=sid2, misconception_id="m2", evidence_count=2, is_active=True),
        ]
        evidence = [
            _ev(student_id=sid1, misconception_id="m1", weight=0.8),
            _ev(student_id=sid2, misconception_id="m2", weight=0.4),
            _ev(student_id=sid2, misconception_id="m2", weight=0.6),
        ]
        return snapshots, evidence

    def test_same_input_produces_same_json_bytes(self) -> None:
        snapshots, evidence = self._sample()
        report_a = build_report(snapshots, evidence, judge_enabled=True)
        report_b = build_report(snapshots, evidence, judge_enabled=True)
        assert dump_json(report_a) == dump_json(report_b)

    def test_dump_json_called_twice_on_same_report_is_identical(self) -> None:
        snapshots, evidence = self._sample()
        report = build_report(snapshots, evidence, judge_enabled=False)
        assert dump_json(report) == dump_json(report)

    def test_dump_json_is_valid_json_with_sorted_keys(self) -> None:
        snapshots, evidence = self._sample()
        report = build_report(snapshots, evidence, judge_enabled=False)
        dumped = dump_json(report)
        assert json.loads(dumped) == report_to_json(report)
        top_level_keys = list(json.loads(dumped).keys())
        assert top_level_keys == sorted(top_level_keys)

    def test_result_independent_of_input_list_order(self) -> None:
        """입력 리스트 순서(같은 집합)가 달라도 집계 결과는 바이트 단위로 동일."""
        snapshots, evidence = self._sample()
        report_forward = build_report(snapshots, evidence, judge_enabled=False)
        report_reversed = build_report(
            list(reversed(snapshots)), list(reversed(evidence)), judge_enabled=False
        )
        assert dump_json(report_forward) == dump_json(report_reversed)


# ──────────────────────────────────────────────────────────────────────────
# 프라이버시 — 개별 학생 식별자 비노출
# ──────────────────────────────────────────────────────────────────────────
class TestPrivacyNoIndividualStudentIds:
    def test_student_uuid_never_appears_in_render_or_json(self) -> None:
        sid = uuid.uuid4()
        report = build_report(
            [_snap(student_id=sid, evidence_count=1, is_active=False)],
            [_ev(student_id=sid, weight=0.9)],
            judge_enabled=False,
        )
        rendered = render_report(report)
        dumped = dump_json(report)
        assert str(sid) not in rendered
        assert str(sid) not in dumped


# ──────────────────────────────────────────────────────────────────────────
# CLI — exit 0(성공)·exit 2(입력·DB 오류), exit 1 없음(게이트 아님)
# ──────────────────────────────────────────────────────────────────────────
class TestCli:
    def test_exit_codes_are_only_0_and_2(self) -> None:
        assert mod._EXIT_OK == 0
        assert mod._EXIT_INPUT_ERROR == 2
        source = inspect.getsource(mod.main)
        assert "return 1" not in source

    def test_main_success_exit_zero_and_writes_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: object,
    ) -> None:
        async def _fake_get_session():  # type: ignore[no-untyped-def]
            yield object()

        async def _fake_fetch_snapshots(session: object) -> list[HypothesisSnapshotRecord]:
            return [_snap(student_id=uuid.uuid4(), evidence_count=1, is_active=False)]

        async def _fake_fetch_evidence(session: object) -> list[EvidenceRecord]:
            return []

        monkeypatch.setattr(db_session_module, "get_session", _fake_get_session)
        monkeypatch.setattr(mod, "fetch_hypothesis_snapshot", _fake_fetch_snapshots)
        monkeypatch.setattr(mod, "fetch_evidence_history", _fake_fetch_evidence)

        json_path = tmp_path / "out.json"  # type: ignore[operator]
        exit_code = mod.main(["--json", str(json_path)])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "root/symptom" in captured.out
        assert json_path.exists()  # type: ignore[union-attr]
        payload = json.loads(json_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        assert payload["total_pairs"] == 1

    def test_main_db_error_exit_two(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        async def _fake_get_session():  # type: ignore[no-untyped-def]
            yield object()

        async def _raise_fetch(session: object) -> list[HypothesisSnapshotRecord]:
            raise ConnectionError("DB 접속 실패(테스트 시뮬레이션)")

        monkeypatch.setattr(db_session_module, "get_session", _fake_get_session)
        monkeypatch.setattr(mod, "fetch_hypothesis_snapshot", _raise_fetch)

        exit_code = mod.main([])

        assert exit_code == 2
        captured = capsys.readouterr()
        assert "ConnectionError" in captured.err
