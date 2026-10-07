@echo off
color 0b
title Shortcut Creator
cd /d "%~dp0"

echo ===================================================
echo      CREAZIONE COLLEGAMENTO SUL DESKTOP...
echo ===================================================
echo.

:: 1. Crea il file di avvio pulito per rimuovere la finestra nera
echo @echo off > Ollama.bat
echo cd /d "%%~dp0" >> Ollama.bat
echo start "" pythonw app.py >> Ollama.bat

:: 2. Crea lo script VBS per piazzare l'icona sul Desktop chiamata "Ollama"
set VBS_SCRIPT="%TEMP%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\Ollama.lnk" >> %VBS_SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_SCRIPT%
echo oLink.TargetPath = "%~dp0Ollama.bat" >> %VBS_SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS_SCRIPT%
echo oLink.Description = "Codex Professional Agent" >> %VBS_SCRIPT%
echo oLink.IconLocation = "%windir%\system32\shell32.dll, 25" >> %VBS_SCRIPT%
echo oLink.Save >> %VBS_SCRIPT%

cscript /nologo %VBS_SCRIPT%
del %VBS_SCRIPT%

echo.
echo ===================================================
echo COLLEGAMENTO CREATO CON SUCCESSO!
echo Troverai l'icona "Ollama" sul tuo Desktop.
echo ===================================================
pause