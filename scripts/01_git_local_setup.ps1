# =============================================================================
# WhyMath (와이매스) - 로컬 Git 정리 스크립트 (1단계)
# =============================================================================
# 목적: GitHub 푸시 전, 로컬 git 저장소를 깨끗하게 정리합니다.
#
# 수행 작업:
#   1. stale .git/index.lock 파일 제거
#   2. zip 파일을 git 추적에서 제거 (파일 자체는 그대로 보존)
#   3. .gitignore 보강 (zip, 사업계획서 등 민감 파일 패턴 추가)
#   4. 변경사항 staging 및 commit
#   5. master 에서 main 으로 브랜치 이름 변경
#
# 사용법 (PowerShell):
#   cd C:\Users\kiki\Desktop\__AI\WhyMath
#   .\scripts\01_git_local_setup.ps1
#
# 주의:
#   - 이 스크립트는 멱등(idempotent)하게 설계되었습니다 (여러 번 실행해도 안전)
#   - 각 단계 실패 시 즉시 중단하고 에러 메시지 출력
# =============================================================================

# 에러 발생 시 즉시 스크립트 중단
$ErrorActionPreference = "Stop"

# 콘솔 출력을 UTF-8로 설정 (한글 깨짐 방지)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 프로젝트 루트 경로 (스크립트 위치 기준 상위 폴더)
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Write-Host "[INFO] 프로젝트 루트: $ProjectRoot" -ForegroundColor Cyan

# 프로젝트 루트로 이동
Set-Location $ProjectRoot

# -----------------------------------------------------------------------------
# 0단계: 사전 확인 - .git 폴더 존재 여부
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 0단계: 사전 환경 확인 =====" -ForegroundColor Yellow

if (-not (Test-Path ".git")) {
    Write-Host "[ERROR] .git 폴더가 없습니다. 이 폴더는 git 저장소가 아닙니다." -ForegroundColor Red
    exit 1
}

# git 명령 사용 가능 여부 확인
try {
    $gitVersion = git --version
    Write-Host "[OK] $gitVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] git이 설치되어 있지 않거나 PATH에 없습니다." -ForegroundColor Red
    Write-Host "https://git-scm.com/download/win 에서 설치 후 재시도하세요." -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------------
# 1단계: stale .git/index.lock 제거
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 1단계: stale index.lock 제거 =====" -ForegroundColor Yellow

$lockFile = ".git\index.lock"
if (Test-Path $lockFile) {
    # 강제 제거 (읽기 전용 속성이라도 무시)
    Remove-Item $lockFile -Force
    Write-Host "[OK] index.lock 제거 완료" -ForegroundColor Green
} else {
    Write-Host "[SKIP] index.lock 없음 (이미 정리됨)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 2단계: 현재 git 상태 표시
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 2단계: 현재 git 상태 =====" -ForegroundColor Yellow
git status --short
Write-Host ""
$curBranch = git branch --show-current
Write-Host "[현재 브랜치] $curBranch" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 3단계: zip 파일을 git 추적에서 제거
# -----------------------------------------------------------------------------
# git rm --cached: working tree의 파일은 그대로 두고 index에서만 제거
# 사용자가 이미 zip 파일을 다른 곳으로 옮겼더라도 git 이력에는 남아있음
Write-Host ""
Write-Host "===== 3단계: zip 파일 추적 해제 =====" -ForegroundColor Yellow

$zipFiles = git ls-files | Select-String -Pattern "\.zip$"
if ($zipFiles) {
    foreach ($f in $zipFiles) {
        $filename = $f.ToString()
        Write-Host "  추적 해제: $filename" -ForegroundColor Gray
        # --ignore-unmatch: 파일이 이미 없어도 에러 안 냄
        git rm --cached --ignore-unmatch "$filename"
    }
    Write-Host "[OK] zip 파일 추적 해제 완료" -ForegroundColor Green
} else {
    Write-Host "[SKIP] 추적 중인 zip 파일 없음" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 4단계: .gitignore 보강
# -----------------------------------------------------------------------------
# 기존 .gitignore에 zip, 사업계획서, 비공개 문서 패턴 추가
# 이미 같은 패턴이 있으면 추가하지 않음 (멱등성)
Write-Host ""
Write-Host "===== 4단계: .gitignore 보강 =====" -ForegroundColor Yellow

$gitignorePath = ".gitignore"
$existingContent = ""
if (Test-Path $gitignorePath) {
    $existingContent = Get-Content $gitignorePath -Raw -Encoding UTF8
}

# 추가할 패턴 (마커로 중복 추가 방지)
$marker = "# WhyMath 추가 보안 패턴 (자동 생성)"

if ($existingContent -notmatch [regex]::Escape($marker)) {
    # 새 패턴을 한 줄씩 배열로 정의 (here-string 회피하여 파싱 오류 방지)
    $newLines = @(
        "",
        "",
        $marker,
        "# 대용량 아카이브 파일 (의도적 추가 시 git add -f 사용)",
        "*.zip",
        "*.tar.gz",
        "*.tar.bz2",
        "*.7z",
        "*.rar",
        "",
        "# 비공개 사업/기획 문서 (민감 정보)",
        "*사업계획*",
        "*business_plan*",
        "*business-plan*",
        "internal/",
        "private/",
        "docs/private/",
        "docs/internal/",
        "",
        "# Office 임시 파일",
        '~$*.docx',
        '~$*.xlsx',
        '~$*.pptx',
        "",
        "# 환경변수, 시크릿 추가 패턴",
        ".env.*",
        "*.env",
        "config/secrets.yaml",
        "config/secrets.yml",
        "credentials.json",
        "service-account.json",
        "",
        "# LLM, API 키 캐시",
        ".openai_cache/",
        ".anthropic_cache/",
        ".langfuse_cache/",
        "",
        "# 데이터셋 캐시",
        "*.parquet.gz",
        "*.arrow",
        "data/cache/"
    )

    # 한 줄씩 추가 (UTF8 인코딩)
    Add-Content -Path $gitignorePath -Value $newLines -Encoding UTF8
    Write-Host "[OK] .gitignore 보강 완료" -ForegroundColor Green
} else {
    Write-Host "[SKIP] .gitignore 이미 보강됨" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 5단계: git 사용자 정보 확인
# -----------------------------------------------------------------------------
# 커밋 작성자 정보가 설정되어 있지 않으면 에러
Write-Host ""
Write-Host "===== 5단계: git 사용자 정보 확인 =====" -ForegroundColor Yellow

$userName = git config user.name
$userEmail = git config user.email

if ([string]::IsNullOrWhiteSpace($userName) -or [string]::IsNullOrWhiteSpace($userEmail)) {
    Write-Host "[WARN] git user.name 또는 user.email이 설정되지 않았습니다." -ForegroundColor Yellow
    Write-Host '권장: git config --global user.name "Kiki"' -ForegroundColor Yellow
    Write-Host '      git config --global user.email "rollrock.ki@gmail.com"' -ForegroundColor Yellow
    Write-Host ""
    Write-Host "임시로 로컬 저장소에 설정합니다..." -ForegroundColor Cyan
    git config user.name "Kiki"
    git config user.email "rollrock.ki@gmail.com"
    $userName = "Kiki"
    $userEmail = "rollrock.ki@gmail.com"
}
# < > 대신 괄호 사용 (PowerShell 예약 문자 회피)
Write-Host "[OK] 작성자: $userName ($userEmail)" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 6단계: 변경사항 staging 및 commit
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 6단계: 변경사항 staging 및 commit =====" -ForegroundColor Yellow

# 현재 변경사항 모두 추가 (삭제, 수정, 신규 모두 포함)
git add -A

# staged 변경사항 확인
$staged = git diff --cached --name-only
if ($staged) {
    Write-Host "[INFO] 커밋할 파일:" -ForegroundColor Cyan
    $staged | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    # 의미 있는 커밋 메시지 (CLAUDE.md 권장 형식)
    # here-string 대신 -m 여러 개로 멀티라인 처리 (파싱 오류 방지)
    git commit `
        -m "chore: prepare repo for GitHub publish" `
        -m "- Remove tracked zip archives (files.zip, WhyMath_harness.zip)" `
        -m "- Strengthen .gitignore with business plan and secret patterns" `
        -m "- Sync .claude/settings.json local changes" `
        -m "Refs: CLAUDE.md L2 + absolute taboo list"
    Write-Host "[OK] 커밋 완료" -ForegroundColor Green
} else {
    Write-Host "[SKIP] staged 변경사항 없음" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 7단계: master 에서 main 으로 브랜치 이름 변경
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 7단계: master 에서 main 으로 브랜치 변경 =====" -ForegroundColor Yellow

$currentBranch = git branch --show-current
if ($currentBranch -eq "master") {
    git branch -m master main
    Write-Host "[OK] master 에서 main 으로 변경 완료" -ForegroundColor Green
} elseif ($currentBranch -eq "main") {
    Write-Host "[SKIP] 이미 main 브랜치" -ForegroundColor Gray
} else {
    Write-Host "[WARN] 현재 브랜치가 '$currentBranch'입니다. 수동 처리 필요." -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# 8단계: 최종 상태 보고
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== 8단계: 최종 상태 보고 =====" -ForegroundColor Yellow

Write-Host ""
Write-Host "[git log] 최근 커밋 5개:" -ForegroundColor Cyan
git log --oneline -5

Write-Host ""
Write-Host "[git branch] 현재 브랜치:" -ForegroundColor Cyan
git branch -v

Write-Host ""
Write-Host "[git status] 작업 트리 상태:" -ForegroundColor Cyan
git status --short

Write-Host ""
Write-Host "[ls-files] 추적 중인 큰 파일 (50KB 이상):" -ForegroundColor Cyan
git ls-files | ForEach-Object {
    if (Test-Path $_) {
        $size = (Get-Item $_).Length
        if ($size -gt 51200) {
            $sizeFmt = "{0,10}" -f $size
            Write-Host "  $sizeFmt bytes  $_" -ForegroundColor Gray
        }
    }
}

# -----------------------------------------------------------------------------
# 완료 안내
# ----------------------------