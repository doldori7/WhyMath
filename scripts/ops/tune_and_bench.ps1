# Phaiakes9 레버 자동 측정 오케스트레이터 — 설정 적용 → Ollama 재시작 → 검증 → 벤치를 한 번에.
#
# 왜 필요한가: 2026-08-22 진단에서 측정 4회가 *측정 자체가 아닌 이유*로 공전했다 —
#   환경변수 변경 후 Ollama 재시작 누락 2회, 고아 llama-server가 커밋을 잠식 1회, 인자 파싱 1회.
#   그 수작업 단계를 전부 스크립트 안으로 넣는다. 사람은 프리셋 이름만 고른다.
#
# 사용법(리포 루트, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\tune_and_bench.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\tune_and_bench.ps1 -Presets "baseline,resident"
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\tune_and_bench.ps1 -Presets "resident" -Models "qwen2.5:7b"
#
# 각 프리셋마다: ①환경변수 적용 ②Ollama·고아 전부 종료 ③재기동 ④/api/version 대기
#               ⑤server.log의 실효 설정이 의도와 일치하는지 검증(불일치면 중단) ⑥벤치 실행
# 마지막에 프리셋 간 비교표를 출력한다.
#
# 설계 규칙(CLAUDE.md): 자가검증은 변별력 있게(실효 설정 대조·서버 응답 확인),
#   침묵 실패 금지(예외 타입명 로깅), 되돌리는 법 명시(전원 계획 원복 명령 출력).

[CmdletBinding()]
param(
    [string]$Presets = "baseline,resident",
    [string]$Models = "qwen2.5:3b,qwen2.5:7b,qwen3.5:27b,qwen3:30b-a3b",
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [int]$Repeat = 2,
    [switch]$SkipPowerPlan,
    [switch]$PowerMode140W   # EVO-X2 전면 버튼 Performance(140W) 수기 확인 플래그
)

$ErrorActionPreference = "Stop"
# Windows PowerShell 콘솔 출력을 UTF-8로 바꿔 한글이 깨지지 않게 한다.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Bench    = Join-Path $PSScriptRoot "bench_ollama.ps1"
$OutDir   = Join-Path $RepoRoot ".gpu_evidence"

function Get-CommitFreeGB {
    try { return [math]::Round((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory / 1MB, 1) }
    catch { return -1 }
}

function Get-OrphanLlamaServers {
    return @(Get-Process llama-server -ErrorAction SilentlyContinue)
}
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# ── 프리셋 정의 ─────────────────────────────────────────────────────────────
# $null 값은 "이 변수를 제거한다"는 뜻이다(기본 동작으로 되돌린다).
$PresetTable = @{
    "baseline" = @{
        desc = "현행 확정 조건 (ctx 8192 · np 1) — 비교 기준선"
        models   = $null   # $null = 전역 -Models 사용
        noUnload = $false
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "false"; OLLAMA_MAX_LOADED_MODELS = "2"
                  OLLAMA_KEEP_ALIVE = "10m"; OLLAMA_IGPU_ENABLE = $null
                  OLLAMA_VULKAN = "0"; OLLAMA_LLM_LIBRARY = $null }
    }
    "power140" = @{
        desc = "전원 모드 140W (L2) — EVO-X2 전면 버튼 Performance 설정 후 실행"
        models   = $null
        noUnload = $false
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "false"; OLLAMA_MAX_LOADED_MODELS = "2"
                  OLLAMA_KEEP_ALIVE = "10m"; OLLAMA_IGPU_ENABLE = $null
                  OLLAMA_VULKAN = "0"; OLLAMA_LLM_LIBRARY = $null }
    }
    "resident" = @{
        desc = "상주 정책 (L6) — 같은 모델 재방문 시 load_ms 가 0에 수렴하는지"
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "1"; OLLAMA_MAX_LOADED_MODELS = "3"
                  OLLAMA_KEEP_ALIVE = "30m"; OLLAMA_IGPU_ENABLE = $null
                  OLLAMA_VULKAN = "0"; OLLAMA_LLM_LIBRARY = $null }
        # 상주 효과는 *같은 모델을 다시 부를 때* 드러난다. 모델마다 언로드하면 측정 자체가 불가능하다.
        # 3모델 × 2회 방문, MAX_LOADED_MODELS=3 이라 전부 상주해야 한다 → 2회차 load_ms ≈ 0 이 기대값.
        # 모델 합계 0.9+1.8+4.4 = 7.1 GB — 커밋 여유 20 GB 안에 안전하게 들어간다
        # (27B 16.2GB 를 여기 넣으면 3모델 합이 22 GB 로 천장을 넘어 실패가 재현된다).
        models   = "qwen2-math:1.5b,qwen2.5:3b,qwen2.5:7b,qwen2-math:1.5b,qwen2.5:3b,qwen2.5:7b"
        noUnload = $true
    }
    "rocm" = @{
        desc = "ROCm + flash attention (L3 대조군) — vulkan과 IGPU_ENABLE 하나만 다르다"
        # baseline 대비: flash attention만 다름 -> flash 효과 분리
        # vulkan  대비: IGPU_ENABLE만 다름     -> 백엔드 효과 분리
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "1"; OLLAMA_MAX_LOADED_MODELS = "3"
                  OLLAMA_KEEP_ALIVE = "30m"; OLLAMA_IGPU_ENABLE = $null
                  OLLAMA_VULKAN = "0"; OLLAMA_LLM_LIBRARY = $null }
        models   = $null
        noUnload = $false
    }
    "vulkan" = @{
        desc = "Vulkan 백엔드 (L3) — iGPU 장치를 살려 ROCm과 대조"
        models   = $null
        noUnload = $false
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "1"; OLLAMA_MAX_LOADED_MODELS = "3"
                  OLLAMA_KEEP_ALIVE = "30m"; OLLAMA_IGPU_ENABLE = "1"
                  OLLAMA_VULKAN = "1"; OLLAMA_LLM_LIBRARY = $null }
    }
    "vulkan_forced" = @{
        desc = "Vulkan 강제 (L3) — OLLAMA_LLM_LIBRARY=vulkan으로 ROCm 후보를 제외"
        models   = $null
        noUnload = $false
        env  = @{ OLLAMA_CONTEXT_LENGTH = "8192"; OLLAMA_NUM_PARALLEL = "1"
                  OLLAMA_FLASH_ATTENTION = "1"; OLLAMA_MAX_LOADED_MODELS = "3"
                  OLLAMA_KEEP_ALIVE = "30m"; OLLAMA_IGPU_ENABLE = "1"
                  OLLAMA_LLM_LIBRARY = "vulkan" }
    }
}

# ── 헬퍼 (호출보다 먼저 정의한다 — PowerShell은 위에서 아래로 실행한다) ─────
function Write-Head { param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Text
    Write-Host ("=" * 78)
}

function Set-PresetEnv {
    param([hashtable]$EnvMap)
    foreach ($k in $EnvMap.Keys) {
        $v = $EnvMap[$k]
        # User 범위 = 영속, Process 범위 = 지금 우리가 띄울 Ollama 자식 프로세스가 상속받는 값.
        # 둘 다 세워야 "설정했는데 재시작을 안 해서 안 먹는" 사고가 사라진다.
        [Environment]::SetEnvironmentVariable($k, $v, "User")
        [Environment]::SetEnvironmentVariable($k, $v, "Process")
        Write-Host ("  {0,-26} = {1}" -f $k, $(if ($null -eq $v) { "(제거)" } else { $v }))
    }
}

function Stop-OllamaAll {
    $procs = @(Get-Process ollama, "ollama app", llama-server -ErrorAction SilentlyContinue)
    if ($procs.Count -gt 0) {
        Write-Host ("  종료 대상 프로세스 " + $procs.Count + "개")
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 4
    $left = @(Get-Process ollama, "ollama app", llama-server -ErrorAction SilentlyContinue)
    $free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory / 1MB, 1)
    Write-Host ("  잔존 " + $left.Count + "개 · CommitFree_GB = " + $free)
    return $free
}

$script:ServerReadyAt = [datetime]::MinValue

function Start-OllamaServer {
    param([string]$Base)
    # 서버 로그 시간 필터는 기동 직전 시각부터 본다.
    $script:ServerReadyAt = Get-Date
    # 앱(트레이) 실행 파일이 있으면 그것을, 없으면 `ollama serve`를 백그라운드로 띄운다.
    $app = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
    if (Test-Path $app) { Start-Process -FilePath $app | Out-Null ; Write-Host "  트레이 앱 기동" }
    else { Start-Process -FilePath "ollama" -ArgumentList @("serve") -WindowStyle Hidden | Out-Null ; Write-Host "  ollama serve 기동(백그라운드)" }

    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        try {
            $v = Invoke-RestMethod -Uri ($Base + "/api/version") -TimeoutSec 5 -ErrorAction Stop
            Write-Host ("  서버 응답 확인 — version " + $v.version)
            return $true
        } catch { Start-Sleep -Seconds 3 }
    }
    Write-Host "  [FAIL] 90초 안에 서버가 응답하지 않았다."
    return $false
}

function ConvertTo-CanonicalEnvValue {
    # Ollama는 불리언 환경변수를 정규화해 로그에 찍는다("1" -> "true").
    # 표기 차이를 불일치로 판정하면 정상 상태에서 멈추는 오탐이 된다
    # (2026-08-22 실측: FLASH_ATTENTION 기대 '1' / 실제 'true'로 resident 프리셋이 중단됐다).
    param([string]$Value)
    switch -Regex ($Value) {
        '^(1|true|on|yes)$'  { return "true" }
        '^(0|false|off|no)$' { return "false" }
        default              { return $Value }
    }
}

function Test-EffectiveConfig {
    param([hashtable]$Expect)
    # 서버가 *기동 시 읽은* 값을 server.log에서 되읽어 의도와 대조한다.
    # 이 대조가 없으면 "설정했다고 믿고 잰" 값이 그대로 결과가 된다(2026-08-22 2회 공전).
    # 시간 필터 필수 — 이전 기동의 server config 줄을 읽으면 MISS로 멈춘다(2026-08-25 실측).
    $lg = Join-Path $env:LOCALAPPDATA "Ollama\server.log"
    if (-not (Test-Path $lg)) { Write-Host "  [WARN] server.log 없음 — 실효 설정 대조 생략"; return $true }
    $all = @(Get-Content $lg -Tail 2000 | Select-String -Pattern 'msg="server config"')
    $cfg = $null
    foreach ($line in $all) {
        $tm = [regex]::Match($line.Line, 'time=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})')
        if ($tm.Success) {
            $ts = [datetime]::MinValue
            if ([datetime]::TryParse($tm.Groups[1].Value, [ref]$ts) -and $ts -ge $script:ServerReadyAt) {
                $cfg = $line
            }
        }
    }
    if ($null -eq $cfg) { Write-Host "  [WARN] 서버 기동 이후 server config 줄이 없다 — 대조 생략"; return $true }

    $ok = $true
    foreach ($k in @("OLLAMA_CONTEXT_LENGTH","OLLAMA_NUM_PARALLEL","OLLAMA_FLASH_ATTENTION","OLLAMA_MAX_LOADED_MODELS","OLLAMA_IGPU_ENABLE","OLLAMA_VULKAN","OLLAMA_LLM_LIBRARY")) {
        if (-not $Expect.ContainsKey($k)) { continue }
        $want = $Expect[$k]
        $m = [regex]::Match($cfg.Line, [regex]::Escape($k) + ":([^ \]]*)")
        $got = if ($m.Success) { $m.Groups[1].Value } else { "" }
        # 기대가 $null(제거)이면 빈 값이어야 하고, "false"/"1" 같은 값은 문자열로 비교한다.
        $wantStr = if ($null -eq $want) { "" } else { [string]$want }
        # 표기가 아니라 *의미*로 비교한다.
        $match = ((ConvertTo-CanonicalEnvValue $got) -eq (ConvertTo-CanonicalEnvValue $wantStr))
        Write-Host ("  {0} {1,-26} 기대 '{2}' / 실제 '{3}'" -f $(if ($match) { "OK  " } else { "MISS" }), $k, $wantStr, $got)
        if (-not $match) { $ok = $false }
    }
    return $ok
}

function Set-HighPerformancePowerPlan {
    # Windows 고성능 전원 계획(내장 GUID). 전면 버튼의 54/85/140W는 OS에서 못 바꾼다 — 눈으로 확인해야 한다.
    $hp = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    $before = (& powercfg /getactivescheme) 2>&1
    Write-Host ("  현재 전원 계획: " + ($before -join " "))
    $list = (& powercfg /list) 2>&1 | Out-String

    # 목록에서 "고성능" / "High performance" 이름을 가진 항목이 이미 있는지 확인한다.
    # 내장 GUID만 체크하면 복제 후 새 GUID가 활성화돼도 다음 실행 때 또 복제하게 된다(2026-08-23 실측).
    $existing = $null
    foreach ($line in ($list -split "`r?`n")) {
        if ($line -match 'High performance|고성능') {
            $m = [regex]::Match($line, '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')
            if ($m.Success) { $existing = $m.Groups[1].Value; break }
        }
    }

    $target = if ($existing) { $existing } else { $hp }
    if (-not $existing -and $list -notmatch [regex]::Escape($hp)) {
        # 최신 Windows는 고성능 계획을 기본 목록에서 숨긴다. 내장 템플릿에서 복제하면 나타난다.
        # (2026-08-22 실측: Win11 26200에서 목록에 없어 전원 레버 측정 자체를 건너뛰었다.)
        Write-Host "  고성능 계획이 목록에 없다 — 내장 템플릿에서 복제한다."
        $dup = (& powercfg -duplicatescheme $hp) 2>&1 | Out-String
        $m = [regex]::Match($dup, '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')
        if (-not $m.Success) {
            Write-Host ("  [WARN] 복제 실패 — 건너뛴다. 출력: " + ($dup.Trim() -replace "\s+", " "))
            Write-Host "  (전면 버튼 54/85/140W는 어차피 눈으로 확인해야 한다.)"
            return
        }
        $target = $m.Groups[1].Value
        Write-Host ("  복제 완료 — 새 GUID " + $target)
    } elseif ($existing) {
        Write-Host ("  기존 고성능 계획 사용 — GUID " + $existing)
    }
    & powercfg /setactive $target
    $after = (& powercfg /getactivescheme) 2>&1
    Write-Host ("  변경 후: " + ($after -join " "))
    Write-Host ("  [되돌리기] powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e   # 균형 조정")
}

function Get-InferenceComputeLines {
    # 서버 기동 이후(serverReadyAt)에 기록된 inference compute 줄만 추출한다.
    # 이전 기동의 stale 로그를 읽어 "모두 ROCm"처럼 오인하는 도구 결함(2026-08-22 10회차)을 방지한다.
    param([datetime]$Since)
    $lg = Join-Path $env:LOCALAPPDATA "Ollama\server.log"
    if (-not (Test-Path $lg)) { return @() }
    $all = @(Get-Content $lg -Tail 2000 | Select-String -Pattern 'msg="inference compute"')
    $out = @()
    foreach ($line in $all) {
        $tm = [regex]::Match($line.Line, 'time=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})')
        if ($tm.Success) {
            $ts = [datetime]::MinValue
            if ([datetime]::TryParse($tm.Groups[1].Value, [ref]$ts) -and $ts -ge $Since) {
                $out += $line
            }
        }
    }
    return $out
}

# ── 실행 ────────────────────────────────────────────────────────────────────
$presetNames = @($Presets.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$unknown = @($presetNames | Where-Object { -not $PresetTable.ContainsKey($_) })
if ($unknown.Count -gt 0) {
    Write-Host ("[FAIL] 알 수 없는 프리셋: " + ($unknown -join ", "))
    Write-Host ("[HINT] 사용 가능: " + (($PresetTable.Keys | Sort-Object) -join ", "))
    exit 1
}

Write-Head "Phaiakes9 레버 자동 측정 — 프리셋: $($presetNames -join ' -> ')"
Write-Host ("모델: " + $Models)
Write-Host ("반복: " + $Repeat + "회/모델")
Write-Host ("power_mode_140W : " + $PowerMode140W)
if ($presetNames -contains "power140" -and -not $PowerMode140W) {
    Write-Host "⚠️  power140 프리셋이 포함돼 있지만 -PowerMode140W 플래그가 꺼져 있습니다."
    Write-Host "    EVO-X2 전면 버튼을 Performance(140W)로 전환한 뒤 다시 실행하세요."
    Write-Host "    140W 확인 없이 측정하면 '전원' 레버를 구분할 수 없습니다."
}

if (-not $SkipPowerPlan) {
    Write-Head "전원 계획 (L2)"
    Set-HighPerformancePowerPlan
}

$results = New-Object System.Collections.ArrayList
foreach ($name in $presetNames) {
    $p = $PresetTable[$name]
    Write-Head "프리셋 [$name] — $($p.desc)"

    Write-Host "① 환경변수 적용"
    Set-PresetEnv -EnvMap $p.env

    Write-Host "② Ollama·고아 프로세스 전부 종료"
    $freeBefore = Stop-OllamaAll

    Write-Host "③ 재기동"
    if (-not (Start-OllamaServer -Base $OllamaHost)) {
        Write-Host "[FAIL] 서버 기동 실패 — 이 프리셋을 건너뛴다."
        continue
    }

    Write-Host "④ 실효 설정 대조"
    if (-not (Test-EffectiveConfig -Expect $p.env)) {
        Write-Host "[FAIL] 서버가 읽은 값이 의도와 다르다 — 이 상태로 재면 결과가 무의미하다. 중단."
        exit 1
    }

    Write-Host "⑤ 벤치"
    $useModels = if ($p.ContainsKey("models") -and $p.models) { $p.models } else { $Models }
    # $args 는 PowerShell 자동 변수다 — 덮어쓰지 않는다.
    $benchArgs = @("-ExecutionPolicy","Bypass","-File",$Bench,"-Label",$name,"-Models",$useModels,"-Repeat",[string]$Repeat)
    if ($PowerMode140W) { $benchArgs += "-PowerMode140W" }
    if ($p.ContainsKey("noUnload") -and $p.noUnload) {
        $benchArgs += "-NoUnload"
        Write-Host "  (모델 상주 유지 — 재방문 load_ms 로 상주 효과를 잰다)"
    }
    Write-Host ("  모델: " + $useModels)
    & powershell @benchArgs
    $benchExit = $LASTEXITCODE

    Write-Host "⑤-b 서버가 실제로 고른 추론 백엔드 (벤치 후)"
    # 프리셋 이름이 "vulkan"이라고 Vulkan 이 쓰인다는 보장은 없다. 로그가 정본이다.
    $icLines = Get-InferenceComputeLines -Since $script:ServerReadyAt
    if ($icLines.Count -eq 0) {
        Write-Host "  [WARN] 서버 기동 이후 inference compute 줄이 없다 — 백엔드 미확인(이전 기동 줄은 읽지 않는다)"
    } else {
        # 여러 모델 로드 시 같은 백엔드가 반복될 수 있다 — 고유한 (library, compute) 조합만 출력.
        $pairs = @($icLines | ForEach-Object {
            $lm = [regex]::Match($_.Line, 'library=(\S+)')
            $cm = [regex]::Match($_.Line, 'compute=(\S+)')
            $lib = if ($lm.Success) { $lm.Groups[1].Value } else { "?" }
            $comp = if ($cm.Success) { $cm.Groups[1].Value } else { "?" }
            "$lib / $comp"
        } | Sort-Object -Unique)
        foreach ($pair in $pairs) {
            Write-Host ("  backend = $pair")
        }
        # 검증: vulkan/vulkan_forced 프리셋이면 ROCm이 나오면 경고.
        $expectVulkan = ($name -like "vulkan*")
        if ($expectVulkan -and ($pairs -notcontains "vulkan / gfx1151") -and ($pairs -match "ROCm")) {
            Write-Host "  [WARN] 프리셋 이름은 vulkan 인데 서버가 ROCm 을 선택했다 — 라벨 검증 실패"
        }
        if (-not $expectVulkan -and ($pairs -contains "vulkan / gfx1151")) {
            Write-Host "  [WARN] 프리셋 이름은 ROCm 계열인데 서버가 Vulkan 을 선택했다 — 라벨 검증 실패"
        }
    }

    $csv = @(Get-ChildItem -Path $OutDir -Filter ("bench_" + $name + "_*.csv") | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    $freeAfter = Get-CommitFreeGB
    $orphAfter = (Get-OrphanLlamaServers).Count
    [void]$results.Add([pscustomobject]@{
        preset = $name; exit = $benchExit
        commit_free_before = $freeBefore
        commit_free_after = $freeAfter
        orphan_count = $orphAfter
        csv = $(if ($csv.Count -gt 0) { $csv[0].FullName } else { "(없음)" })
    })
}

# ── 프리셋 간 비교표 ────────────────────────────────────────────────────────
Write-Head "프리셋 비교"
foreach ($r in $results) {
    Write-Host ("[" + $r.preset + "] exit=" + $r.exit + " · CommitFree " + $r.commit_free_before + " -> " + $r.commit_free_after + " GB · orphan=" + $r.orphan_count)
    if ($r.csv -ne "(없음)") {
        $rows = @(Import-Csv $r.csv | Where-Object { $_.error -eq "" -and $_.gen_tps })
        $rows | Group-Object model | ForEach-Object {
            $g = $_.Group
            $mi = [int][math]::Floor(($g.Count - 1) / 2)
            $gen = @($g.gen_tps | ForEach-Object { [double]$_ } | Sort-Object)[$mi]
            $pp  = @($g.prompt_tps | ForEach-Object { [double]$_ } | Sort-Object)[$mi]
            $ld  = @($g.load_ms | ForEach-Object { [double]$_ } | Sort-Object)[$mi]
            $cf  = @($g.commit_free_gb | ForEach-Object { [double]$_ } | Sort-Object)[$mi]
            $or  = @($g.orphan_llama_servers | ForEach-Object { [int]$_ } | Sort-Object)[$mi]
            Write-Host ("    {0,-20} gen {1,7:N1} t/s   prompt {2,8:N0} t/s   load {3,7:N0} ms   CommitFree {4,5}GB   orphan {5}" -f $_.Name, $gen, $pp, $ld, $cf, $or)
        }
    }
}

Write-Host ""
Write-Host ("-" * 78)
$failed = @($results | Where-Object { $_.exit -ne 0 })
if ($failed.Count -eq 0 -and $results.Count -gt 0) {
    Write-Host "[OK] 전 프리셋 측정 완료. 위 비교표와 .gpu_evidence\ CSV를 공유하세요."
    exit 0
}
Write-Host ("[FAIL] 실패 프리셋 " + $failed.Count + "건 — 해당 구간의 [ERR] 줄을 보세요.")
exit 1
