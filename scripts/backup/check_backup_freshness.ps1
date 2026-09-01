# =============================================================================
# WhyMath backup freshness check - scheduled wrapper (OPS-31)
# =============================================================================
# Runs scripts/backup/backup_status.py check and turns its verdict into
# something an operator can actually notice.
#
# Why a wrapper exists at all: the status ledger only helps if something READS
# it. A checker that a human must remember to run reproduces the very failure
# mode this work set out to remove - a missed backup that looks exactly like a
# healthy one. So this script is registered as its own scheduled task by
# register_backup_schedule.ps1.
#
# The visible signal is an alert FILE in the backup directory, written on
# failure and DELETED on recovery. Deleting it matters: an alert that never
# clears becomes furniture, and then a real one is invisible too.
#
# Honest limit: a file in a directory is a weak signal - it is seen only when
# someone looks there. It is strictly better than nothing (dated, states the
# reason, and the task's LastTaskResult goes non-zero), but real alerting -
# push/mail/central log - is OPS-04's scope, not this script's.
#
# ASCII ONLY - PowerShell 5.1 reads .ps1 in the OS locale encoding (cp949 on
# Korean Windows). Korean documentation lives in the runbook.
#
# Usage (Windows PowerShell, repo root):
#   .\scripts\backup\check_backup_freshness.ps1
#   .\scripts\backup\check_backup_freshness.ps1 -MaxAgeHours 48 -RequireEncrypted
#
# Exit codes: 0 = fresh, 1 = stale/never-recorded/plaintext, 2 = could not
# decide (python or the checker module missing). 2 is never folded into 0 -
# "could not check" is not "nothing wrong".

param(
    [string]$BackupDir = "C:\Users\kiki\Desktop\__AI\WhyMath-backups",
    [double]$MaxAgeHours = 48,
    # Fail when the last artifact is plaintext (offsite operation - runbook 4-1).
    [switch]$RequireEncrypted,
    # Interpreter. Kiki's machine has conda base + .venv active at once, so an
    # explicit path may be needed; see the runbook.
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$alertPath = Join-Path $BackupDir "backup_alert.txt"

function Write-Alert([string]$Reason, [string]$Detail) {
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss+00:00")
    $lines = @(
        "WhyMath backup alert",
        "when : $stamp",
        "why  : $Reason",
        "",
        $Detail,
        "",
        "This file is written by check_backup_freshness.ps1 and is deleted",
        "automatically once a fresh backup is recorded. See the runbook:",
        "docs/architecture/db_backup_dr_runbook.md section 2-2."
    )
    [System.IO.File]::WriteAllLines($alertPath, $lines, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "[ALERT] $Reason - wrote $alertPath"
}

function Clear-Alert {
    if (Test-Path $alertPath) {
        Remove-Item $alertPath -Force
        Write-Host "[OK] recovered - removed stale alert file $alertPath"
    }
}

# ---------------------------------------------------------------------------
# Step 1: locate the checker module (absolute - the task runs from anywhere)
# ---------------------------------------------------------------------------
$checker = Join-Path $PSScriptRoot "backup_status.py"
if (-not (Test-Path $checker)) {
    Write-Alert "checker missing" "backup_status.py not found next to this script: $checker"
    exit 2
}

# ---------------------------------------------------------------------------
# Step 2: run the check. --json so the alert carries the machine verdict.
# ---------------------------------------------------------------------------
# NOT named $args - that is an automatic variable in PowerShell and @args
# splats it specially; shadowing it is a subtle way to pass the wrong argv.
$checkArgs = @("check", "--backup-dir", $BackupDir, "--max-age-hours", "$MaxAgeHours", "--json")
if ($RequireEncrypted) { $checkArgs += "--require-encrypted" }

# try/catch, not a $LASTEXITCODE test: with ErrorActionPreference=Stop a missing
# interpreter throws CommandNotFoundException before any exit code is set, so a
# null-check on $LASTEXITCODE would never run. "Cannot launch the checker" must
# still leave evidence - that is the whole point of this wrapper.
$code = $null
$text = ""
try {
    $out = & $PythonExe $checker @checkArgs 2>&1
    $code = $LASTEXITCODE
    $text = ($out | Out-String).Trim()
} catch {
    Write-Alert "checker did not run" ("could not launch '" + $PythonExe + "': " + $_.Exception.GetType().Name + ": " + $_.Exception.Message)
    exit 2
}

if ($null -eq $code) {
    Write-Alert "checker did not run" "no exit code from '$PythonExe'. Output:`n$text"
    exit 2
}

# ---------------------------------------------------------------------------
# Step 3: verdict -> visible state
# ---------------------------------------------------------------------------
if ($code -eq 0) {
    Clear-Alert
    Write-Host "[OK] backup freshness check passed"
    Write-Host $text
    exit 0
}

if ($code -eq 1) {
    Write-Alert "backup freshness check FAILED" $text
    exit 1
}

Write-Alert "backup freshness check could not decide (exit $code)" $text
exit 2
