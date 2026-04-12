<#
.SYNOPSIS
    One-stop setup script for the QA Automation Framework.
    Run this on a fresh Windows machine to install everything needed.

.DESCRIPTION
    Installs: Python packages, Playwright browsers, Allure 3 CLI, Node.js packages,
    and configures the QA Dashboard.

.EXAMPLE
    # Run from the setup folder:
    .\setup-qa-env.ps1

    # Skip optional desktop automation packages:
    .\setup-qa-env.ps1 -SkipDesktop

    # Specify dashboard path:
    .\setup-qa-env.ps1 -DashboardPath "C:\QA_Reports_Dashboard\qa-report-dashboard"
#>

param(
    [switch]$SkipDesktop,
    [string]$DashboardPath = ""
)

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   QA Automation Framework - Environment Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ===========================
# STEP 0: Check Prerequisites
# ===========================
Write-Host "[Step 0] Checking prerequisites..." -ForegroundColor Yellow

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "        Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $pythonVersion" -ForegroundColor Green

# Check pip
$pipVersion = pip --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip not found. Run: python -m ensurepip --upgrade" -ForegroundColor Red
    exit 1
}
Write-Host "  pip: OK" -ForegroundColor Green

# Check Node.js
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Node.js not found. QA Dashboard requires Node.js." -ForegroundColor Yellow
    Write-Host "          Install from: https://nodejs.org/ (LTS version)" -ForegroundColor Yellow
    $skipNode = $true
} else {
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
    $skipNode = $false
}

# Check Git
$gitVersion = git --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Git not found. Install from: https://git-scm.com/download/win" -ForegroundColor Yellow
} else {
    Write-Host "  Git: $gitVersion" -ForegroundColor Green
}

Write-Host ""

# ===========================
# STEP 1: Python Packages
# ===========================
Write-Host "[Step 1] Installing Python packages..." -ForegroundColor Yellow

$requirementsPath = Join-Path -Path $PSScriptRoot -ChildPath "requirements.txt"
if (Test-Path $requirementsPath) {
    pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARNING] Some packages may have failed. Check output above." -ForegroundColor Yellow
    } else {
        Write-Host "  Python packages installed successfully!" -ForegroundColor Green
    }
} else {
    Write-Host "[ERROR] requirements.txt not found at: $requirementsPath" -ForegroundColor Red
    Write-Host "  Installing core packages manually..." -ForegroundColor Yellow
    pip install pytest pytest-playwright playwright pytest-xdist pytest-html allure-pytest locust gevent pandas openpyxl requests assertpy Faker pyyaml jsonpath-ng pyodbc
}

# Optional desktop automation packages
if (-not $SkipDesktop) {
    Write-Host ""
    Write-Host "  Installing optional desktop automation packages..." -ForegroundColor Yellow
    pip install pyautoit pyautogui
}

Write-Host ""

# ===========================
# STEP 2: Playwright Browsers
# ===========================
Write-Host "[Step 2] Installing Playwright browsers (Chromium, Firefox, WebKit)..." -ForegroundColor Yellow
python -m playwright install
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Playwright browsers installed!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Playwright browser install had issues. Try: python -m playwright install --with-deps" -ForegroundColor Yellow
}

Write-Host ""

# ===========================
# STEP 3: Allure 3 CLI
# ===========================
Write-Host "[Step 3] Installing Allure 3 CLI..." -ForegroundColor Yellow

# Check if npm is available
$npmVersion = npm --version 2>&1
if ($LASTEXITCODE -eq 0) {
    npm install -g allure@3
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Allure 3 CLI installed!" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Allure install failed. Try running as Administrator: npm install -g allure@3" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARNING] npm not found. Install Node.js first, then run: npm install -g allure@3" -ForegroundColor Yellow
}

# Verify Allure
$allureVersion = allure --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Allure version: $allureVersion" -ForegroundColor Green
} else {
    Write-Host "  Allure CLI not yet on PATH. You may need to restart your terminal." -ForegroundColor Yellow
}

Write-Host ""

# ===========================
# STEP 4: QA Dashboard (Node.js)
# ===========================
Write-Host "[Step 4] Setting up QA Dashboard..." -ForegroundColor Yellow

if (-not $skipNode) {
    if ($DashboardPath -and (Test-Path $DashboardPath)) {
        Push-Location $DashboardPath
        npm install
        Pop-Location
        Write-Host "  Dashboard dependencies installed!" -ForegroundColor Green
    } else {
        Write-Host "  Dashboard path not set or not found." -ForegroundColor Yellow
        Write-Host "  To set up later:" -ForegroundColor Yellow
        Write-Host "    cd <your-dashboard-folder>" -ForegroundColor Yellow
        Write-Host "    npm install" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Skipped (Node.js not installed)" -ForegroundColor Yellow
}

Write-Host ""

# ===========================
# STEP 5: Verify Installation
# ===========================
Write-Host "[Step 5] Verifying installation..." -ForegroundColor Yellow

$checks = @(
    @{ Name = "pytest";     Cmd = "python -m pytest --version" },
    @{ Name = "playwright"; Cmd = "python -m playwright --version" },
    @{ Name = "locust";     Cmd = "python -m locust --version" },
    @{ Name = "allure";     Cmd = "allure --version" }
)

$allPassed = $true
foreach ($check in $checks) {
    $result = Invoke-Expression "$($check.Cmd) 2>&1"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $($check.Name): $result" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $($check.Name): Not working" -ForegroundColor Red
        $allPassed = $false
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "   Setup Complete! All tools installed successfully." -ForegroundColor Green
} else {
    Write-Host "   Setup Complete (with warnings). Check items above." -ForegroundColor Yellow
}
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Quick Start:" -ForegroundColor White
Write-Host "  1. Run Playwright tests:  pytest tests/ --alluredir=allure-results" -ForegroundColor Gray
Write-Host "  2. Run Locust tests:      python -m locust -f wss/WSS_Retiredmem.py --headless" -ForegroundColor Gray
Write-Host "  3. Start QA Dashboard:    cd <dashboard-folder> && node server.js" -ForegroundColor Gray
Write-Host "  4. View dashboard:        http://localhost:3000/dashboard" -ForegroundColor Gray
Write-Host ""
