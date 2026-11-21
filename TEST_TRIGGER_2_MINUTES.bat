@echo off
cd /d "%~dp0"
echo ============================================================
echo   YT MANAGER - 2-MINUTE AUTOMATIC TRIGGER AUDIT TEST
echo ============================================================
echo This test will:
echo  1. Register a temporary task set to fire in 2 minutes
echo  2. Show a live countdown while waiting
echo  3. Verify that Windows Task Scheduler fires automatically
echo  4. Measure precision down to the second
echo  5. Clean up the test task
echo.
echo Press any key to start the 2-minute live test...
pause >nul
echo.
python -m yt_manager schedule --test --minutes 2
echo.
pause
