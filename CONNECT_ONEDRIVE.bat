@echo off
title Connect YT-Manager to OneDrive
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_onedrive_inbox.ps1"
echo.
pause
