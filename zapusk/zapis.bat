@echo off
title Zapis pokaza - igraesh OBYCHNO, svoim klientom
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ZAPIS POKAZA. Polnyj ekran, normalnaya mysh, tvoj klient.
echo.
echo Otschet nachnetsya s pervogo zapisannogo kadra, tak chto
echo mozhesh ne toropitsya: shchelkni po Minecraft kogda gotov.
echo.
echo OSTANOVIT: Ctrl+C V ETOM OKNE (ne zakryvaj krestikom).
echo Zapis sohranyaetsya PO HODU kazhdye 30 sekund, poteryat igru nelzya.
echo.
echo ChTO POKAZAT (ranshe zapis eto TERYALA, teper sohranyaet):
echo   1. KRUZHI vokrug zombi bokom - zazhmi A ili D i derzhi pricel na nem.
echo      Eto glavnoe: sushchestvo tak ne umeet i nauchitsya tolko ot tebya.
echo   2. Othodi nazad ne otpuskaya pricel - S plyus dovorot myshyu.
echo   3. Razvernis krugom - proveryaem razmah 180.
echo   4. Paru obychnyh ubijstv s pryzhkovymi kritami.
echo.
echo V konce pokazhet dve stroki: "krupnyh povorotov" i
echo "dvizhenie I povorot vmeste". Esli oba ne nol - urok lyog kak nado.
echo.
pause
"%PY%" zapis.py %*
pause
