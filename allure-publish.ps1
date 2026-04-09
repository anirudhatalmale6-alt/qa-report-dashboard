# allure-publish.ps1
# Run this AFTER allure generate to copy the report into the dashboard's reports folder.
# Usage: .\allure-publish.ps1 -ProjectName "playwright" -DashboardPath "C:\dashboard"
#
# It copies allure-report/ into reports/<project>/<timestamp>/ and
# creates a summary.json from the widgets/summary.json in the report.

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,

    [Parameter(Mandatory=$false)]
    [string]$DashboardPath = ".",

    [Parameter(Mandatory=$false)]
    [string]$ReportPath = "allure-report"
)

Write-Host ">>> Allure Publish Script"

# Validate report exists
if (!(Test-Path $ReportPath)) {
    Write-Error "Report not found at: $ReportPath"
    exit 1
}

# Generate timestamp folder name
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destDir = Join-Path $DashboardPath "reports" $ProjectName $timestamp

Write-Host "Publishing report to: $destDir"

# Create destination and copy report
New-Item -ItemType Directory -Path $destDir -Force | Out-Null
Copy-Item -Path "$ReportPath\*" -Destination $destDir -Recurse -Force

# Extract summary from the Allure report's widgets/summary.json
$widgetSummary = Join-Path $ReportPath "widgets" "summary.json"
if (Test-Path $widgetSummary) {
    $data = Get-Content $widgetSummary -Raw | ConvertFrom-Json
    $stats = $data.statistic
    $summary = @{
        name = "Allure Report"
        stats = @{
            total = [int]($stats.total)
            passed = [int]($stats.passed)
            failed = [int]($stats.failed)
            broken = [int]($stats.broken)
            skipped = [int]($stats.skipped)
            unknown = [int]($stats.unknown)
        }
        duration = [long]($data.time.duration)
    }
    $summaryJson = $summary | ConvertTo-Json -Depth 3
    Set-Content -Path (Join-Path $destDir "summary.json") -Value $summaryJson
    Write-Host "Summary extracted: $($stats.total) total, $($stats.passed) passed, $($stats.failed) failed"
} else {
    Write-Host "WARNING: No widgets/summary.json found in report. Dashboard stats may be empty."
}

# Copy results CSV files if they exist
$resultsDir = "test-results"
if (Test-Path $resultsDir) {
    $csvFiles = Get-ChildItem -Path $resultsDir -Filter "results_*.csv"
    if ($csvFiles.Count -gt 0) {
        $csvDestDir = Join-Path $destDir "csv-results"
        New-Item -ItemType Directory -Path $csvDestDir -Force | Out-Null
        foreach ($csv in $csvFiles) {
            Copy-Item -Path $csv.FullName -Destination $csvDestDir -Force
            Write-Host "CSV copied: $($csv.Name)"
        }
        Write-Host "Results CSVs published ($($csvFiles.Count) files)"
    }
} else {
    Write-Host "No test-results/ folder found. Skipping CSV publish."
}

Write-Host "Done! Report published as: $ProjectName/$timestamp"
Write-Host "Open the dashboard at http://localhost:3000/dashboard to view it."
