# allure.ps1
# Called from conftest.py after test execution
# Generates Allure report AND publishes to QA Dashboard

# Stay in the current working directory (where pytest runs from)
# Do NOT change to $scriptDir - allure-results is in the CWD, not the script folder
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cwd = Get-Location
Write-Host "Working directory: $cwd"
Write-Host "Script directory: $scriptDir"

# Read project name from allure-project.txt (written by conftest.py in CWD)
$ProjectName = "default"
$projectFile = Join-Path $cwd "allure-project.txt"
if (!(Test-Path $projectFile)) {
    # Fallback: check script directory
    $projectFile = Join-Path $scriptDir "allure-project.txt"
}
if (Test-Path $projectFile) {
    $ProjectName = (Get-Content $projectFile -Raw).Trim()
    Write-Host "Project name: $ProjectName"
}

# ================================
#   ENSURE HISTORY DIRECTORY EXISTS
# ================================
$historyDir = Join-Path $cwd "allure-history"
if (!(Test-Path $historyDir)) {
    New-Item -ItemType Directory -Path $historyDir -Force | Out-Null
    Write-Host "Created allure-history directory"
}

# ================================
#   GENERATE ALLURE REPORT
# ================================
# Remove old report before generating (Allure 3 has no --clean flag)
if (Test-Path "allure-report") {
    Remove-Item -Recurse -Force "allure-report"
    Write-Host "Cleaned old allure-report"
}

Write-Host "Generating Allure report..."
allure generate allure-results -o allure-report

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Allure report generation failed"
    exit 1
}

Write-Host "Allure report generated successfully"

# ================================
#   PUBLISH TO QA DASHBOARD
# ================================
# Path to QA Report Dashboard (update this to your dashboard location)
$DashboardPath = "C:\QAReportDashboard"

# Check if dashboard path exists
if (Test-Path $DashboardPath) {
    $publishScript = Join-Path $DashboardPath "allure-publish.ps1"

    if (Test-Path $publishScript) {
        Write-Host "Publishing to QA Dashboard..."
        $reportPath = Join-Path $cwd "allure-report"
        $resultsPath = Join-Path $cwd "test-results"

        & $publishScript -ProjectName $ProjectName -DashboardPath $DashboardPath -ReportPath $reportPath -ResultsPath $resultsPath

        Write-Host "Dashboard publish complete"
    } else {
        Write-Host "WARNING: allure-publish.ps1 not found at $publishScript"
    }
} else {
    Write-Host "WARNING: Dashboard path not found at $DashboardPath. Skipping dashboard publish."
    Write-Host "Update the DashboardPath variable in allure.ps1 to your dashboard location."
}
