@echo off
title Urok 3 - RAZVOROT k zombi, kotoryj SZADI
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 3: RAZVOROT K CELI SZADI  ======
echo.
echo Zdes zombi POYAVLYaETSYa ROVNO ZA TVOEJ SPINOJ kazhduyu volnu.
echo Ranshe on vozникal gde popalo, i takuyu situaciyu prihodilos zhdat -
echo v zapis shli minuty pustogo stoyaniya. Teper ona stavitsya narochno.
echo.
echo ChTO DELAT:
echo   1. Zombi uzhe szadi. Razvernis k nemu ODNIM REZKIM DVIZhENIEM myshi.
echo      NE plavno! Plavnyj povorot razlozhitsya na melkie dovoroty,
echo      i krupnyj razmah v urok ne popadet.
echo   2. Razvernulsya - srazu dobej.
echo   3. Ubil - novyj poyavitsya snova szadi. Povtoryaj.
echo.
echo Zapishetsya "krugom" ili "-90" odnim shagom. V staryh zapisyah ih NOL.
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo.
pause
"%PY%" zapis.py --metka szadi --minut 5 --szadi %*
pause
