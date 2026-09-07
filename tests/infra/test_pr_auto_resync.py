"""PR 자동 재동기화 (HARN-85) 계약 — 스크립트를 **실제로 실행해** 판정한다.

merge queue는 조직 소유 저장소 전용이라 이 저장소(owner.type=User)에서 쓸 수 없다.
그 대체가 `.github/scripts/pr_auto_resync.sh`이며, 이 파일은 그 스크립트가 *성공 경로뿐
아니라 실패 경로에서도* 설계대로 동작하는지를 동결한다.

왜 문자열 검사가 아니라 실행인가: 쉘 스크립트를 `"BEHIND" in text`로 검사하면 조건을
반대로 뒤집어도(`!=` → `=`) 통과한다 — 문자열은 그대로 남기 때문이다. CLAUDE.md
2026-09-01 ①("금지 패턴 열거 대신 산출물 검사")를 쉘에 적용하면 *구성된 결과*는
"이 입력에서 이 호출이 실제로 났는가"다. 그래서 `gh`를 스텁으로 갈아끼우고 돌린다.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "pr_auto_resync.sh"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "pr-auto-resync.yml"
_DOC = _REPO_ROOT / ".github" / "branch-protection-setup.md"

_STUB_GH = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if args[:2] == ["pr", "list"]:
    sys.stdout.write(os.environ.get("STUB_PR_JSON", "[]"))
    sys.exit(int(os.environ.get("STUB_LIST_RC", "0")))
if args[:1] == ["api"]:
    target = args[-1]
    with open(os.environ["STUB_CALLS"], "a", encoding="utf-8") as fh:
        fh.write(target + "\\n")
    sys.stderr.write(os.environ.get("STUB_UPDATE_BODY", ""))
    sys.exit(int(os.environ.get("STUB_UPDATE_RC", "0")))
sys.stderr.write("스텁이 모르는 gh 호출: %r\\n" % (args,))
sys.exit(90)
"""


def _pr(number: int, state: str = "BEHIND", automerge: bool = True) -> dict[str, Any]:
    return {
        "number": number,
        "headRefName": f"claude/branch-{number}",
        "mergeStateStatus": state,
        "autoMergeRequest": {"enabledAt": "2026-09-07T00:00:00Z"} if automerge else None,
    }


def _run(
    tmp_path: Path,
    prs: list[dict[str, Any]],
    *,
    list_rc: int = 0,
    update_rc: int = 0,
    update_body: str = "",
    dry_run: str = "0",
    raw_payload: str | None = None,
) -> tuple[int, str, list[str]]:
    """스텁 `gh`를 PATH 앞에 두고 스크립트를 실행한다. (exit code, 출력, update 호출 목록)"""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(_STUB_GH, encoding="utf-8")
    gh.chmod(0o755)

    calls = tmp_path / "calls.txt"
    calls.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env.update(
        PATH=f"{bindir}{os.pathsep}{env['PATH']}",
        REPO="doldori7/WhyMath",
        DRY_RUN=dry_run,
        STUB_PR_JSON=raw_payload if raw_payload is not None else json.dumps(prs),
        STUB_LIST_RC=str(list_rc),
        STUB_UPDATE_RC=str(update_rc),
        STUB_UPDATE_BODY=update_body,
        STUB_CALLS=str(calls),
    )
    proc = subprocess.run(
        ["bash", str(_SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )
    made = [line for line in calls.read_text(encoding="utf-8").splitlines() if line]
    return proc.returncode, proc.stdout + proc.stderr, made


# ---------------------------------------------------------------------------
# 계약 ① — 후보 선별이 정확한가 (정상 1건 + 주입 3건)
# ---------------------------------------------------------------------------


def test_behind_with_automerge_is_updated(tmp_path: Path) -> None:
    """기준선 — 이것이 초록이어야 아래 '건드리지 않는다'들이 의미를 갖는다."""
    rc, out, calls = _run(tmp_path, [_pr(101)])
    assert rc == 0, out
    assert calls == ["repos/doldori7/WhyMath/pulls/101/update-branch"], out


def test_behind_without_automerge_is_untouched(tmp_path: Path) -> None:
    """auto-merge를 켜지 않은 PR은 건드리지 않는다 — 리뷰 중인 diff를 임의로 전진시키지 않는다."""
    rc, out, calls = _run(tmp_path, [_pr(102, automerge=False)])
    assert rc == 0, out
    assert calls == [], f"auto-merge off인데 update-branch를 불렀다: {calls}"


@pytest.mark.parametrize("state", ["CLEAN", "BLOCKED", "DIRTY", "HAS_HOOKS"])
def test_non_behind_states_are_untouched(state: str, tmp_path: Path) -> None:
    """BEHIND가 아닌 상태는 재동기화 대상이 아니다 — 특히 DIRTY(충돌)는 사람 몫이다."""
    rc, out, calls = _run(tmp_path, [_pr(103, state=state)])
    assert rc == 0, out
    assert calls == [], f"{state}인데 update-branch를 불렀다: {calls}"


def test_unknown_merge_state_is_skipped_and_visible(tmp_path: Path) -> None:
    """모른다 ≠ 아니다 — GitHub이 아직 계산하지 않은 상태를 확정 신호로 접지 않는다.

    UNKNOWN을 '아니다'로 접으면 조용히 건너뛰어 아무도 모르고, 'BEHIND다'로 접으면
    멀쩡한 PR을 전진시킨다. 건너뛰되 **그 사실이 출력에 남아야** 한다.
    """
    rc, out, calls = _run(tmp_path, [_pr(104, state="UNKNOWN")])
    assert rc == 0, out
    assert calls == []
    assert "#104" in out and "미판정" in out, out


# ---------------------------------------------------------------------------
# 계약 ② — 실패 경로가 설계돼 있는가 (성공 경로만 보고 만들지 않았는가)
# ---------------------------------------------------------------------------


def test_conflict_409_is_visible_but_not_fatal(tmp_path: Path) -> None:
    """충돌은 자동 해소 대상이 아니라 건너뛰되, PR 번호와 응답 본문이 남아야 한다."""
    rc, out, calls = _run(
        tmp_path,
        [_pr(105), _pr(106)],
        update_rc=1,
        update_body="gh: merge conflict between base and head (HTTP 409)",
    )
    assert rc == 0, f"409는 잡 전체를 red로 만들지 않는다: {out}"
    assert len(calls) == 2, out
    assert "#105" in out and "409" in out, out
    assert "merge conflict between base and head" in out, "응답 본문이 로그에 없다"
    assert "충돌 2건" in out, out


def test_permission_403_is_fatal(tmp_path: Path) -> None:
    """권한 거부를 경고로 넘기면 자동화가 **상시 무력**인 채 초록으로 보인다.

    CLAUDE.md '상시 실패하는 fail-open 보호를 보호 있음으로 신뢰 금지'의 쓰기측 적용.
    """
    rc, out, _ = _run(
        tmp_path,
        [_pr(107)],
        update_rc=1,
        update_body="gh: Resource not accessible by integration (HTTP 403)",
    )
    assert rc == 1, f"403인데 잡이 초록으로 끝났다: {out}"
    assert "#107" in out and "403" in out, out


def test_unclassified_error_is_reported_with_body(tmp_path: Path) -> None:
    """분류되지 않은 실패도 조용히 사라지지 않는다 — 예외 타입만으론 8개 실패가 같아 보인다."""
    rc, out, _ = _run(tmp_path, [_pr(108)], update_rc=1, update_body="gh: something odd (HTTP 422)")
    assert rc == 0, out
    assert "#108" in out and "422" in out and "something odd" in out, out
    assert "기타실패 1건" in out, out


def test_list_failure_is_measurement_failure_not_zero_candidates(tmp_path: Path) -> None:
    """조회 실패가 '대상 0건 통과'로 위장되면 안 된다 — 인프라가 죽으면 그게 보여야 한다."""
    rc, out, calls = _run(tmp_path, [], list_rc=1)
    assert rc == 1, f"목록 조회 실패인데 초록으로 끝났다: {out}"
    assert calls == []
    assert "측정 실패" in out, out


def test_unparsable_payload_is_measurement_failure(tmp_path: Path) -> None:
    """gh가 exit 0으로 비-JSON을 뱉는 경우(로그인 안내 등)도 0건이 아니라 실패다."""
    rc, out, calls = _run(tmp_path, [], raw_payload="Welcome to GitHub CLI!")
    assert rc == 1, out
    assert calls == []
    assert "파싱 실패" in out, out


# ---------------------------------------------------------------------------
# 계약 ③ — 0건이 침묵이 아니라 값으로 보이는가 + dry-run
# ---------------------------------------------------------------------------


def test_summary_reports_denominator_even_when_nothing_to_do(tmp_path: Path) -> None:
    """스캔 0건 통과는 공허하다 — 분모를 내야 '대상이 없었다'와 '못 봤다'가 구분된다."""
    rc, out, calls = _run(tmp_path, [])
    assert rc == 0 and calls == []
    assert "스캔 0건" in out, out


def test_summary_counts_are_real_not_hardcoded(tmp_path: Path) -> None:
    """분모가 실제 입력을 따라 움직이는지 — 고정 문자열이면 이 단언에서 깨진다."""
    prs = [_pr(201), _pr(202), _pr(203, state="CLEAN"), _pr(204, automerge=False)]
    rc, out, calls = _run(tmp_path, prs)
    assert rc == 0
    assert "스캔 4건" in out, out
    assert "BEHIND+auto-merge 2건" in out, out
    assert "최신화 2건" in out, out
    assert len(calls) == 2


def test_dry_run_makes_no_write_call(tmp_path: Path) -> None:
    """DRY_RUN은 후보를 보여주되 쓰지 않는다 — 배선 확인을 안전하게 할 수 있어야 한다."""
    rc, out, calls = _run(tmp_path, [_pr(109)], dry_run="1")
    assert rc == 0, out
    assert calls == [], out
    assert "#109" in out and "DRY_RUN" in out, out


# ---------------------------------------------------------------------------
# 계약 ④ — 배선 (만들어 두고 아무도 안 돌리는 상태 차단)
# ---------------------------------------------------------------------------


def _workflow() -> dict[str, Any]:
    raw = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1에서 `on:`은 boolean True로 파싱된다.
    raw["on"] = raw.get("on", raw.get(True))
    return raw


def test_workflow_actually_invokes_the_script() -> None:
    """스크립트가 저장소에 존재하는 것과 워크플로가 그것을 부르는 것은 다르다."""
    steps = _workflow()["jobs"]["resync"]["steps"]
    runs = " ".join(str(s.get("run", "")) for s in steps)
    assert ".github/scripts/pr_auto_resync.sh" in runs, "워크플로가 스크립트를 부르지 않는다"


def test_workflow_has_both_triggers_and_write_permissions() -> None:
    wf = _workflow()
    assert "schedule" in wf["on"], "예약 트리거가 없으면 사람이 눌러야만 도는 자동화다"
    assert "workflow_dispatch" in wf["on"], "수동 트리거가 없으면 즉시 검증할 방법이 없다"
    perms = wf["permissions"]
    assert perms.get("contents") == "write", perms
    assert perms.get("pull-requests") == "write", perms


def test_script_is_executable_and_syntactically_valid() -> None:
    assert _SCRIPT.exists(), "스크립트 파일이 없다"
    proc = subprocess.run(["bash", "-n", str(_SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_doc_records_that_merge_queue_is_unavailable_here() -> None:
    """다음 세션이 merge queue를 다시 제안하지 못하게 **조건과 실측**이 문서에 박혀야 한다.

    제목만 검사하면 본문을 지워도 통과하므로 실측 근거(owner.type)까지 본다.
    """
    text = _DOC.read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert any("merge queue" in h for h in headings), f"미제공 사실을 적은 절이 없다: {headings}"
    assert "owner.type" in text and "User" in text, "실측 근거(계정 유형)가 문서에 없다"
    assert "조직" in text, "제공 조건(조직 소유 전용)이 문서에 없다"
