@echo off
title Urok 2 - OTHOD i UDAR V SPRINTE (otkid)
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  UROK 2: OTHOD I UDAR V SPRINTE  ======
echo.
echo Udar V SPRINTE daet USILENNYJ OTKID - im chelovek otbrasyvaet moba ot sebya.
echo Protiv kripera eto spasaet zhizn: on otletaet, ne uspev vzorvatsya.
echo U sushchestva bega ne bylo VOVSE, tak chto ottolknut nikogo ono ne moglo.
echo.
echo RITM, kotoryj nado pokazat (povtoryaj krug za krugom):
echo   1. ZAZhMI S - othodi nazad, myshyu DERZhI PRICEL na zombi.
echo   2. Otoshel na 3-4 bloka - otpusti S.
echo   3. ZAZhMI W + LEVYJ CTRL - razbegajsya na nego (mozhno i dvojnym W).
echo   4. UDAR v moment razbega - zombi otletit.
echo   5. Srazu snova S i othodi. I tak po krugu.
echo.
echo Szadi stena? Uhodi po diagonali: S+A ili S+D. Eto MOZhNO -
echo diagonali kak raz i poyavilis v novom nabore dejstvij.
echo.
echo Zapishetsya "vpered + -5 + udar + begom" - vse chetyre chasti vmeste.
echo V konce posmotri stroku "begom: N shagov, iz nih s udarom: M".
echo Esli M nol - spring v udar ne popal, nado bit imenno na razbege.
echo.
echo Otschet nachnetsya s pervogo kadra: shchelkni po Minecraft kogda gotov.
echo.
pause
"%PY%" zapis.py --metka othod-sprint --minut 5 %*
pause
