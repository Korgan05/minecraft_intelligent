@echo off
title Obuchenie ubijcy - svoya laboratoriya
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo OBUCHENIE S NAGRADOJ. Ni MineRL, ni Malmo - tolko nasha laboratoriya.
echo.
echo Sushchestvo prodolzhaet s mozga posle razminki:
echo 176 tysyach shagov starogo opyta + podrazhanie tvoemu pokazu.
echo.
echo SRAZU POSLE ZAPUSKA shchelkni po oknu Minecraft.
echo Esli fokus ujdet - obuchenie samo vstanet na pauzu i dozhdetsya.
echo.
echo OSTANOVIT: Ctrl+C V ETOM OKNE. Mozg sohranitsya.
echo.
echo Sovet: sdelaj okno igry pomenshe, chtoby videt i konsol tozhe.
echo Na kadr sushchestva eto ne vliyaet - on vsegda 64x64.
echo.
pause
"%PY%" obuchenie.py %*
pause
