#!/usr/bin/env bash
# CHAT CONNECT - start (Linux / macOS). Add "--background" to run detached.
cd "$(dirname "$0")"
PY=./.venv/bin/python
[ -x "$PY" ] || PY=python3

if [ "$1" = "--background" ]; then
    nohup "$PY" main.py --log-file server.log >/dev/null 2>&1 &
    echo "CHAT CONNECT running in background (PID $!). Dashboard: http://localhost:2428"
    echo "Stop it with:  curl -X POST http://localhost:2428/api/shutdown"
else
    "$PY" main.py --open
fi
