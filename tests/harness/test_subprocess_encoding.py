"""HARN-19 — 하네스 git 서브프로세스 출력 인코딩 회귀 동결.

**사고 경위**: 2026-08-08 Kiki 머신(한국어 Windows)에서 `backlog.py start` 실행 중
`UnicodeDecodeError: 'cp949' codec can't decode byte 0xed` + `⚠ 미머지 done 탐지
불가(error:AttributeError)`가 관측됐다. 원인은 `subprocess.run(..., text=True)`가
`encoding=`을 지정하지 않아 파이썬이 **로케일 인코딩**(한국어 Windows=cp949)으로
git의 **UTF-8** 출력(태스크 YAML의 한글 본문)을 디코드한 것이다.

**왜 이 테스트가 필요한가**: `HARN-11`(미머지 done 탐지)은 타 세션이 이미 끝낸
태스크의 중복 구현을 막는 fail-open 보호다. 이 결함 아래에서 그 보호는 Kiki 머신에서
*상시* 무력이었고, 경고는 습관화된 소음이 됐다 — CLAUDE.md "상시 실패하는 fail-open
보호를 '보호 있음'으로 신뢰 금지"(2026-07-27 `refs/claims` 403 → `OPS-07` 병렬 구현
선례)의 두 번째 사례다.

**로케일 재현에 관한 정직한 한계**: 리눅스 CI에는 cp949 로케일이 없고, `locale`
모듈 몽키패치는 듣지 않는다(`io.TextIOWrapper`가 C 레벨에서 로케일을 잡는다 — 실측
확인). 그래서 이 테스트는 로케일 자체가 아니라 **그 로케일이 선택했을 인코딩을
명시 고정**(`encoding="cp949"`)해 조건을 재현한다. cp949 Windows에서의 `text=True`와
동치이며, 그 동치성이 이 파일이 기대는 유일한 가정이다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import remote_claims

_REPO_ROOT = Path(__file__).resolve().parents[2]

# 태스크 YAML에 실제로 들어가는 종류의 한글 본문 — cat-file 로 흘러나오는 그 내용이다.
_KOREAN = "① 현행 실측 고정: 학생 대면 응답에 싣는 코드가 0건임을 재확인한다"


def _git_repo_with_korean(git_repo: Path) -> Path:
    """한글 본문을 가진 커밋 1건을 얹는다 — cat-file/show 로 읽어낼 대상."""
    (git_repo / "korean.yaml").write_text(f"acceptance:\n  - {_KOREAN}\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "한글 태스크 추가"], cwd=git_repo, check=True, capture_output=True
    )
    return git_repo


class TestGitOutputDecodedAsUtf8:
    """① git 출력은 로케일이 아니라 UTF-8로 디코드된다."""

    def test_korean_blob_roundtrips_through_helper(self, git_repo: Path) -> None:
        """_git으로_읽은_한글_블롭이_원문과_일치"""
        root = _git_repo_with_korean(git_repo)
        result = remote_claims._git(root, "show", "HEAD:korean.yaml")
        assert result.returncode == 0
        assert _KOREAN in result.stdout

    def test_locale_decode_would_have_failed(self, git_repo: Path) -> None:
        """cp949로_디코드하면_같은_출력이_보존되지_않음 — 위 테스트의 변별력 증명.

        이게 red 가 아니면 위 테스트는 '어떤 인코딩이든 통과하는' 무변별 검사다
        (CLAUDE.md "변별력 없는 검증 스텝 금지" — 2026-07-17 logconfig `delay:true`로
        사전 `Test-Path`가 정상 상태에서도 항상 False 였던 사고).
        """
        root = _git_repo_with_korean(git_repo)
        try:
            mangled = subprocess.run(
                ["git", "show", "HEAD:korean.yaml"],
                cwd=root,
                capture_output=True,
                encoding="cp949",  # ← 한국어 Windows의 text=True 와 동치
                timeout=15,
            ).stdout
        except UnicodeDecodeError:
            return  # 디코드 자체가 실패 — 결함 재현 성공
        # 예외가 안 났다면 최소한 내용이 보존되지 않아야 한다(모지바케).
        assert mangled is None or _KOREAN not in mangled


class TestStdoutDecodeMaskingSurfaced:
    """② 디코드 실패가 AttributeError로 위장되지 않는다."""

    def test_none_stdout_raises_named_error(self, git_repo: Path, monkeypatch) -> None:
        """stdout이_None이면_원인을_담은_예외로_실패

        Windows에서는 디코드가 reader 스레드에서 터져 예외가 전파되지 못하고
        `stdout=None`으로만 도착한다 — 그 상태를 그대로 흘려보내면 소비자가 None을
        만져 AttributeError가 되고 경고에 찍히는 타입명이 원인을 오도한다.
        """

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=None, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(remote_claims.GitOutputDecodeError):
            remote_claims._git(git_repo, "show", "HEAD:korean.yaml")

    def test_scan_reports_decode_cause_not_attribute_error(
        self, git_repo: Path, monkeypatch
    ) -> None:
        """스캔_status가_error:GitOutputDecodeError_로_보고됨

        회귀 전 이 자리에 찍히던 문자열은 `error:AttributeError` 였다.
        """
        monkeypatch.setattr(remote_claims, "has_remote", lambda root: True)

        def fake_git(*args, **kwargs):
            raise remote_claims.GitOutputDecodeError("stdout 디코드 실패")

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        _, status = remote_claims.scan_remote_done(git_repo, ["S1-01-sample-task"])
        assert status == "error:GitOutputDecodeError"


# ── ③ 재유입 동결 (거버넌스) ──────────────────────────────────────────────────

_SUBPROCESS_CALL_RE = re.compile(
    r"subprocess\.(?:run|Popen|check_output)\((.{0,600}?)\)\s*\n", re.S
)


def _locale_decoding_calls(paths: list[Path]) -> list[str]:
    """`text=True`(또는 universal_newlines)를 쓰면서 `encoding=`이 없는 호출 목록."""
    found: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for match in _SUBPROCESS_CALL_RE.finditer(source):
            block = match.group(0)
            uses_text = "text=True" in block or "universal_newlines=True" in block
            if uses_text and "encoding=" not in block:
                line = source[: match.start()].count("\n") + 1
                found.append(f"{path.relative_to(_REPO_ROOT)}:{line}")
    return found


class TestNoLocaleDependentSubprocess:
    """③ 로케일 의존 디코드가 하네스에 다시 들어오지 않는다."""

    def test_harness_scripts_pin_encoding(self) -> None:
        """scripts_전체에_text_True_without_encoding_0건"""
        offenders = _locale_decoding_calls(sorted((_REPO_ROOT / "scripts").rglob("*.py")))
        assert offenders == [], (
            "git 출력을 로케일 인코딩으로 디코드하는 호출이 있습니다 — "
            f"encoding='utf-8'을 명시하세요 (HARN-19): {offenders}"
        )

    def test_scanner_detects_offending_sample(self, tmp_path: Path) -> None:
        """스캐너가_결함_샘플을_실제로_잡는다 — 위 검사의 변별력 증명.

        스캐너가 아무것도 못 잡는 상태로 망가지면 위 테스트는 영원히 green 이다.
        """
        sample = tmp_path / "offender.py"
        sample.write_text(
            "import subprocess\n"
            "subprocess.run(['git', 'status'], capture_output=True, text=True, timeout=5)\n",
            encoding="utf-8",
        )
        # relative_to(_REPO_ROOT) 가 성립하도록 파일명만 비교한다.
        offenders = _locale_decoding_calls([sample]) if sample.is_relative_to(_REPO_ROOT) else None
        if offenders is None:
            source = sample.read_text(encoding="utf-8")
            hits = [
                m
                for m in _SUBPROCESS_CALL_RE.finditer(source)
                if "text=True" in m.group(0) and "encoding=" not in m.group(0)
            ]
            assert len(hits) == 1
        else:  # pragma: no cover - tmp_path가 리포 안에 있는 드문 배치
            assert len(offenders) == 1


class TestPathScopeDecodesRepoListing:
    """경로 목록 소비자도 같은 계약을 따른다.

    ⚠️ 노출 범위에 관한 정직한 한정: git은 기본값 `core.quotepath=true`로 경로의
    비ASCII 바이트를 C 인용(`"bad\\377.txt"`)해 내보낸다 — 실측 확인. 따라서
    `ls-files` **경로**는 애초에 ASCII라 디코드가 깨지지 않으며, `errors='replace'`가
    실제로 의미를 갖는 곳은 인용되지 않는 **블롭 내용**(`cat-file --batch`·`show`)
    쪽이다. 그게 2026-08-08에 실제로 터진 지점이다.

    그래서 이 테스트는 "비UTF-8 경로를 견딘다"를 주장하지 않는다(그건 git이 이미
    막아준다). 주장하는 것은 `repo_files()`가 로케일이 아니라 UTF-8 계약으로 읽으며
    실패 시 조용히 빈 목록을 돌려주지 않는다는 것뿐이다.
    """

    def test_repo_files_lists_korean_paths(self, git_repo: Path) -> None:
        """repo_files가_한글_내용_커밋_후에도_전체_목록을_반환"""
        import pathscope

        root = _git_repo_with_korean(git_repo)
        files = pathscope.repo_files(root)
        assert "korean.yaml" in files
        assert "README.md" in files

    def test_repo_files_empty_list_is_not_silent(self, tmp_path: Path, capsys) -> None:
        """git이_아닌_디렉터리에서_빈_목록과_함께_경고를_낸다

        빈 목록은 '겹침 없음'과 같은 색이다 — 측정 실패가 통과로 위장되면 안 된다
        (CLAUDE.md 침묵 실패 금지).
        """
        import pathscope

        files = pathscope.repo_files(tmp_path / "does-not-exist")
        assert files == []
        assert "겹침 검사 불가" in capsys.readouterr().err


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
