"""빌드 하네스 테스트 공용 픽스처.

scripts/harness 는 루트 파이썬 패키지가 아니므로(의존성 0 단독 실행 설계)
sys.path 에 직접 추가해 임포트한다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_HARNESS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "harness"
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """빈 git 저장소 (main 브랜치 + 최초 커밋) — check-stop·CLI 테스트용."""

    def run(*argv: str, cwd: Path = tmp_path) -> str:
        result = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    run("init", "-b", "main")
    run("config", "user.email", "test@whymath.local")
    run("config", "user.name", "harness-test")
    (tmp_path / "README.md").write_text("test repo\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-m", "init")
    return tmp_path


def _run_git(*argv: str, cwd: Path) -> str:
    result = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def bare_remote(tmp_path: Path):
    """진짜 로컬 원격(bare) + 클론 생성 헬퍼 — 원격 claim 레이스 재현용.

    반환: (bare 경로, clone(name) 함수). 각 클론은 독립 세션(worktree)을 모사한다.
    """
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _run_git("init", "--bare", "-b", "main", cwd=bare)

    # 최초 커밋을 가진 시드 클론으로 main을 채운다
    seed = tmp_path / "seed"
    _run_git("clone", str(bare), str(seed), cwd=tmp_path)
    _run_git("config", "user.email", "test@whymath.local", cwd=seed)
    _run_git("config", "user.name", "harness-test", cwd=seed)
    (seed / "README.md").write_text("test repo\n", encoding="utf-8")
    _run_git("add", ".", cwd=seed)
    _run_git("commit", "-m", "init", cwd=seed)
    _run_git("push", "origin", "main", cwd=seed)

    def clone(name: str) -> Path:
        """독립 세션 모사 클론 — 브랜치 claude/<name>으로 체크아웃."""
        path = tmp_path / name
        _run_git("clone", str(bare), str(path), cwd=tmp_path)
        _run_git("config", "user.email", "test@whymath.local", cwd=path)
        _run_git("config", "user.name", "harness-test", cwd=path)
        _run_git("checkout", "-b", f"claude/{name}", cwd=path)
        return path

    return bare, clone


@pytest.fixture
def shallow_clone(bare_remote, tmp_path: Path):
    """shallow 클론 생성 헬퍼 — 트렁크 히스토리가 잘린 상태 재현(2026-08-11 사고).

    ⚠ **로컬 *경로* 클론은 git이 `--depth`를 무시한다**(`warning: --depth is ignored in
    local clones` — hardlink 클론이 만들어진다). 반드시 `file://` URL을 써야 한다.

    픽스처가 스스로 `--is-shallow-repository == true`를 assert하는 이유: 조용히
    non-shallow가 만들어지면 이 축의 테스트가 전부 *공허하게 통과*한다 — 정확히 이
    수정이 고치려는 결함(측정 실패와 통과가 같은 색)의 재발이다.
    """
    bare, _clone = bare_remote

    def make(name: str = "shallow-session", depth: int = 1) -> Path:
        path = tmp_path / name
        _run_git("clone", "--depth", str(depth), f"file://{bare}", str(path), cwd=tmp_path)
        _run_git("config", "user.email", "test@whymath.local", cwd=path)
        _run_git("config", "user.name", "harness-test", cwd=path)
        assert (
            _run_git("rev-parse", "--is-shallow-repository", cwd=path) == "true"
        ), "픽스처가 shallow 클론을 만들지 못했다 — file:// URL 없이는 --depth가 무시된다"
        return path

    return make
