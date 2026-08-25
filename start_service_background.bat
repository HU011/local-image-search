@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%CD%\logs" mkdir "%CD%\logs"

set "IMAGE_SEARCH_PYTHON=%CD%\python\python.exe"
if not exist "%IMAGE_SEARCH_PYTHON%" set "IMAGE_SEARCH_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%IMAGE_SEARCH_PYTHON%" (
    call "%CD%\install.bat" >> "%CD%\logs\install.stdout.log" 2>> "%CD%\logs\install.stderr.log"
    if errorlevel 1 exit /b 1
    set "IMAGE_SEARCH_PYTHON=%CD%\venv\Scripts\python.exe"
)

set "PYTHONPATH=%CD%;%CD%\vendor;%CD%\venv\Lib\site-packages"
set "PYTHONNOUSERSITE=1"
set "HF_HOME=%CD%\models\huggingface"
set "TRANSFORMERS_CACHE=%CD%\models\huggingface"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\start_qdrant.ps1" >> "%CD%\logs\qdrant-launch.stdout.log" 2>> "%CD%\logs\qdrant-launch.stderr.log"
if errorlevel 1 exit /b 1

"%IMAGE_SEARCH_PYTHON%" -m app.main >> "%CD%\logs\api.stdout.log" 2>> "%CD%\logs\api.stderr.log"
