<#
.SYNOPSIS
    Manual runner script for YT Manager daily batch execution.
#>
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir
python -m yt_manager run
