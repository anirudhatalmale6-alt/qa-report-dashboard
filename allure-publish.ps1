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
    [string]$ReportPath = "allure-report",

    [Parameter(Mandatory=$false)]
    [string]$ResultsPath = "test-results"
)

Write-Host ">>> Allure Publish Script"

# Validate report exists
if (!(Test-Path $ReportPath)) {
    Write-Error "Report not found at: $ReportPath"
    exit 1
}

# Generate timestamp folder name
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
# PowerShell 5.1: Join-Path only takes 2 args, chain with -ChildPath
$destDir = Join-Path -Path (Join-Path -Path (Join-Path -Path $DashboardPath -ChildPath "reports") -ChildPath $ProjectName) -ChildPath $timestamp

Write-Host "Publishing report to: $destDir"

# Create destination and copy report
New-Item -ItemType Directory -Path $destDir -Force | Out-Null
Copy-Item -Path "$ReportPath\*" -Destination $destDir -Recurse -Force

# Extract summary - supports both Allure 2 (widgets/summary.json) and Allure 3 (root summary.json + widgets/statistic.json)
$summaryExtracted = $false

# --- Allure 2: widgets/summary.json ---
$widgetSummary = Join-Path -Path (Join-Path -Path $ReportPath -ChildPath "widgets") -ChildPath "summary.json"
if (Test-Path $widgetSummary) {
    $data = Get-Content $widgetSummary -Raw | ConvertFrom-Json
    if ($data.statistic) {
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
        Write-Host "Summary extracted (Allure 2): $($stats.total) total, $($stats.passed) passed, $($stats.failed) failed"
        $summaryExtracted = $true
    }
}

# --- Allure 3: root summary.json + widgets/statistic.json + widgets/charts.json ---
if (-not $summaryExtracted) {
    $rootSummary = Join-Path $ReportPath "summary.json"
    $widgetStatistic = Join-Path -Path (Join-Path -Path $ReportPath -ChildPath "widgets") -ChildPath "statistic.json"
    $widgetCharts = Join-Path -Path (Join-Path -Path $ReportPath -ChildPath "widgets") -ChildPath "charts.json"

    $total = 0; $passed = 0; $failed = 0; $broken = 0; $skipped = 0; $unknown = 0; $duration = 0

    # Try widgets/statistic.json first - may have per-status counts
    if (Test-Path $widgetStatistic) {
        $statData = Get-Content $widgetStatistic -Raw | ConvertFrom-Json
        $total = if ($statData.total) { [int]$statData.total } else { 0 }
        $passed = if ($statData.passed) { [int]$statData.passed } else { 0 }
        $failed = if ($statData.failed) { [int]$statData.failed } else { 0 }
        $broken = if ($statData.broken) { [int]$statData.broken } else { 0 }
        $skipped = if ($statData.skipped) { [int]$statData.skipped } else { 0 }
        $unknown = if ($statData.unknown) { [int]$statData.unknown } else { 0 }
        Write-Host "  Found widgets/statistic.json (total=$total)"
    }

    # If statistic.json only had total, try charts.json for per-status breakdown
    if ($total -gt 0 -and ($passed + $failed + $broken + $skipped + $unknown) -eq 0) {
        if (Test-Path $widgetCharts) {
            $chartsData = Get-Content $widgetCharts -Raw | ConvertFrom-Json
            $generalWidgets = $chartsData.general.PSObject.Properties
            foreach ($widget in $generalWidgets) {
                if ($widget.Value.type -eq "testResultSeverities" -and $widget.Value.data) {
                    foreach ($sev in $widget.Value.data) {
                        $passed += [int]$sev.passed
                        $failed += [int]$sev.failed
                        $broken += [int]$sev.broken
                        $skipped += [int]$sev.skipped
                        $unknown += [int]$sev.unknown
                    }
                    Write-Host "  Extracted per-status counts from charts.json severities"
                    break
                }
            }
        }
    }

    # Get duration from root summary.json
    if (Test-Path $rootSummary) {
        $rootData = Get-Content $rootSummary -Raw | ConvertFrom-Json
        if ($rootData.duration) { $duration = [long]$rootData.duration }
        # Root summary may also have detailed stats
        if ($rootData.stats -and $rootData.stats.passed) {
            $passed = [int]$rootData.stats.passed
            $failed = if ($rootData.stats.failed) { [int]$rootData.stats.failed } else { 0 }
            $broken = if ($rootData.stats.broken) { [int]$rootData.stats.broken } else { 0 }
            $skipped = if ($rootData.stats.skipped) { [int]$rootData.stats.skipped } else { 0 }
            $unknown = if ($rootData.stats.unknown) { [int]$rootData.stats.unknown } else { 0 }
            $total = if ($rootData.stats.total) { [int]$rootData.stats.total } else { $passed + $failed + $broken + $skipped + $unknown }
        }
    }

    if ($total -gt 0 -or (Test-Path $widgetStatistic) -or (Test-Path $rootSummary)) {
        $summary = @{
            name = "Allure Report"
            stats = @{
                total = $total
                passed = $passed
                failed = $failed
                broken = $broken
                skipped = $skipped
                unknown = $unknown
            }
            duration = $duration
        }
        $summaryJson = $summary | ConvertTo-Json -Depth 3
        Set-Content -Path (Join-Path $destDir "summary.json") -Value $summaryJson
        Write-Host "Summary extracted (Allure 3): $total total, $passed passed, $failed failed, $broken broken, $skipped skipped"
        $summaryExtracted = $true
    }
}

if (-not $summaryExtracted) {
    Write-Host "WARNING: Could not extract summary from report. Dashboard stats will be empty."
    Write-Host "  Checked: widgets/summary.json, summary.json, widgets/statistic.json, widgets/charts.json"
}

# Copy results CSV files if they exist
$resultsDir = $ResultsPath
Write-Host "Looking for CSV results in: $resultsDir"
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

# Copy runmanager.json if it exists (generated by conftest.py)
# Search in current dir, then parent dirs up to 3 levels
$runmanagerSrc = $null
$searchDir = Get-Location
for ($i = 0; $i -lt 4; $i++) {
    $candidate = Join-Path $searchDir "runmanager.json"
    Write-Host "Looking for runmanager.json in: $candidate"
    if (Test-Path $candidate) {
        $runmanagerSrc = $candidate
        break
    }
    $searchDir = Split-Path $searchDir -Parent
}

if ($runmanagerSrc) {
    Copy-Item -Path $runmanagerSrc -Destination (Join-Path $destDir "runmanager.json") -Force
    $rmData = Get-Content $runmanagerSrc -Raw | ConvertFrom-Json
    Write-Host "RunManager stats copied: Total Scripts=$($rmData.totalScripts), Executed=$($rmData.executed), Did Not Run=$($rmData.didNotRun)"
} else {
    Write-Host "WARNING: No runmanager.json found. Dashboard will show runs without Total Scripts count."
    Write-Host "  Make sure conftest.py ran successfully and generated runmanager.json"
}

Write-Host "Done! Report published as: $ProjectName/$timestamp"
Write-Host "Open the dashboard at http://localhost:3000/dashboard to view it."
