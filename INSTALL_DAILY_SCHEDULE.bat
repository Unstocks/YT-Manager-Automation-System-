@echo off
cd /d "%~dp0"
echo ============================================================
echo   YT MANAGER - REGISTER PERMANENT WINDOWS DAILY TASK
echo ============================================================
echo Registering task in Windows Task Scheduler (hard drive storage)...
echo Triggers:
echo   1. Daily at 18:00 (6:00 PM IST) with WakeToRun
echo   2. At LogOn (Automatic catch-up on boot if 18:00 was missed)
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\install_scheduler.ps1"
echo.
echo ============================================================
echo System Status Verification:
python -m yt_manager status
echo ============================================================
pause
