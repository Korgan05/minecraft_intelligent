@echo off
title Urok 4 - PRYZhKOVYE KRITY
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 4: PRYZhKOVYE KRITY  ======
echo.
echo Kak ty i igraesh obychno. V staryh zapisyah pryzhok na meste vstrechalsya
echo 731 raz - no vmeste s udarom on NE sohranyalsya, pisalos tolko odno.
echo.
echo ChTO DELAT:
echo   1. W, pryzhok, udar v verhnej tochke - obychnyj krit.
echo   2. Mozhesh othodit nazad i uhodit vbok mezhdu kritami - eto MOZhNO,
echo      lyubye sochetaniya teper sohranyayutsya celikom.
echo   3. Derzhi pricel na zombi vse vremya.
echo.
echo Zapishetsya "vpered + pryzhok + udar" vmeste.
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo.
pause
"%PY%" zapis.py --metka pryzhki --minut 5 %*
pause
