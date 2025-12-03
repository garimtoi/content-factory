# Phase 2.5 검증: Code Review + Security Audit
# Windows PowerShell 전용 버전

$ErrorActionPreference = "Stop"

Write-Host "Phase 2.5 검증: Code Review + Security Audit" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true
$requiresApproval = $false
$approvalReasons = @()

# 1. Security Audit
Write-Host "1. Security Audit" -ForegroundColor Cyan

# Node.js 프로젝트
if (Test-Path "package.json") {
    Write-Host "   npm audit 실행 중..." -ForegroundColor Cyan
    $auditResult = & npm audit --json 2>$null | ConvertFrom-Json

    $criticalCount = 0
    $highCount = 0

    if ($auditResult.metadata) {
        $criticalCount = $auditResult.metadata.vulnerabilities.critical
        $highCount = $auditResult.metadata.vulnerabilities.high
    }

    if ($criticalCount -gt 0 -or $highCount -gt 0) {
        Write-Host "   ⚠️  npm audit: Critical ($criticalCount), High ($highCount)" -ForegroundColor Yellow
        $requiresApproval = $true
        $approvalReasons += "Security: Critical($criticalCount), High($highCount) 취약점 발견"
    } else {
        Write-Host "   ✅ npm audit: Critical/High 취약점 없음" -ForegroundColor Green
    }
}

# Python 프로젝트
if (Test-Path "requirements.txt" -or Test-Path "pyproject.toml") {
    if (Get-Command pip-audit -ErrorAction SilentlyContinue) {
        Write-Host "   pip-audit 실행 중..." -ForegroundColor Cyan
        $pipAuditResult = & pip-audit --format json 2>$null | ConvertFrom-Json

        $criticalPy = ($pipAuditResult | Where-Object { $_.vulns.severity -eq "CRITICAL" }).Count
        $highPy = ($pipAuditResult | Where-Object { $_.vulns.severity -eq "HIGH" }).Count

        if ($criticalPy -gt 0 -or $highPy -gt 0) {
            Write-Host "   ⚠️  pip-audit: Critical ($criticalPy), High ($highPy)" -ForegroundColor Yellow
            $requiresApproval = $true
            $approvalReasons += "Security: Python Critical($criticalPy), High($highPy) 취약점"
        } else {
            Write-Host "   ✅ pip-audit: Critical/High 취약점 없음" -ForegroundColor Green
        }
    } else {
        Write-Host "   ℹ️  pip-audit 미설치 (pip install pip-audit)" -ForegroundColor Gray
    }
}

# 2. 보안 체크리스트
Write-Host ""
Write-Host "2. 보안 체크리스트" -ForegroundColor Cyan

# .env 파일 Git 추적 확인
if (Test-Path ".env") {
    $gitLs = & git ls-files ".env" 2>&1
    if ($gitLs) {
        Write-Host "   ❌ .env 파일이 Git에 추적됨!" -ForegroundColor Red
        $allPassed = $false
    } else {
        Write-Host "   ✅ .env 파일이 Git에서 제외됨" -ForegroundColor Green
    }
} else {
    Write-Host "   ✅ .env 파일 없음" -ForegroundColor Green
}

# Hardcoded secrets 검색
Write-Host "   하드코딩된 시크릿 검색 중..." -ForegroundColor Cyan
$secretPatterns = @(
    "password\s*=\s*['\`"](?!{{).{8,}",
    "api[_-]?key\s*=\s*['\`"](?!{{).{20,}",
    "secret\s*=\s*['\`"](?!{{).{10,}"
)

$secretsFound = $false
foreach ($pattern in $secretPatterns) {
    $matches = Get-ChildItem -Path . -Recurse -Include *.py,*.js,*.ts,*.tsx,*.jsx -ErrorAction SilentlyContinue |
        Select-String -Pattern $pattern -CaseSensitive

    if ($matches) {
        $secretsFound = $true
    }
}

if ($secretsFound) {
    Write-Host "   ⚠️  의심스러운 시크릿 발견" -ForegroundColor Yellow
    $requiresApproval = $true
    $approvalReasons += "Security: 하드코딩된 시크릿 의심"
} else {
    Write-Host "   ✅ 하드코딩된 시크릿 없음" -ForegroundColor Green
}

# 최종 결과
Write-Host ""
Write-Host "=" * 60

if (-not $allPassed) {
    Write-Host "❌ Phase 2.5 검증 실패" -ForegroundColor Red
    Write-Host "   위 항목들을 수정하세요" -ForegroundColor Yellow
    exit 1
}

if ($requiresApproval) {
    Write-Host "⏸️  Phase 2.5 검증: 사용자 확인 필요" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "확인 필요 사유:" -ForegroundColor Yellow
    $approvalReasons | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "---JSON_OUTPUT---"
    @{
        passed = $true
        requiresApproval = $true
        reasons = $approvalReasons
    } | ConvertTo-Json -Compress
    exit 2  # 대기 필요
} else {
    Write-Host "✅ Phase 2.5 검증 통과" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계: Phase 3 (버전 자동 결정)" -ForegroundColor Cyan
    Write-Host "   .\scripts\auto-version.ps1"
    Write-Host ""
    Write-Host "---JSON_OUTPUT---"
    @{
        passed = $true
        requiresApproval = $false
        reasons = @()
    } | ConvertTo-Json -Compress
    exit 0
}
