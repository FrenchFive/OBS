@echo off
REM  CHAT YAPPER - silent start used by the OBS auto-launcher (obs_autolaunch.lua).
REM  Follow mode: the Duck exits by itself when CHAT CONNECT is stopped,
REM  so closing OBS (which stops CHAT CONNECT) cleans everything up.
REM  Safe to run twice: a second copy exits (single-instance lock).
cd /d "%~dp0"
set CHAT_YAPPER_EXIT_WITH_SERVER=1
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "CHAT YAPPER" /min python main.py
)
