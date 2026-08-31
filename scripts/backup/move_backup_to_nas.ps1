# ============================================================================
# WhyMath prod DB backup offsite copy - local backups -> NAS
# ============================================================================
# OPS-02-db-backup-dr extension. Copies the newest N .dump files from the
# local backup dir to a NAS path, then verifies each copy with SHA-256.
#
# ASCII ONLY - PowerShell 5.1 reads .ps1 files in the OS locale encoding
# (Korean Windows = cp949). A single non-ASCII byte can break this script on
# the operator machine (2026-07-17 logconfig UnicodeDecodeError incident).
# Frozen by tests/infra/test_move_backup_to_nas.py. Korean documentation lives
# in the runbook: docs/architecture/db_backup_dr_runbook.md
#
# Usage (Windows PowerShell, repo root):
#   .\scripts\backup\move_backup_to_nas.ps1 -NasPath "\\nas\whymath-backups"
#
# Exit codes: 0 = success (all requested copies verified), 1 = failure.

param(
    # Mandatory NAS target. Example UNC: "\\nas\share\whymath-backups".
    # No default value - forcing the operator to state the destination prevents
    # accidental copies to a placeholder path.
    [Parameter(Mandatory = $true)]
    [string]$NasPath,

    # Local backup dir produced by backup_whymath_pg.ps1.
    [string]$BackupDir = "C:\Users\kiki\Desktop\__AI\WhyMath-backups",

    # How many newest .dump files to copy. The newest backup is always included.
    [int]$KeepCount = 2
)

$ErrorActionPreference = "Stop"

function Fail([string]$Reason) {
    Write-Host "[FAIL] $Reason"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 0: validate inputs
# ---------------------------------------------------------------------------
if (-not (Test-Path $BackupDir)) {
    Fail "local backup dir missing: $BackupDir"
}
if ($KeepCount -lt 1) {
    Fail "KeepCount must be >= 1 (got $KeepCount)"
}
if (-not (Test-Path $NasPath)) {
    Fail "NAS path not reachable: $NasPath"
}

# ---------------------------------------------------------------------------
# Step 1: select newest N .dump files
# ---------------------------------------------------------------------------
$localDumps = @(Get-ChildItem -Path $BackupDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First $KeepCount)
if ($localDumps.Count -eq 0) {
    Fail "no .dump files found in $BackupDir"
}

# ---------------------------------------------------------------------------
# Step 2: copy each file with idempotency + SHA-256 verification
# ---------------------------------------------------------------------------
$copied = 0
$skipped = 0
$failed = 0

foreach ($src in $localDumps) {
    $dst = Join-Path $NasPath $src.Name

    # Idempotent skip: same name, size, and last-write-time already present.
    if (Test-Path $dst) {
        $dstItem = Get-Item $dst
        if (($dstItem.Length -eq $src.Length) -and ($dstItem.LastWriteTime -eq $src.LastWriteTime)) {
            $srcHash = (Get-FileHash -Path $src.FullName -Algorithm SHA256).Hash
            $dstHash = (Get-FileHash -Path $dst -Algorithm SHA256).Hash
            if ($srcHash -eq $dstHash) {
                Write-Host "[SKIP] $($src.Name) already on NAS with matching hash"
                $skipped++
                continue
            }
        }
    }

    try {
        Copy-Item -Path $src.FullName -Destination $dst -Force
    } catch {
        Write-Host "[FAIL] copy failed for $($src.Name): $_"
        $failed++
        continue
    }

    # Verify destination size > 0 and hash matches.
    if (-not (Test-Path $dst)) {
        Write-Host "[FAIL] copied file missing on NAS: $dst"
        $failed++
        continue
    }
    $dstSize = (Get-Item $dst).Length
    if ($dstSize -ne $src.Length) {
        Write-Host "[FAIL] size mismatch for $($src.Name): local $($src.Length) vs NAS $dstSize"
        $failed++
        continue
    }
    $srcHash = (Get-FileHash -Path $src.FullName -Algorithm SHA256).Hash
    $dstHash = (Get-FileHash -Path $dst -Algorithm SHA256).Hash
    if ($srcHash -ne $dstHash) {
        Write-Host "[FAIL] SHA-256 mismatch for $($src.Name): local $srcHash vs NAS $dstHash"
        $failed++
        continue
    }

    Write-Host "[OK] copied $($src.Name) ($($src.Length) bytes) hash $dstHash"
    $copied++
}

# ---------------------------------------------------------------------------
# Step 3: summary
# ---------------------------------------------------------------------------
if ($failed -gt 0) {
    Fail "offsite copy incomplete: copied=$copied skipped=$skipped failed=$failed"
}

Write-Host "[OK] offsite copy complete: copied=$copied skipped=$skipped source-count=$($localDumps.Count)"
exit 0
