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

REM pywin32 (used by the pyttsx3 voice) sometimes needs its post-install step
if exist ".venv\Scripts\pywin32_postinstall.py" (
    ".venv\Scripts\python.exe" ".venv\Scripts\pywin32_postinstall.py" -install >nul 2>&1
)

echo Checking the install...
".venv\Scripts\python.exe" -c "import aiohttp, dotenv, obsws_python, openai, pydantic_core" >nul 2>&1
if errorlevel 1 (
    echo Some packages look broken - repairing them, this can take a minute...
    ".venv\Scripts\python.exe" -m pip install --force-reinstall --no-cache-dir openai pydantic pydantic-core
    ".venv\Scripts\python.exe" -c "import aiohttp, dotenv, obsws_python, openai, pydantic_core" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [WARNING] The OpenAI voice packages are still broken on this PC.
        echo           Not a blocker: the Duck will use the built-in Windows voice.
    ) else (
        echo Repaired!
    )
)

echo.
echo ============================================
echo  Done! Double-click run.bat to start.
echo ============================================
pause
