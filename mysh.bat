@echo off
title Proverka myshi - kakoj sposob povorachivaet obzor
cd /d "%~dp0"
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo Probuem TRI sposoba podvinut mysh i posle kazhdogo sprashivaem u servera,
echo izmenilsya li ugol obzora.
echo.
echo SNACHALA v igre: Nastrojki - Upravlenie - Nastrojki myshi -
echo "Vvod bez obrabotki" (Raw Input) = VYKL
echo.
echo Potom shchelkni po oknu Minecraft, bud V IGRE (ne v menyu pauzy)
echo i ne trogaj mysh okolo 10 sekund.
echo.
pause
"%PY%" proba_myshi.py
pause
