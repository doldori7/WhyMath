"""HARN-02 — 실행 표면이 저장소를 **스스로 말하게** 한다 (조직 이관 회귀 가드).

**왜**: 2026-09-09 저장소가 `doldori7/WhyMath`에서 `kiki-s-broom/WhyMath`(조직)로
이관됐다. repo id는 그대로이므로 git은 리다이렉트를 투명 처리하지만 **REST는 301을
낸다**. 그런데 `pr_delivery_audit.py`를 부르는 워크플로가 옛 owner를 리터럴로 넘기고
도구의 curl에 `-L`이 없어, 301 본문(딕셔너리)이 규칙 배열로 파싱되며 필수 체크가
조용히 공집합이 됐다 — harness-audit run 34425627951(2026-09-10T01:28Z)이 그 경로로
red였다. fail-closed 설계 덕에 "이상 없음"으로 위장되지는 않았으나, **관측 좌석이
상시 실패 상태**가 되면 경고가 습관화돼 소음이 된다(CLAUDE.md 2026-07-27 금기).

**무엇을 동결하는가** — 세 축을 따로 잡는다. 하나로 뭉치면 어느 절이 깨졌는지 모른다.
  ① 실행 표면(워크플로·스크립트)에 옛 owner 리터럴이 없다 — 스캔 0건이면 **실패**다
     (대상을 못 찾은 전수 가드는 공허하게 통과한다 · CLAUDE.md 2026-09-01 ④).
  ② harness-audit가 저장소를 환경에서 받는다 — 새 owner 이름을 적어 넣는 것은 같은
     사고를 한 번 더 예약하는 것이므로, 리터럴이 아니라 자기서술이어야 한다.
  ③ 도구가 리다이렉트를 따르고, 실패했을 때 *원인*이 남는다 — 이동(301)·권한(403)·
     진짜 0건(200)이 같은 문구로 보이면 다음 세션이 헛다리를 짚는다.

③은 소스 문자열이 아니라 **실제로 구성된 curl 인자 목록**과 **실행 결과**로 확인한다
(금지 패턴 열거 대신 산출물 검사 · CLAUDE.md 2026-09-01 ①).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "pr_delivery_audit_canon",
    _ROOT / "scripts" / "ops" / "pr_delivery_audit.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

# 이관 전 owner. 실행 표면에 이 문자열이 남아 있으면 그 경로는 옛 저장소를 가리킨다.
_STALE_OWNER = "doldori7"

# 이력 기록(MEMORY.md·backlog·docs/reviews)은 **일부러 제외한다** — 과거 사실의
# 기록이라 현재로 덮어쓰면 판정 시점이 사라진다. 스캔 대상은 "지금 실행되는 것"뿐이다.
_SCAN_GLOBS = (
    # `*.yaml`은 **일부러 넣지 않는다** — 이 저장소의 워크플로는 전부 `.yml`이고,
    # 매치 0건인 글롭을 목록에 두면 아래 글롭별 단언이 상시 red가 된다. 확장자가
    # 늘면 그때 글롭을 추가한다(없는 표면을 미리 선언해 두지 않는다).
    ".github/workflows/*.yml",
    ".github/scripts/*.sh",
    "scripts/ops/*.py",
    "scripts/harness/*.py",
)


def _scan_targets() -> list[Path]:
    found: list[Path] = []
    for pattern in _SCAN_GLOBS:
        found.extend(sorted(_ROOT.glob(pattern)))
    return found


class TestNoStaleOwnerInExecutionSurface:
    """① 실행 표면 전수 — 스캔 0건은 통과가 아니라 실패다."""

    def test_every_glob_actually_matches_something(self):
        # **글롭마다** 확인한다 — 합계만 보면 한 글롭이 0건이 돼도 나머지가 수를 채워
        # 통과한다(실측: 합계 단언만 뒀을 때 워크플로 글롭을 죽인 뮤테이션이 생존했다).
        empty = [g for g in _SCAN_GLOBS if not list(_ROOT.glob(g))]
        assert not empty, f"매치 0건인 스캔 글롭 — 그 표면은 검사되지 않는다: {empty}"

    def test_scan_actually_finds_files(self):
        targets = _scan_targets()
        # 글롭이 어긋나 0건이 되면 아래 전수 검사가 공허하게 통과한다.
        assert len(targets) >= 10, f"스캔 대상이 {len(targets)}건 — 글롭이 어긋났다"

    def test_no_stale_owner_literal(self):
        offenders: list[str] = []
        for path in _scan_targets():
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                if _STALE_OWNER in line:
                    offenders.append(f"{path.relative_to(_ROOT)}:{lineno}: {line.strip()[:100]}")
        assert not offenders, (
            "실행 표면이 이관 전 owner를 가리킨다 — 새 이름을 적어 넣지 말고 자기서술로 바꿔라:\n"
            '  · 워크플로 → "$GITHUB_REPOSITORY"\n'
            "  · gh 런북 문자열 → repos/{owner}/{repo}/... (gh가 현재 저장소로 치환한다)\n"
            + "\n".join(offenders)
        )


class TestHarnessAuditPassesRepoFromEnvironment:
    """② 워크플로가 저장소를 리터럴이 아니라 환경에서 받는다."""

    def _run_block(self) -> str:
        return (_ROOT / ".github" / "workflows" / "harness-audit.yml").read_text(encoding="utf-8")

    def test_audit_invocation_uses_environment(self):
        text = self._run_block()
        invocations = [ln for ln in text.splitlines() if "pr_delivery_audit.py" in ln]
        assert invocations, "harness-audit가 pr_delivery_audit.py를 부르지 않는다 — 배선이 사라졌다"
        for line in invocations:
            assert "$GITHUB_REPOSITORY" in line, f"저장소가 자기서술이 아니다: {line.strip()}"


class TestRedirectHandling:
    """③ 도구가 이동을 따라가고, 실패 원인을 남긴다."""

    def test_curl_argv_follows_redirects(self, monkeypatch):
        seen: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="[]<<<HTTP:200>>>", stderr="")

        monkeypatch.setattr(_mod.subprocess, "run", fake_run)
        status, body = _mod._get("/repos/o/r/rules/branches/main")
        assert status == 200 and body == []
        # 소스에 '-L'이 적혀 있는지가 아니라 **실제로 넘어간 인자**를 본다.
        assert "-L" in seen[0], f"curl이 리다이렉트를 따르지 않는다: {seen[0]}"

    def test_status_marker_missing_reads_as_unknown_not_success(self):
        body, status = _mod._split_status('{"a": 1}')
        # 모른다(0) ≠ 200. 3상태를 2상태로 접으면 모르는 것으로 확정 신호를 낸다.
        assert status == 0 and body == '{"a": 1}'

    def test_moved_response_names_the_cause(self, monkeypatch):
        moved = json.dumps({"message": "Moved Permanently", "status": "301"})

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{moved}<<<HTTP:301>>>", stderr="")

        monkeypatch.setattr(_mod.subprocess, "run", fake_run)
        monkeypatch.setattr(sys, "argv", ["pr_delivery_audit.py", "doldori7/WhyMath"])
        with pytest.raises(SystemExit) as exc:
            _mod.main()
        msg = str(exc.value)
        assert "301" in msg, f"HTTP 상태가 보고되지 않는다: {msg}"
        assert "doldori7/WhyMath" in msg, f"어느 저장소를 물었는지가 없다: {msg}"
        assert "목록이 아니다" in msg, f"'0건'으로 뭉갰다: {msg}"

    def test_readable_rules_with_zero_required_is_a_different_message(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="[]<<<HTTP:200>>>", stderr="")

        monkeypatch.setattr(_mod.subprocess, "run", fake_run)
        monkeypatch.setattr(sys, "argv", ["pr_delivery_audit.py", "kiki-s-broom/WhyMath"])
        with pytest.raises(SystemExit) as exc:
            _mod.main()
        msg = str(exc.value)
        # 읽히긴 했는데 0건인 상태 — 이동/권한과 **구분돼야** 한다.
        assert "읽혔으나" in msg and "200" in msg, msg
        assert "목록이 아니다" not in msg, msg
