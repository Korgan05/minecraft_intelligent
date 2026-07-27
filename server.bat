@echo off
title Server bojni - laboratoriya ubijcy
cd /d "%~dp0server"
echo.
echo Podnimayu server 1.16.5 (mir "bojnya", konsol na 127.0.0.1:25575).
echo Posle stroki "Done" zahodi klientom: Setevaya igra - Pryamoe podklyuchenie - 127.0.0.1
echo.
echo Ostanovit server: napishi v etom okne  stop  i nazhmi Enter.
echo.
"%USERPROFILE%\minecraft-ai\jdk8\bin\java.exe" -Xmx2G -Xms1G -jar server.jar nogui
pause
