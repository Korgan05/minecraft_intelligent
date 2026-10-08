@echo off
title Pochinit razgon Adam posle operacii nad mozgom
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo ======  POChINIT RAZGON ADAM (igra NE nuzhna)  ======
echo.
echo Posle lyuboj operacii nad mozgom (pamyat, kanaly, golova) razgon Adam
echo obnulyaetsya, i pervye obnovleniya shvyryayut mozg naugad.
echo Oba obvala sluchilis srazu posle operacii nad mozgom.
echo.
echo ZAPUSKAT POSLE KAZhDOJ operacii nad mozgom, PERED obucheniem.
echo.
pause
"%PY%" pochinit_razgon.py %*
pause
