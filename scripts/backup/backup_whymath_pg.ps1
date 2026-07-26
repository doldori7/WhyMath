# =============================================================================
# WhyMath prod DB backup - docker "whymath-pg" (pgvector/pg16, host port 5433)
# =============================================================================
# OPS-02-db-backup-dr. Runs pg_dump INSIDE the container (no pg client needed
# on the host), verifies the dump catalog with pg_restore --list BEFORE the
# dump is copied out, then applies the retention policy on the host backup dir.
#
# ASCII ONLY - PowerShell 5.1 reads .ps1 files in the OS locale encoding
# (Korean Windows = cp949). A single non-ASCII byte can break this script on
# the operator machine (2026-07-17 logconfig UnicodeDecodeError incident).
# Frozen by tests/infra/test_backup_script.py. Korean documentation lives in
# the runbook: docs/architecture/db_backup_dr_runbook.md
#
# Usage (Windows PowerShell, repo root):
#   .\scripts\backup\backup_whymath_pg.ps1
#   .\scripts\backup\backup_whymath_pg.ps1 -BackupDir D:\wm-backups -RetentionDays 30
#
# Exit codes: 0 = success, 1 = failure (reason printed; errors are never
# swallowed - every step checks $LASTEXITCODE and prints why it failed).

param(
    # Host directory that receives .dump files (created if missing).
    [string]$BackupDir = "C:\Users\kiki\Desktop\__AI\WhyMath-backups",
    # Delete .dump files older than this many days. The newest backup is
    # ALWAYS exempt, so retention can never delete the last remaining backup.
    [int]$RetentionDays = 14,
    # Prod DB container. NOT the throwaway demo DB (whymath-demo-db:55432).
    [string]$ContainerName = "whymath-pg"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Reason) {
    Write-Host "[FAIL] $Reason"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 0: refuse the demo DB / require the prod container to be running
# ---------------------------------------------------------------------------
if ($ContainerName -eq "whymath-demo-db") {
    Fail "whymath-demo-db is the throwaway demo DB (no volume, port 55432, data vanishes on stop_demo). Prod backups must target whymath-pg."
}

$state = docker inspect -f "{{.State.Running}}" $ContainerName
if ($LASTEXITCODE -ne 0) {
    Fail "container '$ContainerName' not found - is Docker Desktop running and the prod DB container created?"
}
if ("$state" -ne "true") {
    Fail "container '$ContainerName' exists but is not running - start it first: docker start $ContainerName"
}

# ---------------------------------------------------------------------------
# Step 1: pg_dump inside the container (custom format, -Fc)
# ---------------------------------------------------------------------------
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$tmpPath = "/tmp/whymath_$stamp.dump"

docker exec $ContainerName pg_dump -U whymath -d whymath -Fc -f $tmpPath
if ($LASTEXITCODE -ne 0) {
    Fail "pg_dump failed inside '$ContainerName' (exit $LASTEXITCODE). See pg_dump output above."
}

# ---------------------------------------------------------------------------
# Step 2: self-check A - dump catalog must be readable BEFORE copying out.
# Discriminating check: pg_restore --list exits non-zero on a truncated or
# corrupt archive and succeeds only when the dump TOC is actually readable,
# so a broken dump produces a failure signal here (not a false pass).
# ---------------------------------------------------------------------------
docker exec $ContainerName pg_restore --list $tmpPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    docker exec $ContainerName rm -f $tmpPath
    Fail "pg_restore --list rejected the fresh dump (corrupt or truncated archive). Container temp file removed; nothing was copied to the host."
}

# ---------------------------------------------------------------------------
# Step 3: copy the dump to the host backup directory
# ---------------------------------------------------------------------------
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}
$hostPath = Join-Path $BackupDir "whymath_$stamp.dump"

docker cp "${ContainerName}:${tmpPath}" $hostPath
if ($LASTEXITCODE -ne 0) {
    docker exec $ContainerName rm -f $tmpPath
    Fail "docker cp failed (exit $LASTEXITCODE) - dump not retrieved. Container temp file removed."
}

# ---------------------------------------------------------------------------
# Step 4: self-check B - host file must exist and be non-empty
# ---------------------------------------------------------------------------
if (-not (Test-Path $hostPath)) {
    docker exec $ContainerName rm -f $tmpPath
    Fail "backup file missing on host after docker cp: $hostPath"
}
$sizeBytes = (Get-Item $hostPath).Length
if ($sizeBytes -le 0) {
    Remove-Item $hostPath
    docker exec $ContainerName rm -f $tmpPath
    Fail "backup file is empty (0 bytes) and was removed: $hostPath - investigate docker cp."
}

# ---------------------------------------------------------------------------
# Step 5: remove the temp dump inside the container
# ---------------------------------------------------------------------------
docker exec $ContainerName rm -f $tmpPath
if ($LASTEXITCODE -ne 0) {
    Fail "could not remove container temp file $tmpPath (exit $LASTEXITCODE). The host backup at $hostPath is valid, but /tmp inside the container needs manual cleanup."
}

# ---------------------------------------------------------------------------
# Step 6: retention - delete expired .dump files, ALWAYS keeping the newest.
# Select-Object -Skip 1 exempts the newest file from expiry, guaranteeing at
# least one backup survives even if every file is older than the cutoff.
# ---------------------------------------------------------------------------
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$allDumps = @(Get-ChildItem -Path $BackupDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending)
$expired = @($allDumps | Select-Object -Skip 1 | Where-Object { $_.LastWriteTime -lt $cutoff })
foreach ($file in $expired) {
    Remove-Item $file.FullName
    Write-Host "[RETENTION] deleted expired backup: $($file.Name) (last write $($file.LastWriteTime))"
}

$kept = $allDumps.Count - $expired.Count
Write-Host "[OK] backup: $hostPath ($sizeBytes bytes)"
Write-Host "[OK] retention: $RetentionDays day(s), deleted $($expired.Count) expired file(s), $kept kept"
exit 0
