@echo off
REM  CHAT YAPPER - stop a running Duck (background or not).
REM  Finds the process holding the single-instance lock port and ends it.
setlocal
set KILLED=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":2430 " ^| findstr LISTENING') do (
    taskkill /PID %%p /F >nul 2>&1
    set KILLED=1
)
if "%KILLED%"=="1" (echo CHAT YAPPER stopped.) else (echo CHAT YAPPER does not seem to be running.)
timeout /t 3 >nul
