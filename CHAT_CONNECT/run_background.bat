@echo off
REM  CHAT CONNECT - start silently in the background (no window).
REM  Logs go to server.log - stop it with stop.bat or the dashboard button.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py --log-file server.log
) else (
    start "CHAT CONNECT" /min python main.py --log-file server.log
)
echo CHAT CONNECT is starting in the background.
echo Dashboard: http://localhost:2428
timeout /t 3 >nul
