@echo off
title Sborka moda Pupovina
cd /d "%~dp0..\mod"
set "JAVA_HOME=%USERPROFILE%\minecraft-ai\jdk8"
echo.
echo Sobirayu mod. Gotovyj jar lyazhet v mod\build\libs\pupovina-0.1.0.jar
echo Etot fajl mozhno polozhit v .minecraft\mods obychnogo klienta.
echo.
call gradlew.bat build
echo.
dir /b build\libs
pause
