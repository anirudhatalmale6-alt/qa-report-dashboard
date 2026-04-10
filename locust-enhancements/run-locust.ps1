<#
.SYNOPSIS
    Wrapper to run Locust in background and auto-publish results to QA Dashboard.

.DESCRIPTION
    Runs a Locust script with CSV stats output, waits for completion,
    then publishes results to the QA Dashboard. Can run in background
    so you can close the terminal and work on other things.

.PARAMETER ScriptFile
    Path to the Locust script (e.g., "wss/WSS_Retiredmem.py" or "ESS_US_108585.py")

.PARAMETER Users
    Number of concurrent users (default: 1)

.PARAMETER SpawnRate
    User spawn rate (default: 0.2)

.PARAMETER RunTime
    Max run time (default: "480m" for 8 hours). Script stops early if data exhausted.

.PARAMETER EnvName
    Target environment (default: "UAT75")

.PARAMETER DashboardPath
    Path to QA Dashboard folder. Set your default below.

.PARAMETER Background
    Run in background (default: $false). If $true, runs as a background job.

.PARAMETER ExtraArgs
    Additional Locust arguments (e.g., "--only-summary")

.EXAMPLE
    # Run in foreground (see output in terminal)
    .\run-locust.ps1 -ScriptFile "ESS_US_108585.py" -Users 30 -SpawnRate 0.2 -EnvName UAT75

    # Run in background (terminal is free, results auto-publish)
    .\run-locust.ps1 -ScriptFile "ESS_US_108585.py" -Users 30 -SpawnRate 0.2 -EnvName UAT75 -Background

    # Check background job status
    Get-Job | Format-Table

    # View background job output
    Receive-Job -Name "Locust_ESS_US_108585"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptFile,

    [int]$Users = 1,

    [double]$SpawnRate = 0.2,

    [string]$RunTime = "480m",

    [string]$EnvName = "UAT75",

    [string]$DashboardPath = "",  # <-- SET YOUR DEFAULT: e.g., "C:\qa-report-dashboard"

    [switch]$Background,

    [string]$ExtraArgs = "--only-summary"
)

# ===========================
# CONFIGURATION - UPDATE THESE
# ===========================
if (-not $DashboardPath) {
    $DashboardPath = $env:QA_DASHBOARD_PATH
    if (-not $DashboardPath) {
        Write-Host "[ERROR] DashboardPath not set. Either:"
        Write-Host "  1. Pass -DashboardPath 'C:\path\to\qa-dashboard'"
        Write-Host "  2. Set environment variable: `$env:QA_DASHBOARD_PATH = 'C:\path\to\qa-dashboard'"
        Write-Host "  3. Edit the default in this script"
        exit 1
    }
}

# ===========================
# DERIVED VARIABLES
# ===========================
$scriptName = [System.IO.Path]::GetFileNameWithoutExtension($ScriptFile)
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$csvPrefix = Join-Path -Path "locust-results" -ChildPath "${scriptName}_${timestamp}"
$logFile = Join-Path -Path "logs" -ChildPath "${scriptName}_${timestamp}.log"

# Ensure directories exist
New-Item -ItemType Directory -Path "locust-results" -Force | Out-Null
New-Item -ItemType Directory -Path "logs" -Force | Out-Null

# ===========================
# BUILD LOCUST COMMAND
# ===========================
$locustCmd = "locust -f `"$ScriptFile`" -u $Users -r $SpawnRate --headless -t $RunTime --env-name $EnvName --csv `"$csvPrefix`" $ExtraArgs"

# ===========================
# BACKGROUND MODE
# ===========================
if ($Background) {
    Write-Host "================================================================"
    Write-Host "[Locust Runner] Starting in BACKGROUND mode"
    Write-Host "[Locust Runner] Script: $ScriptFile"
    Write-Host "[Locust Runner] Users: $Users | Spawn Rate: $SpawnRate | Time: $RunTime"
    Write-Host "[Locust Runner] Environment: $EnvName"
    Write-Host "[Locust Runner] CSV Prefix: $csvPrefix"
    Write-Host "[Locust Runner] Log: $logFile"
    Write-Host "================================================================"
    Write-Host ""
    Write-Host "You can now close this terminal or work on other things."
    Write-Host "Check status:  Get-Job -Name 'Locust_$scriptName'"
    Write-Host "View output:   Receive-Job -Name 'Locust_$scriptName'"
    Write-Host "Stop it:       Stop-Job -Name 'Locust_$scriptName'"
    Write-Host ""

    $jobScript = {
        param($ScriptFile, $Users, $SpawnRate, $RunTime, $EnvName, $csvPrefix, $logFile, $ExtraArgs, $DashboardPath, $scriptName)

        $startTime = Get-Date
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Starting Locust: $ScriptFile"
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Command: locust -f $ScriptFile -u $Users -r $SpawnRate --headless -t $RunTime --env-name $EnvName --csv $csvPrefix $ExtraArgs"

        # Run Locust
        $process = Start-Process -FilePath "locust" `
            -ArgumentList "-f `"$ScriptFile`" -u $Users -r $SpawnRate --headless -t $RunTime --env-name $EnvName --csv `"$csvPrefix`" $ExtraArgs" `
            -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $logFile `
            -RedirectStandardError (Join-Path -Path "logs" -ChildPath "${scriptName}_${timestamp}_err.log")

        $endTime = Get-Date
        $duration = $endTime - $startTime

        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Locust finished. Exit code: $($process.ExitCode)"
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Duration: $($duration.ToString('hh\:mm\:ss'))"

        # Publish to dashboard
        $publishScript = Join-Path -Path $PSScriptRoot -ChildPath "locust-publish.ps1"
        if (Test-Path $publishScript) {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Publishing to dashboard..."
            & $publishScript -ScriptName $scriptName -CsvPrefix $csvPrefix -DashboardPath $DashboardPath -EnvName $EnvName
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Published to QA Dashboard!"
        } else {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] WARNING: locust-publish.ps1 not found at $publishScript"
        }

        Write-Output ""
        Write-Output "========================================="
        Write-Output "  LOCUST RUN COMPLETE"
        Write-Output "  Script: $ScriptFile"
        Write-Output "  Duration: $($duration.ToString('hh\:mm\:ss'))"
        Write-Output "  CSV: $csvPrefix"
        Write-Output "  Log: $logFile"
        Write-Output "========================================="
    }

    Start-Job -Name "Locust_$scriptName" -ScriptBlock $jobScript `
        -ArgumentList $ScriptFile, $Users, $SpawnRate, $RunTime, $EnvName, $csvPrefix, $logFile, $ExtraArgs, $DashboardPath, $scriptName

    return
}

# ===========================
# FOREGROUND MODE
# ===========================
Write-Host "================================================================"
Write-Host "[Locust Runner] Starting in FOREGROUND mode"
Write-Host "[Locust Runner] Script: $ScriptFile"
Write-Host "[Locust Runner] Users: $Users | Spawn Rate: $SpawnRate | Time: $RunTime"
Write-Host "[Locust Runner] Environment: $EnvName"
Write-Host "[Locust Runner] CSV Prefix: $csvPrefix"
Write-Host "[Locust Runner] Log: $logFile"
Write-Host "================================================================"

$startTime = Get-Date

# Run Locust (foreground - output visible in terminal)
Write-Host ""
Write-Host "Running: $locustCmd"
Write-Host ""

Invoke-Expression "$locustCmd 2>&1 | Tee-Object -FilePath `"$logFile`""

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "[Locust Runner] Finished. Duration: $($duration.ToString('hh\:mm\:ss'))"

# Auto-publish to dashboard
$publishScript = Join-Path -Path $PSScriptRoot -ChildPath "locust-publish.ps1"
if (Test-Path $publishScript) {
    Write-Host "[Locust Runner] Publishing to QA Dashboard..."
    & $publishScript -ScriptName $scriptName -CsvPrefix $csvPrefix -DashboardPath $DashboardPath -EnvName $EnvName
    Write-Host "[Locust Runner] Done! Check dashboard at http://localhost:3000/dashboard"
} else {
    Write-Host "[Locust Runner] WARNING: locust-publish.ps1 not found. Copy it to: $PSScriptRoot"
    Write-Host "[Locust Runner] CSV results saved at: $csvPrefix"
}

Write-Host ""
Write-Host "========================================="
Write-Host "  LOCUST RUN COMPLETE"
Write-Host "  Script: $ScriptFile"
Write-Host "  Duration: $($duration.ToString('hh\:mm\:ss'))"
Write-Host "  CSV: $csvPrefix"
Write-Host "  Log: $logFile"
Write-Host "========================================="
