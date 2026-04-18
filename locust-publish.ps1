<#
.SYNOPSIS
    Publishes Locust CSV stats to the QA Dashboard.

.DESCRIPTION
    After a Locust run with --csv flag, this script copies the Locust stats files
    to the QA Dashboard so they appear under Performance Test.

.PARAMETER ScriptName
    Name of the Locust script (e.g., "WSS_Retiredmem"). Used as the script name.

.PARAMETER CsvPrefix
    Path prefix used with Locust's --csv flag (e.g., "locust-results/WSS_Retiredmem").
    Locust creates files like {prefix}_stats.csv, {prefix}_failures.csv, {prefix}_stats_history.csv

.PARAMETER DashboardPath
    Path to the QA Dashboard folder (where server.js lives).

.PARAMETER App
    Application name (e.g., "ESS", "Clarety", "MiAccount").

.PARAMETER Project
    Project name (e.g., "App_Migration", "ADA", "Maintenance").

.PARAMETER EnvName
    Environment name (e.g., "UAT75"). Stored in run metadata.

.EXAMPLE
    .\locust-publish.ps1 -ScriptName "WSS_Retiredmem" -CsvPrefix "locust-results/WSS_Retiredmem" -DashboardPath "C:\qa-dashboard" -App "ESS" -Project "App_Migration" -EnvName "UAT75"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptName,

    [Parameter(Mandatory=$true)]
    [string]$CsvPrefix,

    [Parameter(Mandatory=$true)]
    [string]$DashboardPath,

    [Parameter(Mandatory=$true)]
    [string]$App,

    [Parameter(Mandatory=$true)]
    [string]$Project,

    [Parameter(Mandatory=$false)]
    [string]$EnvName = "unknown"
)

# Generate timestamp for run ID
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Build destination path: reports/Performance/{App}/{Project}/{ScriptName}/{timestamp}/
$destDir = Join-Path -Path $DashboardPath -ChildPath "reports"
$destDir = Join-Path -Path $destDir -ChildPath "Performance"
$destDir = Join-Path -Path $destDir -ChildPath $App
$destDir = Join-Path -Path $destDir -ChildPath $Project
$destDir = Join-Path -Path $destDir -ChildPath $ScriptName
$destDir = Join-Path -Path $destDir -ChildPath $timestamp

# Create directory
New-Item -ItemType Directory -Path $destDir -Force | Out-Null

Write-Host "[Locust Publish] Destination: $destDir"

# Find and copy all Locust CSV files matching the prefix
$prefixBase = Split-Path $CsvPrefix -Leaf
$prefixDir = Split-Path $CsvPrefix -Parent
if (-not $prefixDir) { $prefixDir = "." }

$csvFiles = Get-ChildItem -Path $prefixDir -Filter "${prefixBase}*.csv" -ErrorAction SilentlyContinue

if ($csvFiles.Count -eq 0) {
    Write-Host "[Locust Publish] WARNING: No CSV files found matching prefix: $CsvPrefix"
    Write-Host "[Locust Publish] Make sure you ran Locust with: --csv $CsvPrefix"
    exit 1
}

foreach ($file in $csvFiles) {
    Copy-Item -Path $file.FullName -Destination $destDir
    Write-Host "[Locust Publish] Copied: $($file.Name)"
}

# Also copy the log file if it exists
$logFile = Join-Path -Path "logs" -ChildPath "${ScriptName}.log"
if (Test-Path $logFile) {
    Copy-Item -Path $logFile -Destination (Join-Path -Path $destDir -ChildPath "script.log")
    Write-Host "[Locust Publish] Copied: script.log"
}

# Create run metadata (summary.json)
$statsFile = $csvFiles | Where-Object { $_.Name -match "_stats\.csv$" } | Select-Object -First 1

$totalRequests = 0
$totalFailures = 0
$avgResponseTime = 0

if ($statsFile) {
    $statsContent = Import-Csv -Path $statsFile.FullName

    # Debug: show CSV column headers
    if ($statsContent.Count -gt 0) {
        $headers = $statsContent[0].PSObject.Properties.Name
        Write-Host "[Locust Publish] CSV columns: $($headers -join ', ')"
    }

    $aggregated = $statsContent | Where-Object { $_.Name -eq "Aggregated" }
    if ($aggregated) {
        Write-Host "[Locust Publish] Found Aggregated row"

        # Try standard column names first, then alternative names
        $reqCount = $aggregated.'Request Count'
        if (-not $reqCount) { $reqCount = $aggregated.'# Requests' }
        if (-not $reqCount) { $reqCount = $aggregated.'# reqs' }

        $failCount = $aggregated.'Failure Count'
        if (-not $failCount) { $failCount = $aggregated.'# Failures' }
        if (-not $failCount) { $failCount = $aggregated.'# fails' }

        $avgRT = $aggregated.'Average Response Time'
        if (-not $avgRT) { $avgRT = $aggregated.'Average response time' }
        if (-not $avgRT) { $avgRT = $aggregated.'Avg Response Time' }

        Write-Host "[Locust Publish] Raw values - Requests: '$reqCount', Failures: '$failCount', Avg RT: '$avgRT'"

        if ($reqCount) { $totalRequests = [int]$reqCount }
        if ($failCount) { $totalFailures = [int]$failCount }
        if ($avgRT) { $avgResponseTime = [math]::Round([double]$avgRT, 0) }
    } else {
        Write-Host "[Locust Publish] WARNING: No 'Aggregated' row found in stats CSV"
        # Show available Name values for debugging
        $names = $statsContent | ForEach-Object { $_.Name } | Select-Object -Unique
        Write-Host "[Locust Publish] Available rows: $($names -join ', ')"
    }
}

# Calculate pass rate separately (PowerShell doesn't allow if-expressions inside hashtable literals)
if ($totalRequests -gt 0) {
    $passRate = [math]::Round((($totalRequests - $totalFailures) / $totalRequests) * 100, 1)
} else {
    $passRate = 0
}

$summary = @{
    scriptName = $ScriptName
    envName = $EnvName
    timestamp = $timestamp
    date = (Get-Date).ToString("o")
    totalRequests = $totalRequests
    totalFailures = $totalFailures
    avgResponseTime = $avgResponseTime
    passRate = $passRate
}

# Write JSON without BOM for Node.js compatibility
$jsonText = $summary | ConvertTo-Json
[System.IO.File]::WriteAllText((Join-Path -Path $destDir -ChildPath "summary.json"), $jsonText)

Write-Host "[Locust Publish] Published run: $App / $Project / $ScriptName / $timestamp"
Write-Host "[Locust Publish] Requests: $totalRequests, Failures: $totalFailures, Avg RT: ${avgResponseTime}ms"
