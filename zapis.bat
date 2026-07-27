@echo off
title Zapis pokaza - igraesh OBYCHNO, svoim klientom
cd /d "%~dp0"
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ZAPIS POKAZA. Polnyj ekran, normalnaya mysh, tvoj klient.
echo.
echo SRAZU POSLE ZAPUSKA shchelkni po oknu Minecraft, inache zapis na pauze.
echo.
echo OSTANOVIT: Ctrl+C V ETOM OKNE (ne zakryvaj krestikom).
echo Zapis sohranyaetsya PO HODU kazhdye 30 sekund, poteryat igru nelzya.
echo.
echo Deris kak obychno. Ubil zombi - prizovu novogo sam.
echo GLAVNOE: POKAZHI POVOROTY K CELI. Sushchestvo bilo stenu,
echo poka zombi ubival ego szadi - povorotov ono ne videlo ni odnogo.
echo.
pause
"%PY%" zapis.py %*
pause
