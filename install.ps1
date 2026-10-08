param([switch]$ShortcutOnly, [string]$ShortcutDirectory = '')
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
Set-Location -LiteralPath $appRoot
function New-AppShortcuts {
    $iconPath = Join-Path $appRoot 'assets\brand\veynuq-dark.ico'
    if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) { throw 'App icon is missing. Extract the complete release archive and run the installer again.' }
    $shortcutShell = New-Object -ComObject WScript.Shell
    $locations = if ($ShortcutDirectory) { @($ShortcutDirectory) } else { @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'Veynuq')) }
    foreach ($location in $locations) {
        New-Item -ItemType Directory -Path $location -Force | Out-Null
        $shortcut = $shortcutShell.CreateShortcut((Join-Path $location 'Veynuq.lnk'))
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $appRoot 'Launcher.ps1') + '"'
        $shortcut.WorkingDirectory = $appRoot
        $shortcut.Description = 'Veynuq desktop AI agent'
        $shortcut.IconLocation = $iconPath + ',0'
        $shortcut.Save()
        $oldPath = Join-Path $location 'Veyq.lnk'
        if (Test-Path -LiteralPath $oldPath) {
            $old = $shortcutShell.CreateShortcut($oldPath)
            if ($old.WorkingDirectory -eq $appRoot) { Remove-Item -LiteralPath $oldPath }
        }
    }
}
if ($ShortcutOnly) { New-AppShortcuts; exit 0 }
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
New-AppShortcuts
Write-Host 'Veynuq installato. Il motore locale già presente continua a funzionare.'
Write-Host 'Se non hai un motore locale, puoi configurare un endpoint API nelle impostazioni.'
Write-Host 'Aggiornamenti automatici abilitati nelle installazioni da pacchetto GitHub Release.'
