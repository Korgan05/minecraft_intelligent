@echo off
title Proverka sredy - krug "uvidel-sdelal-poluchil"
cd /d "%~dp0"
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo Gonyaem SLUCHAJNYE dejstviya 30 sekund i smotrim, chto sreda otdaet:
echo menyaetsya li kadr, kapaet li nagrada za uron, lovitsya li ubijstvo,
echo uklad'yvaemsya li v temp 5 shagov v sekundu.
echo.
echo VAZHNO: shchelkni po oknu Minecraft, bud V IGRE i ne trogaj upravlenie.
echo Sushchestvom budet rasporyazhatsya programma.
echo.
pause
"%PY%" proba_mira.py
pause
