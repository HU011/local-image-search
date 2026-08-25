@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo       Local Image Search Environment Setup
echo ================================================

where py.exe >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv venv
) else (
    where python.exe >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.10 or newer is required.
        echo [INFO] Install Python from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    python -m venv venv
)

if errorlevel 1 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b 1
)

venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1

venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo [OK] Python environment is ready.
exit /b 0
