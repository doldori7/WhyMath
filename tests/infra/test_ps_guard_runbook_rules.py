"""런북 코드펜스 가드 — 규칙별 변별력 동결 (OPS-57).

**왜 이 테스트가 필요한가**: `check_ps_scripts.py`는 실행 검증이 구조적으로 불가능한
구간(Windows 전용 PowerShell)의 유일한 방어선이다. 그런 도구가 조용히 무력해지면
"검사가 없다"가 아니라 **"검사가 통과했다"로 위장**된다 — 이 저장소가 반복해서 당한
형태다(2026-07-17 logconfig `delay:true`로 캡처 파일 미생성 → 사전 `Test-Path`가 정상
상태에서도 항상 False).

그래서 규칙마다 **위반 샘플 exit 1 · 정상 샘플 exit 0** 양쪽을 고정한다. 한쪽만 보면
"항상 통과"·"항상 거부"가 그대로 통과한다.

사고 경위(2026-09-01 관여도 트리아지 게이트 clear 런북): 결함 7건 중 3건이 여기서
고정하는 형태였다. 라이브에서 2건(CP949·main 직접 push)이 터졌고 리뷰가 2건을 더
찾았다(§7-3의 두 번째 main push · `reset --hard` 청결 확인 부재).
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_GUARD = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ops" / "check_ps_scripts.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_ps_scripts", _GUARD)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load()


def _md(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    p = tmp_path / "runbook.md"
    p.write_text(body, encoding="utf-8")
    return p


def _fence(cmds: str) -> str:
    return f"# 런북\n\n```powershell\n{cmds}\n```\n"


class TestFenceExtraction:
    """① 코드펜스를 실제로 읽는가 — 이것이 0이면 아래 규칙 전부가 공허하게 통과한다."""

    def test_powershell_fence_is_found(self, tmp_path: pathlib.Path) -> None:
        blocks = guard.iter_powershell_blocks(_fence("Write-Host hi"))
        assert len(blocks) == 1
        assert "Write-Host hi" in blocks[0][1]

    def test_non_powershell_fence_is_ignored(self, tmp_path: pathlib.Path) -> None:
        """bash 펜스까지 PowerShell 규칙으로 재면 오탐이 쏟아진다."""
        assert guard.iter_powershell_blocks("```bash\ngit push origin main\n```") == []

    def test_document_without_fences_yields_nothing(self) -> None:
        assert guard.iter_powershell_blocks("# 제목\n\n본문뿐이다.\n") == []


class TestProtectedBranchPush:
    """④ `git push origin main`은 GH013으로 거부된다 — 절차의 마지막이 항상 실패한다."""

    def test_direct_main_push_is_rejected(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(_md(tmp_path, _fence("git push origin main")))
        assert any("보호 브랜치 직접 push" in i for i in issues)

    def test_branch_push_passes(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(
            _md(tmp_path, _fence("git push -u origin gates/relevance-triage-clear"))
        )
        assert issues == []

    def test_master_is_also_protected(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(_md(tmp_path, _fence("git push origin master")))
        assert any("보호 브랜치 직접 push" in i for i in issues)


class TestResetHardNeedsCleanCheck:
    """⑤ 미커밋 작업분을 무증상으로 지우는 형태 — 2026-08-10 사고 유형."""

    def test_bare_reset_hard_is_rejected(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(
            _md(tmp_path, _fence("git checkout main\ngit reset --hard origin/main"))
        )
        assert any("git status --porcelain" in i for i in issues)

    def test_preceding_clean_check_in_same_block_passes(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(
            _md(tmp_path, _fence("git status --porcelain\ngit reset --hard origin/main"))
        )
        assert issues == []

    def test_clean_check_in_earlier_block_passes(self, tmp_path: pathlib.Path) -> None:
        """런북은 블록을 나눠 사람에게 확인을 시킨다 — 문서 순서로 인정한다."""
        body = (
            _fence("git status --porcelain")
            + "\n확인 후:\n\n"
            + _fence("git reset --hard origin/main")
        )
        assert guard.check_runbook_markdown(_md(tmp_path, body)) == []

    def test_clean_check_after_the_reset_does_not_count(self, tmp_path: pathlib.Path) -> None:
        """순서가 뒤바뀌면 보호가 아니다 — 지운 뒤에 확인해 봐야 늦다."""
        body = _fence("git reset --hard origin/main") + "\n" + _fence("git status --porcelain")
        issues = guard.check_runbook_markdown(_md(tmp_path, body))
        assert any("git status --porcelain" in i for i in issues)


class TestPythonPipeNeedsUtf8:
    """⑥ 한국어 Windows에서 파이프 stdout은 cp949 — UnicodeEncodeError로 죽는다."""

    def test_piped_python_without_utf8_is_rejected(self, tmp_path: pathlib.Path) -> None:
        issues = guard.check_runbook_markdown(
            _md(tmp_path, _fence('python x.py | Select-String "foo"'))
        )
        assert any("UTF-8" in i for i in issues)

    def test_utf8_in_earlier_block_passes(self, tmp_path: pathlib.Path) -> None:
        body = _fence('$env:PYTHONUTF8="1"') + "\n" + _fence('python x.py | Select-String "foo"')
        assert guard.check_runbook_markdown(_md(tmp_path, body)) == []

    def test_console_output_encoding_also_counts(self, tmp_path: pathlib.Path) -> None:
        body = _fence(
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()\n"
            'python x.py | Select-String "foo"'
        )
        assert guard.check_runbook_markdown(_md(tmp_path, body)) == []

    def test_unpiped_python_needs_nothing(self, tmp_path: pathlib.Path) -> None:
        """콘솔로 바로 내보내면 이 결함이 나지 않는다 — 요구하면 변별력이 사라진다."""
        assert guard.check_runbook_markdown(_md(tmp_path, _fence("python x.py"))) == []

    def test_placeholder_angle_brackets_are_not_redirects(self, tmp_path: pathlib.Path) -> None:
        """실측 오탐(2026-09-01): `--until <종료YYYY-MM-DD> --next ...`를 리다이렉트로 오인.

        오탐이 있는 가드는 사람이 끄게 만든다 — 이 케이스는 반드시 통과해야 한다.
        """
        issues = guard.check_runbook_markdown(
            _md(tmp_path, _fence("python -m x --since <시작YYYY-MM-DD> --until <종료YYYY-MM-DD>"))
        )
        assert issues == []

    def test_real_redirect_is_still_caught(self, tmp_path: pathlib.Path) -> None:
        """오탐을 줄이느라 진짜 리다이렉트까지 놓치면 규칙이 죽는다."""
        issues = guard.check_runbook_markdown(_md(tmp_path, _fence("python x.py > out.txt")))
        assert any("UTF-8" in i for i in issues)


class TestRepositoryAssetsStayGreen:
    """기존 자산 전건이 새 규칙에서 green이어야 CI 차단으로 승격할 수 있다 (acceptance ③)."""

    def test_all_repo_targets_pass(self) -> None:
        root = _GUARD.resolve().parents[2]
        targets = sorted((root / "scripts").rglob("*.ps1")) + sorted((root / "docs").rglob("*.md"))
        offenders: dict[str, list[str]] = {}
        for t in targets:
            issues = (
                guard.check_runbook_markdown(t)
                if t.suffix.lower() == ".md"
                else guard.check_file(t)
            )
            if issues:
                offenders[str(t.relative_to(root))] = issues
        assert not offenders, f"기존 자산 위반: {offenders}"


class TestHistoricalIncidentIsCaught:
    """평가 — 이 가드가 **실제 사고를 잡았을 것인가**.

    2026-09-01 관여도 트리아지 런북의 결함을 재구성해 검출을 확인한다. 규칙이 사고를
    잡지 못하면 그 규칙은 사고와 무관한 것을 재고 있는 것이다.
    """

    def test_the_three_mechanical_defects_are_all_caught(self, tmp_path: pathlib.Path) -> None:
        body = (
            _fence('python scripts/harness/backlog.py gates list | Select-String "gate"')
            + "\n"
            + _fence('git add backlog/\ngit commit -m "clear"\ngit push origin main')
            + "\n"
            + _fence("git checkout main\ngit reset --hard origin/main")
        )
        issues = guard.check_runbook_markdown(_md(tmp_path, body))
        assert any("UTF-8" in i for i in issues), "CP949 결함 미검출"
        assert any("보호 브랜치 직접 push" in i for i in issues), "main 직접 push 미검출"
        assert any("git status --porcelain" in i for i in issues), "reset --hard 결함 미검출"

    @pytest.mark.parametrize("cmd", ["git push origin main", "git reset --hard origin/main"])
    def test_bash_fence_is_out_of_scope(self, tmp_path: pathlib.Path, cmd: str) -> None:
        """정직한 한계 — bash 펜스는 이 가드의 대상이 아니다(리눅스 세션이 직접 실행).

        이 테스트는 통과를 요구하는 것이 아니라 **범위를 명시적으로 고정**한다. 나중에
        bash까지 넓히기로 하면 이 테스트가 먼저 실패해 결정을 강제한다.
        """
        assert guard.check_runbook_markdown(_md(tmp_path, f"```bash\n{cmd}\n```\n")) == []
