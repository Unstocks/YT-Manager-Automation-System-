@echo off
:: Runs YT Manager Telegram Ingestion Bot silently in the background (no black CMD window)
cd /d "%~dp0\.."
start "" pythonw -m yt_manager telegram
echo YT Manager Telegram Bot started silently in the background!
timeout /t 3 >nul
