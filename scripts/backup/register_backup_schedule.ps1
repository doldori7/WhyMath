# =============================================================================
# WhyMath prod DB backup - scheduled task registration (OPS-31)
# =============================================================================
# Registers a Windows scheduled task that runs backup_whymath_pg.ps1 daily.
#
# Why this exists: until now the backup ran only when a human remembered to
# run it, and the runbook (section 6) recorded "schedule depends on logon" as
# a known hole. A logon-dependent task silently skips every day the operator
# does not sign in - and a skipped backup looks exactly like a healthy one.
#
# Two settings do the actual work here:
#   -LogonType S4U        run whether or not the user is logged on, WITHOUT
#                         storing a password (S4U = service-for-user). This is
#                         what removes the logon dependency.
#   -StartWhenAvailable   if the machine was off at trigger time, run as soon
#                         as it comes back instead of dropping the occurrence.
#
# Neither of those makes a missed run OBSERVABLE - that is what the status file
# written by backup_whymath_pg.ps1 and read by backup_status.py does. Scheduling
# reduces misses; the status check is what refuses to call silence success.
#
# ASCII ONLY - PowerShell 5.1 reads .ps1 in the OS locale encoding (cp949 on
# Korean Windows). Korean documentation lives in the runbook.
#
# Usage (Windows PowerShell, ELEVATED - task registration needs admin):
#   .\scripts\backup\register_backup_schedule.ps1
#   .\scripts\backup\register_backup_schedule.ps1 -At 03:30 -RequireEncryption
#   .\scripts\backup\register_backup_schedule.ps1 -Unregister
#
# Exit codes: 0 = success, 1 = failure (reason printed).

param(
    # Daily run time, 24h "HH:mm".
    [string]$At = "04:00",
    # Task name in Task Scheduler.
    [string]$TaskName = "WhyMath-DB-Backup",
    # Passed through to backup_whymath_pg.ps1.
    [string]$BackupDir = "C:\Users\kiki\Desktop\__AI\WhyMath-backups",
    [int]$RetentionDays = 14,
    # Refuse to produce a plaintext backup (see runbook 4-1). Recommended once
    # the key pair exists.
    [switch]$RequireEncryption,
    # Remove the task instead of creating it.
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

function Fail([string]$Reason) {
    Write-Host "[FAIL] $Reason"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 0: unregister path
# ---------------------------------------------------------------------------
if ($Unregister) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "[OK] task '$TaskName' does not exist - nothing to remove"
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    $still = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($still) {
        Fail "Unregister-ScheduledTask returned but '$TaskName' is still registered."
    }
    Write-Host "[OK] task '$TaskName' removed"
    exit 0
}

# ---------------------------------------------------------------------------
# Step 1: resolve the backup script by absolute path
# The task runs with an unpredictable working directory, so a relative path
# would fail at trigger time and be discovered only by a missed backup.
# ---------------------------------------------------------------------------
$scriptPath = Join-Path $PSScriptRoot "backup_whymath_pg.ps1"
if (-not (Test-Path $scriptPath)) {
    Fail "backup script not found next to this file: $scriptPath"
}

# ---------------------------------------------------------------------------
# Step 2: build the action
# ---------------------------------------------------------------------------
$argList = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -BackupDir `"$BackupDir`" -RetentionDays $RetentionDays"
if ($RequireEncryption) {
    $argList = "$argList -RequireEncryption"
}
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argList

# ---------------------------------------------------------------------------
# Step 3: trigger + principal + settings
# S4U is the whole point: run without an interactive logon and without a
# stored password. RunLevel Highest is needed because the script talks to the
# Docker engine.
# ---------------------------------------------------------------------------
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# ---------------------------------------------------------------------------
# Step 4: register (replacing any earlier version of the same task)
# ---------------------------------------------------------------------------
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

# ---------------------------------------------------------------------------
# Step 5: self-verification - read the task BACK and check the two properties
# that carry the meaning. Registering successfully is not evidence that the
# logon dependency is gone; only LogonType is. A check that cannot fail when
# the setting is wrong is not a check.
# ---------------------------------------------------------------------------
$check = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $check) {
    Fail "Register-ScheduledTask reported success but '$TaskName' cannot be read back."
}
$logonType = $check.Principal.LogonType
if ("$logonType" -ne "S4U") {
    Fail "task '$TaskName' registered with LogonType '$logonType', not S4U - it would still depend on an interactive logon. Re-run this script elevated."
}
if (-not $check.Settings.StartWhenAvailable) {
    Fail "task '$TaskName' registered without StartWhenAvailable - a run missed while the machine was off would be dropped silently."
}

Write-Host "[OK] task '$TaskName' registered: daily $At, LogonType S4U, StartWhenAvailable"
Write-Host "[OK] action: powershell.exe $argList"
Write-Host "[NEXT] verify freshness later with:"
Write-Host "       python scripts\backup\backup_status.py check --backup-dir `"$BackupDir`" --max-age-hours 48"
exit 0
