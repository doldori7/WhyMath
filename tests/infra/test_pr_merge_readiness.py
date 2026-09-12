"""HARN-32 ③ — 머지 가능 시점 판정의 계약 동결.

**왜**: 세션이 전체 CI(중앙값 28.6분)를 기다린 뒤 머지를 시도해 왔다. 브랜치 보호가
실제로 요구하는 것은 필수 체크 6종(중앙값 6.5분)뿐이고, 최장 잡
`backend — lint·type·test`는 필수 목록에 **없다**(2026-08-31 API 실측).
main이 40.7분마다 전진하므로 대기 시간이 곧 패배 확률이다 — 필수만 대기 16% vs
전체 대기 70%. 이 세션의 머지 시도 3회는 전부 후자로 실패했다.

이 파일이 동결하는 것 — **양방향**(HARN-32 acceptance ⑤):
  ① 필수가 green이면 비필수가 진행 중이어도 **머지 가능**으로 판정한다
     (이게 회수하는 22분이다 — 한 방향만 만들면 도구가 무의미해진다)
  ② 필수가 진행 중/실패면 **막는다**(비필수 green에 속지 않는다)
  ③ behind·dirty·미해결 스레드는 각각 별도 사유로 막는다 —
     strict_required_status_checks_policy=true·required_review_thread_resolution=true 실측
  ④ skipped는 필수를 **충족**한다(GitHub 규칙) — doc-only PR이 영원히 막히면 안 된다
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pr_merge_readiness",
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "pr_merge_readiness.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
# @dataclass가 cls.__module__로 sys.modules를 조회하므로 exec 전에 등록해야 한다
# (등록 없이 exec하면 AttributeError: 'NoneType' object has no attribute '__dict__')
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
decide = _mod.decide

REQUIRED = {"policy-guard", "backend — 마이그레이션·통합 (실 PG)", "infra/phaiakes9"}
LONG_JOB = "backend — lint·type·test"  # 필수 아님 — 이 도구의 요점


def _ok(**kw):
    base = dict(mergeable_state="clean", unresolved_threads=0)
    base.update(kw)
    return base


class TestRequiredOnlyGating:
    """① 필수만 본다 — 비필수 진행 중이어도 머지 가능."""

    def test_ready_while_long_nonrequired_job_still_running(self):
        runs = {name: "success" for name in REQUIRED}
        runs[LONG_JOB] = None  # 30분짜리 최장 잡이 아직 진행 중
        v = decide(REQUIRED, runs, **_ok())
        assert v.ready, "필수가 green인데 비필수 대기로 막혔다 — 22분을 그대로 버린다"

    def test_nonrequired_failure_does_not_block_but_is_surfaced(self):
        runs = {name: "success" for name in REQUIRED}
        runs[LONG_JOB] = "failure"
        v = decide(REQUIRED, runs, **_ok())
        assert v.ready, "비필수 실패가 머지를 막으면 안 된다(보호 규칙이 요구하지 않는다)"
        assert any("비필수" in r and LONG_JOB in r for r in v.reasons), "숨기지도 않아야 한다"


class TestRequiredBlocks:
    """② 변별력 대조 — 필수가 미충족이면 막는다."""

    def test_required_pending_blocks(self):
        runs = {name: "success" for name in REQUIRED}
        runs["policy-guard"] = None
        runs[LONG_JOB] = "success"
        v = decide(REQUIRED, runs, **_ok())
        assert not v.ready
        assert "policy-guard" in v.pending

    def test_required_failure_blocks(self):
        runs = {name: "success" for name in REQUIRED}
        runs["policy-guard"] = "failure"
        v = decide(REQUIRED, runs, **_ok())
        assert not v.ready
        assert "policy-guard" in v.failing

    def test_required_never_fired_blocks(self):
        """체크런 자체가 없는 필수 — 트리거 미발화(HARN-30)를 통과로 읽으면 안 된다."""
        runs = {LONG_JOB: "success"}
        v = decide(REQUIRED, runs, **_ok())
        assert not v.ready
        assert set(v.pending) == REQUIRED


class TestBranchAndThreadGates:
    """③ 실측된 보호 규칙 2종을 각각 별도 사유로 막는다."""

    def test_behind_blocks_with_strict_policy_reason(self):
        runs = {name: "success" for name in REQUIRED}
        v = decide(REQUIRED, runs, mergeable_state="behind", unresolved_threads=0)
        assert not v.ready
        assert any("strict policy" in r for r in v.reasons)

    def test_dirty_blocks(self):
        runs = {name: "success" for name in REQUIRED}
        v = decide(REQUIRED, runs, mergeable_state="dirty", unresolved_threads=0)
        assert not v.ready
        assert any("충돌" in r for r in v.reasons)

    def test_unresolved_threads_block(self):
        runs = {name: "success" for name in REQUIRED}
        v = decide(REQUIRED, runs, mergeable_state="clean", unresolved_threads=3)
        assert not v.ready
        assert any("스레드 3건" in r for r in v.reasons)


class TestSkippedSatisfies:
    """④ skipped는 충족 — doc-only PR이 영원히 막히면 안 된다."""

    def test_skipped_required_checks_are_satisfied(self):
        runs = {name: "skipped" for name in REQUIRED}
        v = decide(REQUIRED, runs, **_ok())
        assert (
            v.ready
        ), "doc-only PR에서 data-pipeline 잡은 skipped다 — 이걸 막으면 아무것도 못 머지한다"
