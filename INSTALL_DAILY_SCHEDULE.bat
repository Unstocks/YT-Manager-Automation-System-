@echo off
cd /d "%~dp0"
echo ============================================================
echo   YT MANAGER - REGISTER PERMANENT WINDOWS DAILY TASK
echo ============================================================
echo Registering task in Windows Task Scheduler (hard drive storage)...
echo Trigger: Daily at 18:00 (6:00 PM IST) + on system boot if missed
echo.
python -m yt_manager schedule --install
echo.
echo ============================================================
echo Task status check:
python -m yt_manager status
echo ============================================================
pause
