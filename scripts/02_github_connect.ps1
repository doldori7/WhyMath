# =============================================================================
# WhyMath (와이매스) - GitHub 연결 스크립트 (2단계)
# =============================================================================
# 목적: 로컬 저장소를 새로 만든 GitHub Private 레포에 연결하고 첫 푸시 수행
#
# 사전 요구사항:
#   - 1단계 스크립트(01_git_local_setup.ps1) 완료
#   - github.com 에서 'whymath' Private 레포 수동 생성 완료
#     (README/.gitignore/license 모두 체크 해제 상태)
#
# 사용법 (PowerShell):
#   .\scripts\02_github_connect.ps1 -RepoUrl "https://github.com/USERNAME/whymath.git"
#
# 또는 SSH 방식:
#   .\scripts\02_github_connect.ps1 -RepoUrl "git@github.com:USERNAME/whymath.git"
# =============================================================================

# 스크립트 파라미터: GitHub 레포 URL을 필수로 받음
param(
    [Parameter(Mandatory=$true, HelpMessage="GitHub 레포 URL (HTTPS 또는 SSH)")]
    [string]$RepoUrl
)

# 에러 발생 시 즉시 중단
$ErrorActionPreference = "Stop"

# 콘솔 UTF-8 출력 (한글 깨짐 방지)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 프로젝트 루트로 이동
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Write-Host "[INFO] 프로젝트 루트: $ProjectRoot" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 0단계: URL 형식 검증
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 0단계: URL 검증 =====" -ForegroundColor Yellow

# HTTPS 또는 SSH 형식인지 확인
$isHttps = $RepoUrl -match "^https://github\.com/.+/whymath(\.git)?$"
$isSsh = $RepoUrl -match "^git@github\.com:.+/whymath(\.git)?$"

if (-not ($isHttps -or $isSsh)) {
    Write-Host "[ERROR] URL 형식이 올바르지 않습니다." -ForegroundColor Red
    Write-Host "예시 (HTTPS): https://github.com/USERNAME/whymath.git" -ForegroundColor Yellow
    Write-Host "예시 (SSH)  : git@github.com:USERNAME/whymath.git" -ForegroundColor Yellow
    exit 1
}

# .git 접미사가 없으면 추가
if ($RepoUrl -notmatch "\.git$") {
    $RepoUrl = "$RepoUrl.git"
    Write-Host "[INFO] .git 접미사 자동 추가: $RepoUrl" -ForegroundColor Gray
}
Write-Host "[OK] URL 형식 OK: $RepoUrl" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 1단계: 현재 브랜치 확인 (main 이어야 함)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 1단계: 브랜치 확인 =====" -ForegroundColor Yellow

$currentBranch = git branch --show-current
if ($currentBranch -ne "main") {
    Write-Host "[ERROR] 현재 브랜치가 '$currentBranch' 입니다. 'main' 이어야 합니다." -ForegroundColor Red
    Write-Host "01_git_local_setup.ps1을 먼저 실행하세요." -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] 현재 브랜치: main" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 2단계: remote 추가 (이미 있으면 갱신)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 2단계: GitHub remote 추가 =====" -ForegroundColor Yellow

# 기존 origin remote가 있는지 확인
$existingRemote = git remote 2>$null | Select-String -Pattern "^origin$"
if ($existingRemote) {
    # 기존 remote URL 표시
    $oldUrl = git remote get-url origin
    Write-Host "[INFO] 기존 origin: $oldUrl" -ForegroundColor Gray
    Write-Host "[INFO] 새 URL로 갱신..." -ForegroundColor Cyan
    git remote set-url origin $RepoUrl
} else {
    git remote add origin $RepoUrl
}
Write-Host "[OK] origin 설정 완료: $RepoUrl" -ForegroundColor Green

# remote 목록 표시
Write-Host ""
Write-Host "[git remote -v]" -ForegroundColor Cyan
git remote -v

# -----------------------------------------------------------------------------
# 3단계: GitHub로 푸시
# -----------------------------------------------------------------------------
# -u (--set-upstream): 로컬 main과 origin/main을 연결하여 이후 git push만으로 가능
Write-Host ""
Write-Host "===== 3단계: GitHub로 첫 푸시 =====" -ForegroundColor Yellow
Write-Host "[INFO] 인증 창이 뜨면 GitHub 계정으로 로그인하세요" -ForegroundColor Cyan
Write-Host "[INFO] HTTPS 방식이면 Personal Access Token이 필요할 수 있습니다" -ForegroundColor Cyan
Write-Host "       https://github.com/settings/tokens 에서 생성 가능" -ForegroundColor Gray
Write-Host ""

# 푸시 실행
try {
    git push -u origin main
    Write-Host ""
    Write-Host "[OK] 푸시 성공!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "[ERROR] 푸시 실패: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "흔한 원인:" -ForegroundColor Yellow
    Write-Host "  1) GitHub 인증 실패 - Personal Access Token 발급 필요" -ForegroundColor Yellow
    Write-Host "     https://github.com/settings/tokens (repo 권한 체크)" -ForegroundColor Yellow
    Write-Host "  2) 레포지토리에 이미 파일이 있음 (README 등) - 다시 만들 때 모든 옵션 체크 해제" -ForegroundColor Yellow
    Write-Host "  3) 네트워크 문제 또는 방화벽" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "문제 해결 후 다시 실행:" -ForegroundColor Cyan
    Write-Host "  .\scripts\02_github_connect.ps1 -RepoUrl `"$RepoUrl`"" -ForegroundColor Cyan
    exit 1
}

# -----------------------------------------------------------------------------
# 4단계: 최종 확인
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 4단계: 최종 확인 =====" -ForegroundColor Yellow

Write-Host "[git log]" -ForegroundColor Cyan
git log --oneline -5

Write-Host ""
Write-Host "[git branch -vv] (upstream 추적 확인)" -ForegroundColor Cyan
git branch -vv

# 웹 URL 추출 (.git 제거)
$webUrl = $RepoUrl -replace "\.git$", ""
if ($isSsh) {
    # git@github.com:USER/whymath 에서 https://github.com/USER/whymath 로
    $webUrl = $webUrl -replace "^git@github\.com:", "https://github.com/"
}

# -----------------------------------------------------------------------------
# 완료 안내
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================================================" -ForegroundColor Green
Write-Host " [완료] GitHub 연결 완료!" -ForegroundColor Green
Write-Host "=============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "레포지토리: $webUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "이후 작업:" -ForegroundColor Cyan
Write-Host '  git add <파일>             # 파일 추가' -ForegroundColor Gray
Write-Host '  git commit -m "메