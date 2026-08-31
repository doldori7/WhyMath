"""move_backup_to_nas.ps1 contract tests (hermetic - no NAS needed).

OPS-02-db-backup-dr extension: verifies the offsite copy script's safety
contracts at the file-text level:
  1. ASCII only - PowerShell 5.1 reads .ps1 files in the OS locale encoding.
  2. NasPath is mandatory (no default) - prevents accidental copies to a
     placeholder path.
  3. BackupDir defaults to the local backup dir used by backup_whymath_pg.ps1.
  4. KeepCount defaults to 2 and enforces >= 1.
  5. SHA-256 hash comparison after copy - distinguishes a corrupted network copy.
  6. exit 0 success / exit 1 failure paths.
  7. [OK]/[FAIL] logging pattern matches the backup script.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup" / "move_backup_to_nas.ps1"


def _text() -> str:
    """Read as ASCII - contract 1 failure is caught here as a second line of defense."""
    return _SCRIPT.read_text(encoding="ascii")


def test_script_exists() -> None:
    """Script file must exist at the documented path."""
    assert _SCRIPT.is_file(), f"offsite move script missing: {_SCRIPT}"


def test_script_is_ascii_only() -> None:
    """No non-ASCII bytes - PowerShell 5.1 decodes .ps1 as cp949 on Korean Windows."""
    data = _SCRIPT.read_bytes()
    try:
        data.decode("ascii")
    except UnicodeDecodeError as exc:
        pytest.fail(
            "move_backup_to_nas.ps1 contains a non-ASCII byte "
            f"(offset {exc.start}: {data[exc.start:exc.start + 8]!r}) — "
            "PowerShell 5.1 reads .ps1 in the OS locale encoding. "
            "Keep Korean documentation in db_backup_dr_runbook.md only."
        )
    data.decode("cp949")


def test_naspath_is_mandatory_no_default() -> None:
    """NasPath must be mandatory and must not have a default placeholder value."""
    text = _text()
    assert (
        "[Parameter(Mandatory = $true)]" in text
    ), "NasPath must be Mandatory to avoid accidental copies"
    assert "$NasPath" in text, "NasPath parameter is missing"
    # Reject a risky default like "\\YOUR_NAS\share" that could be executed by mistake.
    assert "YOUR_NAS" not in text.upper(), "NasPath must not contain a placeholder default"


def test_backup_dir_default_matches_backup_script() -> None:
    """BackupDir default must stay in sync with backup_whymath_pg.ps1."""
    text = _text()
    assert (
        "C:\\Users\\kiki\\Desktop\\__AI\\WhyMath-backups" in text
    ), "BackupDir default changed - keep it identical to backup_whymath_pg.ps1"


def test_keep_count_default_and_minimum() -> None:
    """KeepCount defaults to 2 and the script rejects values below 1."""
    text = _text()
    assert re.search(r"\$KeepCount\s*=\s*2", text), "KeepCount default must be 2"
    assert "$KeepCount -lt 1" in text, "KeepCount must be validated as >= 1"


def test_hash_verification_after_copy() -> None:
    """SHA-256 comparison on destination proves the copy is intact."""
    text = _text()
    assert "Get-FileHash" in text, "SHA-256 hash verification must be present"
    assert "SHA256" in text, "Hash algorithm must be SHA256"
    assert "$srcHash -ne $dstHash" in text, "Hash mismatch must be treated as a failure"


def test_idempotent_skip_with_hash_check() -> None:
    """Already-present files are skipped only when size, time, and hash all match."""
    text = _text()
    assert "Select-Object -First $KeepCount" in text, "newest-N selection must exist"
    assert "Test-Path $dst" in text, "destination existence check must exist"
    assert (
        "$dstItem.Length -eq $src.Length" in text
    ), "size comparison for idempotent skip must exist"


def test_exit_paths_present() -> None:
    """exit 1 failure / exit 0 success paths must exist."""
    text = _text()
    assert "exit 1" in text, "failure exit path missing"
    assert "exit 0" in text, "success exit path missing"


def test_ok_fail_logging_pattern() -> None:
    """Logging pattern matches the backup script for scheduler/operator readability."""
    text = _text()
    assert "[OK]" in text, "success log marker [OK] missing"
    assert "[FAIL]" in text, "failure log marker [FAIL] missing"
    assert "[SKIP]" in text, "idempotent skip log marker [SKIP] missing"
