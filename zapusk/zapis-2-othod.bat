@echo off
title Urok 2 - OTHOD i podhod ne otpuskaya pricel
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 2: OTHOD I PODHOD S PRICELOM  ======
echo.
echo Tvoj sobstvennyj priem: udaril - otoshel, chtoby ne poluchit v otvet.
echo.
echo ChTO DELAT:
echo   1. Udaril zombi - ZAZhMI S i othodi nazad.
echo   2. Myshyu derzhi pricel na nem vse vremya othoda.
echo   3. Otoshel na paru blokov - zazhmi W i nastupaj obratno, bej na podhode.
echo   4. Szadi stena? Uhodi po diagonali: S+A ili S+D. Eto MOZhNO i nuzhno -
echo      diagonali kak raz i poyavilis v novom nabore dejstvij.
echo.
echo Zapishetsya "nazad-vlevo + -5" i "vpered + +5 + udar".
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo.
pause
"%PY%" zapis.py --metka othod --minut 5 %*
pause
