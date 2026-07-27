@echo off
title Proverka tela - glaza i ruki na zhivoj igre
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo REShAYuShchAYa PROVERKA: dojdut li nashi glaza i ruki do igry.
echo.
echo Nazhmem klavishi i podvinem mysh, a pravdu sprosim U SERVERA:
echo sdvinulsya li igrok i povernulsya li obzor. Vrat tut nechem.
echo.
echo VAZHNO: posle zapuska shchelkni po oknu Minecraft i NE trogaj
echo mysh s klaviaturoj okolo 20 sekund. Inache vvod ujdet ne tuda.
echo.
pause
"%PY%" -m proby.proba_tela
pause
