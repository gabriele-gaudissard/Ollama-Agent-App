$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$pythonPath = Join-Path $appRoot '.venv\Scripts\pythonw.exe'
$runtimeFile = Join-Path $appRoot 'runtime.json'
if (Test-Path -LiteralPath $runtimeFile) {
    $runtimeInfo = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    $candidate = [IO.Path]::GetFullPath($runtimeInfo.python)
    if ($candidate.StartsWith($appRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        $pythonPath = $candidate.Replace('python.exe', 'pythonw.exe')
    }
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $systemPython = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($systemPython) { $pythonPath = $systemPython.Source }
    else { throw 'Python non trovato. Esegui Installer.bat.' }
}
# pythonw already avoids a console. Hiding this process also hides its first
# Windows Forms window, leaving a running agent with no visible interface.
Start-Process -FilePath $pythonPath -ArgumentList @('"' + (Join-Path $appRoot 'app.py') + '"') -WorkingDirectory $appRoot -WindowStyle Normal
