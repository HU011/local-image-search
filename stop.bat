@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$listener=Get-NetTCPConnection -LocalPort 4568 -State Listen -ErrorAction SilentlyContinue; if($listener){Stop-Process -Id $listener.OwningProcess -Force}"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\stop_qdrant.ps1"

echo [OK] Local Image Search services stopped.
pause
