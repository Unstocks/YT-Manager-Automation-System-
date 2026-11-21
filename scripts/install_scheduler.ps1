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
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At "18:00"
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive

try {
    # Attempt dual trigger (Daily 18:00 + Logon catch-up)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerDaily, $TriggerLogon) -Settings $Settings -Principal $Principal -Description "YT Manager Autonomous Daily YouTube Upload at 6:00 PM IST (with Catch-Up)" -Force
    Write-Host "`nSUCCESS: Scheduled Task '$TaskName' registered (Daily 18:00 IST + Boot/Logon Catch-Up)." -ForegroundColor Green
    Write-Host "Check status anytime with: python -m yt_manager status" -ForegroundColor Yellow
} catch {
    # Fallback to single daily trigger if dual trigger is restricted by policy
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $TriggerDaily -Settings $Settings -Principal $Principal -Description "YT Manager Autonomous Daily YouTube Upload at 6:00 PM IST" -Force
        Write-Host "`nSUCCESS: Scheduled Task '$TaskName' registered to run daily at 6:00 PM IST." -ForegroundColor Green
    } catch {
        Write-Error "Failed to register Scheduled Task: $_"
    }
}
