#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source ./venv/bin/activate
echo "Starting Subtitle Studio on http://127.0.0.1:8000 ..."
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
