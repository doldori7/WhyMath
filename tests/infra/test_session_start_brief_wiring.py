"""[HARN-14] 설계 문서 중복 착수 스캔의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`remote_claims.scan_doc_series_duplicates`가 저장소에 존재하는 것과 SessionStart 훅이
실제로 그것을 브리핑에 태우는 것은 다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이
완료 선언 금지" — `test_qa_pipeline_wiring.py`(ARCH-21)·`test_test_suite_wiring.py`(OPS-10)
동형 선례). 이 테스트가 없으면 `.claude/settings.json`의 SessionStart 커맨드가 조용히
`--format hook`을 빠뜨리거나, `cmd_brief`가 스캐너 호출을 조용히 지워도 아무 신호가 나지 않는다.

검증 계약
--------
① `.claude/settings.json`의 SessionStart 훅 커맨드가 `backlog.py brief --format hook`을
   호출한다 — 이 정확한 커맨드가 훅이 실제로 실행하는 것이다(`2>/dev/null`이 stderr를
   버리므로, 실패 메시지는 반드시 이 커맨드의 stdout 안에 있어야 한다 — report.py 독스트링과
   동형 원칙).
② 그 정확한 커맨드(`python3 scripts/harness/backlog.py brief --format hook`)를 실제
   서브프로세스로 이 저장소에 대해 실행하면 성공하고, 브리핑 헤더가 나온다 — "저장소에
   존재함"이 아니라 "돌아감"을 증명한다(OPS-10 패턴).
③ `backlog.py`의 `cmd_brief`가 `remote_claims.scan_doc_series_duplicates`를 실제로 호출하고
   그 결과를 `report.render_brief`의 `doc_series_candidates`/`doc_series_status` 인자로
   전달한다 — 소스 레벨 콜그래프로 "죽은 코드가 아님"을 고정한다.
④ 파서가 위장하지 않는다 — 훅 설정을 못 찾으면 "위반 0 통과"가 아니라 **실패**.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS_PATH = _REPO_ROOT / ".claude" / "settings.json"
_BACKLOG_PY = _REPO_ROOT / "scripts" / "harness" / "backlog.py"
_EXPECTED_INVOCATION = 'backlog.py" brief --format hook'


def _load_settings() -> dict:
    if not _SETTINGS_PATH.is_file():
        raise AssertionError(f"{_SETTINGS_PATH} 이(가) 없다 — 훅 배선을 확인할 수 없다.")
    return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))


def _session_start_command() -> str:
    settings = _load_settings()
    hooks = settings.get("hooks", {})
    session_start = hooks.get("SessionStart") or []
    commands = [
        h.get("command", "")
        for group in session_start
        for h in (group.get("hooks") or [])
        if isinstance(h, dict)
    ]
    matching = [c for c in commands if _EXPECTED_INVOCATION in c]
    if not matching:
        raise AssertionError(
            f"SessionStart 훅에 `{_EXPECTED_INVOCATION}` 호출이 없다 — 브리핑이 조용히 "
            f"빠졌다(발견된 커맨드: {commands})."
        )
    return matching[0]


def test_session_start_hook_invokes_brief_format_hook() -> None:
    """① — 훅 설정이 정확한 커맨드를 호출한다."""
    command = _session_start_command()
    assert "brief --format hook" in command


def test_session_start_command_actually_runs_end_to_end() -> None:
    """② — ①에서 확인한 그 커맨드를 실제로 실행해 브리핑이 실제로 나오는지 확인한다.

    셸 문자열을 그대로 재실행하지 않는다(따옴표·`$CLAUDE_PROJECT_DIR`·`2>/dev/null` 폴백이
    셸 종속적이라 재현이 불안정해진다) — 대신 그 커맨드가 실제로 호출하는 서브커맨드
    (`brief --format hook`)를 이 저장소 루트에서 직접 실행해 **같은 진입점**이 살아있는지
    본다. 이것이 위장이 아닌 이유: `_EXPECTED_INVOCATION`이 이미 실제 커맨드 문자열의
    부분 문자열이므로, 여기서 실행하는 것은 그 문자열이 실제로 참조하는 스크립트·인자 그대로다.
    """
    _session_start_command()  # 선행 실패 시 여기서 먼저 죽는다(중복 실패 신호 방지)
    result = subprocess.run(
        [sys.executable, str(_BACKLOG_PY), "brief", "--format", "hook"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"`brief --format hook`이 실제로 실패했다(exit={result.returncode}) — "
        f"stderr: {result.stderr[:2000]}"
    )
    assert (
        "[빌드하네스 브리핑]" in result.stdout
    ), f"브리핑 헤더가 stdout에 없다 — stdout: {result.stdout[:2000]}"


def test_cmd_brief_calls_doc_series_scanner_and_forwards_to_render_brief() -> None:
    """③ — 소스 레벨 콜그래프: cmd_brief가 스캐너를 호출하고 render_brief로 결과를 넘긴다.

    죽은 코드 방지 — 함수가 정의만 되고 아무도 호출하지 않는 상태(OPS-03 tests/infra 199건
    선례)를 막는다. 함수 리네임에는 자연히 깨지므로 실명 그대로 검사한다.
    """
    source = _BACKLOG_PY.read_text(encoding="utf-8")
    assert (
        "def cmd_brief(" in source
    ), "backlog.py에 cmd_brief가 없다 — 파일이 개명됐다면 정정 필요."
    cmd_brief_body = source.split("def cmd_brief(", 1)[1]

    assert "scan_doc_series_duplicates(" in cmd_brief_body, (
        "cmd_brief가 remote_claims.scan_doc_series_duplicates를 호출하지 않는다 — "
        "스캐너가 존재해도 브리핑 경로에서 죽은 코드다."
    )
    assert "doc_series_candidates=doc_series_candidates" in cmd_brief_body, (
        "cmd_brief가 render_brief 호출에 doc_series_candidates를 전달하지 않는다 — "
        "스캔 결과가 계산되고도 렌더링에 도달하지 못한다."
    )
    assert "doc_series_status=doc_series_status" in cmd_brief_body, (
        "cmd_brief가 render_brief 호출에 doc_series_status를 전달하지 않는다 — "
        "스캔 실패가 이중 회계 없이 조용히 사라질 수 있다."
    )
