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
Start-Process -FilePath $pythonPath -ArgumentList @('"' + (Join-Path $appRoot 'app.py') + '"') -WorkingDirectory $appRoot -WindowStyle Hidden
