# Auto Version Detection based on Conventional Commits
# Windows PowerShell 전용 버전

param(
    [string]$BaseBranch = "main"
)

$ErrorActionPreference = "Stop"

Write-Host "버전 자동 결정 (Conventional Commits 분석)" -ForegroundColor Cyan
Write-Host ""

# 현재 버전 가져오기 (package.json 또는 pyproject.toml)
$currentVersion = "0.0.0"

if (Test-Path "package.json") {
    $packageJson = Get-Content "package.json" -Raw | ConvertFrom-Json
    $currentVersion = $packageJson.version
    Write-Host "현재 버전 (package.json): $currentVersion" -ForegroundColor Gray
} elseif (Test-Path "pyproject.toml") {
    $pyproject = Get-Content "pyproject.toml" -Raw
    if ($pyproject -match 'version\s*=\s*"([^"]+)"') {
        $currentVersion = $matches[1]
        Write-Host "현재 버전 (pyproject.toml): $currentVersion" -ForegroundColor Gray
    }
}

# 버전 파싱
$versionParts = $currentVersion -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
$patch = [int]$versionParts[2]

# 커밋 히스토리 분석
Write-Host ""
Write-Host "커밋 히스토리 분석 중..." -ForegroundColor Cyan

$commits = & git log --oneline "$BaseBranch..HEAD" 2>$null
if (-not $commits) {
    Write-Host "⚠️  $BaseBranch 이후 커밋이 없습니다." -ForegroundColor Yellow
    exit 0
}

Write-Host "분석 대상 커밋:" -ForegroundColor Gray
$commits | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host ""

# 버전 변경 타입 결정
$bumpType = "patch"
$isBreaking = $false
$hasFeature = $false
$hasFix = $false

foreach ($commit in $commits) {
    if ($commit -match "BREAKING CHANGE" -or $commit -match "!:") {
        $isBreaking = $true
    }
    if ($commit -match "^[a-f0-9]+\s+feat(\(.+\))?:") {
        $hasFeature = $true
    }
    if ($commit -match "^[a-f0-9]+\s+fix(\(.+\))?:") {
        $hasFix = $true
    }
}

# 버전 결정
if ($isBreaking) {
    $bumpType = "major"
    $major++
    $minor = 0
    $patch = 0
} elseif ($hasFeature) {
    $bumpType = "minor"
    $minor++
    $patch = 0
} elseif ($hasFix) {
    $bumpType = "patch"
    $patch++
} else {
    $bumpType = "patch"
    $patch++
}

$newVersion = "$major.$minor.$patch"

# 결과 출력
Write-Host "=" * 60
Write-Host ""

if ($isBreaking) {
    Write-Host "⚠️  BREAKING CHANGE 감지!" -ForegroundColor Yellow
    Write-Host "   버전 변경: $currentVersion → $newVersion (MAJOR)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⏸️  사용자 확인 필요" -ForegroundColor Yellow
    Write-Host "   Breaking changes는 영향도 검토가 필요합니다." -ForegroundColor Gray
    Write-Host ""

    # JSON 출력 (파이프라인용)
    $result = @{
        currentVersion = $currentVersion
        newVersion = $newVersion
        bumpType = $bumpType
        requiresApproval = $true
        reason = "BREAKING CHANGE detected"
    }
    Write-Host "---JSON_OUTPUT---"
    $result | ConvertTo-Json -Compress
    exit 1  # 대기 필요
} else {
    Write-Host "✅ 버전 자동 결정 완료" -ForegroundColor Green
    Write-Host "   버전 변경: $currentVersion → $newVersion ($($bumpType.ToUpper()))" -ForegroundColor Green
    Write-Host ""

    # JSON 출력 (파이프라인용)
    $result = @{
        currentVersion = $currentVersion
        newVersion = $newVersion
        bumpType = $bumpType
        requiresApproval = $false
        reason = "Auto-determined from commits"
    }
    Write-Host "---JSON_OUTPUT---"
    $result | ConvertTo-Json -Compress
    exit 0  # 자동 진행
}
