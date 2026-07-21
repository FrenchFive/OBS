@echo off
REM  CHAT YAPPER - one-time install (creates .venv, installs deps)
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

echo Creating virtual environment...
%PY% -m venv .venv
if errorlevel 1 (
    echo.
    echo [ERROR] Python was not found. Install it from https://www.python.org/downloads/
    echo         and RE-RUN this file. During install, tick "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Installing requirements...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Install failed. Check your internet connection and re-run install.bat
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Done! Double-click run.bat to start.
echo ============================================
pause
