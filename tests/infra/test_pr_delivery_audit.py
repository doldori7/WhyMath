"""HARN-30 ③⑤ — PR 배송 상태 분류의 계약 동결 (양방향).

**왜**: '체크런 0건'과 'green인데 미머지'는 처방이 다르다 — 전자는 트리거를 깨워야
하고 후자는 사람 결정 대기다. 한 덩어리("미머지 PR")로 보면 처방을 못 고른다.
이 상태는 **무증상**이라 아무도 보지 않으면 조용히 방치된다(실측: 도구 첫 실행에서
열린 PR 13건 중 NO_CHECKS 5건·READY_UNMERGED 7건이 드러났다).

**양방향 요구(acceptance ⑤)**: 체크런 0건 PR과 green PR **양쪽**에서 서로 다른
신호가 나야 한다. 한쪽만 확인하고 통과 선언하면, 모든 PR을 같은 상태로 뭉개는
분류기도 절반은 맞는다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pr_delivery_audit",
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "pr_delivery_audit.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # @dataclass/모듈 조회 대비 — exec 전 등록
_spec.loader.exec_module(_mod)
classify = _mod.classify
PRESCRIPTION = _mod.PRESCRIPTION
ATTENTION = _mod.ATTENTION

REQUIRED = {"policy-guard", "backend — 마이그레이션·통합 (실 PG)"}
LONG_JOB = "backend — lint·type·test"  # 필수 아님


class TestBidirectionalDiscrimination:
    """⑤ 핵심 — 체크런 0건과 green이 **서로 다른** 상태를 내야 한다."""

    def test_no_checks_and_ready_differ(self):
        empty = classify(REQUIRED, {}, mergeable_state="clean")
        green = classify(REQUIRED, {n: "success" for n in REQUIRED}, mergeable_state="clean")
        assert empty == "NO_CHECKS"
        assert green == "READY_UNMERGED"
        assert empty != green, "두 상태를 같게 판정하면 처방을 고를 수 없다"

    def test_each_state_carries_a_distinct_prescription(self):
        """상태만 알려주고 처방이 없으면 다음 세션이 다시 판단해야 한다."""
        seen = {PRESCRIPTION[s] for s in PRESCRIPTION}
        assert len(seen) == len(PRESCRIPTION), "처방이 중복되면 상태 분리의 의미가 없다"
        assert ATTENTION == {"NO_CHECKS", "READY_UNMERGED"}


class TestNoChecksDetection:
    """부분 미발화도 미발화다 — 필수가 하나라도 없으면 다른 판정이 무의미하다."""

    def test_completely_empty_is_no_checks(self):
        assert classify(REQUIRED, {}, mergeable_state="clean") == "NO_CHECKS"

    def test_missing_one_required_is_no_checks(self):
        runs = {"policy-guard": "success", LONG_JOB: "success"}
        assert classify(REQUIRED, runs, mergeable_state="clean") == "NO_CHECKS"

    def test_nonrequired_only_is_no_checks(self):
        """비필수만 돌았다 — green처럼 보이지만 배송은 안 됐다."""
        assert classify(REQUIRED, {LONG_JOB: "success"}, mergeable_state="clean") == "NO_CHECKS"

    def test_empty_checks_is_no_checks_even_with_no_required(self):
        """필수 목록이 비어도 체크런 0건은 NO_CHECKS다 — 이 줄이 지키는 엣지.

        뮤테이션 O1(첫 가드 제거)이 최초 생존했다: required가 비어 있지 않으면
        아래 루프가 같은 결론을 내므로 첫 가드가 중복으로 보였다. 그러나 required가
        빈 경우(규칙 조회가 부분 실패한 상태 등) 가드가 없으면 **아무것도 안 돌았는데
        READY_UNMERGED**가 나온다 — 측정 실패를 '머지 준비 완료'로 위장하는 최악의 오판이다.
        """
        assert classify(set(), {}, mergeable_state="clean") == "NO_CHECKS"


class TestPriorityOrder:
    """순서가 곧 처방 우선순위 — 실패는 대기보다, 대기는 머지 상태보다 앞선다."""

    def test_failing_beats_pending(self):
        runs = {"policy-guard": "failure", "backend — 마이그레이션·통합 (실 PG)": None}
        assert classify(REQUIRED, runs, mergeable_state="clean") == "REQUIRED_FAILING"

    def test_pending_beats_behind(self):
        runs = {"policy-guard": "success", "backend — 마이그레이션·통합 (실 PG)": None}
        assert classify(REQUIRED, runs, mergeable_state="behind") == "REQUIRED_PENDING"

    def test_conflict_and_behind_are_distinct(self):
        runs = {n: "success" for n in REQUIRED}
        assert classify(REQUIRED, runs, mergeable_state="dirty") == "CONFLICT"
        assert classify(REQUIRED, runs, mergeable_state="behind") == "BEHIND"


class TestSkippedSatisfies:
    """doc-only PR에서 data-pipeline 잡은 skipped다 — 이걸 미충족으로 보면 전부 막힌다."""

    def test_skipped_required_is_ready(self):
        runs = {n: "skipped" for n in REQUIRED}
        assert classify(REQUIRED, runs, mergeable_state="clean") == "READY_UNMERGED"
