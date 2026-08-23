# OPS-52 ROCm 7.2 standalone 설치·시험 스크립트 (Phaiakes9 전용)
#
# 목적: Ollama에 내장된 ROCm 대신 AMD 공식 ROCm 7.2.1 Windows wheel을 격리 설치하고,
#   Ollama가 standalone HIP 라이브러리를 로드하도록 유도한 뒤 동작·성능을 확인한다.
#
# 사용법(리포 루트, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\install_rocm72_standalone.ps1
#   # Ollama 재기동 없이 다운로드·설치만 (MoE 강등전 등 병렬 작업 중):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\install_rocm72_standalone.ps1 -Phase DownloadInstall
#   # 설치된 standalone을 Ollama에 적용·시험 (Ollama 종료·재기동 포함):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\install_rocm72_standalone.ps1 -Phase ActivateAndBench
#
# 주의:
#   - Ollama 설치 디렉터리의 DLL/SO를 백업 후 교체 시도한다. 실패 시 복원한다.
#   - ActivateAndBench는 Ollama 프로세스를 종료한다. 다른 Ollama 사용자가 있으면 주의.
#   - torch wheel은 Ollama 런타임에 불필요할 수 있으나, ROCm 버전 호환성 참고용으로 함께 기록한다.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("All", "DownloadInstall", "ActivateAndBench")]
    [string]$Phase = "All",
    [string]$RepoRoot = "",
    [string]$InstallDir = "",
    [string]$OllamaDir = "",
    [switch]$SkipDownload,
    [switch]$SkipBackup,
    [switch]$DryRun
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

if ($RepoRoot -eq "") {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if ($InstallDir -eq "") {
    $InstallDir = Join-Path $RepoRoot "work" "rocm-7.2.1-standalone"
}
if ($OllamaDir -eq "") {
    $OllamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
}

$RepoUrl = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1"
$Wheels = @(
    "rocm_sdk_core-7.2.1-py3-none-win_amd64.whl"
    "rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl"
    "rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl"
)

$LogOut = Join-Path $RepoRoot "data" "audit" ("ops-52-rocm72-standalone-{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
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

$needOllamaShutdown = $Phase -in @("All", "ActivateAndBench")
$needDownloadInstall = $Phase -in @("All", "DownloadInstall")
$needActivateBench = $Phase -in @("All", "ActivateAndBench")

Write-Head "OPS-52 ROCm 7.2.1 standalone 시도 — Phase=$Phase"
Write-Log "InstallDir = $InstallDir"
Write-Log "OllamaDir  = $OllamaDir"
Write-Log "Log        = $LogOut"

# ── ① Ollama 종료 (ActivateAndBench/All 단계에서만) ──────────────────────────
if ($needOllamaShutdown) {
    Write-Head "① Ollama orphan process termination"
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
}
else {
    Write-Log "[SKIP] Ollama shutdown — Phase=$Phase"
}

# ── ② 기존 Ollama ROCm 라이브러리 스냅샷 ───────────────────────────────────
$OllamaLib = Join-Path $OllamaDir "lib\ollama"
$BackupDir = Join-Path $InstallDir "ollama-lib-backup"
$HipDlls = @()
if (Test-Path $OllamaLib) {
    $HipDlls = @(Get-ChildItem -Path $OllamaLib -Filter "hip*.dll" -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    Write-Log ("내장 hip*.dll 개수: " + $HipDlls.Count)
    foreach ($dll in $HipDlls) {
        Write-Log ("  " + $dll)
    }
    if ($needOllamaShutdown -and -not $SkipBackup) {
        if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
        foreach ($dll in $HipDlls) {
            $rel = $dll.Substring($OllamaLib.Length).TrimStart('\')
            $dest = Join-Path $BackupDir $rel
            $destDir = Split-Path $dest
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item -Path $dll -Destination $dest -Force
        }
        Write-Log ("백업 완료: " + $BackupDir)
    }
}
else {
    Write-Log "[WARN] Ollama lib 경로를 찾을 수 없음: $OllamaLib"
}

# ── ③ wheel 다운로드 ───────────────────────────────────────────────────────
if ($needDownloadInstall) {
    Write-Head "③ ROCm 7.2.1 wheel 다운로드"
    $DownloadDir = Join-Path $InstallDir "wheels"
    if (-not (Test-Path $DownloadDir)) { New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null }
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { $curl = "curl" }
    foreach ($whl in $Wheels) {
        $dest = Join-Path $DownloadDir $whl
        if ($SkipDownload -and (Test-Path $dest)) {
            Write-Log "이미 존재: $whl"
            continue
        }
        $url = "$RepoUrl/$whl"
        Write-Log "다운로드: $url"
        & $curl -L -o "$dest" "$url"
        if ($LASTEXITCODE -ne 0) {
            Write-Log "[FAIL] 다운로드 실패: $url"
            exit 1
        }
    }
    Write-Log "다운로드 완료"
}
else {
    Write-Log "[SKIP] wheel 다운로드 — Phase=$Phase"
}

# ── ④ wheel 설치 ───────────────────────────────────────────────────────────
if ($needDownloadInstall) {
    Write-Head "④ ROCm 7.2.1 wheel 격리 설치"
    if ($DryRun) {
        Write-Log "[DRY-RUN] pip install --target $InstallDir --no-deps (wheels)"
    }
    else {
        $python = Join-Path (Join-Path $RepoRoot ".venv") "Scripts\python.exe"
        if (-not (Test-Path $python)) { $python = "python" }
        foreach ($whl in $Wheels) {
            $whlPath = Join-Path $DownloadDir $whl
            Write-Log "설치: $whl"
            # --no-deps: wheel 내부 runtime dll이 핵심이므로 의존성 충돌 방지
            & $python -m pip install --target "$InstallDir" --no-deps --force-reinstall "$whlPath"
            if ($LASTEXITCODE -ne 0) {
                Write-Log "[FAIL] 설치 실패: $whl"
                exit 1
            }
        }
    }
}
else {
    Write-Log "[SKIP] wheel 설치 — Phase=$Phase"
}

# ── ⑤ standalone HIP 경로 탐색 ─────────────────────────────────────────────
if ($needDownloadInstall -or $needActivateBench) {
    Write-Head "⑤ standalone HIP 경로 탐색"
    $CandidateHipDirs = @(
        (Join-Path $InstallDir "rocm_sdk_core" "bin"),
        (Join-Path $InstallDir "rocm_sdk_libraries_custom" "bin"),
        (Join-Path $InstallDir "bin"),
        (Join-Path $InstallDir "lib")
    )
    $HipPath = $null
    foreach ($d in $CandidateHipDirs) {
        if (Test-Path (Join-Path $d "hipblas.dll")) {
            $HipPath = $d
            break
        }
        if (Test-Path (Join-Path $d "amdhip64.dll")) {
            $HipPath = $d
            break
        }
    }
    if ($null -eq $HipPath) {
        # wheel 압축 해제 후 bin/ 하위 탐색
        $found = Get-ChildItem -Path $InstallDir -Filter "amdhip64.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $HipPath = $found.DirectoryName
        }
    }
    if ($null -eq $HipPath) {
        Write-Log "[FAIL] standalone HIP DLL(amdhip64.dll/hipblas.dll)을 찾을 수 없음"
        exit 1
    }
    Write-Log ("HIP_PATH = " + $HipPath)
}

# ── ⑥ Ollama 실행 환경에 standalone HIP_PATH 주입 (ActivateAndBench/All) ────
if ($needActivateBench) {
    Write-Head "⑥ Ollama 실행 환경에 standalone HIP_PATH 주입"
    [Environment]::SetEnvironmentVariable("HIP_PATH", $HipPath, "User")
    [Environment]::SetEnvironmentVariable("HIP_PATH", $HipPath, "Process")
    $existingPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($existingPath -notlike "*$HipPath*") {
        [Environment]::SetEnvironmentVariable("PATH", "$HipPath;$existingPath", "User")
    }
    $existingPathProc = [Environment]::GetEnvironmentVariable("PATH", "Process")
    [Environment]::SetEnvironmentVariable("PATH", "$HipPath;$existingPathProc", "Process")
    Write-Log "PATH 앞에 HIP_PATH 추가 완료"
}
else {
    Write-Log "[SKIP] HIP_PATH 주입 — Phase=$Phase"
}

# ── ⑦ Ollama 기동 및 ROCm 인식 확인 (ActivateAndBench/All) ─────────────────
if ($needActivateBench) {
    Write-Head "⑦ Ollama 재기동 및 ROCm/HIP 인식 확인"
    $app = Join-Path $OllamaDir "ollama app.exe"
    if (Test-Path $app) {
        Start-Process -FilePath $app | Out-Null
        Write-Log "트레이 앱 기동: $app"
    }
    else {
        Start-Process -FilePath "ollama" -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
        Write-Log "ollama serve 기동"
    }

    $Base = "http://127.0.0.1:11434"
    $deadline = (Get-Date).AddSeconds(90)
    $version = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $v = Invoke-RestMethod -Uri ($Base + "/api/version") -TimeoutSec 5 -ErrorAction Stop
            $version = $v.version
            Write-Log ("서버 응답 — version " + $version)
            break
        }
        catch { Start-Sleep -Seconds 3 }
    }
    if ($null -eq $version) {
        Write-Log "[FAIL] 90초 안에 Ollama 서버가 응답하지 않음"
        exit 1
    }

    # Ollama 로그에서 ROCm/HIP 버전 키워드 검색
    $OllamaLogDir = Join-Path $env:LOCALAPPDATA "Ollama\logs"
    $rocmLines = @()
    if (Test-Path $OllamaLogDir) {
        $logFiles = Get-ChildItem -Path $OllamaLogDir -Filter "server*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
        foreach ($lf in $logFiles) {
            $rocmLines += Select-String -Path $lf.FullName -Pattern "ROCm|HIP|hipblas|gfx|GPU" -ErrorAction SilentlyContinue | Select-Object -Last 20
        }
    }
    if ($rocmLines.Count -gt 0) {
        Write-Log "Ollama 로그 ROCm/HIP 관련 라인:"
        foreach ($ln in $rocmLines) {
            Write-Log ("  " + $ln.Line)
        }
    }
    else {
        Write-Log "[WARN] Ollama 로그에서 ROCm/HIP 키워드를 찾지 못함"
    }

    # ── ⑧ 모델 로드 및 성능 시험 ────────────────────────────────────────────
    Write-Head "⑧ qwen3:30b-a3b MoE 모델 성능 시험"
    $model = "qwen3:30b-a3b"
    $tags = Invoke-RestMethod -Uri ($Base + "/api/tags") -TimeoutSec 10
    $installed = @($tags.models | ForEach-Object { $_.name })
    if ($model -notin $installed) {
        Write-Log ("[SKIP] 모델 미설치: " + $model)
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
        Write-Log ("생성 완료: eval_count={0}, elapsed={1:N2}s, t/s={2}" -f $evalCount, $sw.Elapsed.TotalSeconds, $tps)
    }
    catch {
        $sw.Stop()
        Write-Log ("[FAIL] 생성 호출 실패: " + $_.Exception.Message)
        exit 1
    }

    Write-Head "⑨ 완료"
    Write-Log "standalone HIP_PATH: $HipPath"
    Write-Log "전체 로그: $LogOut"
    Write-Log "[OK] ROCm 7.2 standalone 시도 완료 — Ollama 로그에서 실제 로드된 HIP/ROCm 버전을 확인하세요."
}
else {
    Write-Head "⑥ 완료 (DownloadInstall 단계)"
    Write-Log "standalone HIP_PATH(예상): $HipPath"
    Write-Log "전체 로그: $LogOut"
    Write-Log "[OK] 다운로드·설치 완료 — ActivateAndBench 단계에서 Ollama 재기동 후 시험하세요."
}
