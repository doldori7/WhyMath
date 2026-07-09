# S1 탈출 게이트 ① — 실기기 학습 루프 15분 시연 원커맨드 기동 (Windows/Phaiakes9 네이티브).
#
# run_demo.sh(bash)의 PowerShell 미러. 하드 블로커 3종을 한 번에 해소:
#   ① 인증  — WHYMATH_DEMO_AUTH_ENABLED=true + /v1/auth/demo/callback으로 실 JWT 자동 발급 → DEMO_TOKEN
#   ② API_URL — LAN IP를 탐지해 정확한 `flutter run --dart-define=API_URL=...` 명령 출력
#   ③ LLM   — /status로 모드 보고. 이 PC(Phaiakes9)에서 Ollama for Windows 가동 시 코치 라이브
#             (config.py ollama_host 기본 127.0.0.1:11434). 없어도 결정론 경로로 루프 완주.
#
# ★로컬 시연 호스트 전용. JWT 시크릿은 매 실행 런타임 생성(하드코딩 0), DB는 throwaway compose PG.
# 전제: Docker Desktop 실행 중 · src\backend\.venv 세팅 완료(README 참조). 정리: .\scripts\demo\stop_demo.ps1
#
# 사용법(리포 루트, PowerShell):  .\scripts\demo\run_demo.ps1
#   실행정책 오류 시 먼저:        Set-ExecutionPolicy -Scope Process -Bypass

$ErrorActionPreference = "Stop"

# ── 경로·상수 ────────────────────────────────────────────────────────────────
$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackendDir = Join-Path $RepoRoot "src\backend"
$ComposeFile = Join-Path $RepoRoot "docker-compose.demo.yml"
$Port = if ($env:WHYMATH_DEMO_PORT) { $env:WHYMATH_DEMO_PORT } else { "8000" }
$PidFile = Join-Path $RepoRoot ".demo_uvicorn.pid"
$LogFile = Join-Path $RepoRoot ".demo_uvicorn.log"
$ErrFile = Join-Path $RepoRoot ".demo_uvicorn.err.log"

# ── venv 자동 결선(활성 안 했어도 동작 — Scripts를 PATH 선두에) ──────────────────
$VenvScripts = Join-Path $BackendDir ".venv\Scripts"
if (-not (Test-Path (Join-Path $VenvScripts "python.exe"))) {
  throw "venv 없음: $VenvScripts — src\backend에서 'uv venv --python 3.12 .venv' + 'uv pip install -e `".[dev]`"' 먼저(README)."
}
$env:PATH = "$VenvScripts;$env:PATH"

# ── 시연 전용 환경(런타임 생성 시크릿·하드코딩 0) ───────────────────────────────
if (-not $env:WHYMATH_DATABASE_URL) {
  $env:WHYMATH_DATABASE_URL = "postgresql+asyncpg://whymath@127.0.0.1:5432/whymath"
}
$env:WHYMATH_DEMO_AUTH_ENABLED = "true"
if (-not $env:WHYMATH_JWT_SECRET_KEY) {
  $env:WHYMATH_JWT_SECRET_KEY = (python -c "import secrets;print(secrets.token_urlsafe(48))")
}

Write-Host "▶ [1/6] throwaway Postgres 기동…"
docker compose -f $ComposeFile up -d demo-db
if ($LASTEXITCODE -ne 0) { throw "docker compose 실패 — Docker Desktop이 실행 중인지 확인." }
Write-Host "  · PG health 대기…"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  docker compose -f $ComposeFile exec -T demo-db pg_isready -U whymath -d whymath *> $null
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
  Start-Sleep -Seconds 1
}
if (-not $ok) { throw "PG가 시간 내 준비되지 않음." }
Write-Host "  · PG ready."

Write-Host "▶ [2/6] alembic 스키마 마이그레이션(upgrade head)…"
Push-Location $BackendDir
try {
  alembic -c alembic.ini upgrade head
  if ($LASTEXITCODE -ne 0) { throw "alembic upgrade 실패." }
} finally {
  Pop-Location
}

Write-Host "▶ [3/6] 진단 문제 시드(멱등)…"
python (Join-Path $RepoRoot "scripts\demo\seed_demo.py")
if ($LASTEXITCODE -ne 0) { throw "문제 시드 실패." }

Write-Host "▶ [4/6] backend(uvicorn) 기동 — 0.0.0.0:$Port (실기기 LAN 도달)…"
$Uvicorn = Join-Path $VenvScripts "uvicorn.exe"
# -NoNewWindow + 리다이렉트 조합(백그라운드·출력은 로그파일로). -WindowStyle Hidden은
# 리다이렉트와 충돌할 수 있어 -NoNewWindow를 쓴다(현 콘솔 공유·팝업 없음·서버 창 유지).
$proc = Start-Process -FilePath $Uvicorn `
  -ArgumentList @("whymath_backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", $Port) `
  -WorkingDirectory $BackendDir -PassThru -NoNewWindow `
  -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile
$proc.Id | Out-File -FilePath $PidFile -Encoding ascii
Write-Host "  · /health 대기…"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null
    $ok = $true; break
  } catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) { throw "backend가 시간 내 안 떴습니다. 로그 확인: $ErrFile" }
Write-Host "  · backend ready."

Write-Host "▶ [5/6] 데모 토큰 발급(/v1/auth/demo/callback) — 데모 사용자 lazy upsert…"
$Body = '{"code":"demo","redirect_uri":"https://demo/cb"}'
$AccessToken = (Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/v1/auth/demo/callback" `
  -ContentType 'application/json' -Body $Body).access_token
if (-not $AccessToken) { throw "토큰 발급 실패." }

Write-Host "▶ [6/6] LLM 모드·인증 sanity·실행 명령…"
# LLM 모드 보고(블로커 ③).
try {
  $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -TimeoutSec 5
  if ($st.reachable -or $st.cloud_configured) {
    $srcs = @()
    if ($st.reachable) { $srcs += "Ollama(로컬)" }
    if ($st.cloud_configured) { $srcs += "클라우드" }
    Write-Host "  · LLM 모드: 라이브($($srcs -join ' + ')) — 코치 발문/문제 생성 LLM 사용."
  } else {
    Write-Host "  · LLM 모드: 결정론(degraded) — Ollama/키 없음(루프는 완주). Ollama for Windows 가동 확인."
  }
} catch {
  Write-Host "  · /status 조회 실패(무시 가능)."
}

# 인증+시드+비미성년 게이트 통합 sanity(앱 없이 1회).
try {
  Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/me/next-problem" `
    -Headers @{ Authorization = "Bearer $AccessToken" } -TimeoutSec 10 | Out-Null
  Write-Host "  · sanity: /v1/me/next-problem 200 — 인증·시드·비미성년 게이트 OK."
} catch {
  Write-Host "  · sanity: /v1/me/next-problem 비200 — 시드/LLM 상태 확인(루프는 진행 가능할 수 있음)."
}

# LAN IP 탐지(실기기가 붙을 주소) — 기본 게이트웨이가 있는 어댑터의 IPv4를 택한다. Docker/WSL
# 가상 어댑터는 게이트웨이가 없어 자동 배제되므로, 인터넷/LAN 향하는 실제 Wi-Fi·이더넷을 고른다.
$LanIp = $null
$cfg = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
  Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
  Select-Object -First 1
if ($cfg) { $LanIp = ($cfg.IPv4Address.IPAddress | Select-Object -First 1) }
if (-not $LanIp) { $LanIp = "<ipconfig의 Wi-Fi IPv4 주소>" }

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════════════"
Write-Host " 실기기 시연 준비 완료. 패드에서 아래 명령으로 앱을 실행하세요(src\mobile에서·"
Write-Host " 'flutter pub get' + 'dart run build_runner build --delete-conflicting-outputs' 후):"
Write-Host ""
Write-Host "   flutter run --dart-define=API_URL=http://${LanIp}:$Port --dart-define=DEMO_TOKEN=$AccessToken"
Write-Host ""
Write-Host " 앱이 이미 인증된 상태로 부팅됩니다(router가 /problem로 이동) →"
Write-Host " 온보딩→진단→문제→코치(영속 세션)→CoachSignalCard 검증 신호 = 1루프 완주."
Write-Host " 서버는 백그라운드(pid $($proc.Id))에서 돕니다. 로그: $LogFile / $ErrFile"
Write-Host ""
Write-Host " ⚠ 게이트 G-kiki-device-demo는 Kiki가 실기기 15분 루프를 *녹화*할 때까지 PENDING입니다."
Write-Host " 정리: .\scripts\demo\stop_demo.ps1"
Write-Host "════════════════════════════════════════════════════════════════════════"
