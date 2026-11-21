@echo off
title Unstocks - Upgrade Uploaded Clips Only
cd /d "%~dp0"

echo =====================================================================
echo         UNSTOCKS: TARGETED UPGRADE FOR UPLOADED CLIPS ONLY
echo =====================================================================
echo.
echo Strict Policy:
echo   - Pre-existing channel videos (Campa Cola, Rameshwaram Cafe, DS Group,
echo     Pay Yourself First, etc.) will NOT be touched.
echo   - ONLY the 4 pipeline-uploaded clips will be upgraded with in-depth
echo     voiceover and visual frame analysis:
echo.
echo     1. [wuMZFV_zse8] How Netflix Built A 325M Subscriber Monopoly
echo     2. [dNrMoLs5VOY] The $8 Billion SaaS Secret Behind Zoom
echo     3. [9PK37JRn6C8] Why Hustle Culture Kills Startups: Build Systems Instead
echo     4. [n0x4dClBWgM] The 35,000 Daily Decisions That Make Or Break Startups
echo.
echo Press any key to apply this upgrade to YouTube...
pause >nul

python scripts\upgrade_uploaded_clips_only.py

echo.
echo =====================================================================
echo                    TARGETED UPGRADE COMPLETED!
echo =====================================================================
pause
