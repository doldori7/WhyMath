"""[FLOW-HEALTH] 통합 흐름 신호의 계약 동결 — **양방향** 변별력.

왜 이 테스트가 있는가
--------------------
이 저장소는 "검증 스텝이 정상/결함 양쪽에서 같은 값을 내는" 실패를 이미 겪었다
(CLAUDE.md "변별력 없는 검증 스텝 금지" — 2026-07-17 logconfig `delay:true`).
탐지기 테스트가 결함 입력에서 발화하는 것만 확인하면, **모든 입력에 발화하는**
탐지기도 절반은 통과한다. 그래서 모든 신호를 정상 입력에서 **침묵**하고 결함
입력에서 **발화**하는 쌍으로 동결한다.

두 번째 축 — **측정 실패 ≠ 통과**
개발 중 실측으로 드러난 결함 하나를 계약으로 못박는다: `refs/pull/<N>/head`는
PR이 *제출된 적 있음*만 증명하는데 이를 *열려 있음*으로 읽으면, closed·unmerged
PR(#675 실측)이 ①리뷰 부하 없는 PR에 PR-03을 발화시키고 ②트렁크 밖에 남은
작업을 WIP 집계에서 뺀다. `pr_ref`와 `pr_open`은 분리된 채로 있어야 한다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "flow_health",
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "flow_health.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # @dataclass 조회 대비 — exec 전 등록
_spec.loader.exec_module(_mod)

BranchFlow = _mod.BranchFlow
classify = _mod.classify
PRESCRIPTION = _mod.PRESCRIPTION
UNMEASURED = _mod.UNMEASURED


def healthy(name: str = "feat/ok", **kw) -> BranchFlow:
    """정상 브랜치 — 어떤 신호도 내면 안 되는 기준점."""
    base = dict(
        branch=name,
        ahead=3,
        behind=2,
        age_days=1.0,
        files=5,
        conflicts=0,
        pr_ref=100,
        pr_open=True,
        active=False,
    )
    base.update(kw)
    return BranchFlow(**base)


def codes(findings) -> set[str]:
    return {f.code for f in findings}


class TestSilentWhenHealthy:
    """정상 입력에서 **침묵**해야 한다 — 이게 없으면 아래 발화 테스트가 무의미하다."""

    def test_healthy_branches_produce_no_findings(self):
        assert classify([healthy("a"), healthy("b")], []) == []

    def test_healthy_fleet_under_wip_limit_is_silent(self):
        fleet = [healthy(f"b{i}", pr_ref=None, pr_open=False) for i in range(5)]
        assert codes(classify(fleet, [])) == set(), "상한 이하 WIP는 신호가 아니다"


class TestEachSignalFires:
    """결함 입력에서 **해당 코드만** 발화해야 한다."""

    def test_git01_drift_needs_both_behind_and_age(self):
        # behind만 크고 최신 → 침묵 (오늘 만든 브랜치가 오래된 base에서 갈라진 정상 상태)
        assert "GIT-01" not in codes(classify([healthy(behind=500, age_days=0.5)], []))
        # age만 크고 behind 작음 → 침묵
        assert "GIT-01" not in codes(classify([healthy(behind=1, age_days=99)], []))
        # 둘 다 → 발화
        assert "GIT-01" in codes(classify([healthy(behind=500, age_days=99)], []))

    def test_git04_conflict_fires_on_real_conflict(self):
        assert "GIT-04" not in codes(classify([healthy(conflicts=0)], []))
        assert "GIT-04" in codes(classify([healthy(conflicts=1)], []))

    def test_pr03_fires_only_on_open_oversized_pr(self):
        assert "PR-03" in codes(classify([healthy(files=999, pr_open=True)], []))
        assert "PR-03" not in codes(
            classify([healthy(files=999, pr_open=False)], [])
        ), "닫힌 PR은 리뷰 부하가 아니다"

    def test_pr04_fires_on_overlap(self):
        two = [healthy("a"), healthy("b")]
        assert "PR-04" not in codes(classify(two, [("a", "b", 1)]))
        assert "PR-04" in codes(classify(two, [("a", "b", 50)]))

    def test_flow01_fires_above_wip_limit(self):
        many = [healthy(f"b{i}", pr_ref=None, pr_open=False) for i in range(50)]
        assert "FLOW-01" in codes(classify(many, []))


class TestUnmeasuredIsNotPass:
    """측정 실패와 통과가 같은 색이면 안 된다 (CLAUDE.md 이중 회계)."""

    def test_unmeasured_conflict_is_not_read_as_zero(self):
        f = classify([healthy(conflicts=UNMEASURED)], [])
        assert "GIT-04" not in codes(f), "미측정을 충돌로 오판하면 안 된다"
        assert UNMEASURED != 0, "센티널이 '충돌 없음'과 같은 값이면 구분이 불가능하다"
        assert UNMEASURED < 0, "파일 수는 음수가 될 수 없으므로 센티널은 음수여야 한다"

    def test_pr03_does_not_guess_when_openness_unknown(self):
        # pr_open=None = API 조회 실패. 추측으로 신호를 만들지 않는다.
        f = classify([healthy(files=999, pr_open=None)], [])
        assert "PR-03" not in codes(f)


class TestClosedPrCountsAsUnintegrated:
    """실측 결함(#675)의 계약화 — closed·unmerged는 '처리됨'이 아니다."""

    def test_closed_unmerged_pr_counts_toward_wip(self):
        # PR ref는 있으나 닫힘 → 작업은 여전히 트렁크 밖이다
        closed = [healthy(f"b{i}", pr_ref=600 + i, pr_open=False) for i in range(50)]
        assert "FLOW-01" in codes(
            classify(closed, [])
        ), "닫힌 PR을 '제출됨'으로 세면 고립 작업이 집계에서 사라진다"

    def test_pr_ref_and_pr_open_are_independent_fields(self):
        b = healthy(pr_ref=675, pr_open=False)
        assert (
            b.pr_ref == 675 and b.pr_open is False
        ), "제출 이력과 열림 여부는 분리된 채로 있어야 한다"


class TestActiveBranchesExcluded:
    """진행 중 브랜치를 방치로 부르면 오경보다 (HARN-47이 겪은 형태)."""

    def test_active_branch_not_flagged_as_drift_or_wip(self):
        act = healthy(behind=500, age_days=99, pr_ref=None, pr_open=False, active=True)
        assert codes(classify([act] * 50, [])) == set()

    def test_active_branch_still_flagged_for_conflict(self):
        # 충돌은 진행 중이어도 지금 고쳐야 할 사실이다
        act = healthy(conflicts=5, active=True)
        assert "GIT-04" in codes(classify([act], []))


class TestPrescriptionsAreDistinct:
    """코드마다 처방이 달라야 한다 — 같으면 분리할 이유가 없다."""

    def test_every_code_has_a_unique_prescription(self):
        assert len(set(PRESCRIPTION.values())) == len(PRESCRIPTION)

    def test_findings_carry_their_prescription(self):
        f = classify([healthy(conflicts=3)], [])
        assert f[0].prescription == PRESCRIPTION["GIT-04"]


class TestWarnOnlyDoesNotMaskMeasurementFailure:
    """`--warn-only`는 **신호**만 낮춘다 — 측정 실패까지 삼키면 안 된다.

    이 구분이 없으면 CI 잡이 "관측 전용"이라는 이유로 shallow·git 오류까지
    초록으로 만든다. 그것이 정확히 CLAUDE.md가 금지하는 "측정 실패가 0건
    통과로 위장되는" 상태다. `main()`은 collect가 ok가 아니면 `--warn-only`
    **이전에** 2를 반환해야 한다.
    """

    def test_measurement_failure_returns_2_even_with_warn_only(self, monkeypatch, capsys):
        monkeypatch.setattr(
            _mod,
            "collect",
            lambda *a, **k: _mod.Report(status="shallow", message="테스트 주입"),
        )
        assert _mod.main(["--warn-only"]) == 2
        assert "측정 불가" in capsys.readouterr().out

    def test_findings_are_downgraded_to_0_by_warn_only(self, monkeypatch):
        bad = healthy(conflicts=9)
        monkeypatch.setattr(
            _mod, "collect", lambda *a, **k: _mod.Report(status="ok", branches=[bad])
        )
        monkeypatch.setattr(_mod, "compute_overlaps", lambda *a, **k: [])
        monkeypatch.setattr(_mod, "_active_branches", lambda *a, **k: (frozenset(), ""))
        assert _mod.main([]) == 1, "신호가 있으면 기본은 1"
        assert _mod.main(["--warn-only"]) == 0, "--warn-only는 신호를 0으로 낮춘다"


class TestUnknownPrStateIsNotCountedAsUnfiled:
    """Codex P2 #3899930470 — 모르는 것을 '없음'으로 세지 않는다.

    `not b.pr_open`은 `None`(열림 여부 미판정)까지 "PR 없음"으로 센다. API 장애·
    rate limit이면 전 브랜치가 미판정이 되므로, 순전히 모르는 데이터로 FLOW-01이
    **확정 발화**한다 — `collect()`가 같은 상황을 unmeasured로 표시해 놓고 신호는
    내는 자기모순이다.
    """

    def test_unknown_pr_state_does_not_trigger_flow01(self):
        unknown = [healthy(f"b{i}", pr_ref=None, pr_open=None) for i in range(50)]
        assert "FLOW-01" not in codes(
            classify(unknown, [])
        ), "열림 여부를 모르는 브랜치로 WIP 초과를 선언하면 안 된다"

    def test_known_unfiled_still_triggers(self):
        # 변별력 — 아는 상태에서는 여전히 발화해야 한다
        known = [healthy(f"b{i}", pr_ref=None, pr_open=False) for i in range(50)]
        assert "FLOW-01" in codes(classify(known, []))


class TestSummaryMatchesDetail:
    """Codex P2 #3899930474 — 첫 줄 합계가 아래 진단과 모순되면 안 된다."""

    def test_drift_summary_applies_age_condition(self):
        # 오래된 trunk에서 오늘 갈라진 브랜치: behind는 크지만 표류가 아니다
        fresh = healthy("new", behind=500, age_days=0.1)
        report = _mod.Report(status="ok", branches=[fresh])
        findings = classify([fresh], [])
        text = _mod.render(report, findings)
        assert "GIT-01" not in text, "상세에는 GIT-01이 없어야 한다"
        assert "표류 0건" in text, f"요약도 0이어야 모순이 없다 — 실제: {text.splitlines()[0]}"

    def test_summary_counts_real_drift(self):
        old = healthy("old", behind=500, age_days=99)
        report = _mod.Report(status="ok", branches=[old])
        text = _mod.render(report, classify([old], []))
        assert "표류 1건" in text


class TestActiveClaimFailureIsReported:
    """Codex P2 #3899930463 — claim 조회 실패를 조용히 빈 집합으로 만들지 않는다.

    초판은 ⓐ `sys.path`에 `scripts`를 넣어 `ModuleNotFoundError`, ⓑ 존재하지 않는
    `load_remote_claim_map` 호출로 `AttributeError`를 냈고 광범위 `except`가 둘 다
    삼켰다. 실측 시점에 claim 3건이 살아 있었는데 `frozenset()`이 나왔고, 그 결과
    타 세션 작업 브랜치가 전부 dormant로 분류돼 오경보 대상이 된다.
    """

    def test_returns_tuple_of_set_and_reason(self, tmp_path):
        result = _mod._active_branches(tmp_path)
        assert (
            isinstance(result, tuple) and len(result) == 2
        ), "실패 사유를 반환값으로 올려야 호출부가 리포트에 남길 수 있다"
        branches, reason = result
        assert isinstance(branches, frozenset)
        assert isinstance(reason, str)

    def test_uses_existing_harness_reader(self):
        """존재하지 않는 API를 부르지 않는다 — 소스에 `list_claims`가 있어야 한다."""
        src = (
            Path(__file__).resolve().parents[2] / "scripts" / "ops" / "flow_health.py"
        ).read_text(encoding="utf-8")
        assert "list_claims(" in src, "backlog.py와 같은 리더를 호출해야 한다"
        # 문자열 *언급*이 아니라 **호출**을 본다 — 사고 경위를 docstring에 남기는 것은
        # 금지 대상이 아니다(그걸 잡으면 왜 이 규칙이 있는지 적을 수 없다).
        assert "load_remote_claim_map(" not in src, "존재하지 않는 함수를 호출하고 있다"

    def test_failure_reason_reaches_the_report(self, monkeypatch, capsys):
        monkeypatch.setattr(
            _mod, "_active_branches", lambda r: (frozenset(), "BoomError: 조회불가")
        )
        monkeypatch.setattr(
            _mod, "collect", lambda *a, **k: _mod.Report(status="ok", branches=[healthy()])
        )
        monkeypatch.setattr(_mod, "compute_overlaps", lambda *a, **k: [])
        _mod.main([])
        out = capsys.readouterr().out
        assert (
            "active판정" in out and "BoomError" in out
        ), f"claim 조회 실패가 리포트에 안 보인다 — 침묵 실패다: {out}"
