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
# OPS-31 adds age encryption at rest. Dumps carry minor PII in the clear
# (email, school, grade), so an offsite copy MUST be encrypted (runbook 4-1).
# Encryption is fail-closed: when a recipients file is configured but age is
# missing or the encrypt step fails, the run FAILS and the plaintext dump is
# deleted. A half-encrypted run never leaves readable PII behind.
#
# Usage (Windows PowerShell, repo root):
#   .\scripts\backup\backup_whymath_pg.ps1
#   .\scripts\backup\backup_whymath_pg.ps1 -BackupDir D:\wm-backups -RetentionDays 30
#   .\scripts\backup\backup_whymath_pg.ps1 -RequireEncryption
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
    [string]$ContainerName = "whymath-pg",
    # age recipients file (one public key per line). When empty, the script
    # looks for <BackupDir>\recipients.txt - so once encryption is set up it
    # can never be silently skipped by forgetting a flag.
    [string]$RecipientsFile = "",
    # Refuse to produce a plaintext backup at all. Use this for any run whose
    # output is bound for offsite storage (runbook 4-1).
    [switch]$RequireEncryption,
    # age binary. Override when age is not on PATH.
    [string]$AgeBin = "age"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Reason) {
    Write-Host "[FAIL] $Reason"
    exit 1
}

# Write the last-success record read by scripts/backup/backup_status.py.
# Keys are frozen by tests/infra/test_backup_encryption.py against the Python
# reader, so a rename on either side fails CI instead of going unnoticed.
# Written atomically (temp file + Move-Item -Force) so a crash mid-write can
# never leave a truncated status that the reader would report as corrupt.
function Write-BackupStatus {
    param(
        [string]$StatusPath,
        [string]$Artifact,
        [long]$SizeBytes,
        [bool]$Encrypted,
        [string]$RecipientsFingerprint
    )
    $fp = $null
    if ($RecipientsFingerprint) { $fp = $RecipientsFingerprint }
    $record = [ordered]@{
        last_success_utc        = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss+00:00")
        artifact                = $Artifact
        size_bytes              = $SizeBytes
        encrypted               = $Encrypted
        recipients_fingerprint  = $fp
    }
    # BOM-free UTF-8. PowerShell 5.1's `Set-Content -Encoding UTF8` emits a BOM,
    # which makes json.loads(..., encoding="utf-8") fail on the reader side with
    # "Unexpected UTF-8 BOM" - every successful backup would then look like a
    # failed freshness check. The reader also tolerates a BOM (utf-8-sig), but a
    # writer that does not create the problem is the better half of the fix.
    $tmp = "$StatusPath.tmp"
    $json = $record | ConvertTo-Json
    [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding $false))
    Move-Item -Path $tmp -Destination $StatusPath -Force
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
# Step 6: encryption at rest (age). The dump contains minor PII in the clear,
# so this is the step that decides whether the artifact may leave this disk.
#
# Recipient resolution - explicit flag wins, otherwise <BackupDir>\recipients.txt.
# The directory default matters: once the operator drops a recipients file in
# the backup directory, EVERY later run encrypts, including scheduled ones that
# nobody passes flags to. Encryption cannot be lost by forgetting an argument.
#
# FAIL-CLOSED: from the moment a recipients file is resolved, any failure below
# deletes the plaintext dump and exits 1. Half-encrypted is worse than failed -
# it leaves readable PII on disk under a name that looks handled.
# ---------------------------------------------------------------------------
$resolvedRecipients = ""
if ($RecipientsFile) {
    if (-not (Test-Path $RecipientsFile)) {
        Remove-Item $hostPath
        Fail "-RecipientsFile '$RecipientsFile' not found. Plaintext dump deleted (encryption was requested and could not be applied)."
    }
    $resolvedRecipients = $RecipientsFile
} else {
    $defaultRecipients = Join-Path $BackupDir "recipients.txt"
    if (Test-Path $defaultRecipients) {
        $resolvedRecipients = $defaultRecipients
    }
}

$encrypted = $false
$fingerprint = ""
$finalPath = $hostPath

if (-not $resolvedRecipients) {
    if ($RequireEncryption) {
        Remove-Item $hostPath
        Fail "-RequireEncryption was given but no recipients file was found (checked -RecipientsFile and $BackupDir\recipients.txt). Plaintext dump deleted. Create the key pair first - see runbook section 1b."
    }
    Write-Host "[WARN] backup is NOT encrypted - no recipients file at $BackupDir\recipients.txt."
    Write-Host "[WARN] this artifact contains minor PII in the clear and MUST NOT be copied offsite (runbook 4-1)."
} else {
    $ageProbe = Get-Command $AgeBin -ErrorAction SilentlyContinue
    if (-not $ageProbe) {
        Remove-Item $hostPath
        Fail "age binary '$AgeBin' not found on PATH but a recipients file exists at $resolvedRecipients. Plaintext dump deleted rather than left readable. Install age (winget install FiloSottile.age) or pass -AgeBin."
    }

    $recipientLines = @(Get-Content $resolvedRecipients | Where-Object { $_.Trim() -ne "" -and -not $_.Trim().StartsWith("#") })
    if ($recipientLines.Count -eq 0) {
        Remove-Item $hostPath
        Fail "recipients file $resolvedRecipients has no public keys (only blank/comment lines). Plaintext dump deleted - an empty recipients file must not silently degrade to no encryption."
    }

    $encPath = "$hostPath.age"
    & $AgeBin -R $resolvedRecipients -o $encPath $hostPath
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $hostPath
        if (Test-Path $encPath) { Remove-Item $encPath }
        Fail "age encryption failed (exit $LASTEXITCODE). Plaintext dump deleted; no readable PII left behind."
    }
    if (-not (Test-Path $encPath)) {
        Remove-Item $hostPath
        Fail "age reported success but produced no output file at $encPath. Plaintext dump deleted."
    }

    # Self-check: the ciphertext must NOT start with the pg_dump custom-format
    # magic. Discriminating - if age were replaced by a copy, this fires.
    $head = [System.IO.File]::ReadAllBytes($encPath)[0..4]
    $headText = -join ($head | ForEach-Object { [char]$_ })
    if ($headText -eq "PGDMP") {
        Remove-Item $hostPath
        Remove-Item $encPath
        Fail "the '.age' artifact still starts with the PGDMP magic - it is a plaintext dump, not ciphertext. Both files deleted."
    }

    # Plaintext removal is the point of the whole step. It happens only after
    # the ciphertext exists and passed the magic check.
    Remove-Item $hostPath
    if (Test-Path $hostPath) {
        Fail "could not delete the plaintext dump at $hostPath - readable PII would remain next to the ciphertext. Remove it by hand."
    }

    $encrypted = $true
    $finalPath = $encPath
    $firstKey = $recipientLines[0].Trim()
    if ($firstKey.Length -ge 8) { $fingerprint = $firstKey.Substring($firstKey.Length - 8) }
    $sizeBytes = (Get-Item $finalPath).Length
    Write-Host "[OK] encrypted with age for $($recipientLines.Count) recipient(s), key ...$fingerprint; plaintext removed"
}

# ---------------------------------------------------------------------------
# Step 7: record the success so a MISSED run is observable.
# Without this the failure mode is silence - a scheduled run that never fires
# looks exactly like a healthy system. scripts/backup/backup_status.py check
# turns that silence into exit 1.
# ---------------------------------------------------------------------------
$statusPath = Join-Path $BackupDir "backup_status.json"
Write-BackupStatus -StatusPath $statusPath -Artifact $finalPath -SizeBytes $sizeBytes -Encrypted $encrypted -RecipientsFingerprint $fingerprint

# ---------------------------------------------------------------------------
# Step 8: retention - delete expired backups, ALWAYS keeping the newest.
# Select-Object -Skip 1 exempts the newest file from expiry, guaranteeing at
# least one backup survives even if every file is older than the cutoff.
# ---------------------------------------------------------------------------
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$allDumps = @(Get-ChildItem -Path $BackupDir -File | Where-Object { $_.Name -like "*.dump" -or $_.Name -like "*.dump.age" } | Sort-Object LastWriteTime -Descending)
$expired = @($allDumps | Select-Object -Skip 1 | Where-Object { $_.LastWriteTime -lt $cutoff })
foreach ($file in $expired) {
    Remove-Item $file.FullName
    Write-Host "[RETENTION] deleted expired backup: $($file.Name) (last write $($file.LastWriteTime))"
}

$kept = $allDumps.Count - $expired.Count
$encLabel = "PLAINTEXT - do not copy offsite"
if ($encrypted) { $encLabel = "encrypted (age, key ...$fingerprint)" }
Write-Host "[OK] backup: $finalPath ($sizeBytes bytes) - $encLabel"
Write-Host "[OK] status: $statusPath"
Write-Host "[OK] retention: $RetentionDays day(s), deleted $($expired.Count) expired file(s), $kept kept"
exit 0
