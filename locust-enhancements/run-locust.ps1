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
    Target environment (default: "UAT75"). Only passed to Locust if script supports --env-name.

.PARAMETER NoEnvName
    Skip passing --env-name to Locust (for older scripts that don't register it).

.PARAMETER DashboardPath
    Path to QA Dashboard folder. Set your default below or use $env:QA_DASHBOARD_PATH.

.PARAMETER Background
    Run in background (default: $false). If $true, runs as a background job.

.PARAMETER ExtraArgs
    Additional Locust arguments (e.g., "--only-summary")

.EXAMPLE
    # Run in foreground
    .\run-locust.ps1 -ScriptFile "wss/WSS_Retiredmem.py" -Users 1 -SpawnRate 0.2 -EnvName UAT75

    # Run in background
    .\run-locust.ps1 -ScriptFile "wss/WSS_Retiredmem.py" -Users 1 -SpawnRate 0.2 -EnvName UAT75 -Background

    # Older script without --env-name support
    .\run-locust.ps1 -ScriptFile "wss/108585.py" -Users 30 -SpawnRate 0.2 -NoEnvName -Background

    # Check background job
    Get-Job | Format-Table
    Receive-Job -Name "Locust_WSS_Retiredmem" -Keep
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptFile,

    [int]$Users = 1,

    [double]$SpawnRate = 0.2,

    [string]$RunTime = "480m",

    [string]$EnvName = "UAT75",

    [switch]$NoEnvName,

    [string]$App = "",

    [string]$DashboardPath = "",

    [switch]$Background,

    [string]$ExtraArgs = "--only-summary"
)

# ===========================
# CONFIGURATION
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
$errFile = Join-Path -Path "logs" -ChildPath "${scriptName}_${timestamp}_err.log"

# Ensure directories exist
New-Item -ItemType Directory -Path "locust-results" -Force | Out-Null
New-Item -ItemType Directory -Path "logs" -Force | Out-Null

# Build argument list
$locustArgs = @(
    "-f", $ScriptFile,
    "-u", $Users,
    "-r", $SpawnRate,
    "--headless",
    "-t", $RunTime,
    "--csv", $csvPrefix,
    "--logfile", $logFile
)
if (-not $NoEnvName) {
    $locustArgs += @("--env-name", $EnvName)
}
if ($App) {
    $locustArgs += @("--app", $App)
}
if ($ExtraArgs) {
    $locustArgs += $ExtraArgs.Split(" ")
}

# Resolve full paths BEFORE entering background job (where $PSScriptRoot is empty)
$publishScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "locust-publish.ps1"
$workingDir = (Get-Location).Path

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
    Write-Host "View output:   Receive-Job -Name 'Locust_$scriptName' -Keep"
    Write-Host "Stop it:       Stop-Job -Name 'Locust_$scriptName'"
    Write-Host ""

    $jobScript = {
        param($locustArgs, $logFile, $errFile, $csvPrefix, $scriptName, $EnvName, $DashboardPath, $publishScriptPath, $workingDir)

        # Background jobs start in user home - switch to actual working directory
        Set-Location $workingDir
        New-Item -ItemType Directory -Path "locust-results" -Force | Out-Null
        New-Item -ItemType Directory -Path "logs" -Force | Out-Null

        $startTime = Get-Date
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Working directory: $(Get-Location)"
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Starting Locust..."
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Command: locust $($locustArgs -join ' ')"

        # Run Locust directly with & operator (not Start-Process - avoids path issues)
        # --logfile captures Locust's own output; 2>$errFile captures stderr
        & locust @locustArgs 2>$errFile

        $exitCode = $LASTEXITCODE
        $endTime = Get-Date
        $duration = $endTime - $startTime

        Write-Output ""
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Locust finished. Exit code: $exitCode"
        Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Duration: $($duration.ToString('hh\:mm\:ss'))"

        # Show stderr if any errors were captured
        if ((Test-Path $errFile) -and (Get-Item $errFile).Length -gt 0) {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] STDERR output:"
            Get-Content $errFile | ForEach-Object { Write-Output "  $_" }
        }

        # Show log tail
        if ((Test-Path $logFile) -and (Get-Item $logFile).Length -gt 0) {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Log tail:"
            Get-Content $logFile -Tail 10 | ForEach-Object { Write-Output "  $_" }
        }

        # Publish to dashboard
        if ($exitCode -eq 0 -or $exitCode -eq $null) {
            if (Test-Path $publishScriptPath) {
                Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Publishing to dashboard..."
                & $publishScriptPath -ScriptName $scriptName -CsvPrefix $csvPrefix -DashboardPath $DashboardPath -EnvName $EnvName
                Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Published to QA Dashboard!"
            } else {
                Write-Output "[$(Get-Date -Format 'HH:mm:ss')] WARNING: locust-publish.ps1 not found at: $publishScriptPath"
            }
        } else {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Locust failed (exit code $exitCode). Skipping publish."
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Check log: $logFile"
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Check errors: $errFile"
        }

        Write-Output ""
        Write-Output "========================================="
        Write-Output "  LOCUST RUN COMPLETE"
        Write-Output "  Script: $($locustArgs[1])"
        Write-Output "  Duration: $($duration.ToString('hh\:mm\:ss'))"
        Write-Output "  Exit Code: $exitCode"
        Write-Output "========================================="
    }

    # Pass locustArgs as a nested array so PowerShell doesn't flatten it
    Start-Job -Name "Locust_$scriptName" -ScriptBlock $jobScript `
        -ArgumentList @(,$locustArgs), $logFile, $errFile, $csvPrefix, $scriptName, $EnvName, $DashboardPath, $publishScriptPath, $workingDir

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

Write-Host ""
Write-Host "Running: locust $($locustArgs -join ' ')"
Write-Host ""

# Run Locust - --logfile writes Locust's log; 2>&1 shows stderr in terminal too
& locust @locustArgs 2>&1

$exitCode = $LASTEXITCODE
$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "[Locust Runner] Finished. Exit code: $exitCode | Duration: $($duration.ToString('hh\:mm\:ss'))"

# Auto-publish to dashboard
if ($exitCode -eq 0 -or $exitCode -eq $null) {
    if (Test-Path $publishScriptPath) {
        Write-Host "[Locust Runner] Publishing to QA Dashboard..."
        & $publishScriptPath -ScriptName $scriptName -CsvPrefix $csvPrefix -DashboardPath $DashboardPath -EnvName $EnvName
        Write-Host "[Locust Runner] Done! Check dashboard at http://localhost:3000/dashboard"
    } else {
        Write-Host "[Locust Runner] WARNING: locust-publish.ps1 not found at: $publishScriptPath"
    }
} else {
    Write-Host "[Locust Runner] Locust failed (exit code $exitCode). Skipping publish."
}

Write-Host ""
Write-Host "========================================="
Write-Host "  LOCUST RUN COMPLETE"
Write-Host "  Script: $ScriptFile"
Write-Host "  Duration: $($duration.ToString('hh\:mm\:ss'))"
Write-Host "  Exit Code: $exitCode"
Write-Host "  CSV: $csvPrefix"
Write-Host "  Log: $logFile"
Write-Host "========================================="
