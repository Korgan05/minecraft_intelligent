@echo off
title Minecraft 1.16.5 s modom Pupovina
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo Zapuskayu chistyj Forge 1.16.5, gde stoit TOLKO nash mod.
echo Sborka JoJo iz .minecraft ne zagruzhaetsya - u nas svoya papka igry.
echo.
echo SNAChALA podnimi server: zapusk\server.bat
echo Server "Bojnya (mod)" uzhe v spiske: Setevaya igra - dvojnoj shchelchok.
echo Pauza obucheniya v igre - klavisha P.
echo.
pause
"%PY%" igra.py
pause
