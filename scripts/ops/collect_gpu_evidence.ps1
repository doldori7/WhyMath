# Phaiakes9 (Ryzen AI Max+ 395 / Radeon 8060S) GPU 추론 증거 수집기 — Phase 0.
#
# 목적: "GPU가 잡히는가"를 추측이 아니라 파일 하나로 남긴다. 수집 항목 =
#   ① 시스템(CPU·RAM·메모리 속도)  ② GPU(이름·드라이버·PNP)  ③ 전용 VRAM 실제 바이트(레지스트리·dxdiag)
#   ④ 전원 계획  ⑤ Ollama(버전·모델·상주 상태·/api/ps 오프로드)  ⑥ 관련 환경변수  ⑦ Ollama 서버 로그의 GPU 탐지 줄
#
# 사용법(리포 루트, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\collect_gpu_evidence.ps1
#
# 설계 규칙(CLAUDE.md):
#   - 침묵 실패 금지: 각 수집 단계는 실패해도 계속하되 [ERR] + *예외 타입명*을 반드시 남긴다.
#   - 변별력 있는 자가검증: 마지막에 산출 파일의 존재·크기·필수 섹션 수를 되읽어 [OK]/[FAIL] + exit code로 판정한다.
#   - 판정은 화면 문자열이 아니라 exit code로 한다.

[CmdletBinding()]
param(
    [string]$OutDir = "",
    [string]$OllamaHost = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Continue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot ".gpu_evidence" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$Stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$OutFile = Join-Path $OutDir ("evidence_" + $Stamp + ".txt")

$Lines = New-Object System.Collections.ArrayList
function Add-Line { param([string]$Text = "") ; [void]$Lines.Add($Text) ; Write-Host $Text }
function Add-Section {
    param([string]$Title, [scriptblock]$Body)
    Add-Line ""
    Add-Line ("=" * 78)
    Add-Line ("## " + $Title)
    Add-Line ("=" * 78)
    try {
        $out = & $Body
        if ($null -ne $out) { foreach ($l in ($out | Out-String -Width 200).TrimEnd().Split("`n")) { Add-Line $l.TrimEnd() } }
    } catch {
        # 예외 타입명 필수 (무타입 경고 금지 — CLAUDE.md)
        Add-Line ("[ERR] " + $_.Exception.GetType().FullName + ": " + $_.Exception.Message)
    }
}

Add-Line "WhyMath / Phaiakes9 GPU evidence"
Add-Line ("collected_at : " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K"))
Add-Line ("hostname     : " + $env:COMPUTERNAME)
Add-Line ("repo_root    : " + $RepoRoot)
Add-Line ("git_branch   : " + (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null))
Add-Line ("git_commit   : " + (& git -C $RepoRoot rev-parse --short HEAD 2>$null))

Add-Section "1. System (CPU / RAM / memory speed)" {
    Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-List
    $cs = Get-CimInstance Win32_ComputerSystem
    "TotalPhysicalMemory_GB : {0:N1}" -f ($cs.TotalPhysicalMemory / 1GB)
    "Manufacturer/Model     : {0} / {1}" -f $cs.Manufacturer, $cs.Model
    Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel, Capacity, Speed, ConfiguredClockSpeed | Format-Table -AutoSize
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List
}

Add-Section "2. GPU (video controllers)" {
    Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion, DriverDate, VideoProcessor, VideoModeDescription, PNPDeviceID, Status |
        Format-List
}

Add-Section "3. Dedicated VRAM (registry qwMemorySize) - VGM 실제 반영값" {
    # Win32_VideoController.AdapterRAM은 4GB에서 wrap 되어 신뢰 불가.
    # 드라이버가 보고하는 실제 전용 메모리는 이 레지스트리 값이다.
    $base = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    Get-ChildItem $base -ErrorAction Stop | ForEach-Object {
        $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
        if ($null -ne $p -and $null -ne $p."HardwareInformation.qwMemorySize") {
            $bytes = [uint64]$p."HardwareInformation.qwMemorySize"
            "{0,-6} {1,-45} dedicated = {2,10:N0} MB ({3:N1} GB)" -f $_.PSChildName, $p.DriverDesc, ($bytes/1MB), ($bytes/1GB)
        }
    }
}

Add-Section "4. Dedicated / Shared memory (dxdiag)" {
    $dx = Join-Path $env:TEMP ("whymath_dxdiag_" + $Stamp + ".txt")
    Start-Process -FilePath "dxdiag" -ArgumentList ("/whs /t " + $dx) -WindowStyle Hidden -ErrorAction Stop | Out-Null
    # dxdiag는 비동기로 파일을 쓴다 — 존재만 보지 말고 안정화까지 폴링한다(변별력 있는 대기).
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $dx) { $sz = (Get-Item $dx).Length ; Start-Sleep -Seconds 2 ; if ((Get-Item $dx).Length -eq $sz -and $sz -gt 0) { break } }
        else { Start-Sleep -Seconds 2 }
    }
    if (Test-Path $dx) {
        Select-String -Path $dx -Pattern "Card name|Display Memory|Dedicated Memory|Shared Memory|Driver Version|Chip type" |
            ForEach-Object { $_.Line.Trim() }
        Remove-Item $dx -Force -ErrorAction SilentlyContinue
    } else {
        "[ERR] System.IO.FileNotFoundException: dxdiag output not produced within 90s"
    }
}

Add-Section "5. Power plan / power mode" {
    (& powercfg /getactivescheme) 2>&1
    "--- (참고) EVO-X2 전면 버튼: Quiet 54W / Balanced 85W / Performance 140W — OS에서는 안 보인다. 눈으로 확인할 것."
}

Add-Section "6. Ollama - version / models / running" {
    (& ollama --version) 2>&1
    "--- ollama list ---"
    (& ollama list) 2>&1
    "--- ollama ps ---"
    (& ollama ps) 2>&1
}

Add-Section "7. Ollama REST (/api/version, /api/ps) - GPU offload fraction" {
    $v = Invoke-RestMethod -Uri ($OllamaHost + "/api/version") -TimeoutSec 15 -ErrorAction Stop
    "api_version : " + $v.version
    $ps = Invoke-RestMethod -Uri ($OllamaHost + "/api/ps") -TimeoutSec 15 -ErrorAction Stop
    if ($null -eq $ps.models -or $ps.models.Count -eq 0) {
        "loaded_models : (none) — 상주 모델 없음. 벤치 전이라면 정상."
    } else {
        foreach ($m in $ps.models) {
            $frac = if ($m.size -gt 0) { [math]::Round(($m.size_vram / $m.size), 4) } else { 0 }
            "{0,-24} size={1,8:N0} MB  size_vram={2,8:N0} MB  gpu_fraction={3}" -f $m.name, ($m.size/1MB), ($m.size_vram/1MB), $frac
        }
        "--- gpu_fraction 1.0 = 전량 GPU / 0.0 = 전량 CPU (ollama ps의 PROCESSOR 열과 같은 값의 기계 판독형)"
    }
}

Add-Section "8. Relevant environment variables (Process / User / Machine)" {
    $names = @("OLLAMA_HOST","OLLAMA_DEBUG","OLLAMA_VULKAN","OLLAMA_IGPU_ENABLE","OLLAMA_FLASH_ATTENTION",
               "OLLAMA_KV_CACHE_TYPE","OLLAMA_MAX_LOADED_MODELS","OLLAMA_KEEP_ALIVE","OLLAMA_NUM_PARALLEL",
               "OLLAMA_CONTEXT_LENGTH","OLLAMA_GPU_OVERHEAD","OLLAMA_MODELS",
               "HSA_OVERRIDE_GFX_VERSION","HIP_VISIBLE_DEVICES","ROCR_VISIBLE_DEVICES","GGML_VK_VISIBLE_DEVICES")
    foreach ($n in $names) {
        $p = [Environment]::GetEnvironmentVariable($n, "Process")
        $u = [Environment]::GetEnvironmentVariable($n, "User")
        $m = [Environment]::GetEnvironmentVariable($n, "Machine")
        if ($p -or $u -or $m) { "{0,-26} process='{1}' user='{2}' machine='{3}'" -f $n, $p, $u, $m }
        else                  { "{0,-26} (unset)" -f $n }
    }
}

Add-Section "9. Ollama server log - GPU discovery lines (tail)" {
    $logs = @(
        (Join-Path $env:LOCALAPPDATA "Ollama\server.log"),
        (Join-Path $env:LOCALAPPDATA "Ollama\app.log")
    )
    $found = $false
    foreach ($lg in $logs) {
        if (Test-Path $lg) {
            $found = $true
            "--- " + $lg + " ---"
            Get-Content $lg -Tail 400 |
                Select-String -Pattern "gfx|ROCm|rocm|Vulkan|vulkan|HIP|hip|library|inference compute|amdgpu|8060S|VRAM|total blobs|no compatible GPUs" |
                Select-Object -Last 40 | ForEach-Object { $_.Line.Trim() }
        }
    }
    if (-not $found) { "[ERR] System.IO.FileNotFoundException: no Ollama server.log/app.log under " + $env:LOCALAPPDATA + "\Ollama" }
}

# ── 저장 ─────────────────────────────────────────────────────────────────────
Set-Content -Path $OutFile -Value $Lines -Encoding UTF8

# ── 자가검증 (변별력 있는 검사: 존재 + 크기 + 필수 섹션 수) ──────────────────
Write-Host ""
Write-Host ("-" * 78)
$ok = $true
if (-not (Test-Path $OutFile)) { Write-Host "[FAIL] evidence file was not created"; $ok = $false }
else {
    $size = (Get-Item $OutFile).Length
    $sections = @(Select-String -Path $OutFile -Pattern "^## \d\.").Count
    Write-Host ("[INFO] file     : " + $OutFile)
    Write-Host ("[INFO] size     : " + $size + " bytes")
    Write-Host ("[INFO] sections : " + $sections + " / 9")
    if ($size -lt 500)   { Write-Host "[FAIL] evidence file is suspiciously small"; $ok = $false }
    if ($sections -lt 9) { Write-Host "[FAIL] some sections did not render"; $ok = $false }
}
if ($ok) { Write-Host "[OK] Phase 0 evidence collected. 이 파일을 그대로 공유하세요." ; exit 0 }
else     { Write-Host "[FAIL] Phase 0 incomplete — 위 [ERR]/[FAIL] 줄을 그대로 붙여넣고 멈추세요." ; exit 1 }
