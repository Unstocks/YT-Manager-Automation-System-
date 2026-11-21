@echo off
title Unstocks Channel - Restore All Original Video Titles & Context
cd /d "%~dp0"

echo =====================================================================
echo        UNSTOCKS YOUTUBE CHANNEL: RESTORE ORIGINAL METADATA
echo =====================================================================
echo.
echo Restoring exact original topics and authentic context for all 11 videos:
echo.
echo   1. Can Reliance Make Campa Cola Beat Coca-Cola & Pepsi?
echo   2. Rameshwaram Cafe: The High-Volume Dosa Empire
echo   3. DS Group Strategy: From Raw Tobacco to FMCG Giant
echo   4. DS Group: 1 Rs to 750 Crore - Pulse Candy Disruption
echo   5. Pay Yourself First..! (Wealth Mindset)
echo   6. Let Assets Pay Your Liabilities..!
echo   7. Paying Yourself First Actually Works
echo   8. Decision-Making Is a Trained Skill (Mental Models)
echo   9. Decision-Making Is a Trained Skill (Structured Problem Solving)
echo  10. Garden & Flower Bed Design Ideas
echo  11. Kitchen Organization & Space Saving Ideas
echo.
echo NO VIDEOS WILL BE DELETED. All original content is preserved!
echo.
echo Press any key to apply this restoration to YouTube...
pause >nul

python scripts\restore_video_metadata.py

echo.
echo =====================================================================
echo                    ALL VIDEOS SUCCESSFULLY RESTORED!
echo =====================================================================
pause
