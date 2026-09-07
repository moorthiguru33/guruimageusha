@echo off
title TamilPSD - Auto Pipeline Dashboard
color 0A
cd /d "%~dp0"
echo ==========================================================
echo       TAMILPSD AUTOMATED PIPELINE DASHBOARD
echo ==========================================================
echo Starting local web server...
timeout /t 2 >nul
start "" http://localhost:3000
node server.js
pause
