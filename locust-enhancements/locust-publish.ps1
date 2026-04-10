<#
.SYNOPSIS
    Publishes Locust CSV stats to the QA Dashboard.

.DESCRIPTION
    After a Locust run with --csv flag, this script copies the Locust stats files
    to the QA Dashboard so they appear in the Locust tab.

.PARAMETER ScriptName
    Name of the Locust script (e.g., "WSS_Retiredmem"). Used as the project name.

.PARAMETER CsvPrefix
    Path prefix used with Locust's --csv flag (e.g., "locust-results/WSS_Retiredmem").
    Locust creates files like {prefix}_stats.csv, {prefix}_failures.csv, {prefix}_stats_history.csv

.PARAMETER DashboardPath
    Path to the QA Dashboard folder (where server.js lives).

.PARAMETER EnvName
    Environment name (e.g., "UAT75"). Stored in run metadata.

.EXAMPLE
    .\locust-publish.ps1 -ScriptName "WSS_Retiredmem" -CsvPrefix "locust-results/WSS_Retiredmem" -DashboardPath "C:\qa-dashboard" -EnvName "UAT75"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptName,

    [Parameter(Mandatory=$true)]
    [string]$CsvPrefix,

    [Parameter(Mandatory=$true)]
    [string]$DashboardPath,

    [Parameter(Mandatory=$false)]
    [string]$EnvName = "unknown"
)

# Generate timestamp for run ID
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Build destination path: reports/Locust/{ScriptName}/{timestamp}/
$destDir = Join-Path -Path (Join-Path -Path (Join-Path -Path $DashboardPath -ChildPath "reports") -ChildPath "Locust") -ChildPath $ScriptName
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
    $aggregated = $statsContent | Where-Object { $_.Name -eq "Aggregated" }
    if ($aggregated) {
        $totalRequests = [int]($aggregated.'Request Count')
        $totalFailures = [int]($aggregated.'Failure Count')
        $avgResponseTime = [math]::Round([double]($aggregated.'Average Response Time'), 0)
    }
}

$summary = @{
    scriptName = $ScriptName
    envName = $EnvName
    timestamp = $timestamp
    date = (Get-Date).ToString("o")
    totalRequests = $totalRequests
    totalFailures = $totalFailures
    avgResponseTime = $avgResponseTime
    passRate = if ($totalRequests -gt 0) { [math]::Round((($totalRequests - $totalFailures) / $totalRequests) * 100, 1) } else { 0 }
} | ConvertTo-Json

$summary | Out-File -FilePath (Join-Path -Path $destDir -ChildPath "summary.json") -Encoding UTF8

Write-Host "[Locust Publish] Published run: $ScriptName / $timestamp"
Write-Host "[Locust Publish] Requests: $totalRequests, Failures: $totalFailures, Avg RT: ${avgResponseTime}ms"
