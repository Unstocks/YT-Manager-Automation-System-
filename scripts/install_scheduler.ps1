<#
.SYNOPSIS
    Installs the persistent Windows Scheduled Task for YT Manager.
.DESCRIPTION
    Triggers daily at 6:00 PM IST (18:00 Asia/Kolkata).
    Executes unattended, wakes or runs when available, and survives restarts.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonExe = (Get-Command python).Source

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "      YT MANAGER — WINDOWS TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project Directory: $ProjectDir"
Write-Host "Python Executable: $PythonExe"

$TaskName = "YT-Manager-Daily"
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m yt_manager run" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At "18:00"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "YT Manager Autonomous Daily YouTube Upload at 6:00 PM IST" -Force
    Write-Host "`nSUCCESS: Scheduled Task '$TaskName' registered to run daily at 6:00 PM IST." -ForegroundColor Green
    Write-Host "Check status anytime with: python -m yt_manager status" -ForegroundColor Yellow
} catch {
    Write-Error "Failed to register Scheduled Task: $_"
}
