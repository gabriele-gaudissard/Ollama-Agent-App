@echo off
cd /d "%~dp0"
echo Installazione librerie...
python -m pip install pywebview requests
echo.
echo Avvio in corso...
python app.py
pause