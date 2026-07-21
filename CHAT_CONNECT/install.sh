#!/usr/bin/env bash
# CHAT CONNECT - one-time install (Linux / macOS)
cd "$(dirname "$0")"
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
echo
echo "Done! Start with:  ./run.sh"
