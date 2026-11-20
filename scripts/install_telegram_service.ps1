<#
.SYNOPSIS
    Registers YT Manager Telegram Bot to run automatically and silently at Windows logon.
.DESCRIPTION
    Launches headless via pythonw.exe so no console window is ever visible.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonwExe = (Get-Command pythonw).Source

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   YT MANAGER — TELEGRAM BOT BACKGROUND SERVICE SETUP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project Directory: $ProjectDir"
Write-Host "Pythonw Executable: $PythonwExe"

$TaskName = "YT-Manager-Telegram-Bot"
$Action = New-ScheduledTaskAction -Execute $PythonwExe -Argument "-m yt_manager telegram" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "YT Manager Telegram Phone Ingest Background Service" -Force
    Write-Host "`nSUCCESS: Background service '$TaskName' registered to run on Windows startup!" -ForegroundColor Green
    Write-Host "You never need to open CMD again — the bot will always be ready for phone uploads." -ForegroundColor Green
} catch {
    Write-Error "Failed to register Scheduled Task: $_"
}
