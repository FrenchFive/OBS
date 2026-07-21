@echo off
REM  Cut the message the Duck is currently speaking (for Stream Deck
REM  "System > Open", desktop shortcuts, macros...). Closes instantly.
curl -s -m 2 -X POST http://127.0.0.1:2428/api/duck/skip >nul 2>&1
