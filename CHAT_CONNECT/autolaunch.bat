@echo off
REM  CHAT CONNECT - silent start used by the OBS auto-launcher (obs_autolaunch.lua).
REM  Same as run_background.bat but with no output and no pause.
REM  Safe to run twice: a second copy exits because the port is taken.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py --log-file server.log
) else (
    start "CHAT CONNECT" /min python main.py --log-file server.log
)
