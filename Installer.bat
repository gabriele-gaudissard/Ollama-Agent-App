@echo off
color 0b
title Codex Agent Setup
cd /d "%~dp0"

echo ===================================================
echo      INSTALLING CODEX AGENT...
echo ===================================================
echo.

echo [1/4] Installing Python libraries...
python -m pip install pywebview requests beautifulsoup4

echo.
echo [2/4] Checking local Ollama installation...
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo Ollama not found. Starting automatic download...
    powershell -Command "irm https://ollama.com/install.ps1 | iex"
) else (
    echo Ollama is already installed and ready.
)

echo.
echo ===================================================
echo [3/4] SELECT YOUR STARTING AI MODEL
echo ===================================================
echo You can change this later or download new ones from the App Settings.
echo.
echo [1] qwen2.5-coder:14b (Recommended for 16GB+ RAM - Advanced Coding)
echo [2] qwen2.5-coder:7b  (Recommended for 8GB+ RAM - Fast Coding)
echo [3] llama3.1:8b       (Great for general chat and fast tasks)
echo.
set /p MCHOICE="Enter 1, 2, or 3 (default 1): "

set MODEL=qwen2.5-coder:14b
if "%MCHOICE%"=="2" set MODEL=qwen2.5-coder:7b
if "%MCHOICE%"=="3" set MODEL=llama3.1:8b

echo.
echo You selected: %MODEL%
echo Downloading %MODEL%... This might take a few minutes.
ollama pull %MODEL%

:: Configurazione iniziale
echo {"settings": {"lang": "it", "url": "http://localhost:11434", "token": "", "model": "%MODEL%"}, "memory": "", "sessions": []} > codex_data.json

echo.
echo [4/4] Creating launcher and Desktop shortcut...
echo @echo off > Start_Codex.bat
echo cd /d "%%~dp0" >> Start_Codex.bat
echo start "" pythonw app.py >> Start_Codex.bat

set VBS_SCRIPT="%TEMP%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\Codex Agent.lnk" >> %VBS_SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_SCRIPT%
echo oLink.TargetPath = "%~dp0Start_Codex.bat" >> %VBS_SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS_SCRIPT%
echo oLink.Description = "Codex Professional Agent" >> %VBS_SCRIPT%
echo oLink.IconLocation = "%windir%\system32\shell32.dll, 25" >> %VBS_SCRIPT%
echo oLink.Save >> %VBS_SCRIPT%

cscript /nologo %VBS_SCRIPT%
del %VBS_SCRIPT%

echo.
echo ===================================================
echo SETUP COMPLETED SUCCESSFULLY!
echo You can now launch the app from your Desktop shortcut.
echo ===================================================
pause