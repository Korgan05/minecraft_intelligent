@echo off
title Obuchenie protiv zombi - svoya laboratoriya
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  OBUCHENIE S NAGRADOJ (protiv zombi)  ======
echo.
echo SNAChALA dolzhny byt zapushcheny:
echo   server.bat        - server
echo   igra-s-modom.bat  - klient s modom, i ty V MIRE
echo.
echo Fokus okna igre NE nuzhen: mod chitaet kadrovyj bufer igry, a ne ekran.
echo Okno mozhno zakryt drugimi oknami. NELZYA tolko svorachivat -
echo svernutoe okno sistema perestaet pererisovyvat, i sushchestvo osleplo.
echo.
echo Poka idet obuchenie, NE zahodi v igru myshyu: esli fokus na igre,
echo tvoi dvizheniya myshyu skladyvayutsya s ego pricelom i portyat navodku.
echo.
echo PAUZA - klavisha P v igre. Escape pri aktivnom okne tozhe ostanavlivaet.
echo OSTANOVIT SOVSEM: Ctrl+C V ETOM OKNE. Mozg sohranitsya.
echo Mozg sohranyaetsya i po hodu, kazhdye 1000 shagov (models\ubijca_ckpt_*).
echo.
echo SKOLKO ShAGOV (5 shagov v sekundu):
echo   obuchenie.bat --shagov 10000    okolo 35 minut
echo   obuchenie.bat --shagov 20000    okolo 1 ch 10 min
echo   obuchenie.bat --shagov 40000    okolo 2 ch 20 min
echo Bez klyucha idet do dvuh millionov - poka sam ne ostanovish Ctrl+C.
echo.
pause
"%PY%" obuchenie.py %*
pause
