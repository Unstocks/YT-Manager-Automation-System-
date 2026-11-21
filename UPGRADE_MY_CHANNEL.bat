@echo off
title Unstocks Channel Retrofit & Video Upgrade Engine
cd /d "%~dp0"

echo =====================================================================
echo           UNSTOCKS YOUTUBE CHANNEL RETROFIT & UPGRADE ENGINE
echo =====================================================================
echo.
echo Target Channel: @unstocks (UCT0tm0KSB2BlIjdY6uUZCeA)
echo Scope:
echo   1. Fetch all currently uploaded videos.
echo   2. Update Titles to High-CTR Brand-First Business formulas.
echo   3. Replace Descriptions with 6-Stage Authority Funnel & Keywords.
echo   4. Inject High-Volume Business & Shorts Hashtags.
echo   5. Switch Category to 27 (Education).
echo   6. Update Channel About Bio & Keywords.
echo.
echo Press any key to start the upgrade...
pause >nul

python scripts\upgrade_channel_videos.py

echo.
echo =====================================================================
echo                      UPGRADE COMPLETED!
echo =====================================================================
pause
