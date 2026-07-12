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
        result = subprocess.run(
            ["git", *argv], cwd=cwd, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    run("init", "-b", "main")
    run("config", "user.email", "test@whymath.local")
    run("config", "user.name", "harness-test")
    (tmp_path / "README.md").write_text("test repo\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-m", "init")
    return tmp_path
