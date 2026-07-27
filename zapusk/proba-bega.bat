@echo off
title Proverka bega - vidit li mod tvoj sprint i begaet li sushchestvo
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo PROVERKA BEGA. Dve raznye veshchi:
echo   1. vidit li mod TVOJ beg (nuzhno dlya zapisi uroka);
echo   2. begaet li SAMO SUShchESTVO, kogda mod prosit.
echo.
echo Vtoraya vazhnee: pod beg zaveden celyj kanal, i esli on nichego ne delaet,
echo sushchestvo budet tratit na nego resheniya darom.
echo.
echo Merim ne priznak, a PROJDENNOE RASSTOYaNIE: shagom okolo 4.3 bloka
echo v sekundu, begom okolo 5.6. Priznak mog by vrat, rasstoyanie net.
echo.
echo Tolko proverka sushchestva, bez tebya:  proba-bega.bat --bez-menya
echo.
pause
"%PY%" -m proby.proba_bega %*
pause
