@echo off
:: Stops running pythonw instances of the Telegram bot
taskkill /f /im pythonw.exe 2>nul
echo YT Manager Telegram Bot background process stopped.
timeout /t 3 >nul
