@echo off
title Unstocks Master Automation Console
cd /d "%~dp0"
cls

:MENU
cls
echo =====================================================================
echo                    UNSTOCKS AUTOMATION CONSOLE
echo =====================================================================
echo   Target Channel: @unstocks (UCT0tm0KSB2BlIjdY6uUZCeA)
echo   Schedule: 18:00 IST Daily + Boot Catch-up
echo =====================================================================
echo.
echo   [1] Run Today's Upload Batch (Manual Execution)
echo   [2] Install / Verify Windows Task Scheduler (18:00 IST)
echo   [3] Survey Channel Videos (Refresh Inventory)
echo   [4] Apply Targeted Upgrade to Uploaded Clips Only
echo   [5] Restore Video Metadata from Plan
echo   [6] Connect / Setup OneDrive Inbox
echo   [7] Run Full Test Suite (35 Tests)
echo   [0] Exit
echo.
echo =====================================================================
set /p choice="Enter choice [0-7]: "

if "%choice%"=="1" goto RUN_UPLOAD
if "%choice%"=="2" goto INSTALL_SCHED
if "%choice%"=="3" goto SURVEY
if "%choice%"=="4" goto UPGRADE_TARGETED
if "%choice%"=="5" goto RESTORE
if "%choice%"=="6" goto ONEDRIVE
if "%choice%"=="7" goto RUN_TESTS
if "%choice%"=="0" goto EXIT

echo Invalid option. Please try again.
timeout /t 2 >nul
goto MENU

:RUN_UPLOAD
cls
echo Starting Today's Batch Upload...
python -m yt_manager run
echo.
pause
goto MENU

:INSTALL_SCHED
cls
echo Installing / Verifying Windows Task Scheduler...
powershell -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1
echo.
pause
goto MENU

:SURVEY
cls
echo Surveying Channel Videos...
python scripts\survey_channel.py
echo.
pause
goto MENU

:UPGRADE_TARGETED
cls
echo Upgrading Uploaded Clips (Guaranteed to not touch pre-existing videos)...
python scripts\upgrade_uploaded_clips_only.py
echo.
pause
goto MENU

:RESTORE
cls
echo Restoring Video Metadata from data\restore_plan.json...
python scripts\restore_video_metadata.py
echo.
pause
goto MENU

:ONEDRIVE
cls
echo Setting up OneDrive Inbox Link...
powershell -ExecutionPolicy Bypass -File scripts\setup_onedrive_inbox.ps1
echo.
pause
goto MENU

:RUN_TESTS
cls
echo Running Full Automated Test Suite...
python -m unittest discover tests
echo.
pause
goto MENU

:EXIT
exit /b 0
