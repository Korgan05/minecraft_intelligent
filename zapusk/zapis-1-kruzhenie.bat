@echo off
title Urok 1 - KRUZhENIE s uderzhaniem pricela
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 1: KRUZhENIE VOKRUG ZOMBI  ======
echo.
echo Eto SAMYJ VAZhNYJ urok. Sushchestvo tak ne umeet vovse:
echo bokom ono hodit 0.8%% vremeni, a chelovek kruzhit vokrug celi vsegda.
echo.
echo ChTO DELAT:
echo   1. Daj zombi podojti na 2-3 bloka.
echo   2. ZAZhMI A (ili D) i NE OTPUSKAJ - idi bokom vokrug nego.
echo   3. Myshyu nepreryvno dovorachivaj, chtoby pricel NE shodil s zombi.
echo   4. Bej levoj knopkoj kazhdyj raz kak mech perezaryadilsya.
echo   5. Menyaj storonu: pokruzhil vlevo - perejdi na D i kruzhi vpravo.
echo.
echo Zapishetsya "vlevo + +5 + udar" - nogi, dovorot i udar VMESTE.
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo Ostanovit ranshe: Ctrl+C V ETOM OKNE.
echo.
pause
"%PY%" zapis.py --metka kruzhenie --minut 6 --szadi %*
pause
