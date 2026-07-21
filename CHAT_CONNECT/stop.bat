@echo off
REM  CHAT CONNECT - stop a running server (background or not)
powershell -NoProfile -Command "try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:2428/api/shutdown | Out-Null; Write-Host 'CHAT CONNECT stopped.' } catch { Write-Host 'CHAT CONNECT does not seem to be running.' }"
timeout /t 3 >nul
