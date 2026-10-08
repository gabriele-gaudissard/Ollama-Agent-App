@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shortcutShell=New-Object -ComObject WScript.Shell; $link=$shortcutShell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Veyq.lnk')); $link.TargetPath=[IO.Path]::Combine((Get-Location).Path,'Veyq.bat'); $link.WorkingDirectory=(Get-Location).Path; $link.Description='Veyq desktop AI agent'; $link.Save()"
pause
