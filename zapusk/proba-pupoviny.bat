@echo off
title Proverka pupoviny - glaza i ruki cherez mod
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo PROVERKA MODA: pravda li on daet sushchestvu glaza i ruki.
echo.
echo Mod govorit "povernul na 90 gradusov" - a my sprashivaem SERVER,
echo na skolko povernulsya igrok na samom dele.
echo.
echo Nuzhno: server podnyat (server.bat) i igra s modom zapushchena
echo (igra-s-modom.bat), igrok stoit v zagone.
echo.
echo V konce budet proverka BEZ FOKUSA - tam nado budet pereklyuchitsya
echo na drugoe okno. Radi etogo mod i delalsya.
echo.
pause
"%PY%" -m proby.proba_pupoviny
pause
