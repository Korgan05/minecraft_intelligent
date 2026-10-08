@echo off
title Urok 5 - DUEL S MEChNIKOM (pokaz taktiki)
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 5: DUEL S MEChNIKOM  ======
echo.
echo POChEMU ETOT UROK NUZhEN. Tri progona RL ne nashli kontr-taktiku protiv
echo zombi s zheleznym mechom: razvedka ne otkryvaet svyazku "vyshel iz
echo zamaha - voshel - udaril - vyshel", a kazhdaya neudachnaya popytka
echo nakazyvaetsya smertyu. Sushchestvo deretsya s mechnikom tem zhe razmenom,
echo chto i s prostym zombi - i proigryvaet kazhduyu vtoruyu duel.
echo.
echo USLOVIYa (uzhe vystavleny v arene):
echo   * VSE zombi s zheleznymi mechami;
echo   * u tebya ChESTNYE 20 zdorovya i zheleznyj mech - to zhe telo, chto u sushchestva.
echo.
echo ChTO POKAZYVAT - taktiku, kotoroj ty bil ego v sparringe:
echo   1. NE stoj v razmen! Mechnik bet ~8 - DVE-TRI oshibki i smert. Igraj chisto.
echo   2. Strafe vokrug, vhodi na udar KOGDA MEChNIK PROMAHNULSYa,
echo      bej 1-2 raza i SRAZU vyhodi iz ego zamaha.
echo   3. Otstuplenie - zakonnyj priem: otoshel, podlechilsya, voshel snova.
echo.
echo GLAVNOE PRAVILO POKAZA: on obyazan soderzhat RABOTAYuShchIJ priem.
echo Sushchestvo skopiruet VSE, chto ty delaesh - i pobedy, i oshibki.
echo Esli boj poshel ploho - luchshe pogibni bystro, chem pokazyvaj
echo minutu bespomoshchnogo begstva: ono skopiruet begstvo.
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo Ostanovit zapis: Escape pri aktivnom okne igry.
echo.
pause
"%PY%" zapis.py --metka duel-mechnik --minut 6 %*
pause
