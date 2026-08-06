"""HARN-14 — 설계 문서 중복 탐지 스캐너의 SessionStart 브리핑 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`scan_new_review_docs`(HARN-14)는 `cmd_brief`/`render_brief`에 배선됐지만, "저장소에
존재함"과 "돌아감"은 다르다(OPS-10 배선 실재성 패턴) — 함수가 옳게 동작해도 실제
SessionStart 진입점(`backlog.py brief --format hook`)이 그 함수를 정말 호출하고
결과를 출력에 반영하는지는 **별도로 증명**해야 한다. `tests/harness/test_remote_claims.py`
가 `scan_new_review_docs` 자체의 단위 동작(당일 커밋 감지·양방향 변별력·실패 비위장)을
검증하고, 이 파일은 그 함수가 실제 CLI 엔트리포인트를 통해 SessionStart 훅과 동일한
방식으로 호출됐을 때 stdout에 도달함을 검증한다.

검증 계약
--------
① `.claude/settings.json`의 SessionStart 훅이 여전히 `brief --format hook`를 호출한다
   (이 태스크가 훅 자체는 건드리지 않았음을 동결 — HARN-14 수용 기준 ④ 전제).
② 진짜 로컬 git 원격(합성 fixture)에서, 미머지 브랜치가 트렁크에 없는
   `docs/**/*_review.md`를 추가하면 훅과 **동일한 절대경로 호출 방식**
   (`python3 <repo>/scripts/harness/backlog.py brief`, cwd=관찰자 클론)으로 실행한
   결과 stdout에 그 사실이 나타난다.
③ 그런 문서가 없으면 그 블록 자체가 나타나지 않는다 — "찾은 게 없다"가 "고장났다"와
   같은 문자열이면 안 된다(변별력 없는 검증 금지, 2026-07-17 delay:true 선례).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS = _REPO_ROOT / ".claude" / "settings.json"
_BACKLOG_CLI = _REPO_ROOT / "scripts" / "harness" / "backlog.py"


def _run_git(*argv: str, cwd: Path) -> str:
    result = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _make_bare_remote_and_clones(tmp_path: Path) -> tuple[Path, Path]:
    """진짜 로컬 bare 원격 + 클론 2개(author·observer) — `tests/harness/conftest.py`의
    `bare_remote` 픽스처와 동형이나, `tests/infra`는 그 conftest를 상속하지 않아
    이 파일에 자족적으로 둔다(디렉터리 간 fixture 결합 회피)."""
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _run_git("init", "--bare", "-b", "main", cwd=bare)

    seed = tmp_path / "seed"
    _run_git("clone", str(bare), str(seed), cwd=tmp_path)
    _run_git("config", "user.email", "test@whymath.local", cwd=seed)
    _run_git("config", "user.name", "harness-test", cwd=seed)
    (seed / "README.md").write_text("test repo\n", encoding="utf-8")
    _run_git("add", ".", cwd=seed)
    _run_git("commit", "-m", "init", cwd=seed)
    _run_git("push", "origin", "main", cwd=seed)

    author = tmp_path / "author"
    _run_git("clone", str(bare), str(author), cwd=tmp_path)
    _run_git("config", "user.email", "test@whymath.local", cwd=author)
    _run_git("config", "user.name", "harness-test", cwd=author)
    _run_git("checkout", "-b", "claude/doc-series-x", cwd=author)

    observer = tmp_path / "observer"
    _run_git("clone", str(bare), str(observer), cwd=tmp_path)
    _run_git("config", "user.email", "test@whymath.local", cwd=observer)
    _run_git("config", "user.name", "harness-test", cwd=observer)

    return author, observer


def _run_brief(cwd: Path) -> str:
    """SessionStart 훅과 동일한 절대경로 호출 방식 — cwd만 관찰자 클론으로."""
    result = subprocess.run(
        ["python3", str(_BACKLOG_CLI), "brief", "--format", "hook"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout


def test_세션스타트_훅이_여전히_brief_hook을_호출한다() -> None:
    """수용 기준 ④ 전제 — 이 태스크는 훅 자체를 건드리지 않았음을 동결."""
    text = _SETTINGS.read_text(encoding="utf-8")
    assert "backlog.py" in text and "brief" in text and "--format hook" in text, (
        "SessionStart 훅이 'brief --format hook'을 호출하지 않는다 — "
        "HARN-14 스캐너가 배선돼도 실제로는 안 뜬다"
    )


def test_미머지_신규_리뷰문서가_brief_출력에_실제로_나타난다(tmp_path: Path) -> None:
    """진짜 CLI 호출(단위 함수 아님)로 배선 실재성을 증명 — 수용 기준 ④ 본체."""
    author, observer = _make_bare_remote_and_clones(tmp_path)

    doc_path = author / "docs" / "architecture" / "wiring_test_gap_review.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("wiring test\n", encoding="utf-8")
    _run_git("add", "docs/architecture/wiring_test_gap_review.md", cwd=author)
    _run_git("commit", "-m", "add gap review doc", cwd=author)
    _run_git("push", "-u", "origin", "claude/doc-series-x", cwd=author)

    stdout = _run_brief(observer)

    assert (
        "미머지 브랜치의 신규 설계 문서" in stdout
    ), f"HARN-14 스캐너가 실제 brief 출력에 안 나타났다(배선 누락 가능성) — stdout:\n{stdout}"
    assert "claude/doc-series-x" in stdout
    assert "wiring_test_gap_review.md" in stdout


def test_신규_리뷰문서가_없으면_블록_자체가_없다(tmp_path: Path) -> None:
    """변별력 검증 — '없음'과 '고장'이 같은 출력이면 안 된다(수용 기준 ③ 확장)."""
    _, observer = _make_bare_remote_and_clones(tmp_path)

    stdout = _run_brief(observer)

    assert "미머지 브랜치의 신규 설계 문서" not in stdout
    assert "조회 불가" not in stdout  # 정상 스캔(찾은 게 0건)이지 판정 불가가 아니다
