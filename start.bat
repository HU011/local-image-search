@echo off
setlocal
chcp 65001 >nul
title Local Image Search Service

cd /d "%~dp0"

set "IMAGE_SEARCH_PYTHON=%CD%\python\python.exe"
if not exist "%IMAGE_SEARCH_PYTHON%" set "IMAGE_SEARCH_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%IMAGE_SEARCH_PYTHON%" (
    echo [INFO] First run: installing the isolated Python environment...
    call "%CD%\install.bat"
    if errorlevel 1 exit /b 1
    set "IMAGE_SEARCH_PYTHON=%CD%\venv\Scripts\python.exe"
)

set "PYTHONPATH=%CD%;%CD%\vendor;%CD%\venv\Lib\site-packages"
set "PYTHONNOUSERSITE=1"
set "HF_HOME=%CD%\models\huggingface"
set "TRANSFORMERS_CACHE=%CD%\models\huggingface"

echo [INFO] Starting local Qdrant Server...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\start_qdrant.ps1"
if errorlevel 1 (
    echo [ERROR] Qdrant Server failed to start.
    pause
    exit /b 1
)

echo ================================================
echo           Local Image Search Service
echo ================================================
echo [INFO] API:  http://127.0.0.1:4568
echo [INFO] Docs: http://127.0.0.1:4568/docs
echo [INFO] Vector DB: local Qdrant Server at 127.0.0.1:6335
echo [INFO] Data: %CD%\data\qdrant-server\storage
echo [INFO] Existing snapshots are restored on first startup when present.
echo.

"%IMAGE_SEARCH_PYTHON%" -m app.main

pause
