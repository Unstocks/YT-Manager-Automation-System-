@echo off
title Unstocks Channel - Complete Video Survey
cd /d "%~dp0"

echo =====================================================================
echo            UNSTOCKS YOUTUBE CHANNEL: VIDEO SURVEY AGENT
echo =====================================================================
echo.
echo Connecting to YouTube Channel: @unstocks
echo Surveying every video, pulling titles, descriptions, views, and links...
echo.

python scripts\survey_channel.py

echo.
echo =====================================================================
echo Survey Report written to: data\channel_inventory.md
echo =====================================================================
pause
