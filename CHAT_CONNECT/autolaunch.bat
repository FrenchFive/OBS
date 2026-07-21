@echo off
REM  CHAT CONNECT - silent start used by the OBS auto-launcher (obs_autolaunch.lua)
REM  and usable directly. Tries the venv first, then the py launcher, then python.
REM  Safe to run twice: a second copy exits because the port is taken.
cd /d "%~dp0"
if exist AUTOLAUNCH_ERROR.txt del AUTOLAUNCH_ERROR.txt

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py --log-file server.log
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    start "CHAT CONNECT" /min py -3 main.py --log-file server.log
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    start "CHAT CONNECT" /min python main.py --log-file server.log
    exit /b 0
)
echo CHAT CONNECT could not start: no Python environment found.> AUTOLAUNCH_ERROR.txt
echo Run install.bat in this folder once, then restart OBS.>> AUTOLAUNCH_ERROR.txt
exit /b 1
