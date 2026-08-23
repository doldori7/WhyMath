# OPS-52 ROCm 7.2 standalone 적용·시험 스크립트 (Phaiakes9 전용)
#
# 사전 조건: install_rocm72_standalone.ps1 -Phase DownloadInstall 또는 동등한 curl+pip 설치가 끝난 상태.
#   이 스크립트는 Ollama를 종료하고, standalone HIP_PATH를 주입한 뒤 Ollama를 재기동해
#   qwen3:30b-a3b로 간단한 생성 시험을 한다.

[CmdletBinding()]
param(
    [string]$RepoRoot = ""
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

if ($RepoRoot -eq "") {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$InstallDir = Join-Path $RepoRoot "work" "rocm-7.2.1-standalone"
$OllamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
$OllamaLib = Join-Path $OllamaDir "lib\ollama"

$LogOut = Join-Path $RepoRoot "data" "audit" ("ops-52-rocm72-activate-{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$null = New-Item -ItemType Directory -Path (Split-Path $LogOut) -Force

function Write-Head($Text) {
    Write-Host ""
    Write-Host ("=" * 72)
    Write-Host $Text
    Write-Host ("=" * 72)
}
function Write-Log($Text) {
    $line = ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text)
    Write-Host $line
    Add-Content -Path $LogOut -Value $line -Encoding UTF8
}

Write-Head "OPS-52 ROCm 7.2.1 standalone 적용·시험"
Write-Log "InstallDir = $InstallDir"
Write-Log "OllamaDir  = $OllamaDir"
Write-Log "Log        = $LogOut"

# ── ① Ollama 종료 ────────────────────────────────────────────────────────────
Write-Head "① Ollama process termination"
$procs = @()
$procs += Get-Process -Name "ollama" -ErrorAction SilentlyContinue
$procs += Get-Process -Name "ollama app" -ErrorAction SilentlyContinue
$procs += Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
if ($procs.Count -gt 0) {
    Write-Log ("terminating " + $procs.Count + " process(es)")
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
}
$left = @()
$left += Get-Process -Name "ollama" -ErrorAction SilentlyContinue
$left += Get-Process -Name "ollama app" -ErrorAction SilentlyContinue
$left += Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
Write-Log ("remaining processes: " + $left.Count)
if ($left.Count -gt 0) {
    Write-Log "[FAIL] Ollama process termination failed"
    exit 1
}

# ── ② standalone HIP 경로 탐색 및 amdhip64.dll alias ─────────────────────────
Write-Head "② standalone HIP path discovery"
$coreBin = Join-Path $InstallDir "_rocm_sdk_core" "bin"
$customBin = Join-Path $InstallDir "_rocm_sdk_libraries_custom" "bin"
$HipPath = $coreBin

if (-not (Test-Path (Join-Path $coreBin "amdhip64_7.dll"))) {
    Write-Log "[FAIL] amdhip64_7.dll not found in $coreBin"
    exit 1
}

# Ollama는 보통 amdhip64.dll 이름으로 로드하므로 버전 suffix DLL에 대한 alias를 만든다.
$aliasSrc = Join-Path $coreBin "amdhip64_7.dll"
$aliasDst = Join-Path $coreBin "amdhip64.dll"
if (-not (Test-Path $aliasDst)) {
    Copy-Item -Path $aliasSrc -Destination $aliasDst -Force
    Write-Log "copied amdhip64_7.dll -> amdhip64.dll"
}
else {
    Write-Log "amdhip64.dll alias already exists"
}

# hipblas.dll 경로도 PATH에 포함
$pathEntries = @($coreBin, $customBin) | Where-Object { Test-Path $_ }
Write-Log ("HIP_PATH = " + $HipPath)

# ── ③ Ollama lib 백업 및 standalone DLL 병행 배치 ────────────────────────────
# Ollama.exe가 있는 디렉터리의 DLL 검색 우선순위를 우회하기 위해,
# Ollama lib 디렉터리에도 alias를 배치한다(원본은 백업).
$BackupDir = Join-Path $InstallDir "ollama-lib-backup"
if (Test-Path $OllamaLib) {
    $hipDlls = @(Get-ChildItem -Path $OllamaLib -Filter "hip*.dll" -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    Write-Log ("built-in hip*.dll count: " + $hipDlls.Count)
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        foreach ($dll in $hipDlls) {
            $rel = $dll.Substring($OllamaLib.Length).TrimStart('\')
            $dest = Join-Path $BackupDir $rel
            $destDir = Split-Path $dest
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item -Path $dll -Destination $dest -Force
        }
        Write-Log ("backed up Ollama lib: " + $BackupDir)
    }

    # Ollama lib 루트에 standalone 핵심 DLL 복사(검색 우선순위 상승)
    $destCore = Join-Path $OllamaLib "amdhip64.dll"
    $destHipblas = Join-Path $OllamaLib "hipblas.dll"
    Copy-Item -Path (Join-Path $coreBin "amdhip64.dll") -Destination $destCore -Force
    Copy-Item -Path (Join-Path $customBin "hipblas.dll") -Destination $destHipblas -Force
    Write-Log "copied standalone amdhip64.dll / hipblas.dll into Ollama lib"
}
else {
    Write-Log "[WARN] Ollama lib path not found: $OllamaLib"
}

# ── ④ 환경변수 주입 ──────────────────────────────────────────────────────────
Write-Head "③ environment variable injection"
[Environment]::SetEnvironmentVariable("HIP_PATH", $HipPath, "User")
[Environment]::SetEnvironmentVariable("HIP_PATH", $HipPath, "Process")
$existingPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$newUserPath = ($pathEntries + ($existingPath -split ";" | Where-Object { $_ -and $_ -ne "" })) -join ";"
[Environment]::SetEnvironmentVariable("PATH", $newUserPath, "User")
$existingPathProc = [Environment]::GetEnvironmentVariable("PATH", "Process")
$newProcPath = ($pathEntries + ($existingPathProc -split ";" | Where-Object { $_ -and $_ -ne "" })) -join ";"
[Environment]::SetEnvironmentVariable("PATH", $newProcPath, "Process")
Write-Log "PATH prepended with HIP dirs"

# ── ⑤ Ollama 기동 ───────────────────────────────────────────────────────────
Write-Head "④ Ollama restart"
$app = Join-Path $OllamaDir "ollama app.exe"
if (Test-Path $app) {
    Start-Process -FilePath $app | Out-Null
    Write-Log "started tray app: $app"
}
else {
    Start-Process -FilePath "ollama" -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
    Write-Log "started ollama serve"
}

$Base = "http://127.0.0.1:11434"
$deadline = (Get-Date).AddSeconds(90)
$version = $null
while ((Get-Date) -lt $deadline) {
    try {
        $v = Invoke-RestMethod -Uri ($Base + "/api/version") -TimeoutSec 5 -ErrorAction Stop
        $version = $v.version
        Write-Log ("server responded — version " + $version)
        break
    }
    catch { Start-Sleep -Seconds 3 }
}
if ($null -eq $version) {
    Write-Log "[FAIL] Ollama server did not respond within 90s"
    exit 1
}

# ── ⑥ Ollama 로그에서 ROCm/HIP 키워드 추출 ────────────────────────────────
Write-Head "⑤ ROCm/HIP log inspection"
$OllamaLogDir = Join-Path $env:LOCALAPPDATA "Ollama\logs"
$rocmLines = @()
if (Test-Path $OllamaLogDir) {
    $logFiles = Get-ChildItem -Path $OllamaLogDir -Filter "server*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
    foreach ($lf in $logFiles) {
        $rocmLines += Select-String -Path $lf.FullName -Pattern "ROCm|HIP|hipblas|amdhip|gfx|GPU" -ErrorAction SilentlyContinue | Select-Object -Last 30
    }
}
if ($rocmLines.Count -gt 0) {
    Write-Log "Ollama log ROCm/HIP lines:"
    foreach ($ln in $rocmLines) {
        Write-Log ("  " + $ln.Line)
    }
}
else {
    Write-Log "[WARN] no ROCm/HIP keyword found in Ollama logs"
}

# ── ⑦ 모델 생성 시험 ─────────────────────────────────────────────────────────
Write-Head "⑥ qwen3:30b-a3b generation test"
$model = "qwen3:30b-a3b"
$tags = Invoke-RestMethod -Uri ($Base + "/api/tags") -TimeoutSec 10
$installed = @($tags.models | ForEach-Object { $_.name })
if ($model -notin $installed) {
    Write-Log ("[SKIP] model not installed: " + $model)
    exit 0
}

$prompt = "Solve step by step: 2x + 5 = 13, find x. Answer only the value."
$body = @{ model = $model; prompt = $prompt; stream = $false; options = @{ num_predict = 64; temperature = 0 } } | ConvertTo-Json -Depth 5
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $resp = Invoke-RestMethod -Uri ($Base + "/api/generate") -Method POST -Body $body -ContentType "application/json" -TimeoutSec 120 -ErrorAction Stop
    $sw.Stop()
    $evalCount = $resp.eval_count
    $tps = if ($evalCount -and $sw.Elapsed.TotalSeconds -gt 0) { [math]::Round($evalCount / $sw.Elapsed.TotalSeconds, 2) } else { 0 }
    Write-Log ("generation ok: eval_count=$evalCount, elapsed=$($sw.Elapsed.TotalSeconds.ToString('N2'))s, t/s=$tps")
}
catch {
    $sw.Stop()
    Write-Log ("[FAIL] generation call failed: " + $_.Exception.Message)
    exit 1
}

Write-Head "⑦ done"
Write-Log "standalone HIP_PATH: $HipPath"
Write-Log "full log: $LogOut"
Write-Log "[OK] ROCm 7.2 standalone activation complete — verify loaded HIP/ROCm version in the log lines above."
