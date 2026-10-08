@echo off
title Razbor razvala - pochemu sushchestvo razuchivaetsya
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  RAZBOR RAZVALA (igra NE nuzhna)  ======
echo.
echo Tri merki na nastoyashchih kadrah tvoej igry:
echo   1. skolko reshenij menyaetsya za 1000 shagov obucheniya
echo   2. kuda smeshchaetsya vybor po kazhdomu kanalu
echo   3. vinovaty li svezhie vesa pamyati
echo.
pause
"%PY%" proby\razbor_razvala.py %*
pause
