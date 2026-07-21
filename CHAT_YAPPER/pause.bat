@echo off
REM  Mute / unmute the Duck's TTS entirely (toggle). Pausing also cuts the
REM  current message and empties the queue. For Stream Deck / shortcuts.
curl -s -m 2 -X POST http://127.0.0.1:2428/api/duck/toggle >nul 2>&1
