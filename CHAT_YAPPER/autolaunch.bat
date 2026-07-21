@echo off
REM  CHAT YAPPER - silent start used by the OBS auto-launcher (obs_autolaunch.lua)
REM  and usable directly. Follow mode: the Duck exits by itself when CHAT
REM  CONNECT is stopped, so closing OBS cleans everything up.
REM  Safe to run twice: a second copy exits (single-instance lock).
cd /d "%~dp0"
if exist AUTOLAUNCH_ERROR.txt del AUTOLAUNCH_ERROR.txt
set CHAT_YAPPER_EXIT_WITH_SERVER=1

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py --exit-with-server
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    start "CHAT YAPPER" /min py -3 main.py --exit-with-server
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    start "CHAT YAPPER" /min python main.py --exit-with-server
    exit /b 0
)
echo CHAT YAPPER could not start: no Python environment found.> AUTOLAUNCH_ERROR.txt
echo Run install.bat in this folder once, then restart OBS.>> AUTOLAUNCH_ERROR.txt
exit /b 1
