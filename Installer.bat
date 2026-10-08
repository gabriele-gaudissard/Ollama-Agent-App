@echo off
cd /d "%~dp0"
title Veyq Setup
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 echo Installazione non completata. Leggi l'errore qui sopra.
pause
