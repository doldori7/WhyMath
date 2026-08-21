# Phaiakes9 로컬 LLM 벤치 — 모델별 생성/프롬프트 처리 속도 + GPU 오프로드 비율 실측.
#
# 목적: "GPU가 잡혔다"(오프로드 비율)와 "빠른가"(t/s)를 *분리해서* 잰다. 둘은 다른 실패다.
#   - gpu_fraction ≈ 0  → CPU 폴백 (VGM·백엔드 문제)
#   - gpu_fraction ≈ 1 인데 gen_tps가 기대치의 절반 → 오프로드는 됐으나 느림 (전원·백엔드 문제)
#   - gen_tps가 기대 범위 안 → 이미 메모리 대역폭 한계. 설정 튜닝을 멈추고 모델을 바꾼다.
#   기대치 표 = docs/ops/amd395_local_llm_performance.md §2
#
# 사용법(리포 루트, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label baseline
#   powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label vulkan -Models qwen2.5:7b
#
# 레버를 하나 바꿀 때마다 -Label을 바꿔 실행하면 .gpu_evidence\ 아래에 비교 가능한 CSV가 쌓인다.
#
# 측정 원리: /api/generate(stream=false)가 반환하는 나노초 단위 계측을 그대로 쓴다.
#   gen_tps    = eval_count / (eval_duration / 1e9)              ← 토큰 생성 속도
#   prompt_tps = prompt_eval_count / (prompt_eval_duration / 1e9) ← 프롬프트 처리(prefill) 속도
#   gpu_fraction = /api/ps 의 size_vram / size                    ← `ollama ps` PROCESSOR 열의 기계 판독형

[CmdletBinding()]
param(
    [string]$Label = "run",
    [string[]]$Models = @(),
    [int]$NumPredict = 128,
    [int]$Repeat = 2,
    [int]$PromptRepeat = 8,
    [switch]$WithMoe,
    [switch]$NoUnload,
    [string]$Prompt = "",
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot ".gpu_evidence" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$RunStart = Get-Date        # 로그 tail을 이 시각 이후로 자른다(이전 런의 로그를 이번 런의 증거로 오독 금지)
$Stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$OutFile = Join-Path $OutDir ("bench_" + $Label + "_" + $Stamp + ".csv")

# WhyMath L3 라우터가 실제로 쓰는 로컬 모델 핀 (src/backend/whymath_backend/l3/router.py)
$WhyMathPins = @("qwen2-math:1.5b", "qwen2.5:3b", "qwen2-math:7b", "qwen2.5:7b", "qwen3-vl:8b", "qwen3.5:27b")

# dense(qwen3.5:27b) 대비 MoE 대조군 — -WithMoe 로 추가한다.
# 이 프로젝트에서 가장 값어치 있는 단일 측정: 같은 ~17GB 적재량에서 활성 파라미터만 다른 두 구조의 t/s 차이.
$MoeComparison = @("qwen3:30b-a3b", "qwen3-coder:30b")

# ── 헬퍼 함수 (호출보다 먼저 정의해야 한다 — PowerShell은 위에서 아래로 실행한다) ──

function Get-CommitFreeGB {
    # Windows 커밋 여유(= 이 프로세스가 추가로 커밋할 수 있는 최대치).
    # 2026-08-22 실측: 이 값이 0.9 GB로 마르면 물리 여유 34.9 GB와 무관하게
    # 1.0 GiB 할당조차 실패한다. 로드 실패의 실제 구속 자원이므로 매 측정에 기록한다.
    try { return [math]::Round((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory / 1MB, 1) }
    catch { return -1 }
}

function Get-OrphanLlamaServers {
    # /api/ps 가 비어 있는데 llama-server 가 살아 있으면 고아다.
    # 실패한 로드가 남긴 고아가 커밋을 점유해 *다음* 로드를 실패시키는 자기증식 구조가 실측됐다
    # (2026-08-22: 하루 전 08:47·09:22에 뜬 고아 2개가 커밋 19.3 GB를 잡고 있었다).
    return @(Get-Process llama-server -ErrorAction SilentlyContinue)
}

function Get-HttpErrorBody {
    param($Rec)
    # CLAUDE.md 침묵 실패 금지의 HTTP 축: 500의 *원인*은 예외 타입명이 아니라 응답 본문에 있다.
    # (2026-08-22 실측 사고: 7개 모델이 전부 500이었는데 타입명만 찍혀 원인 판정이 불가능했다.)
    $body = $null
    if ($Rec.ErrorDetails -and $Rec.ErrorDetails.Message) { $body = $Rec.ErrorDetails.Message }
    if (-not $body -and $Rec.Exception.PSObject.Properties.Name -contains "Response" -and $Rec.Exception.Response) {
        try {
            $sr = New-Object System.IO.StreamReader($Rec.Exception.Response.GetResponseStream())
            $body = $sr.ReadToEnd()
            $sr.Close()
        } catch { }
    }
    if ([string]::IsNullOrWhiteSpace($body)) { return "(응답 본문 없음)" }
    return (($body -replace "\s+", " ").Trim())
}

function Remove-LoadedModel {
    # keep_alive=0 으로 즉시 언로드. 모델 간 메모리 간섭을 끊어 500 연쇄를 막는다.
    param([string]$Model)
    try {
        $payload = @{ model = $Model; keep_alive = 0 } | ConvertTo-Json -Depth 3
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        Invoke-RestMethod -Uri ($OllamaHost + "/api/generate") -Method Post -Body $bytes `
                          -ContentType "application/json; charset=utf-8" -TimeoutSec 120 | Out-Null
    } catch {
        Write-Host ("  [WARN] 언로드 실패: " + $_.Exception.GetType().FullName)
    }
}

function Invoke-Generate {
    param([string]$Model, [string]$Text, [int]$Predict)
    $payload = @{
        model   = $Model
        prompt  = $Text
        stream  = $false
        options = @{ num_predict = $Predict; temperature = 0 }
    } | ConvertTo-Json -Depth 5
    # 한국어 프롬프트가 깨지지 않도록 UTF-8 바이트로 직접 보낸다 (PS 기본 인코딩에 맡기지 않는다).
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    return Invoke-RestMethod -Uri ($OllamaHost + "/api/generate") -Method Post -Body $bytes `
                             -ContentType "application/json; charset=utf-8" -TimeoutSec 900
}

function Get-PsInfo {
    param([string]$Model)
    # 반환: gpu_fraction(오프로드 비율) + context_length(실제 적용된 컨텍스트).
    # 컨텍스트는 이 머신의 주요 병목 후보다(2026-08-22 실측: 기본값이 262144로 잡혀 있었다).
    $r = [pscustomobject]@{ frac = -1; ctx = $null }
    try {
        $ps = Invoke-RestMethod -Uri ($OllamaHost + "/api/ps") -TimeoutSec 20
        foreach ($m in $ps.models) {
            if ($m.name -eq $Model -or $m.model -eq $Model) {
                if ($m.size -gt 0) { $r.frac = [math]::Round(($m.size_vram / $m.size), 4) }
                if ($null -ne $m.context_length) { $r.ctx = $m.context_length }
                return $r
            }
        }
        return $r   # 상주 목록에 없음 (이미 언로드됨)
    } catch {
        Write-Host ("[ERR] " + $_.Exception.GetType().FullName + ": /api/ps 조회 실패")
        return $r
    }
}


# ── 프롬프트 (prefill을 재려면 충분히 길어야 한다) ──────────────────────────
if ([string]::IsNullOrWhiteSpace($Prompt)) {
    $unit = "이차함수 y = x^2 - 4x + 3 의 그래프가 x축과 만나는 점의 좌표를 구하는 과정을 단계별로 설명하시오. 각 단계에서 왜 그 변형이 정당한지 근거를 밝히시오. "
    $sb = New-Object System.Text.StringBuilder
    for ($i = 0; $i -lt $PromptRepeat; $i++) { [void]$sb.Append($unit) }
    [void]$sb.Append("위 내용을 요약하지 말고, 마지막 질문에만 답하시오: 이 함수의 두 근의 합은?")
    $Prompt = $sb.ToString()
}

# ── 설치된 모델 확인 → 측정 대상 확정 ────────────────────────────────────────
try {
    $tags = Invoke-RestMethod -Uri ($OllamaHost + "/api/tags") -TimeoutSec 20
} catch {
    Write-Host ("[FAIL] " + $_.Exception.GetType().FullName + ": Ollama 서버에 닿지 못했습니다 (" + $OllamaHost + ")")
    Write-Host "[HINT] 트레이 Ollama가 떠 있는지, 또는 별도 창에서 'ollama serve'가 도는지 확인하세요."
    exit 1
}
# powershell.exe -File 로 실행하면 `-Models a,b` 가 배열이 아니라 *문자열 1개*로 도착한다.
# (2026-08-22 실측 사고: 측정 2회가 "invalid model name" 하나로 통째 공전했다.)
if ($Models.Count -eq 1 -and $Models[0] -match ",") {
    $Models = @($Models[0].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    Write-Host ("[INFO] -Models 를 콤마로 분해: " + $Models.Count + "개")
}

$installed = @($tags.models | ForEach-Object { $_.name })
Write-Host ("[INFO] installed models : " + ($installed -join ", "))

if ($Models.Count -eq 0) {
    $pool = if ($WithMoe) { $WhyMathPins + $MoeComparison } else { $WhyMathPins }
    $Models = @($pool | Where-Object { $installed -contains $_ })
    if ($Models.Count -eq 0) {
        Write-Host "[WARN] WhyMath 핀 모델이 하나도 설치돼 있지 않습니다. 설치된 모델 중 앞 3개로 대체합니다."
        $Models = @($installed | Select-Object -First 3)
    }
}
if ($Models.Count -eq 0) { Write-Host "[FAIL] 측정할 모델이 없습니다. 'ollama pull qwen2.5:7b' 후 다시 실행하세요."; exit 1 }

# 서버에 던지기 전에 이름을 검증한다 — 오타를 500으로 알아내지 않는다.
$unknown = @($Models | Where-Object { $installed -notcontains $_ })
if ($unknown.Count -gt 0) {
    Write-Host ("[FAIL] 설치되지 않은 모델: " + ($unknown -join ", "))
    Write-Host ("[HINT] 설치 목록에서 골라 다시 지정하세요. 콤마 구분, 공백 없이.")
    exit 1
}

# 서버가 실제로 어떤 설정으로 떠 있는지 — 환경변수를 바꾸고 재시작을 안 하면 여기서 드러난다.
$srvLog = Join-Path $env:LOCALAPPDATA "Ollama\server.log"
if (Test-Path $srvLog) {
    $cfg = @(Select-String -Path $srvLog -Pattern 'msg="server config"') | Select-Object -Last 1
    if ($null -ne $cfg) {
        foreach ($k in @("OLLAMA_CONTEXT_LENGTH","OLLAMA_NUM_PARALLEL","OLLAMA_FLASH_ATTENTION","OLLAMA_MAX_LOADED_MODELS","OLLAMA_VULKAN","OLLAMA_IGPU_ENABLE")) {
            $m = [regex]::Match($cfg.Line, [regex]::Escape($k) + ":([^ \]]*)")
            if ($m.Success) { Write-Host ("[SRV ] " + $k.PadRight(26) + "= " + $m.Groups[1].Value) }
        }
        Write-Host "[SRV ] ^ 서버가 기동 시 읽은 값이다. 방금 바꾼 환경변수가 여기 없으면 Ollama 재시작이 안 된 것이다."
    }
}
$commit0 = Get-CommitFreeGB
Write-Host ("[MEM ] CommitFree_GB (시작) = " + $commit0 + "   <- 로드 실패의 실제 구속 자원")
$orph0 = Get-OrphanLlamaServers
if ($orph0.Count -gt 0) {
    $sum = [math]::Round((($orph0 | Measure-Object -Property PrivateMemorySize64 -Sum).Sum)/1GB, 2)
    Write-Host ("[MEM ] llama-server 프로세스 " + $orph0.Count + "개 상주 (합계 커밋 " + $sum + " GB)")
    try {
        $psNow = Invoke-RestMethod -Uri ($OllamaHost + "/api/ps") -TimeoutSec 10
        if ($null -eq $psNow.models -or @($psNow.models).Count -eq 0) {
            Write-Host "[WARN] /api/ps 는 상주 모델 0건인데 llama-server 가 살아 있다 = 고아 프로세스."
            Write-Host "       실패한 로드가 남긴 잔해이며 커밋을 점유해 다음 로드를 실패시킨다."
            Write-Host "       해소: Get-Process ollama*, llama-server | Stop-Process -Force  후 Ollama 재실행."
        }
    } catch { }
}
Write-Host ("[INFO] benchmark target : " + ($Models -join ", "))
Write-Host ("[INFO] prompt chars     : " + $Prompt.Length + " / num_predict : " + $NumPredict + " / repeat : " + $Repeat)
Write-Host ""

$Rows = New-Object System.Collections.ArrayList

foreach ($model in $Models) {
    Write-Host ("=== " + $model + " ===")

    # 워밍업 — 모델 로드 시간을 측정 본체에서 분리한다.
    $loadMs = -1
    try {
        $w = Invoke-Generate -Model $model -Text "1+1=" -Predict 8
        $loadMs = [math]::Round(($w.load_duration / 1e6), 1)
        Write-Host ("  warmup ok  (load_duration = " + $loadMs + " ms)")
    } catch {
        $why = Get-HttpErrorBody $_
        Write-Host ("  [ERR] " + $_.Exception.GetType().Name + " :: " + $why)
        Write-Host ("        CommitFree_GB = " + (Get-CommitFreeGB) + " (실패 직후)")
        [void]$Rows.Add([pscustomobject]@{
            label=$Label; model=$model; run=0; gen_tps=$null; prompt_tps=$null
            eval_count=$null; prompt_eval_count=$null; load_ms=$null; total_ms=$null
            gpu_fraction=$null; context_length=$null; commit_free_gb=(Get-CommitFreeGB)
            error=($_.Exception.GetType().Name + ": " + $why) })
        if (-not $NoUnload) { Remove-LoadedModel -Model $model }
        continue
    }

    $info = Get-PsInfo -Model $model
    $frac = $info.frac
    $ctx  = $info.ctx
    Write-Host ("  gpu_fraction = " + $frac + "   (1.0=전량 GPU / 0.0=전량 CPU / -1=조회 실패)")
    Write-Host ("  context      = " + $(if ($null -ne $ctx) { $ctx } else { "(미보고)" }))

    for ($r = 1; $r -le $Repeat; $r++) {
        try {
            $res = Invoke-Generate -Model $model -Text $Prompt -Predict $NumPredict
            $genTps = if ($res.eval_duration -gt 0) { [math]::Round($res.eval_count / ($res.eval_duration / 1e9), 2) } else { 0 }
            $ppTps  = if ($res.prompt_eval_duration -gt 0) { [math]::Round($res.prompt_eval_count / ($res.prompt_eval_duration / 1e9), 2) } else { 0 }
            $totMs  = [math]::Round(($res.total_duration / 1e6), 1)
            Write-Host ("  run " + $r + " : gen " + $genTps + " t/s | prompt " + $ppTps + " t/s | total " + $totMs + " ms | out " + $res.eval_count + " tok")
            [void]$Rows.Add([pscustomobject]@{
                label=$Label; model=$model; run=$r; gen_tps=$genTps; prompt_tps=$ppTps
                eval_count=$res.eval_count; prompt_eval_count=$res.prompt_eval_count
                load_ms=[math]::Round(($res.load_duration/1e6),1); total_ms=$totMs
                gpu_fraction=$frac; context_length=$ctx; commit_free_gb=(Get-CommitFreeGB); error="" })
        } catch {
            $why = Get-HttpErrorBody $_
            Write-Host ("  [ERR] run " + $r + " : " + $_.Exception.GetType().Name + " :: " + $why)
            [void]$Rows.Add([pscustomobject]@{
                label=$Label; model=$model; run=$r; gen_tps=$null; prompt_tps=$null
                eval_count=$null; prompt_eval_count=$null; load_ms=$null; total_ms=$null
                gpu_fraction=$frac; context_length=$ctx; commit_free_gb=(Get-CommitFreeGB)
                error=($_.Exception.GetType().Name + ": " + $why) })
        }
    }
    if (-not $NoUnload) { Remove-LoadedModel -Model $model }
    Write-Host ""
}

$Rows | Export-Csv -Path $OutFile -NoTypeInformation -Encoding UTF8

# ── 요약 (모델별 중앙값) ─────────────────────────────────────────────────────
Write-Host ("-" * 78)
Write-Host ("요약 — label=" + $Label)
$ok = @($Rows | Where-Object { $_.error -eq "" -and $null -ne $_.gen_tps })
if ($ok.Count -gt 0) {
    $ok | Group-Object model | ForEach-Object {
        $g = $_.Group
        $medGen = ($g.gen_tps | Sort-Object)[[int][math]::Floor($g.Count/2)]
        $medPp  = ($g.prompt_tps | Sort-Object)[[int][math]::Floor($g.Count/2)]
        "{0,-20} gen {1,8} t/s   prompt {2,9} t/s   gpu_fraction {3}   ctx {4}" -f $_.Name, $medGen, $medPp, $g[0].gpu_fraction, $g[0].context_length
    } | ForEach-Object { Write-Host $_ }
}

# ── 실패가 있으면 서버 로그 tail 자동 첨부 (원인 판정 재료를 같은 화면에 모은다) ──
$failed = @($Rows | Where-Object { $_.error -ne "" })
if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host ("-" * 78)
    Write-Host ("실패 " + $failed.Count + "건 — Ollama 서버 로그 tail (원인은 대개 여기 있다)")
    $lg = Join-Path $env:LOCALAPPDATA "Ollama\server.log"
    if (Test-Path $lg) {
        # 이번 실행 이후의 줄만 본다. 이전 런의 로그를 이번 런의 증거로 읽는 오독을 막는다.
        # (2026-08-22 실측 사고: 실행조차 안 된 런에 이전 런의 OOM 로그가 붙어 나왔다.)
        $lines = @(Get-Content $lg -Tail 4000)
        $startIdx = -1
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $m = [regex]::Match($lines[$i], 'time=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})')
            if ($m.Success) {
                $ts = [datetime]::MinValue
                if ([datetime]::TryParse($m.Groups[1].Value, [ref]$ts)) {
                    if ($ts -ge $RunStart) { $startIdx = $i; break }
                }
            }
        }
        if ($startIdx -lt 0) {
            Write-Host "  [중요] 이번 실행 이후 기록된 서버 로그가 없다 — 서버가 모델 로드를 *시도조차 하지 않았다*."
            Write-Host "         요청이 서버에 닿기 전에 거부됐다는 뜻이다(모델명 오류 등). 위 [ERR] 본문을 보라."
        } else {
            $lines[$startIdx..($lines.Count-1)] |
                Select-String -Pattern "level=ERROR|level=WARN|error|memory|unable|failed|insufficient|out of|cudaMalloc|ROCm|vram|num_ctx|n_ctx" |
                Select-Object -Last 30 | ForEach-Object { Write-Host ("  " + $_.Line.Trim()) }
        }
    } else {
        Write-Host ("  [ERR] System.IO.FileNotFoundException: " + $lg)
    }
}

# ── 커밋·고아 프로세스 후처리 보고 ─────────────────────────────────────────
$commit1 = Get-CommitFreeGB
$orph1 = Get-OrphanLlamaServers
Write-Host ("-" * 78)
Write-Host ("[MEM ] CommitFree_GB : 시작 " + $commit0 + " -> 종료 " + $commit1)
if ($orph1.Count -gt 0) {
    $sum1 = [math]::Round((($orph1 | Measure-Object -Property PrivateMemorySize64 -Sum).Sum)/1GB, 2)
    Write-Host ("[MEM ] 종료 시점 llama-server " + $orph1.Count + "개 잔존 (합계 커밋 " + $sum1 + " GB)")
    Write-Host "       다음 실행 전에 정리하지 않으면 커밋이 계속 깎여 실패가 누적된다."
}

# ── 자가검증 ────────────────────────────────────────────────────────────────
Write-Host ("-" * 78)
$pass = $true
if (-not (Test-Path $OutFile)) { Write-Host "[FAIL] CSV was not created"; $pass = $false }
else {
    $n = @(Import-Csv $OutFile).Count
    Write-Host ("[INFO] csv  : " + $OutFile)
    Write-Host ("[INFO] rows : " + $n + " (성공 " + $ok.Count + ")")
    if ($n -lt 1)        { Write-Host "[FAIL] CSV has no rows"; $pass = $false }
    if ($ok.Count -lt 1) { Write-Host "[FAIL] 성공한 측정이 0건입니다 — 위 [ERR] 줄이 원인입니다."; $pass = $false }
}
if ($pass) { Write-Host "[OK] 벤치 완료. 이 CSV를 docs/ops/amd395_local_llm_performance.md §5 진단표에 옮기세요."; exit 0 }
else       { Write-Host "[FAIL] 벤치 실패 — 추정으로 다음 단계 진행 금지."; exit 1 }
