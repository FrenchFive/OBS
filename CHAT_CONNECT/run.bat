@echo off
REM  CHAT CONNECT - start with a console window and open the dashboard
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --open
) else (
    python main.py --open
)
pause
