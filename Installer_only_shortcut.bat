@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shortcutShell=New-Object -ComObject WScript.Shell; $link=$shortcutShell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Veyq.lnk')); $link.TargetPath=[IO.Path]::Combine($env:SystemRoot,'System32\WindowsPowerShell\v1.0\powershell.exe'); $link.Arguments='-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File '+[char]34+[IO.Path]::Combine((Get-Location).Path,'Launcher.ps1')+[char]34; $link.WorkingDirectory=(Get-Location).Path; $link.Description='Veyq desktop AI agent'; $link.IconLocation=[IO.Path]::Combine((Get-Location).Path,'assets\brand\veyq-dark.ico')+',0'; $link.Save()"
pause
