@echo off
REM  CHAT YAPPER - start silently in the background (no window).
REM  Output goes to yapper.log - stop it with stop.bat.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "CHAT YAPPER" /min python main.py
)
echo CHAT YAPPER is starting in the background (log: yapper.log).
timeout /t 3 >nul
