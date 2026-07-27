@echo off
title BOJ SUShchESTVA PROTIV CheLOVEKA
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  BOJ PROTIV CheLOVEKA  ======
echo.
echo Chto menyaetsya v etom rezhime:
echo   * zombi NE prizyvayutsya - protivnik ty;
echo   * ubijstvo cheloveka schitaetsya pobedoj (schetchik player_kills);
echo   * oba bojca gotovyatsya odinakovo: 40 zdorovya i zheleznyj mech;
echo   * vas rasstavlyayut po raznym storonam zagona, licom drug k drugu.
echo.
echo SNAChALA dolzhny byt zapushcheny:
echo   server.bat, igra-s-modom.bat (Boec), vtoroj-klient.bat (Chelovek)
echo.
echo SOVET po obucheniyu: ne ubivaj ego srazu. Daj sebya udarit neskolko raz -
echo sushchestvo poluchaet nagradu za uron i nachinaet schitat tebya celyu.
echo Esli vynesti ego s pervoj sekundy, on nichemu ne nauchitsya.
echo.
echo VNIMANIE: mozg budet menyatsya. Snimok sdelaj zarani, esli zhalko.
echo.
pause
"%PY%" obuchenie.py --protiv-cheloveka %*
pause
