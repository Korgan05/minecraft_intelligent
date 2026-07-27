@echo off
title Vtoroj klient - za nim igraesh TY, protiv sushchestva
cd /d "%~dp0.."
set "PY=%USERPROFILE%\minecraft-ai\venv\Scripts\python.exe"
echo.
echo VTOROJ KLIENT dlya boya protiv sushchestva.
echo.
echo Imya igroka: Chelovek. Papka igry: klient2 (svoya, chtoby dva klienta
echo ne zatirali drug drugu nastrojki i logi).
echo.
echo MODA ZDES NET, i eto narochno: za etim klientom igraesh ty rukami,
echo a dva moda stali by dratsya za odin i tot zhe port 25580.
echo.
echo Poryadok boya:
echo   1. server.bat            - podnyat server
echo   2. igra-s-modom.bat      - klient SUShchESTVA (imya Boec)
echo   3. etot fajl             - tvoj klient (imya Chelovek)
echo   4. boj-s-chelovekom.bat  - zapustit boj
echo.
pause
"%PY%" igra.py --vtoroj %*
pause
