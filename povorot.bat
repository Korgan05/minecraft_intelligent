@echo off
title Zamer povorota - skolko gradusov daet sdvig myshi
cd /d "%~dp0"
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo Sushchestvo povorachivaetsya "na millimetr", hotya po raschetu dolzhno
echo na 15 gradusov. Podozrenie: uskorenie myshi Windows davit melkie sdvigi.
echo.
echo Merim VOSEM velichin i sprashivaem ugol U SERVERA. Vrat nechem.
echo.
echo Shchelkni po oknu Minecraft, bud V IGRE, ne trogaj mysh ~30 sekund.
echo.
pause
"%PY%" proba_povorota.py
pause
