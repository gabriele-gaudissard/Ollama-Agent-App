$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
Set-Location -LiteralPath $appRoot
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    Write-Host 'Python 3.11+ non trovato. Installalo da python.org e avvia di nuovo Installer.bat.'
    exit 1
}
& $pythonCommand.Source -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ richiesto'"
if ($LASTEXITCODE -ne 0) { exit 1 }
& $pythonCommand.Source -m venv .venv
if ($LASTEXITCODE -ne 0) { exit 1 }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit 1 }
& '.\.venv\Scripts\python.exe' app.py --install
if ($LASTEXITCODE -ne 0) { exit 1 }
$shortcutShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcut = $shortcutShell.CreateShortcut((Join-Path $desktopPath 'Veyq.lnk'))
$shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $appRoot 'Launcher.ps1') + '"'
$shortcut.WorkingDirectory = $appRoot
$shortcut.Description = 'Veyq desktop AI agent'
$shortcut.IconLocation = (Join-Path $appRoot 'assets\brand\veyq-dark.ico') + ',0'
$shortcut.Save()
Write-Host 'Veyq installato. Il motore locale già presente continua a funzionare.'
Write-Host 'Se non hai un motore locale, puoi configurare un endpoint API nelle impostazioni.'
Write-Host 'Aggiornamenti automatici abilitati nelle installazioni da pacchetto GitHub Release.'
