# S1 시연 정리(Windows) — uvicorn 종료 + throwaway Postgres(볼륨째) 제거.
# 사용법(리포 루트, PowerShell):  .\scripts\demo\stop_demo.ps1

$ErrorActionPreference = "SilentlyContinue"

$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ComposeFile = Join-Path $RepoRoot "docker-compose.demo.yml"
$PidFile = Join-Path $RepoRoot ".demo_uvicorn.pid"

# $pid는 PowerShell 예약 자동변수라 $procId를 쓴다.
if (Test-Path $PidFile) {
  $procId = (Get-Content $PidFile | Select-Object -First 1)
  if ($procId) {
    Write-Host "▶ uvicorn 종료(pid=$procId)…"
    Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $PidFile -Force
}

Write-Host "▶ throwaway Postgres 제거(볼륨 포함)…"
docker compose -f $ComposeFile down -v

Write-Host "정리 완료."
