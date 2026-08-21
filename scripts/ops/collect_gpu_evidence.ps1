# Phaiakes9 (Ryzen AI Max+ 395 / Radeon 8060S) GPU 추론 증거 수집기 — Phase 0.
#
# 목적: "GPU가 잡히는가"를 추측이 아니라 파일 하나로 남긴다. 수집 항목 =
#   ① 시스템(CPU·RAM·메모리 속도)  ② GPU 카브아웃 실측(= VGM 반영값)  ③ GPU 컨트롤러
#   ④ 전용 VRAM 레지스트리(권한 있을 때)  ⑤ 전원 계획  ⑥ Ollama REST  ⑦ Ollama CLI
#   ⑧ 관련 환경변수  ⑨ Ollama 서버 로그의 GPU 탐지 줄
#
# 사용법(리포 루트, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\collect_gpu_evidence.ps1
#   dxdiag까지 받고 싶으면(느리고 실패 잦음):  ... collect_gpu_evidence.ps1 -WithDxdiag
#
# 설계 규칙(CLAUDE.md):
#   - 침묵 실패 금지: 각 수집 단계는 실패해도 계속하되 [ERR] + *예외 타입명*을 반드시 남긴다.
#   - 증거 유실 금지: 섹션마다 파일에 즉시 append 한다. 중간에 멈춰도 거기까지가 디스크에 남는다.
#     (v1 실측 사고 2026-08-22: ollama CLI가 §6에서 무한 대기 → 마지막에 한 번만 쓰는 설계라
#      앞서 수집한 5개 섹션이 통째로 유실됐다. 파일이 아예 안 생겼다.)
#   - 외부 프로세스는 전부 타임아웃: 멈추는 명령은 "멈춘다"는 증거를 남기고 강제 종료한다.
#   - 변별력 있는 자가검증: 산출 파일의 섹션 수를 되읽어 [OK]/[FAIL] + exit code로 판정한다.

[CmdletBinding()]
param(
    [string]$OutDir = "",
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [switch]$WithDxdiag,
    [int]$NativeTimeoutSec = 20
)

$ErrorActionPreference = "Continue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot ".gpu_evidence" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$Stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$OutFile = Join-Path $OutDir ("evidence_" + $Stamp + ".txt")
Set-Content -Path $OutFile -Value "" -Encoding UTF8

# ── 출력 = 화면 + 파일 즉시 append (중간에 멈춰도 증거가 남는다) ─────────────
function Add-Line {
    param([string]$Text = "")
    Write-Host $Text
    Add-Content -Path $OutFile -Value $Text -Encoding UTF8
}

function Add-Section {
    param([string]$Title, [scriptblock]$Body)
    Add-Line ""
    Add-Line ("=" * 78)
    Add-Line ("## " + $Title)
    Add-Line ("=" * 78)
    try {
        $out = & $Body
        if ($null -ne $out) {
            foreach ($l in ($out | Out-String -Width 200).TrimEnd().Split("`n")) { Add-Line $l.TrimEnd() }
        }
    } catch {
        # 예외 타입명 필수 (무타입 경고 금지 — CLAUDE.md)
        Add-Line ("[ERR] " + $_.Exception.GetType().FullName + ": " + $_.Exception.Message)
    }
}

# ── 외부 실행파일 호출: 반드시 타임아웃 (멈추면 증거를 남기고 죽인다) ────────
function Invoke-Native {
    param([string]$File, [string[]]$Arguments = @(), [int]$TimeoutSec = 0)
    if ($TimeoutSec -le 0) { $TimeoutSec = $NativeTimeoutSec }
    $o = [System.IO.Path]::GetTempFileName()
    $e = [System.IO.Path]::GetTempFileName()
    try {
        $sp = @{ FilePath = $File; NoNewWindow = $true; PassThru = $true
                 RedirectStandardOutput = $o; RedirectStandardError = $e }
        if ($Arguments.Count -gt 0) { $sp["ArgumentList"] = $Arguments }
        $p = Start-Process @sp
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            try { $p.Kill() } catch {}
            return ("[TIMEOUT] " + $File + " " + ($Arguments -join " ") + " — " + $TimeoutSec +
                    "초 초과로 강제 종료. 이 명령이 멈춘다는 것 자체가 증상이다(서버 미기동·좀비 프로세스 의심).")
        }
        Start-Sleep -Milliseconds 150   # 리다이렉트 파일 flush 여유
        $txt = ((Get-Content $o -Raw -ErrorAction SilentlyContinue) +
                (Get-Content $e -Raw -ErrorAction SilentlyContinue))
        if ([string]::IsNullOrWhiteSpace($txt)) { return ("(출력 없음, exit=" + $p.ExitCode + ")") }
        return $txt.TrimEnd()
    } catch {
        return ("[ERR] " + $_.Exception.GetType().FullName + ": " + $_.Exception.Message)
    } finally {
        Remove-Item $o, $e -Force -ErrorAction SilentlyContinue
    }
}

Add-Line "WhyMath / Phaiakes9 GPU evidence"
Add-Line ("collected_at : " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K"))
Add-Line ("hostname     : " + $env:COMPUTERNAME)
Add-Line ("repo_root    : " + $RepoRoot)
Add-Line ("git_branch   : " + (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null))
Add-Line ("git_commit   : " + (& git -C $RepoRoot rev-parse --short HEAD 2>$null))
Add-Line ("elevated     : " + ([Security.Principal.WindowsPrincipal]::new(
                                [Security.Principal.WindowsIdentity]::GetCurrent()
                              ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)))

Add-Section "1. System (CPU / RAM / memory speed)" {
    Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-List
    $cs = Get-CimInstance Win32_ComputerSystem
    "TotalPhysicalMemory_GB : {0:N1}   (Windows 가용)" -f ($cs.TotalPhysicalMemory / 1GB)
    "Manufacturer/Model     : {0} / {1}" -f $cs.Manufacturer, $cs.Model
    Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel, Capacity, Speed, ConfiguredClockSpeed | Format-Table -AutoSize
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List
}

Add-Section "2. GPU carve-out (= VGM 반영값 · 관리자 권한 불요)" {
    # 핵심 판정치. UMA 머신에서 GPU에 떼어 준 메모리는
    #   (설치된 물리 메모리 합) - (Windows가 보는 가용 메모리) 로 나온다.
    # 레지스트리·dxdiag가 막혀도 이 값은 항상 나온다.
    $installed = ((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum) / 1GB
    $visible   = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    $carve     = $installed - $visible
    "installed_physical_GB : {0:N1}" -f $installed
    "windows_visible_GB    : {0:N1}" -f $visible
    "gpu_carveout_GB       : {0:N1}   <- VGM + 펌웨어 예약" -f $carve
    ""
    if ($carve -lt 8)      { "판정: 카브아웃이 너무 작다 — Adrenalin에서 가변 그래픽 메모리를 올려야 한다(문서 §3 L1)." }
    elseif ($carve -gt 100){ "판정: 카브아웃 과다 — OS·개발 스택 여유가 부족하다. 64GB로 낮추는 것을 검토(문서 §3 L1)." }
    else                   { "판정: 카브아웃 정상 범위. WhyMath 모델 총합 상주 소요는 약 30~35GB(문서 §3 L1)." }
}

Add-Section "3. GPU (video controllers)" {
    Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion, DriverDate, VideoProcessor, VideoModeDescription, PNPDeviceID, Status |
        Format-List
    "(주의) Win32_VideoController.AdapterRAM 은 4GB에서 wrap 되어 신뢰 불가 — §2 카브아웃을 쓴다."
}

Add-Section "4. Dedicated VRAM (registry / dxdiag) - 보조 확인" {
    $base = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try {
        Get-ChildItem $base -ErrorAction Stop | ForEach-Object {
            $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if ($null -ne $p -and $null -ne $p."HardwareInformation.qwMemorySize") {
                $bytes = [uint64]$p."HardwareInformation.qwMemorySize"
                "{0,-6} {1,-40} dedicated = {2,10:N0} MB ({3:N1} GB)" -f $_.PSChildName, $p.DriverDesc, ($bytes/1MB), ($bytes/1GB)
            }
        }
    } catch {
        "[ERR] " + $_.Exception.GetType().FullName + ": " + $_.Exception.Message
        "(이 키는 관리자 권한이 필요할 수 있다. §2 카브아웃으로 대체 판정하므로 실패해도 무방하다.)"
    }

    if ($WithDxdiag) {
        $dx = Join-Path $env:TEMP ("whymath_dxdiag_" + $Stamp + ".txt")
        Start-Process -FilePath "dxdiag" -ArgumentList @("/t", $dx) -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $deadline) {
            if (Test-Path $dx) { $sz = (Get-Item $dx).Length ; Start-Sleep -Seconds 2 ; if ((Get-Item $dx).Length -eq $sz -and $sz -gt 0) { break } }
            else { Start-Sleep -Seconds 2 }
        }
        if (Test-Path $dx) {
            Select-String -Path $dx -Pattern "Card name|Display Memory|Dedicated Memory|Shared Memory|Chip type" |
                ForEach-Object { $_.Line.Trim() }
            Remove-Item $dx -Force -ErrorAction SilentlyContinue
        } else {
            "[ERR] System.IO.FileNotFoundException: dxdiag output not produced within 60s"
        }
    } else {
        "(dxdiag 건너뜀 — 느리고 실패가 잦다. 필요하면 -WithDxdiag 로 실행한다.)"
    }
}

Add-Section "5. Power plan / power mode" {
    Invoke-Native -File "powercfg" -Arguments @("/getactivescheme") -TimeoutSec 15
    "--- (참고) EVO-X2 전면 버튼: Quiet 54W / Balanced 85W / Performance 140W — OS에서는 안 보인다. 눈으로 확인할 것."
}

Add-Section "6. Ollama REST (/api/version, /api/ps) - 서버가 살아 있는지 먼저" {
    # CLI보다 REST를 먼저 본다. CLI는 서버 상태에 따라 멈출 수 있기 때문이다(v1 실측 사고).
    try {
        $v = Invoke-RestMethod -Uri ($OllamaHost + "/api/version") -TimeoutSec 10 -ErrorAction Stop
        "api_version : " + $v.version
        "server      : UP (" + $OllamaHost + ")"
    } catch {
        "server      : DOWN 또는 무응답 — " + $_.Exception.GetType().FullName
        "(트레이 Ollama가 꺼져 있거나, 다른 프로세스가 11434를 점유 중일 수 있다.)"
        return
    }
    try {
        $ps = Invoke-RestMethod -Uri ($OllamaHost + "/api/ps") -TimeoutSec 15 -ErrorAction Stop
        if ($null -eq $ps.models -or @($ps.models).Count -eq 0) {
            "loaded_models : (none) — 상주 모델 없음. 벤치 전이라면 정상."
        } else {
            foreach ($m in $ps.models) {
                $frac = if ($m.size -gt 0) { [math]::Round(($m.size_vram / $m.size), 4) } else { 0 }
                "{0,-24} size={1,8:N0} MB  size_vram={2,8:N0} MB  gpu_fraction={3}" -f $m.name, ($m.size/1MB), ($m.size_vram/1MB), $frac
            }
            "--- gpu_fraction 1.0 = 전량 GPU / 0.0 = 전량 CPU ('ollama ps'의 PROCESSOR 열의 기계 판독형)"
        }
    } catch {
        "[ERR] " + $_.Exception.GetType().FullName + ": /api/ps 조회 실패"
    }
    try {
        $tags = Invoke-RestMethod -Uri ($OllamaHost + "/api/tags") -TimeoutSec 20 -ErrorAction Stop
        "--- installed models (/api/tags) ---"
        foreach ($m in $tags.models) { "{0,-28} {1,8:N1} GB" -f $m.name, ($m.size/1GB) }
    } catch {
        "[ERR] " + $_.Exception.GetType().FullName + ": /api/tags 조회 실패"
    }
}

Add-Section "7. Ollama CLI (타임아웃 보호)" {
    "--- ollama --version ---"
    Invoke-Native -File "ollama" -Arguments @("--version")
    "--- ollama ps ---"
    Invoke-Native -File "ollama" -Arguments @("ps")
    "(CLI가 [TIMEOUT]으로 끝나면 서버 미기동·좀비 프로세스 신호다. §6의 REST 결과와 대조할 것.)"
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
                Select-String -Pattern "gfx|ROCm|rocm|Vulkan|vulkan|HIP|hip|library|inference compute|amdgpu|8060S|VRAM|no compatible GPUs" |
                Select-Object -Last 40 | ForEach-Object { $_.Line.Trim() }
        }
    }
    if (-not $found) { "[ERR] System.IO.FileNotFoundException: no Ollama server.log/app.log under " + $env:LOCALAPPDATA + "\Ollama" }
}

# ── 자가검증 (변별력 있는 검사: 존재 + 크기 + 섹션 수) ───────────────────────
Add-Line ""
Add-Line ("-" * 78)
$ok = $true
if (-not (Test-Path $OutFile)) { Write-Host "[FAIL] evidence file was not created"; $ok = $false }
else {
    $size = (Get-Item $OutFile).Length
    $sections = @(Select-String -Path $OutFile -Pattern "^## \d\.").Count
    Write-Host ("[INFO] file     : " + $OutFile)
    Write-Host ("[INFO] size     : " + $size + " bytes")
    Write-Host ("[INFO] sections : " + $sections + " / 9")
    if ($size -lt 500)   { Write-Host "[FAIL] evidence file is suspiciously small"; $ok = $false }
    if ($sections -lt 9) { Write-Host "[FAIL] some sections did not render — 파일의 마지막 '## N.' 이 멈춘 지점이다"; $ok = $false }
}
if ($ok) { Write-Host "[OK] Phase 0 evidence collected. 이 파일을 그대로 공유하세요." ; exit 0 }
else     { Write-Host "[FAIL] Phase 0 incomplete — 위 [ERR]/[FAIL]/[TIMEOUT] 줄과 파일을 그대로 붙여넣고 멈추세요." ; exit 1 }
