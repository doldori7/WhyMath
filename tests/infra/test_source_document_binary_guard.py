"""[LIC-07 ④] 저작권 위험 원본 문서 차단 가드의 **변별력** 동결.

왜 이 테스트가 있는가
--------------------
2026-08-08에 KICE 평가기준 개발 연구 보고서 원본 PDF 2건이 저장소에 들어왔고, 아무 신호도
나지 않았다(제거 경위: `docs/ops/kice_pdf_history_purge_runbook.md`). 그 가드를 만들었으니
이제 **가드가 막으려는 상태를 실제로 주입해 red를 확인**해야 "보호 있음"으로 칠 수 있다
(CLAUDE.md 2026-09-01 "보호 장치를 실패 주입 없이 '보호 있음'으로 선언 금지").

정상 입력에서 초록인 것은 보호의 증거가 아니다 — *모든* 입력에서 초록인 가드도 같은 화면을
낸다. 그래서 아래 모든 케이스가 **위반을 주입한 뒤 exit 1을 요구**한다.

검증 축(가드의 ⓪①②와 대응)
--------------------------
⓪ `.gitignore` 1차 방어선이 뚫리면 red — 규칙을 지워도 아무 신호가 없으면 방어선이 아니다.
① 차단 확장자(`.pdf`·`.hwp` …)가 추적되면 red.
② **확장자를 바꿔도** 매직 바이트로 잡는다 — `보고서.pdf` → `보고서.txt` 한 번으로 뚫리면
   금지 목록은 표기 변형에서 무력하다(CLAUDE.md "금지 패턴 열거 대신 산출물 검사").
③ 허용 목록은 *사유 있는 영구 예외*이지 구멍이 아니다 — 등재분은 통과하되, 실재하지 않는
   항목(죽은 예외)이 쌓이면 red.
④ **측정 실패는 통과가 아니다** — 전수 스캔이 성립하지 않으면 exit 2(0건 통과로 위장 금지).
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_GUARD = _REPO_ROOT / "scripts" / "ops" / "check_source_document_binaries.py"

_PDF_MAGIC = b"%PDF-1.7\n(KICE \xec\x97\xb0\xea\xb5\xac\xeb\xb3\xb4\xea\xb3\xa0\xec\x84\x9c)"


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("check_source_document_binaries", _GUARD)
    assert spec is not None and spec.loader is not None, f"가드 스크립트 부재: {_GUARD}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_repo(
    tmp_path: pathlib.Path, guard, monkeypatch, *, min_files: int | None = None
) -> pathlib.Path:
    """차단 규칙이 갖춰진 깨끗한 tmp 저장소.

    `main()`의 전수성 하한을 넘기려면 파일이 충분히 있어야 하므로 더미를 채운다 — 하한을
    테스트용으로 낮추는 seam을 두지 않는다(그 seam이 곧 가드를 약화시키는 통로가 된다).

    실 저장소용 `_ALLOWED`는 비운다. tmp 저장소엔 그 경로가 없어 **죽은 예외**로 잡히는데,
    그건 가드가 옳게 동작하는 것이지 이 테스트가 보려는 축이 아니다(허용 목록 축은
    `test_allowlisted_path_passes`가 따로 본다).
    """
    monkeypatch.setattr(guard, "_ALLOWED", {})
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")

    rules = "\n".join(f"*{suffix}" for suffix in sorted(guard.BLOCKED_SUFFIXES))
    (repo / ".gitignore").write_text(rules + "\n", encoding="utf-8")

    count = guard._MIN_TRACKED_FILES + 5 if min_files is None else min_files
    filler = repo / "filler"
    filler.mkdir()
    for i in range(count):
        (filler / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _run(guard, repo: pathlib.Path) -> int:
    return guard.main(["check", str(repo)])


# ──────────────────────────────────────────────────────────────────────
# 기준선 — 깨끗한 상태는 통과해야 한다(아래 red들이 의미를 가지려면)
# ──────────────────────────────────────────────────────────────────────


def test_clean_repo_passes(guard, tmp_path, monkeypatch) -> None:
    assert _run(guard, _make_repo(tmp_path, guard, monkeypatch)) == guard.EXIT_OK


def test_real_repository_passes(guard) -> None:
    """실 저장소가 통과한다 — 이 계약이 깨지면 원본 문서가 들어온 것이다."""
    assert guard.main(["check", str(_REPO_ROOT)]) == guard.EXIT_OK


# ──────────────────────────────────────────────────────────────────────
# ① 확장자 축 — 위반 주입
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "docs/(고등학교)2015 개정 교육과정에 따른 평가기준 개발 연구(수학과).pdf",  # 실제 사고 파일명
        "docs/평가기준.hwp",
        "docs/자료.docx",
        "docs/모음.zip",
    ],
)
def test_blocked_suffix_is_red(guard, tmp_path, monkeypatch, name: str) -> None:
    repo = _make_repo(tmp_path, guard, monkeypatch)
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_PDF_MAGIC)
    _git(repo, "add", "-f", name)  # .gitignore를 뚫고 들어온 상황을 재현
    assert _run(guard, repo) == guard.EXIT_VIOLATION, f"{name}을 잡지 못했다"


# ──────────────────────────────────────────────────────────────────────
# ② 매직 바이트 축 — 확장자 위장
# ──────────────────────────────────────────────────────────────────────


def test_renamed_pdf_is_caught_by_magic(guard, tmp_path, monkeypatch) -> None:
    """확장자만 바꾼 PDF — 금지 확장자 목록만 있으면 여기서 뚫린다."""
    repo = _make_repo(tmp_path, guard, monkeypatch)
    disguised = repo / "docs" / "innocuous_notes.txt"
    disguised.parent.mkdir(parents=True, exist_ok=True)
    disguised.write_bytes(_PDF_MAGIC)
    _git(repo, "add", "-A")
    assert _run(guard, repo) == guard.EXIT_VIOLATION

    # 대칭 — 진짜 텍스트는 통과해야 한다(모든 .txt를 잡는 가드가 아니라는 증명)
    disguised.write_text("보통의 메모\n", encoding="utf-8")
    _git(repo, "add", "-A")
    assert _run(guard, repo) == guard.EXIT_OK


def test_renamed_office_zip_is_caught_by_magic(guard, tmp_path, monkeypatch) -> None:
    repo = _make_repo(tmp_path, guard, monkeypatch)
    disguised = repo / "docs" / "data.json"
    disguised.parent.mkdir(parents=True, exist_ok=True)
    disguised.write_bytes(b"PK\x03\x04rest-of-an-xlsx")
    _git(repo, "add", "-A")
    assert _run(guard, repo) == guard.EXIT_VIOLATION


# ──────────────────────────────────────────────────────────────────────
# ③ 허용 목록 — 예외이되 구멍이 아니다
# ──────────────────────────────────────────────────────────────────────


def test_allowlisted_path_passes(guard, tmp_path, monkeypatch) -> None:
    repo = _make_repo(tmp_path, guard, monkeypatch)
    name = "docs/self_authored.xlsx"
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PK\x03\x04" + "자체작성".encode("utf-8"))
    _git(repo, "add", "-f", name)

    monkeypatch.setattr(guard, "_ALLOWED", {name: "자체작성 — 제3자 저작물 아님"})
    assert _run(guard, repo) == guard.EXIT_OK

    # 같은 파일이 허용 목록에서 빠지면 즉시 red — 통과가 목록 덕임을 증명한다
    monkeypatch.setattr(guard, "_ALLOWED", {})
    assert _run(guard, repo) == guard.EXIT_VIOLATION


def test_dead_allowance_is_red(guard, tmp_path, monkeypatch) -> None:
    """실재하지 않는 예외가 남아 있으면 red — 예외가 조용히 쌓이는 것을 막는다."""
    repo = _make_repo(tmp_path, guard, monkeypatch)
    monkeypatch.setattr(guard, "_ALLOWED", {"docs/사라진파일.pdf": "옛 예외"})
    assert _run(guard, repo) == guard.EXIT_VIOLATION


# ──────────────────────────────────────────────────────────────────────
# ⓪ .gitignore 1차 방어선
# ──────────────────────────────────────────────────────────────────────


def test_missing_gitignore_rule_is_red(guard, tmp_path, monkeypatch) -> None:
    """규칙을 지우면 red — 지워도 조용하면 그건 방어선이 아니다."""
    repo = _make_repo(tmp_path, guard, monkeypatch)
    rules = [
        line
        for line in (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line != "*.pdf"
    ]
    (repo / ".gitignore").write_text("\n".join(rules) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    assert _run(guard, repo) == guard.EXIT_VIOLATION


def test_real_gitignore_covers_every_blocked_suffix(guard) -> None:
    """실 저장소의 1차 방어선이 차단 확장자를 전부 덮는다."""
    assert guard.find_unignored_suffixes(_REPO_ROOT) == []


# ──────────────────────────────────────────────────────────────────────
# ④ 측정 실패 ≠ 통과
# ──────────────────────────────────────────────────────────────────────


def test_thin_inventory_is_measurement_failure_not_pass(guard, tmp_path, monkeypatch) -> None:
    """전수 스캔이 성립하지 않으면 exit 2 — '0건 통과'로 위장하지 않는다."""
    repo = _make_repo(tmp_path, guard, monkeypatch, min_files=3)
    assert _run(guard, repo) == guard.EXIT_MEASUREMENT_FAILURE


def test_non_git_directory_is_measurement_failure(guard, tmp_path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert guard.main(["check", str(plain)]) == guard.EXIT_MEASUREMENT_FAILURE
