@echo off
cd /d "%~dp0"
echo ============================================================
echo   YT MANAGER - RUN TODAY'S HARVEST AND UPLOAD
echo ============================================================
echo 1. Checking inbox / Pinterest board
echo 2. Auto-harvesting 2 vertical Shorts
echo 3. Generating SEO metadata
echo 4. Uploading to YouTube (@unstocks)
echo ============================================================
python -m yt_manager run
echo.
pause
